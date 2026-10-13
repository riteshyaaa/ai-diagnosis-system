"""Tests for bounded memory use when reading client-uploaded files."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.exceptions import FileValidationError
from app.utils import uploads


@pytest.mark.asyncio
async def test_read_upload_limited_accepts_content_at_limit(monkeypatch):
    monkeypatch.setattr(
        uploads,
        "get_settings",
        lambda: SimpleNamespace(max_upload_size_bytes=4, max_upload_size_mb=1),
    )
    upload = UploadFile(filename="small.png", file=BytesIO(b"1234"))

    assert await uploads.read_upload_limited(upload) == b"1234"


@pytest.mark.asyncio
async def test_read_upload_limited_rejects_content_over_limit(monkeypatch):
    monkeypatch.setattr(
        uploads,
        "get_settings",
        lambda: SimpleNamespace(max_upload_size_bytes=4, max_upload_size_mb=1),
    )
    upload = UploadFile(filename="large.png", file=BytesIO(b"12345"))

    with pytest.raises(FileValidationError, match="maximum allowed size"):
        await uploads.read_upload_limited(upload)
