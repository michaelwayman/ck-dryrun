from typing import Any

from accounts.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from tokens import refresh
from tokens.errors import InvalidCredentials, InvalidRefresh
from tokens.serializers import (
    ErrorSerializer,
    LoginSerializer,
    RefreshSerializer,
    TokenPairSerializer,
)
from tokens.signing import mint_access_token

_ERROR = OpenApiResponse(ErrorSerializer)


class TokenView(APIView):
    """Base for the token endpoints: POST only, no auth header, never cached."""

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    def finalize_response(self, request: Request, response: Any, *args: Any, **kwargs: Any) -> Any:
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def token_pair(access: str, refresh_token: str) -> Response:
        return Response(TokenPairSerializer.pair(access, refresh_token))


class LoginView(TokenView):
    """Exchange a username and password for an access token and a refresh token."""

    @extend_schema(
        operation_id="login",
        request=LoginSerializer,
        responses={200: TokenPairSerializer, 400: _ERROR, 401: _ERROR, 503: _ERROR},
    )
    def post(self, request: Request) -> Response:
        body = LoginSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        # ModelBackend gives None for unknown, wrong and inactive alike, and re-hashes WP passwords.
        user = authenticate(
            request._request,
            username=body.validated_data["username"],
            password=body.validated_data["password"],
        )
        if not isinstance(user, User):
            raise InvalidCredentials
        now = timezone.now()
        # Mint first: a signing failure must not leave a stored refresh token the client never got.
        access = mint_access_token(user, now)
        return self.token_pair(access, refresh.issue(user, now))


class RefreshView(TokenView):
    """Exchange a refresh token for a new pair; the old refresh token is rotated out."""

    @extend_schema(
        operation_id="refresh",
        request=RefreshSerializer,
        responses={200: TokenPairSerializer, 400: _ERROR, 401: _ERROR, 503: _ERROR},
    )
    def post(self, request: Request) -> Response:
        body = RefreshSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        now = timezone.now()
        try:
            access, new_refresh = refresh.rotate(
                body.validated_data["refresh"], now, lambda user: mint_access_token(user, now)
            )
        except refresh.InvalidRefreshToken:
            raise InvalidRefresh from None
        return self.token_pair(access, new_refresh)


class LogoutView(TokenView):
    """Revoke a refresh token. Idempotent: unknown or already revoked tokens also give 204."""

    @extend_schema(
        operation_id="logout",
        request=RefreshSerializer,
        responses={204: None, 400: _ERROR, 503: _ERROR},
    )
    def post(self, request: Request) -> Response:
        body = RefreshSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        refresh.revoke(body.validated_data["refresh"], timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
