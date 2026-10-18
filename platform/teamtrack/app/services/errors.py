"""Domain errors. The API turns each into the error envelope {"error": {"code", "message"}}."""

from __future__ import annotations


class ServiceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class BadRequest(ServiceError):
    status_code = 400
    code = "bad_request"


class Unauthorized(ServiceError):
    status_code = 401
    code = "unauthorized"


class Forbidden(ServiceError):
    status_code = 403
    code = "forbidden"


class NotFound(ServiceError):
    """Also used for other orgs' resources: never reveal that they exist."""

    status_code = 404
    code = "not_found"


class Conflict(ServiceError):
    status_code = 409
    code = "conflict"


class Invalid(ServiceError):
    status_code = 422
    code = "validation_error"
