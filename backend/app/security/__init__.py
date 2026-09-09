"""
MedFusion AI — Security Package.

Provides password hashing, JWT token lifecycle, and RBAC dependencies.
"""

from app.security.password import hash_password, verify_password, is_password_strong
from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_token_type,
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
)
from app.security.dependencies import (
    get_current_user,
    require_roles,
    require_admin,
    require_clinician,
    require_radiologist,
    require_auditor,
    require_clinical_staff,
)

__all__ = [
    "hash_password",
    "verify_password",
    "is_password_strong",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "verify_token_type",
    "ACCESS_TOKEN_TYPE",
    "REFRESH_TOKEN_TYPE",
    "get_current_user",
    "require_roles",
    "require_admin",
    "require_clinician",
    "require_radiologist",
    "require_auditor",
    "require_clinical_staff",
]
