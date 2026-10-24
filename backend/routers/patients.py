import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from utils.database import get_patients_collection, get_scans_collection, next_id, now_utc
from utils.logger import logger
from utils.security import get_current_user
from utils.views import DETAIL_PROJECTION, LIST_PROJECTION, patient_view, scan_view, study_sizes

# Create Router
router = APIRouter(prefix="/api/patients", tags=["Patients"])


class PatientCreate(BaseModel):
    """Pseudonymised patient — no names or identifiers are stored."""
    age: int = Field(ge=0, le=120)
    sex: Literal["F", "M"]
    referring_unit: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=2000)


def _latest_scans() -> dict:
    """patient_id -> (number of scans, latest scan document)"""
    summary = {}
    for s in get_scans_collection().find({}, LIST_PROJECTION).sort("created_at", -1):
        count, latest = summary.get(s["patient_id"], (0, s))
        summary[s["patient_id"]] = (count + 1, latest)
    return summary


# --- Routes ---

@router.get("")
async def list_patients(search: str = "", user: dict = Depends(get_current_user)):
    query = {"id": {"$regex": re.escape(search.strip()), "$options": "i"}} if search.strip() else {}
    latest = _latest_scans()
    patients = get_patients_collection().find(query).sort("created_at", -1)
    return [patient_view(p, *latest.get(p["id"], (0, None))) for p in patients]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_patient(body: PatientCreate, user: dict = Depends(get_current_user)):
    doc = {**body.model_dump(), "id": next_id("P"), "created_at": now_utc(), "created_by": str(user["_id"])}
    get_patients_collection().insert_one(doc)
    logger.info(f"Patient created: {doc['id']}")
    return patient_view(doc, 0, None)


@router.get("/{patient_id}")
async def get_patient(patient_id: str, user: dict = Depends(get_current_user)):
    p = get_patients_collection().find_one({"id": patient_id})
    if p is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    history = list(get_scans_collection().find({"patient_id": patient_id}, DETAIL_PROJECTION).sort("created_at", -1))
    view = patient_view(p, len(history), history[0] if history else None)
    sizes = study_sizes(history)
    view["history"] = [scan_view(s, with_images=True, sizes=sizes) for s in history]
    view["files"] = []   # files move to Azure Blob Storage in a later step
    return view
