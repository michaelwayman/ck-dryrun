"""The claim schema and role constants shared by auth (minting) and the app (checking)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Role(StrEnum):
    READER = "reader"
    EDITOR = "editor"


CLAIMS_VERSION = 1
SUPPORTED_VERSIONS: frozenset[int] = frozenset({1})


@dataclass(frozen=True, slots=True)
class Claims:
    sub: str
    username: str
    roles: frozenset[Role]
    issued_at: datetime
    expires_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class VerifierConfig:
    public_keys: Mapping[str, str]
    issuer: str
    audience: str
    leeway_seconds: int = 30


def has_role(claims: Claims, role: Role) -> bool:
    return role in claims.roles
