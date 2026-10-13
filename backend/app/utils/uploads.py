"""Bounded reads for request-uploaded files."""

from fastapi import UploadFile

from app.config import get_settings
from app.exceptions import FileValidationError


async def read_upload_limited(upload: UploadFile) -> bytes:
    """Read at most the configured upload limit plus one byte."""
    settings = get_settings()
    content = await upload.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise FileValidationError(
            f"File exceeds the maximum allowed size of {settings.max_upload_size_mb} MB."
        )
    return content
