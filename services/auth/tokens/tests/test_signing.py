from datetime import UTC, datetime
from pathlib import Path

import jwt
import pytest
from accounts.models import User
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.exceptions import ImproperlyConfigured
from pytest_django.fixtures import Settings
from tokenauth import Role, verify_token

from tokens.signing import derive_kid, mint_access_token, signing_key
from tokens.tests.conftest import CONTRACTS, contract_example, make_user, verifier_config

pytestmark = pytest.mark.django_db


def test_editor_token_matches_the_contract_example_byte_for_byte() -> None:
    example = contract_example("access-token", "editor.json")
    user = make_user("admin", "pw", "editor")
    User.objects.filter(pk=user.pk).update(id=1)
    user.refresh_from_db()
    now = datetime.fromtimestamp(example["payload"]["iat"], UTC)

    token = mint_access_token(user, now)

    assert jwt.get_unverified_header(token) == example["header"]
    assert jwt.decode(token, options={"verify_signature": False}) == example["payload"]
    expected = (CONTRACTS / "access-token" / "mock" / "tokens" / "editor.jwt").read_text().strip()
    assert token == expected


def test_minted_token_passes_tokenauth_with_the_apps_config() -> None:
    user = make_user("both", "pw", "reader", "editor")
    now = datetime(2026, 10, 26, 12, tzinfo=UTC)

    claims = verify_token(mint_access_token(user, now), verifier_config(), now=now)

    assert claims.sub == str(user.pk)
    assert claims.username == "both"
    assert claims.roles == {Role.READER, Role.EDITOR}
    assert (claims.expires_at - claims.issued_at).total_seconds() == 600


def test_user_without_roles_gets_an_empty_roles_claim() -> None:
    token = mint_access_token(make_user("nobody", "pw"), datetime.now(UTC))
    assert jwt.decode(token, options={"verify_signature": False})["roles"] == []


def test_kid_is_derived_like_dev_keys_sh(settings: Settings, tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    (tmp_path / "signing.pem").write_bytes(pem)
    settings.AUTH_SIGNING_KEY = str(tmp_path / "signing.pem")
    settings.AUTH_SIGNING_KID = ""

    kid = signing_key().kid
    assert kid == derive_kid(key)
    assert kid.startswith("dev-") and len(kid) == 16


def test_missing_key_setting_is_a_configuration_error(settings: Settings) -> None:
    settings.AUTH_SIGNING_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        signing_key()
