import json
from collections.abc import Callable
from typing import Any

import pytest
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from tokenauth import Claims, Role
from tokenauth.drf import BearerTokenAuthentication, HasRole, TokenUser

from tests.conftest import CONTRACTS, mock_token

pytestmark = pytest.mark.drf


class EditorView(APIView):
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [HasRole(Role.EDITOR)]

    def get(self, request: Request) -> Response:
        user: Any = request.user
        return Response({"id": user.id, "username": user.username})


def call(authorization: str | None = None) -> Response:
    headers: dict[str, Any] = {} if authorization is None else {"HTTP_AUTHORIZATION": authorization}
    response: Response = EditorView.as_view()(APIRequestFactory().get("/", **headers))
    return response


def authenticate(authorization: str) -> tuple[TokenUser, Claims] | None:
    request = Request(APIRequestFactory().get("/", HTTP_AUTHORIZATION=authorization))
    return BearerTokenAuthentication().authenticate(request)


def test_no_header_is_anonymous_and_gets_401() -> None:
    assert BearerTokenAuthentication().authenticate(Request(APIRequestFactory().get("/"))) is None
    response = call()
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    assert response.data["detail"].code == "not_authenticated"


def test_other_scheme_is_anonymous() -> None:
    assert authenticate("Basic dXNlcjpwYXNz") is None
    assert call("Basic dXNlcjpwYXNz").status_code == 401


@pytest.mark.parametrize("header", ["Bearer", "Bearer a b", "Bearer not-a-jwt"])
def test_bad_header_is_invalid_token(header: str) -> None:
    response = call(header)
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer error="invalid_token"'
    assert response.data["detail"].code == "invalid_token"


@pytest.mark.parametrize("name", ["expired", "wrong-audience", "alg-none", "unknown-kid"])
def test_token_error_is_invalid_token(name: str, clock: Callable[[str], None]) -> None:
    clock(name)
    response = call(f"Bearer {mock_token(name)}")
    assert response.status_code == 401
    assert response.data["detail"].code == "invalid_token"


def test_expired_matches_brands_api_example(clock: Callable[[str], None]) -> None:
    example = json.loads(
        (CONTRACTS / "brands-api" / "examples" / "patch-expired-token.json").read_text()
    )
    expected = example["response"]
    clock("expired")
    response = call(f"Bearer {mock_token('expired')}")
    assert response.status_code == expected["status"]
    assert response["WWW-Authenticate"] == expected["headers"]["WWW-Authenticate"]
    assert response.data["detail"].code == expected["body"]["error"]["code"]
    assert str(response.data["detail"]) == expected["body"]["error"]["message"]


def test_valid_editor() -> None:
    result = authenticate(f"Bearer {mock_token('editor')}")
    assert result is not None
    user, claims = result
    assert (user.id, user.pk, user.username) == ("1", "1", "admin")
    assert user.roles == claims.roles == frozenset({Role.EDITOR})
    assert user.is_authenticated and not user.is_anonymous
    assert not hasattr(user, "save")

    response = call(f"bearer {mock_token('editor')}")
    assert response.status_code == 200
    assert response.data == {"id": "1", "username": "admin"}


def test_valid_reader_lacks_editor_role() -> None:
    result = authenticate(f"Bearer {mock_token('reader')}")
    assert result is not None
    assert result[0].roles == frozenset({Role.READER})

    response = call(f"Bearer {mock_token('reader')}")
    assert response.status_code == 403
    assert str(response.data["detail"]) == "Requires role: editor."
