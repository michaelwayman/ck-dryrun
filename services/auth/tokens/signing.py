"""Access-token minting, per docs/contracts/access-token.md. Verification lives in tokenauth."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path

import jwt
from accounts.models import User
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from tokenauth import CLAIMS_VERSION


@dataclass(frozen=True)
class SigningKey:
    private_key: Ed25519PrivateKey
    kid: str


def signing_key() -> SigningKey:
    """The configured key, loaded on first use and cached per (path, kid) setting."""
    return _load(settings.AUTH_SIGNING_KEY, settings.AUTH_SIGNING_KID)


@cache
def _load(path: str, kid: str) -> SigningKey:
    if not path:
        raise ImproperlyConfigured("AUTH_SIGNING_KEY must name an Ed25519 private key PEM file.")
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ImproperlyConfigured("AUTH_SIGNING_KEY must be an Ed25519 private key.")
    return SigningKey(private_key=key, kid=kid or derive_kid(key))


def derive_kid(key: Ed25519PrivateKey) -> str:
    """`dev-` + the first 12 hex of SHA-256 of the public key's SPKI DER, as dev-keys.sh does."""
    spki_der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return "dev-" + hashlib.sha256(spki_der).hexdigest()[:12]


def mint_access_token(user: User, now: datetime) -> str:
    """A signed access JWT carrying the user's current roles, valid for ACCESS_TOKEN_TTL_SECONDS."""
    key = signing_key()
    iat = int(now.timestamp())
    payload = {
        "iss": settings.AUTH_ISSUER,
        "aud": settings.AUTH_AUDIENCE,
        "sub": str(user.pk),
        "username": user.username,
        "roles": user.role_names(),
        "v": CLAIMS_VERSION,
        "iat": iat,
        "exp": iat + settings.ACCESS_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(
        payload, key.private_key, algorithm="EdDSA", headers={"kid": key.kid, "typ": "JWT"}
    )
