import json
import re
import socket
from datetime import UTC, datetime
from functools import partial
from typing import Any

import pytest
import tokenauth
import tokenauth.drf
from django.test import Client
from django.test.utils import override_settings

from api.tests.conftest import CONTRACTS, example
from catalog.models import Brand
from catalog.tests import factories

pytestmark = pytest.mark.django_db
TOKENS = CONTRACTS / "access-token"
PUBLIC_KEYS = json.loads((TOKENS / "mock/test-keypair/public-keys.json").read_text())
URL = "/api/brands/acme-insurance/"


@pytest.fixture(autouse=True)
def keys() -> Any:
    with override_settings(
        TOKENAUTH_PUBLIC_KEYS=PUBLIC_KEYS,
        TOKENAUTH_ISSUER="brand-reviews-auth",
        TOKENAUTH_AUDIENCE="brand-reviews-app",
    ):
        yield


def token_header(name: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """A mock token, verified at its example's verify_at rather than wall-clock time."""
    verify_at = json.loads((TOKENS / f"examples/{name}.json").read_text())["verify_at"]
    now = datetime.fromtimestamp(verify_at, UTC)
    monkeypatch.setattr(tokenauth.drf, "verify_token", partial(tokenauth.verify_token, now=now))
    return "Bearer " + (TOKENS / f"mock/tokens/{name}.jwt").read_text().strip()


def send(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    request: dict[str, Any],
) -> Any:
    headers = dict(request.get("headers", {}))
    match = re.search(r"access-token/examples/([\w-]+)\.json", headers.pop("Authorization", ""))
    if match:
        headers["Authorization"] = token_header(match[1], monkeypatch)
    headers.pop("Content-Type", None)
    return client.generic(
        request["method"],
        request["path"],
        json.dumps(request["body"]),
        content_type="application/json",
        headers=headers,
    )


@pytest.mark.parametrize(
    "name",
    [
        "patch-ok",
        "patch-reader-forbidden",
        "patch-no-token",
        "patch-expired-token",
        "patch-unknown-field",
        "patch-unknown-slug",
    ],
)
def test_patch_examples(
    client: Client, monkeypatch: pytest.MonkeyPatch, seeded: None, name: str
) -> None:
    ex = example(name)
    before = Brand.objects.get(slug="acme-insurance").short_description

    response = send(client, monkeypatch, ex["request"])

    assert response.status_code == ex["response"]["status"]
    assert response.json() == ex["response"]["body"]
    for header, value in ex["response"].get("headers", {}).items():
        assert response.headers[header] == value
    after = Brand.objects.get(slug="acme-insurance").short_description
    if name == "patch-ok":
        assert after == ex["request"]["body"]["short_description"]
    else:
        assert after == before


@pytest.fixture
def editor(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    return {"Authorization": token_header("editor", monkeypatch)}


def patch(client: Client, body: Any, headers: dict[str, str], url: str = URL) -> Any:
    return client.patch(url, json.dumps(body), content_type="application/json", headers=headers)


@pytest.mark.parametrize(
    ("body", "fields"),
    [
        ({}, {"short_description": ["This field is required."]}),
        ({"short_description": 5}, {"short_description": ["Must be a string."]}),
        ({"short_description": None}, {"short_description": ["This field may not be null."]}),
        (
            {"short_description": "x" * 501},
            {"short_description": ["Ensure this field has no more than 500 characters."]},
        ),
    ],
)
def test_invalid_body(
    client: Client, seeded: None, editor: dict[str, str], body: Any, fields: Any
) -> None:
    response = patch(client, body, editor)

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "invalid_body", "message": "Invalid request body.", "fields": fields}
    }


def test_value_is_trimmed_before_the_length_check(
    client: Client, seeded: None, editor: dict[str, str]
) -> None:
    response = patch(client, {"short_description": f"  {'x' * 500}\n"}, editor)

    assert response.status_code == 200
    assert response.json()["short_description"] == "x" * 500


def test_empty_short_description_is_allowed(
    client: Client, seeded: None, editor: dict[str, str]
) -> None:
    assert patch(client, {"short_description": "   "}, editor).json()["short_description"] == ""


@pytest.mark.parametrize("body", [[], "text", 3])
def test_body_that_is_not_an_object_is_invalid_body(
    client: Client, seeded: None, editor: dict[str, str], body: Any
) -> None:
    response = patch(client, body, editor)

    assert (response.status_code, response.json()["error"]["code"]) == (400, "invalid_body")


def test_malformed_json_is_invalid_body(
    client: Client, seeded: None, editor: dict[str, str]
) -> None:
    response = client.patch(URL, "{not json", content_type="application/json", headers=editor)

    assert (response.status_code, response.json()["error"]["code"]) == (400, "invalid_body")


def test_every_unknown_field_is_named(client: Client, seeded: None, editor: dict[str, str]) -> None:
    response = patch(client, {"name": "A", "slug": "b"}, editor)

    assert response.json()["error"]["fields"] == {
        "name": ["Unknown field."],
        "slug": ["Unknown field."],
    }


def test_inactive_brand_is_404(client: Client, editor: dict[str, str]) -> None:
    brand = factories.brand(is_active=False)

    response = patch(client, {"short_description": "x"}, editor, f"/api/brands/{brand.slug}/")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "token", ["wrong-audience", "unknown-kid", "alg-none", "unsupported-version"]
)
def test_rejected_tokens_are_401_invalid_token(
    client: Client, monkeypatch: pytest.MonkeyPatch, seeded: None, token: str
) -> None:
    response = patch(
        client, {"short_description": "x"}, {"Authorization": token_header(token, monkeypatch)}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
    assert response.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'


def test_a_bad_signature_is_401(
    client: Client, monkeypatch: pytest.MonkeyPatch, seeded: None
) -> None:
    header = token_header("editor", monkeypatch)
    tampered = header[:-4] + ("AAAA" if not header.endswith("AAAA") else "BBBB")

    response = patch(client, {"short_description": "x"}, {"Authorization": tampered})

    assert (response.status_code, response.json()["error"]["code"]) == (401, "invalid_token")


def test_with_no_public_keys_every_token_is_rejected(
    client: Client, seeded: None, editor: dict[str, str]
) -> None:
    with override_settings(TOKENAUTH_PUBLIC_KEYS={}):
        response = patch(client, {"short_description": "x"}, editor)

    assert response.status_code == 401


def test_other_schemes_are_not_authenticated(client: Client, seeded: None) -> None:
    response = patch(client, {"short_description": "x"}, {"Authorization": "Basic dTpw"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("method", ["put", "post", "delete", "get"])
def test_other_methods_are_405_even_without_a_token(
    client: Client, seeded: None, method: str
) -> None:
    response = getattr(client, method)(URL)

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_order_is_401_then_403_then_404(
    client: Client, monkeypatch: pytest.MonkeyPatch, seeded: None
) -> None:
    unknown = "/api/brands/no-such-brand/"
    reader = {"Authorization": token_header("reader", monkeypatch)}

    assert patch(client, {"bad": 1}, {}, unknown).status_code == 401
    assert patch(client, {"bad": 1}, reader, unknown).status_code == 403


def test_patch_never_opens_a_network_connection(
    client: Client, monkeypatch: pytest.MonkeyPatch, seeded: None, editor: dict[str, str]
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the app must not call the auth service")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    assert patch(client, {"short_description": "Offline."}, editor).status_code == 200
