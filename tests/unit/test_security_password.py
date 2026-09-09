"""
MedFusion AI — Password Security Unit Tests.
"""

from app.security.password import hash_password, verify_password, is_password_strong


def test_hash_password_produces_bcrypt_hash():
    """Verify that hash_password returns a bcrypt formatted hash."""
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(pwd, hashed) is True


def test_verify_password_rejects_incorrect():
    """Verify that wrong passwords fail verification."""
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert verify_password("WrongPassword123!", hashed) is False


def test_password_strength_validation():
    """Test clinical password complexity rules."""
    # Valid
    valid, msg = is_password_strong("ClinicalDoc2026!")
    assert valid is True
    assert msg == ""

    # Too short (< 8 chars)
    valid, msg = is_password_strong("Med1!")
    assert valid is False
    assert "8 characters" in msg

    # Missing uppercase
    valid, msg = is_password_strong("lowercase123!")
    assert valid is False
    assert "uppercase" in msg

    # Missing lowercase
    valid, msg = is_password_strong("UPPERCASE123!")
    assert valid is False
    assert "lowercase" in msg

    # Missing digit
    valid, msg = is_password_strong("NoDigitsHere!!")
    assert valid is False
    assert "digit" in msg

    # Missing special char
    valid, msg = is_password_strong("NoSpecialChars123")
    assert valid is False
    assert "special character" in msg
