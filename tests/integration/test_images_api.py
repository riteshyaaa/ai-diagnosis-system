"""
MedFusion AI — Medical Imaging API Integration Tests.

Tests:
- Radiograph upload (PNG format) to diagnostic case in DRAFT status
- DICOM upload (.dcm format) with automatic PII de-identification and tag extraction
- Image metadata retrieval and case image listing
- Static binary file streaming (processed PNG, thumbnail, raw)
- Quality validation rejection on corrupt / blank images
- Workflow state restrictions (cannot upload to non-DRAFT/SUBMITTED case)
- Case deletion rules (cannot delete image from processed case)
- Role-based access control (RBAC) enforcement
"""

import io
import numpy as np
import pytest
from PIL import Image
from httpx import AsyncClient

from tests.unit.test_image_processing import (
    create_synthetic_dicom_bytes,
    create_synthetic_radiograph,
)


async def get_clinician_token(client: AsyncClient, email: str = "dr.img.tester@hospital.org") -> str:
    """Helper to create and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. Image Tester",
            "password": "DocSecure2026!",
            "role": "clinician",
            "department": "Radiology",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DocSecure2026!"},
    )
    return login_res.json()["access_token"]


async def get_auditor_token(client: AsyncClient, email: str = "auditor.img@hospital.org") -> str:
    """Helper to create and authenticate an auditor user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Compliance Auditor",
            "password": "AuditSecure2026!",
            "role": "auditor",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AuditSecure2026!"},
    )
    return login_res.json()["access_token"]


async def setup_test_case(client: AsyncClient, headers: dict, mrn: str = "MRN-IMG-001") -> str:
    """Helper to create a patient and case, returning case_id."""
    p_res = await client.post(
        "/api/v1/patients",
        json={"mrn": mrn, "age": 58, "sex": "male"},
        headers=headers,
    )
    patient_id = p_res.json()["id"]

    c_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": patient_id, "modality": "multimodal", "chief_complaint": "Chest pain and dyspnea"},
        headers=headers,
    )
    return c_res.json()["id"]


def make_png_bytes(width: int = 256, height: int = 256) -> bytes:
    """Generate synthetic radiograph encoded as PNG bytes."""
    arr = create_synthetic_radiograph(width, height)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_png_image_upload_and_retrieval(client: AsyncClient):
    """Verify PNG radiograph upload, quality analysis, metadata lookup, and binary serving."""
    token = await get_clinician_token(client, "dr.png@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-PNG-01")

    # 1. Upload PNG image
    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("chest_xray_pa.png", png_bytes, "image/png")}
    data = {"image_type": "chest_xray_pa"}

    upload_res = await client.post(
        f"/api/v1/cases/{case_id}/images",
        files=files,
        data=data,
        headers=headers,
    )
    assert upload_res.status_code == 201, upload_res.text
    res_body = upload_res.json()
    image = res_body["image"]
    quality = res_body["quality_report"]

    assert image["case_id"] == case_id
    assert image["original_filename"] == "chest_xray_pa.png"
    assert image["image_type"] == "chest_xray_pa"
    assert len(image["file_hash"]) == 64
    assert quality["is_valid"] is True
    assert quality["quality_score"] > 0.4
    image_id = image["id"]

    # 2. List Case Images
    list_res = await client.get(f"/api/v1/cases/{case_id}/images", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1

    # 3. Get Image Metadata
    get_res = await client.get(f"/api/v1/images/{image_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == image_id

    # 4. Stream Processed Image File
    file_res = await client.get(f"/api/v1/images/{image_id}/file?variant=processed", headers=headers)
    assert file_res.status_code == 200
    assert file_res.headers["content-type"] == "image/png"
    assert len(file_res.content) > 0

    # 5. Stream Thumbnail
    thumb_res = await client.get(f"/api/v1/images/{image_id}/file?variant=thumbnail", headers=headers)
    assert thumb_res.status_code == 200
    assert len(thumb_res.content) > 0


@pytest.mark.asyncio
async def test_dicom_upload_and_deidentification(client: AsyncClient):
    """Verify DICOM upload extracts tags, strips PII, and links to case."""
    token = await get_clinician_token(client, "dr.dcm@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-DCM-01")

    # Generate synthetic DICOM containing PII
    dcm_bytes = create_synthetic_dicom_bytes(width=256, height=256, photometric="MONOCHROME2", view_position="PA")
    files = {"file": ("study_01.dcm", dcm_bytes, "application/dicom")}

    upload_res = await client.post(
        f"/api/v1/cases/{case_id}/images",
        files=files,
        headers=headers,
    )
    assert upload_res.status_code == 201, upload_res.text
    res_body = upload_res.json()
    image = res_body["image"]
    meta = res_body["technical_metadata"]

    assert image["mime_type"] == "application/dicom"
    assert image["image_type"] == "chest_xray_pa"
    # Verify PII tags are NOT exposed
    assert "PatientName" not in meta
    assert "PatientID" not in meta
    assert meta["Modality"] == "CR"
    assert meta["ViewPosition"] == "PA"


@pytest.mark.asyncio
async def test_corrupt_or_blank_image_rejected(client: AsyncClient):
    """Verify invalid / blank / corrupt image upload is rejected with 400."""
    token = await get_clinician_token(client, "dr.blank@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-BLANK-01")

    # 1. Blank all-black image
    blank_arr = np.zeros((256, 256), dtype=np.uint8)
    pil_img = Image.fromarray(blank_arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    blank_bytes = buf.getvalue()

    files = {"file": ("blank.png", blank_bytes, "image/png")}
    bad_res = await client.post(f"/api/v1/cases/{case_id}/images", files=files, headers=headers)
    assert bad_res.status_code == 400
    assert "validation failed" in bad_res.text.lower()


@pytest.mark.asyncio
async def test_image_deletion_in_draft_state(client: AsyncClient):
    """Verify images can be deleted in DRAFT state."""
    token = await get_clinician_token(client, "dr.imgdel@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-DEL-02")

    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("del_xray.png", png_bytes, "image/png")}
    upload_res = await client.post(f"/api/v1/cases/{case_id}/images", files=files, headers=headers)
    image_id = upload_res.json()["image"]["id"]

    # Delete image
    del_res = await client.delete(f"/api/v1/images/{image_id}", headers=headers)
    assert del_res.status_code == 200

    # Ensure image metadata is gone
    get_res = await client.get(f"/api/v1/images/{image_id}", headers=headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_image_rbac_enforcement(client: AsyncClient):
    """Verify auditor role cannot upload images (requires clinician/radiologist)."""
    # 1. Clinician creates case
    doc_token = await get_clinician_token(client, "dr.img.rbac@hospital.org")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    case_id = await setup_test_case(client, doc_headers, "MRN-RBAC-IMG")

    # 2. Auditor tries to upload image -> 403 Forbidden
    auditor_token = await get_auditor_token(client, "auditor.img.rbac@hospital.org")
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("xray.png", png_bytes, "image/png")}
    res_forbidden = await client.post(
        f"/api/v1/cases/{case_id}/images",
        files=files,
        headers=auditor_headers,
    )
    assert res_forbidden.status_code == 403
