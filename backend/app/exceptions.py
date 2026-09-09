"""
MedFusion AI — Custom Exception Classes.

Centralized exceptions for consistent error handling across the application.
"""

from typing import Any


class MedFusionError(Exception):
    """Base exception for all MedFusion AI errors."""

    def __init__(self, message: str = "An error occurred", details: Any = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


# --- Authentication & Authorization ---

class AuthenticationError(MedFusionError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class AuthorizationError(MedFusionError):
    """Raised when a user lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message)


class AccountLockedError(MedFusionError):
    """Raised when an account is locked due to failed login attempts."""

    def __init__(self, message: str = "Account is temporarily locked"):
        super().__init__(message)


# --- Resource Errors ---

class NotFoundError(MedFusionError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str = "Resource", identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(message)


class DuplicateError(MedFusionError):
    """Raised when attempting to create a duplicate resource."""

    def __init__(self, resource: str = "Resource", field: str = ""):
        message = f"{resource} already exists"
        if field:
            message = f"{resource} with this {field} already exists"
        super().__init__(message)


# --- Validation Errors ---

class ValidationError(MedFusionError):
    """Raised for domain-level validation failures."""

    def __init__(self, message: str = "Validation failed", details: Any = None):
        super().__init__(message, details)


class FileValidationError(MedFusionError):
    """Raised when an uploaded file fails validation."""

    def __init__(self, message: str = "File validation failed"):
        super().__init__(message)


# --- ML / Inference Errors ---

class ModelNotFoundError(MedFusionError):
    """Raised when a requested ML model is not available."""

    def __init__(self, model_name: str = ""):
        message = "Model not found"
        if model_name:
            message = f"Model '{model_name}' not found or not loaded"
        super().__init__(message)


class InferenceError(MedFusionError):
    """Raised when model inference fails."""

    def __init__(self, message: str = "Inference failed"):
        super().__init__(message)


class PreprocessingError(MedFusionError):
    """Raised when data preprocessing fails."""

    def __init__(self, message: str = "Preprocessing failed"):
        super().__init__(message)
