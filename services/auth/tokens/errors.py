"""The auth-api error shape: `{"error": {"code", "message", "fields"}}` for every failure."""

from typing import Any

from django.db import OperationalError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class InvalidCredentials(exceptions.APIException):
    # Not AuthenticationFailed: DRF turns that into 403 when the view has no authenticator.
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_credentials"
    default_detail = "Invalid username or password."


class InvalidRefresh(exceptions.APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_refresh"
    default_detail = "Refresh token is invalid, expired or revoked."


class Unavailable(exceptions.APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "unavailable"
    default_detail = "The auth service is temporarily unavailable."


def error_body(code: str, message: str, fields: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "fields": fields}}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, OperationalError):  # auth-db unreachable
        exc = Unavailable()
    if isinstance(exc, exceptions.ValidationError | exceptions.ParseError):
        fields = exc.detail if isinstance(exc, exceptions.ValidationError) else None
        if fields is not None and not isinstance(fields, dict):
            fields = {"non_field_errors": fields}
        body = error_body("invalid_body", "Invalid request body.", fields)
        return Response(body, status=status.HTTP_400_BAD_REQUEST)
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, exceptions.APIException):
        code = exc.get_codes()
        response.data = error_body(code if isinstance(code, str) else exc.default_code, str(exc.detail))
    return response
