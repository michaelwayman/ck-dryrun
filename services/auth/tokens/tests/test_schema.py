"""R19: the served OpenAPI schema must accept every auth-api contract example."""

import copy
from typing import Any

import pytest
from django.test import Client
from jsonschema import Draft202012Validator

from tokens.tests.conftest import CONTRACTS, contract_example

EXAMPLES = sorted(p.name for p in (CONTRACTS / "auth-api" / "examples").glob("*.json"))


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    document: dict[str, Any] = Client().get("/api/schema/", {"format": "json"}).json()
    return document


def closed(document: dict[str, Any]) -> dict[str, Any]:
    """The components with additionalProperties: false on every object with properties, so a
    field the contract adds or the schema drops fails validation."""
    components = copy.deepcopy(document["components"])
    for component in components["schemas"].values():
        if "properties" in component:
            component.setdefault("additionalProperties", False)
    return components


def validator(document: dict[str, Any], schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator({**schema, "components": closed(document)})


def test_schema_is_openapi_3_and_documents_every_endpoint(schema: dict[str, Any]) -> None:
    assert schema["openapi"].startswith("3.")
    assert {path: set(ops) for path, ops in schema["paths"].items()} == {
        "/api/token/": {"post"},
        "/api/token/refresh/": {"post"},
        "/api/token/logout/": {"post"},
    }


def test_every_contract_example_is_covered() -> None:
    assert EXAMPLES == [
        "login-bad-credentials.json",
        "login-missing-field.json",
        "login-ok.json",
        "logout-ok.json",
        "refresh-ok.json",
        "refresh-revoked.json",
    ]


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_matches_the_schema(schema: dict[str, Any], name: str) -> None:
    example = contract_example("auth-api", name)
    request, response = example["request"], example["response"]
    operation = schema["paths"][request["path"]][request["method"].lower()]

    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    request_ok = validator(schema, request_schema).is_valid(request["body"])
    # A 400 example sends a body the schema must reject; every other example a valid one.
    assert request_ok is (response["status"] != 400)

    documented = operation["responses"][str(response["status"])]
    if "body" not in response:
        assert "content" not in documented
        return
    response_schema = documented["content"]["application/json"]["schema"]
    validator(schema, response_schema).validate(response["body"])


def test_swagger_ui_is_served(client: Client) -> None:
    response = client.get("/api/docs/")

    assert response.status_code == 200
    assert b"swagger-ui" in response.content
