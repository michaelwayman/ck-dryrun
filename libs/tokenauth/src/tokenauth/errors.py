"""Verification errors. Each subclass carries the `.code` named in the shared-lib contract."""


class TokenError(Exception):
    code = "token_error"


class ExpiredToken(TokenError):
    code = "expired"


class InvalidSignature(TokenError):
    code = "invalid_signature"


class InvalidAlgorithm(TokenError):
    code = "invalid_algorithm"


class InvalidIssuer(TokenError):
    code = "invalid_issuer"


class InvalidAudience(TokenError):
    code = "invalid_audience"


class UnknownKey(TokenError):
    code = "unknown_key"


class MissingClaim(TokenError):
    code = "missing_claim"


class UnsupportedVersion(TokenError):
    code = "unsupported_version"


class MalformedToken(TokenError):
    code = "malformed"
