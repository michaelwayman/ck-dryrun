"""Shared token verification for the app and auth services. See docs/contracts/shared-lib.md.

The DRF classes live in `tokenauth.drf`, which is never imported here, so core needs no Django.
"""

from tokenauth.claims import (
    CLAIMS_VERSION,
    SUPPORTED_VERSIONS,
    Claims,
    Role,
    VerifierConfig,
    has_role,
)
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
from tokenauth.verify import verify_token

__version__ = "1.0.0"

__all__ = [
    "CLAIMS_VERSION",
    "SUPPORTED_VERSIONS",
    "Claims",
    "ExpiredToken",
    "InvalidAlgorithm",
    "InvalidAudience",
    "InvalidIssuer",
    "InvalidSignature",
    "MalformedToken",
    "MissingClaim",
    "Role",
    "TokenError",
    "UnknownKey",
    "UnsupportedVersion",
    "VerifierConfig",
    "has_role",
    "verify_token",
]
