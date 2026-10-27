"""Contract data, read in place from docs/contracts (mounted read-only by `make test`)."""

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jwt
import pytest
from tokenauth import VerifierConfig

CONTRACTS = Path(__file__).resolve().parents[3] / "docs" / "contracts"
MOCK = CONTRACTS / "access-token" / "mock"
KID = "test-2026-10"

# The no-Django run (`pip install .[test]`) has no DRF, so it skips the drf tests entirely.
collect_ignore = [] if importlib.util.find_spec("rest_framework") else ["drf"]


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CONTRACTS / "access-token" / "examples" / name).read_text())
    return data


def mock_token(name: str) -> str:
    return (MOCK / "tokens" / f"{name}.jwt").read_text().strip()


def verify_at(name: str) -> datetime:
    return datetime.fromtimestamp(example(f"{name}.json")["verify_at"], UTC)


def public_keys() -> dict[str, str]:
    keys: dict[str, str] = json.loads((MOCK / "test-keypair" / "public-keys.json").read_text())
    return keys


def sign(payload: dict[str, Any], **header: Any) -> str:
    """Sign with the TEST-ONLY private key, for cases the mock tokens don't cover."""
    private_key = (MOCK / "test-keypair" / "TEST-ONLY-private.pem").read_text()
    return jwt.encode(payload, private_key, algorithm="EdDSA", headers={"kid": KID, **header})


@pytest.fixture
def config() -> VerifierConfig:
    return VerifierConfig(
        public_keys=public_keys(), issuer="brand-reviews-auth", audience="brand-reviews-app"
    )
