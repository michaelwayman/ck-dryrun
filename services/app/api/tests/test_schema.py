import re
from typing import Any

import pytest
from django.test import Client
from jsonschema import Draft202012Validator

from api.tests.conftest import EXAMPLES, example

EXAMPLE_NAMES = sorted(p.stem for p in EXAMPLES.glob("*.json"))


@pytest.fixture(scope="module")
def schema(django_db_blocker: Any) -> dict[str, Any]:
    with django_db_blocker.unblock():
        response = Client().get("/api/schema/", {"format": "json"})
    assert response.status_code == 200
    doc: dict[str, Any] = response.json()
    return doc


def validate(doc: dict[str, Any], schema: dict[str, Any], instance: Any) -> None:
    """Validate against an OpenAPI 3.1 schema object, resolving refs within the document."""
    Draft202012Validator({**schema, "components": doc["components"]}).validate(instance)


def operation(doc: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    for template, item in doc["paths"].items():
        if re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), path):
            op: dict[str, Any] = item[method.lower()]
            return op
    raise AssertionError(f"{method} {path} is not in the schema")


def test_schema_is_openapi_3_1_with_bearer_auth(schema: dict[str, Any]) -> None:
    assert schema["openapi"].startswith("3.1")
    assert schema["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "An access token from the auth service (access-token contract).",
    }
    assert operation(schema, "PATCH", "/api/brands/x/")["security"] == [{"bearerAuth": []}]
    assert "security" not in operation(schema, "GET", "/api/brands/")


def test_get_documents_every_query_parameter(schema: dict[str, Any]) -> None:
    params = {p["name"] for p in operation(schema, "GET", "/api/brands/")["parameters"]}

    assert params == {"page", "page_size", "industry", "ordering"}


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_every_brands_api_example_matches_the_schema(schema: dict[str, Any], name: str) -> None:
    ex = example(name)
    request, response = ex["request"], ex["response"]
    op = operation(schema, request["method"], request["path"])

    documented = op["responses"].get(str(response["status"]))
    assert documented, f"{name}: status {response['status']} is not documented"
    validate(schema, documented["content"]["application/json"]["schema"], response["body"])

    if response["status"] >= 400:
        return  # the request is invalid on purpose
    params = {p["name"]: p["schema"] for p in op.get("parameters", []) if p["in"] == "query"}
    for key, value in request.get("query", {}).items():
        assert key in params, f"{name}: query parameter {key} is not documented"
        param = params[key]
        if param.get("type") == "integer":
            value = int(value)
        validate(schema, param, value)
    if "body" in request:
        body_schema = op["requestBody"]["content"]["application/json"]["schema"]
        validate(schema, body_schema, request["body"])


def test_schema_rejects_a_body_that_drifts_from_the_contract(schema: dict[str, Any]) -> None:
    body = example("list-default")["response"]["body"]
    body["results"][0]["review_count"] = None
    op = operation(schema, "GET", "/api/brands/")

    with pytest.raises(Exception, match="None is not of type 'integer'"):
        validate(schema, op["responses"]["200"]["content"]["application/json"]["schema"], body)


def test_swagger_ui_is_served(client: Client) -> None:
    response = client.get("/api/docs/")

    assert response.status_code == 200
    assert b"swagger-ui-dist@5.33.1" in response.content
