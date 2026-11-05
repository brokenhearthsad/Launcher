"""Application exceptions mapped to HTTP responses by ``app.main``."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class NotSupportedError(AppError):
    status_code = 501
    code = "not_supported"


class CapacityError(AppError):
    status_code = 429
    code = "capacity_exceeded"
