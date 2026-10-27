"""Contract data read in place from docs/contracts (mounted read-only by `make test`)."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pytest_django.fixtures import Settings
from tokenauth import VerifierConfig

if TYPE_CHECKING:
    from accounts.models import User

CONTRACTS = Path(__file__).resolve().parents[4] / "docs" / "contracts"
KEYPAIR = CONTRACTS / "access-token" / "mock" / "test-keypair"
TEST_KID = "test-2026-10"


def contract_example(contract: str, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CONTRACTS / contract / "examples" / name).read_text())
    return data


def verifier_config() -> VerifierConfig:
    """The app's view of auth: the TEST-ONLY public key set, issuer and audience."""
    return VerifierConfig(
        public_keys=json.loads((KEYPAIR / "public-keys.json").read_text()),
        issuer="brand-reviews-auth",
        audience="brand-reviews-app",
    )


@pytest.fixture(autouse=True)
def test_signing_key(settings: Settings) -> None:
    """Sign with the contract's TEST-ONLY key and kid, never a runtime key."""
    settings.AUTH_SIGNING_KEY = str(KEYPAIR / "TEST-ONLY-private.pem")
    settings.AUTH_SIGNING_KID = TEST_KID


def make_user(username: str, password: str, *roles: str, **fields: Any) -> "User":
    # Imported here: this conftest loads before Django is set up.
    from accounts.models import Role, User

    user = User.objects.create_user(username, password=password, **fields)
    user.roles.set(Role.objects.filter(name__in=roles))
    return user
