from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.collection import Collection

from utils.config import MONGODB_URI, MONGODB_DB_NAME
from utils.logger import logger

# Global client, created on first use
_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        logger.info("Connecting to MongoDB...")
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def set_client(client) -> None:
    """Replaces the MongoDB client (used by the tests to plug in an in-memory database)."""
    global _client
    _client = client


def _db():
    return get_client()[MONGODB_DB_NAME]


def get_users_collection() -> Collection:
    return _db()["users"]


def get_patients_collection() -> Collection:
    return _db()["patients"]


def get_scans_collection() -> Collection:
    return _db()["scans"]


def get_reference_collection() -> Collection:
    """Reference library: confirmed cases from a labelled dataset, used for similar-case search."""
    return _db()["reference_cases"]


def next_id(prefix: str, width: int = 4) -> str:
    """Readable sequential ids, e.g. P-0001 for patients and S-2026-0001 for scans."""
    doc = _db()["counters"].find_one_and_update(
        {"_id": prefix}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"{prefix}-{doc['seq']:0{width}d}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_indexes() -> None:
    """Creates the indexes the routes rely on (safe to run on every start)."""
    get_users_collection().create_index([("email", ASCENDING)], unique=True, name="unique_email")
    get_patients_collection().create_index([("id", ASCENDING)], unique=True, name="unique_patient_id")
    get_scans_collection().create_index([("id", ASCENDING)], unique=True, name="unique_scan_id")
    get_scans_collection().create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)], name="patient_history")
    get_reference_collection().create_index([("id", ASCENDING)], unique=True, name="unique_case_id")
    logger.info("MongoDB indexes ready")


def ping() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except Exception as e:
        logger.warning(f"MongoDB ping failed: {e}")
        return False
