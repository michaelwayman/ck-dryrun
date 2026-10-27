import jwt
import pytest
from django.db import OperationalError
from django.test import Client
from tokenauth import verify_token

from accounts.models import User
from tokens.models import RefreshToken
from tokens.tests.conftest import contract_example, make_user, verifier_config

pytestmark = pytest.mark.django_db


def post(client: Client, path: str, body: object) -> object:
    return client.post(path, body, content_type="application/json")


def test_login_ok_matches_the_contract() -> None:
    example = contract_example("auth-api", "login-ok.json")
    make_user("admin", "admin", "editor")

    response = Client().post(
        example["request"]["path"], example["request"]["body"], content_type="application/json"
    )

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert set(body) == set(example["response"]["body"])
    assert body["token_type"] == "Bearer" and body["expires_in"] == 600
    claims = verify_token(body["access"], verifier_config())
    assert claims.username == "admin" and [r.value for r in claims.roles] == ["editor"]
    header = jwt.get_unverified_header(body["access"])
    assert header == {"alg": "EdDSA", "typ": "JWT", "kid": "test-2026-10"}


def test_refresh_token_is_stored_only_as_a_hash_for_24_hours(client: Client) -> None:
    make_user("admin", "admin", "editor")
    raw = client.post(
        "/api/token/", {"username": "admin", "password": "admin"}, content_type="application/json"
    ).json()["refresh"]

    assert len(raw) >= 43
    stored = RefreshToken.objects.get()
    assert stored.token_hash != raw and raw not in stored.token_hash
    assert (stored.expires_at - stored.created_at).total_seconds() == 24 * 3600


@pytest.mark.parametrize("case", ["unknown", "wrong", "inactive"])
def test_bad_credentials_share_one_401(client: Client, case: str) -> None:
    example = contract_example("auth-api", "login-bad-credentials.json")
    make_user("admin", "admin", "editor", is_active=case != "inactive")
    username = "ghost" if case == "unknown" else "admin"
    password = "wrong" if case == "wrong" else "admin"

    response = client.post(
        "/api/token/", {"username": username, "password": password}, content_type="application/json"
    )

    assert response.status_code == 401
    assert response.json() == example["response"]["body"]
    assert response["Cache-Control"] == "no-store"


def test_missing_field_matches_the_contract(client: Client) -> None:
    example = contract_example("auth-api", "login-missing-field.json")

    response = client.post(
        example["request"]["path"], example["request"]["body"], content_type="application/json"
    )

    assert response.status_code == 400
    assert response.json() == example["response"]["body"]


@pytest.mark.parametrize(
    "body", [{"username": "admin", "password": 123}, {"username": None, "password": "x"}, [1]]
)
def test_non_string_fields_are_invalid_body(client: Client, body: object) -> None:
    response = client.post("/api/token/", body, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_body"


def test_malformed_json_is_invalid_body(client: Client) -> None:
    response = client.post("/api/token/", "{nope", content_type="application/json")

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_body",
        "message": "Invalid request body.",
        "fields": None,
    }


def test_wp_password_is_rehashed_on_first_login(client: Client) -> None:
    from accounts.tests.test_hashers import stored

    user = make_user("wp", "unused", "reader")
    User.objects.filter(pk=user.pk).update(password=stored("wp-pass"))

    response = client.post(
        "/api/token/", {"username": "wp", "password": "wp-pass"}, content_type="application/json"
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.password.startswith("pbkdf2_sha256$")


def test_database_down_is_503(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(*args: object, **kwargs: object) -> None:
        raise OperationalError("connection refused")

    monkeypatch.setattr("tokens.views.authenticate", down)

    response = client.post(
        "/api/token/", {"username": "a", "password": "b"}, content_type="application/json"
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unavailable"


def test_get_is_not_allowed(client: Client) -> None:
    response = client.get("/api/token/")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
