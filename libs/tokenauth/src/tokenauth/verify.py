"""verify_token: applies every rule in docs/contracts/access-token.md."""

from datetime import UTC, datetime
from typing import Any

import jwt

from tokenauth.claims import SUPPORTED_VERSIONS, Claims, Role, VerifierConfig
from tokenauth.errors import (
    ExpiredToken,
    InvalidAlgorithm,
    InvalidAudience,
    InvalidIssuer,
    InvalidSignature,
    MalformedToken,
    MissingClaim,
    TokenError,
    UnknownKey,
    UnsupportedVersion,
)

ALGORITHMS = ["EdDSA"]
# The contract's rule 3, plus username, which Claims needs and the claim table makes non-nullable.
REQUIRED_CLAIMS = ["iss", "aud", "sub", "username", "exp", "iat", "v", "roles"]
_ROLE_VALUES = {role.value for role in Role}

# PyJWT exception -> contract error, most specific first (InvalidSignatureError is a DecodeError).
_ERROR_MAP: list[tuple[type[jwt.PyJWTError], type[TokenError]]] = [
    (jwt.InvalidSignatureError, InvalidSignature),
    (jwt.InvalidAlgorithmError, InvalidAlgorithm),
    (jwt.InvalidIssuerError, InvalidIssuer),
    (jwt.InvalidAudienceError, InvalidAudience),
    (jwt.MissingRequiredClaimError, MissingClaim),
]


def verify_token(token: str, config: VerifierConfig, *, now: datetime | None = None) -> Claims:
    """Return the token's claims, or raise a TokenError subclass. `now` exists for tests."""
    key = _public_key(token, config)
    payload = _decode(token, key, config)
    return _claims(payload, config, now or datetime.now(UTC))


def _public_key(token: str, config: VerifierConfig) -> str:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise MalformedToken("token header cannot be decoded") from None
    kid = header.get("kid")
    if not isinstance(kid, str) or kid not in config.public_keys:
        raise UnknownKey(f"no public key for kid {kid!r}")
    return config.public_keys[kid]


def _decode(token: str, key: str, config: VerifierConfig) -> dict[str, Any]:
    try:
        # exp and iat are checked in _claims against `now`; PyJWT only reads the wall clock.
        return jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            issuer=config.issuer,
            audience=config.audience,
            options={
                "require": REQUIRED_CLAIMS,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "strict_aud": True,
            },
        )
    except jwt.PyJWTError as exc:
        for pyjwt_error, token_error in _ERROR_MAP:
            if isinstance(exc, pyjwt_error):
                raise token_error(str(exc)) from None
        raise MalformedToken(str(exc)) from None


def _claims(payload: dict[str, Any], config: VerifierConfig, now: datetime) -> Claims:
    iat, exp, version = payload["iat"], payload["exp"], payload["v"]
    sub, username, roles = payload["sub"], payload["username"], payload["roles"]
    if not all(_is_int(value) for value in (iat, exp, version)):
        raise MalformedToken("iat, exp and v must be integers")
    if not (isinstance(sub, str) and isinstance(username, str) and isinstance(roles, list)):
        raise MalformedToken("sub and username must be strings and roles a list")

    timestamp = now.timestamp()
    if exp <= timestamp - config.leeway_seconds:
        raise ExpiredToken("token has expired")
    if iat > timestamp + config.leeway_seconds:
        raise MalformedToken("token was issued in the future")
    if version not in SUPPORTED_VERSIONS:
        raise UnsupportedVersion(f"claims version {version} is not supported")

    return Claims(
        sub=sub,
        username=username,
        roles=frozenset(Role(r) for r in roles if isinstance(r, str) and r in _ROLE_VALUES),
        issued_at=datetime.fromtimestamp(iat, UTC),
        expires_at=datetime.fromtimestamp(exp, UTC),
        version=version,
    )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
