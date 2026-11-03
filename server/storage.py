"""
Swayam-sevak Evidence Storage Service
Handles secure upload and signing of multimedia evidence to Supabase Storage.
Enforces strict MIME type, file extension, and file size constraints.
"""

import os
import uuid
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "evidence")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "application/pdf": [".pdf"],
    # Voice notes from "Report a problem" (browser recorders produce webm/ogg/mp4)
    "audio/webm": [".webm"],
    "audio/ogg": [".ogg", ".oga"],
    "audio/mpeg": [".mp3"],
    "audio/mp4": [".m4a", ".mp4"],
    # Pothole videos (phone galleries: MP4 on Android, MOV/MP4 on iPhone). Stored as .mp4/.mov only, so a video is
    # never mistaken for a .webm voice note.
    "video/mp4": [".mp4"],
    "video/quicktime": [".mov"],
}
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # the Supabase project limit
EVIDENCE_PREFIX = "evidence://"  # what the database stores: where the file is, never a public link

# Lazy client initialization
_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        if SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


class StorageValidationError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_file(file_bytes: bytes, filename: str, content_type: str):
    """Enforces MIME whitelist, extension match, and 10MB file size limit."""
    # Size check
    limit = MAX_VIDEO_SIZE if content_type.lower().startswith("video/") else MAX_FILE_SIZE
    if len(file_bytes) > limit:
        raise StorageValidationError(
            f"File size {len(file_bytes)} bytes exceeds the {limit // (1024 * 1024)} MB limit", 
            status_code=413
        )

    # Content-Type check
    normalized_mime = content_type.lower().split(";")[0].strip()
    if normalized_mime not in ALLOWED_MIME_TYPES:
        raise StorageValidationError(
            f"Unsupported media type: {content_type}. Allowed: image/jpeg, image/png, application/pdf",
            status_code=415
        )

    # Extension check
    _, ext = os.path.splitext(filename.lower())
    valid_exts = ALLOWED_MIME_TYPES[normalized_mime]
    if ext not in valid_exts:
        raise StorageValidationError(
            f"File extension '{ext}' does not match MIME type '{normalized_mime}'. Expected one of: {valid_exts}",
            status_code=415
        )

    return ext


def upload_evidence(
    file_bytes: bytes, 
    filename: str, 
    content_type: str, 
    report_id: str
) -> Dict[str, Any]:
    """
    Validates and uploads evidence to Supabase Storage.
    Returns storage path, signed URL, and public URL.
    """
    ext = validate_file(file_bytes, filename, content_type)
    file_id = str(uuid.uuid4())
    storage_path = f"{report_id}/{file_id}{ext}"

    client = get_supabase()
    if client:
        # Upload to Supabase Storage
        res = client.storage.from_(SUPABASE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        # Get public URL or signed URL
        try:
            public_url_res = client.storage.from_(SUPABASE_BUCKET).get_public_url(storage_path)
            public_url = public_url_res if isinstance(public_url_res, str) else public_url_res.get("publicURL", "")
        except Exception:
            public_url = ""

        # Create 1-hour signed URL
        try:
            signed_url_res = client.storage.from_(SUPABASE_BUCKET).create_signed_url(storage_path, 3600)
            signed_url = signed_url_res.get("signedURL") or signed_url_res.get("signedUrl") or public_url
        except Exception:
            signed_url = public_url

        return {
            "storage_path": storage_path,
            "ref": EVIDENCE_PREFIX + storage_path,
            "url": public_url or signed_url,
            "signed_url": signed_url,
            "file_size": len(file_bytes),
            "content_type": content_type
        }
    else:
        # Fallback local storage
        local_dir = os.path.join(".data", "uploads", report_id)
        os.makedirs(local_dir, exist_ok=True)
        local_file_path = os.path.join(local_dir, f"{file_id}{ext}")
        with open(local_file_path, "wb") as f:
            f.write(file_bytes)
        local_url = f"/uploads/{report_id}/{file_id}{ext}"
        return {
            "storage_path": storage_path,
            "ref": EVIDENCE_PREFIX + storage_path,
            "url": local_url,
            "signed_url": local_url,
            "file_size": len(file_bytes),
            "content_type": content_type
        }


def storage_path_of(stored: str | None) -> str | None:
    """The storage path inside our bucket, from what the database holds: an evidence:// reference (current), or the
    public/signed Supabase link older rows saved (those never opened, because the bucket is private). None for
    anything else, e.g. an outside image link."""
    if not stored:
        return None
    if stored.startswith(EVIDENCE_PREFIX):
        path = stored[len(EVIDENCE_PREFIX):]
    else:
        marker = next((m for m in (f"/object/public/{SUPABASE_BUCKET}/", f"/object/sign/{SUPABASE_BUCKET}/") if m in stored), None)
        if not marker or not (SUPABASE_URL and stored.startswith(SUPABASE_URL)):
            return None
        path = stored.split(marker, 1)[1].split("?", 1)[0]
    parts = path.split("/")
    if len(parts) != 2 or ".." in path or not all(parts):
        return None
    return path


def read_evidence(storage_path: str) -> tuple[bytes, str] | None:
    """Bytes and content type of a stored file, fetched with the server's key (the bucket stays private)."""
    import mimetypes
    media = mimetypes.guess_type(storage_path)[0] or "application/octet-stream"
    client = get_supabase()
    if client:
        try:
            return client.storage.from_(SUPABASE_BUCKET).download(storage_path), media
        except Exception:
            return None
    local = os.path.join(".data", "uploads", storage_path)
    if os.path.isfile(local):
        with open(local, "rb") as f:
            return f.read(), media
    return None


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Returns a signed URL for an existing storage path."""
    client = get_supabase()
    if client:
        try:
            res = client.storage.from_(SUPABASE_BUCKET).create_signed_url(storage_path, expires_in)
            return res.get("signedURL") or res.get("signedUrl") or ""
        except Exception as e:
            return ""
    return f"/uploads/{storage_path}"
