from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone
from tokenauth import verify_token

from accounts.models import Role, User
from tokens.models import RefreshToken
from tokens.tests.conftest import contract_example, make_user, verifier_config

pytestmark = pytest.mark.django_db


def post(client: Client, path: str, body: Any) -> Any:
    return client.post(path, body, content_type="application/json")


def login(client: Client) -> dict[str, Any]:
    body: dict[str, Any] = post(client, "/api/token/", {"username": "admin", "password": "admin"}).json()
    return body


@pytest.fixture
def admin() -> User:
    return make_user("admin", "admin", "editor")


def test_refresh_ok_rotates_and_matches_the_contract(client: Client, admin: User) -> None:
    example = contract_example("auth-api", "refresh-ok.json")
    token_a = login(client)["refresh"]

    response = post(client, example["request"]["path"], {"refresh": token_a})

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert set(body) == set(example["response"]["body"])
    assert body["refresh"] != token_a and body["expires_in"] == 600
    assert verify_token(body["access"], verifier_config()).username == "admin"


def test_role_change_shows_in_the_refreshed_token(client: Client, admin: User) -> None:
    token_a = login(client)["refresh"]
    admin.roles.add(Role.objects.get(name="reader"))

    access = post(client, "/api/token/refresh/", {"refresh": token_a}).json()["access"]

    roles = {r.value for r in verify_token(access, verifier_config()).roles}
    assert roles == {"editor", "reader"}


def test_replaying_a_rotated_token_revokes_the_whole_family(client: Client, admin: User) -> None:
    example = contract_example("auth-api", "refresh-revoked.json")
    other_session = login(client)["refresh"]
    token_a = login(client)["refresh"]
    token_b = post(client, "/api/token/refresh/", {"refresh": token_a}).json()["refresh"]

    replay = post(client, "/api/token/refresh/", {"refresh": token_a})

    assert replay.status_code == 401
    assert replay.json() == example["response"]["body"]
    for token in (token_b, other_session):
        assert post(client, "/api/token/refresh/", {"refresh": token}).status_code == 401
    assert not RefreshToken.objects.filter(revoked_at__isnull=True).exists()


@pytest.mark.parametrize("case", ["unknown", "expired", "inactive"])
def test_dead_tokens_are_invalid_refresh(client: Client, admin: User, case: str) -> None:
    token = login(client)["refresh"]
    if case == "unknown":
        token = "x" * 43
    elif case == "expired":
        day_ago = timezone.now() - timedelta(days=1, seconds=1)
        RefreshToken.objects.update(created_at=day_ago, expires_at=day_ago + timedelta(days=1))
    else:
        User.objects.filter(pk=admin.pk).update(is_active=False)

    response = post(client, "/api/token/refresh/", {"refresh": token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh"


def test_logout_revokes_and_is_idempotent(client: Client, admin: User) -> None:
    example = contract_example("auth-api", "logout-ok.json")
    token = login(client)["refresh"]

    for refresh in (token, token, "never-issued"):
        response = post(client, example["request"]["path"], {"refresh": refresh})
        assert response.status_code == example["response"]["status"] == 204
        assert response.content == b""

    logged_out = post(client, "/api/token/refresh/", {"refresh": token})
    assert logged_out.status_code == 401
    # Logout alone revokes one token, not the family.
    assert post(client, "/api/token/refresh/", {"refresh": login(client)["refresh"]}).status_code == 200


@pytest.mark.parametrize("path", ["/api/token/refresh/", "/api/token/logout/"])
@pytest.mark.parametrize("body", [{}, {"refresh": None}, {"refresh": 5}])
def test_missing_refresh_is_invalid_body(client: Client, path: str, body: Any) -> None:
    response = post(client, path, body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_body" and "refresh" in error["fields"]
