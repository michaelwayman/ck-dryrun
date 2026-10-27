"""DRF authentication and permission classes. Needs the `drf` extra; core never imports this."""

from typing import Any

from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from tokenauth.claims import Claims, Role, VerifierConfig
from tokenauth.errors import TokenError
from tokenauth.verify import verify_token

_MESSAGES = {
    "expired": "Token has expired.",
    "malformed_header": "Authorization header must be 'Bearer <token>'.",
}


class TokenUser:
    """The request user for a verified token. It lives only for the request and is never saved."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, claims: Claims) -> None:
        self.id = self.pk = claims.sub
        self.username = claims.username
        self.roles = claims.roles

    def __str__(self) -> str:
        return self.username


class BearerTokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request: Request) -> tuple[TokenUser, Claims] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword.lower().encode():
            return None  # no header, or another scheme: anonymous
        if len(parts) != 2:
            raise _invalid("malformed_header")
        try:
            token = parts[1].decode("ascii")
        except UnicodeDecodeError:
            raise _invalid("malformed_header") from None
        try:
            claims = verify_token(token, _config())
        except TokenError as exc:
            raise _invalid(exc.code) from None
        return TokenUser(claims), claims

    def authenticate_header(self, request: Request) -> str:
        return self.keyword


def HasRole(role: Role) -> type[BasePermission]:  # named like a class, as the contract does
    """Return a permission class that allows only requests whose token carries `role`."""

    class _HasRole(BasePermission):
        message = f"Requires role: {role.value}."

        def has_permission(self, request: Request, view: APIView) -> bool:
            # False for anonymous too: DRF answers 401 when no authenticator succeeded, else 403.
            user: Any = request.user
            return isinstance(user, TokenUser) and role in user.roles

    _HasRole.__name__ = _HasRole.__qualname__ = f"HasRole_{role.value}"
    return _HasRole


def _config() -> VerifierConfig:
    return VerifierConfig(
        public_keys=settings.TOKENAUTH_PUBLIC_KEYS,
        issuer=settings.TOKENAUTH_ISSUER,
        audience=settings.TOKENAUTH_AUDIENCE,
        leeway_seconds=getattr(settings, "TOKENAUTH_LEEWAY_SECONDS", 30),
    )


def _invalid(reason: str) -> AuthenticationFailed:
    return AuthenticationFailed(_MESSAGES.get(reason, "Invalid token."), code="invalid_token")
