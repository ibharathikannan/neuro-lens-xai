"""Azure Blob Storage for scan images and heatmaps.

With AZURE_STORAGE_CONNECTION_STRING set, images are uploaded to the private container and the dashboard
receives short-lived read-only links (SAS URLs). Without it, images are stored inside the MongoDB record as
base64 JPEG (local development and tests) — every function here handles both cases.
"""
import base64
import io
from datetime import datetime, timedelta, timezone

from PIL import Image

from utils.config import AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER, BLOB_URL_MINUTES
from utils.logger import logger

_container = None


def enabled() -> bool:
    return bool(AZURE_STORAGE_CONNECTION_STRING)


def _get_container():
    global _container
    if _container is None:
        from azure.storage.blob import BlobServiceClient
        service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        _container = service.get_container_client(AZURE_STORAGE_CONTAINER)
        if not _container.exists():
            _container.create_container()          # private: no anonymous access
            logger.info(f"Created blob container '{AZURE_STORAGE_CONTAINER}'")
    return _container


def to_jpeg(img: Image.Image, size: int) -> bytes:
    img = img.convert("RGB")
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def save_image(img: Image.Image, blob_path: str, size: int = 512) -> dict:
    """Stores an image and returns the fields to keep in the MongoDB record:
    {"blob": path} with Blob Storage, otherwise {"jpeg": base64} (smaller copy)."""
    if enabled():
        from azure.storage.blob import ContentSettings
        _get_container().upload_blob(blob_path, to_jpeg(img, size), overwrite=True,
                                     content_settings=ContentSettings(content_type="image/jpeg"))
        return {"blob": blob_path}
    return {"jpeg": base64.b64encode(to_jpeg(img, 320)).decode("ascii")}


def image_fields(img: Image.Image | None, blob_path: str, prefix: str) -> dict:
    """save_image() as record fields, e.g. prefix "image" -> {"image_blob": ...} or {"image_jpeg": ...}."""
    if img is None:
        return {}
    return {f"{prefix}_{k}": v for k, v in save_image(img, blob_path).items()}


def image_url(doc: dict, prefix: str) -> str | None:
    """Link the dashboard can show: a read-only SAS URL for a blob, or a data: URL for an inline image."""
    blob_path = doc.get(f"{prefix}_blob")
    if blob_path and enabled():
        try:
            return _sas_url(blob_path)
        except Exception as e:
            logger.warning(f"Could not create a link for {blob_path}: {e}")
            return None
    b64 = doc.get(f"{prefix}_jpeg")
    return f"data:image/jpeg;base64,{b64}" if b64 else None


def image_bytes(doc: dict, prefix: str) -> bytes | None:
    """Raw JPEG bytes (for the DOCX report and for re-analysing old scans)."""
    blob_path = doc.get(f"{prefix}_blob")
    if blob_path and enabled():
        try:
            return _get_container().download_blob(blob_path).readall()
        except Exception as e:
            logger.warning(f"Could not download {blob_path}: {e}")
            return None
    b64 = doc.get(f"{prefix}_jpeg")
    return base64.b64decode(b64) if b64 else None


def _sas_url(blob_path: str) -> str:
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas
    container = _get_container()
    credential = container.credential
    sas = generate_blob_sas(
        account_name=container.account_name, container_name=AZURE_STORAGE_CONTAINER, blob_name=blob_path,
        account_key=credential.account_key, permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=BLOB_URL_MINUTES),
    )
    return f"{container.url}/{blob_path}?{sas}"


def status() -> tuple[str, bool]:
    """(text, healthy) for the Model & System page."""
    if not enabled():
        return "Not configured — images kept in MongoDB", False
    try:
        _get_container().get_container_properties()
        return f"Connected · container '{AZURE_STORAGE_CONTAINER}'", True
    except Exception as e:
        logger.warning(f"Blob Storage check failed: {e}")
        return "Unavailable", False
