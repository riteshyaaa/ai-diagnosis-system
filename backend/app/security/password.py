"""
MedFusion AI — Password Hashing & Verification.

Uses native bcrypt (12 rounds) for secure clinical-grade password storage.
Never store or log plaintext passwords.
"""

import bcrypt

# Work factor: 12 rounds for HIPAA / security compliance
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt with 12 rounds.

    Args:
        password: Plaintext password to hash.

    Returns:
        Secure bcrypt hash string UTF-8 decoded.
    """
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain_password: Password entered by user.
        hashed_password: Stored bcrypt hash string.

    Returns:
        True if password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def is_password_strong(password: str) -> tuple[bool, str]:
    """
    Validate password strength against enterprise clinical standards:
    - Minimum 8 characters (12 recommended)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Plaintext password to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit."
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character."
    return True, ""
