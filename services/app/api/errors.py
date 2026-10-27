"""Every API error body is {"error": {code, message, fields}} (brands-api, Conventions)."""

from typing import Any

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# DRF codes renamed to the contract's; the rest (not_authenticated, permission_denied, not_found,
# method_not_allowed) already match.
_CODES = {"parse_error": "invalid_body", "authentication_failed": "invalid_token"}


class ApiError(exceptions.APIException):
    """An error whose code, message and fields are exactly what the contract shows."""

    def __init__(
        self,
        code: str,
        message: str,
        fields: dict[str, list[str]] | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(message, code)
        self.code, self.message, self.fields, self.status_code = code, message, fields, status_code


def invalid_parameter(fields: dict[str, list[str]]) -> ApiError:
    return ApiError("invalid_parameter", "Invalid query parameter.", fields)


def error_body(
    code: str, message: str, fields: dict[str, list[str]] | None = None
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "fields": fields}}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    # DRF's handler sets the status and the WWW-Authenticate header; only the body is replaced.
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ApiError):
        response.data = error_body(exc.code, exc.message, exc.fields)
    elif isinstance(exc, exceptions.APIException):
        code = exc.get_codes() if isinstance(exc.detail, str) else exc.default_code
        message = str(exc.detail) if isinstance(exc.detail, str) else str(exc.default_detail)
        response.data = error_body(_CODES.get(str(code), str(code)), message)
    return response
