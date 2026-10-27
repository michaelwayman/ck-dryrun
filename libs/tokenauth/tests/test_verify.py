import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import tokenauth
from tokenauth import Claims, Role, VerifierConfig, has_role, verify_token

from .conftest import CONTRACTS, MOCK, example, mock_token, sign, verify_at

ERRORS: dict[str, dict[str, str]] = json.loads(
    (CONTRACTS / "shared-lib" / "examples" / "errors.json").read_text()
)
NOW = verify_at("editor")


def editor_payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {**example("editor.json")["payload"], **changes}
    return {key: value for key, value in payload.items() if value is not None}


@pytest.mark.parametrize("path", sorted(ERRORS))
def test_contract_error_examples(path: str, config: VerifierConfig) -> None:
    name = path.removeprefix("access-token/examples/").removesuffix(".json")
    expected = ERRORS[path]
    with pytest.raises(tokenauth.TokenError) as raised:
        verify_token(mock_token(name), config, now=verify_at(name))
    assert type(raised.value).__name__ == expected["raises"]
    assert raised.value.code == expected["code"]


def test_editor_matches_claims_example(config: VerifierConfig) -> None:
    data = json.loads((CONTRACTS / "shared-lib" / "examples" / "claims-editor.json").read_text())
    expected = data["claims"]
    claims = verify_token(mock_token("editor"), config, now=NOW)
    assert claims == Claims(
        sub=expected["sub"],
        username=expected["username"],
        roles=frozenset(Role(role) for role in expected["roles"]),
        issued_at=datetime.fromisoformat(expected["issued_at"]),
        expires_at=datetime.fromisoformat(expected["expires_at"]),
        version=expected["version"],
    )
    assert claims.issued_at.tzinfo == UTC
    assert has_role(claims, Role.EDITOR)
    assert not has_role(claims, Role.READER)


def test_reader(config: VerifierConfig) -> None:
    claims = verify_token(mock_token("reader"), config, now=verify_at("reader"))
    assert claims.roles == frozenset({Role.READER})
    assert has_role(claims, Role.READER)
    assert not has_role(claims, Role.EDITOR)


def test_unknown_roles_are_dropped(config: VerifierConfig) -> None:
    token = sign(editor_payload(roles=["editor", "admin", 7]))
    assert verify_token(token, config, now=NOW).roles == frozenset({Role.EDITOR})


def test_empty_roles_are_allowed(config: VerifierConfig) -> None:
    assert verify_token(sign(editor_payload(roles=[])), config, now=NOW).roles == frozenset()


def test_hs256_signed_with_the_public_key_is_rejected(config: VerifierConfig) -> None:
    secret = (MOCK / "test-keypair" / "TEST-ONLY-public.pem").read_bytes()
    # PyJWT refuses PEM keys as HMAC secrets, so build the token by hand as an attacker would.
    token = _hand_signed(editor_payload(), {"alg": "HS256", "typ": "JWT", "kid": "test-2026-10"})
    token = token + _hmac(token, secret)
    with pytest.raises(tokenauth.InvalidAlgorithm):
        verify_token(token, config, now=NOW)


def test_bad_signature(config: VerifierConfig) -> None:
    header, payload, _ = mock_token("editor").split(".")
    signature = mock_token("reader").split(".")[2]
    with pytest.raises(tokenauth.InvalidSignature) as raised:
        verify_token(f"{header}.{payload}.{signature}", config, now=NOW)
    assert raised.value.code == "invalid_signature"


@pytest.mark.parametrize("claim", ["iss", "aud", "sub", "username", "exp", "iat", "v", "roles"])
def test_missing_claim(claim: str, config: VerifierConfig) -> None:
    with pytest.raises(tokenauth.MissingClaim) as raised:
        verify_token(sign(editor_payload(**{claim: None})), config, now=NOW)
    assert raised.value.code == "missing_claim"


def test_wrong_issuer(config: VerifierConfig) -> None:
    with pytest.raises(tokenauth.InvalidIssuer) as raised:
        verify_token(sign(editor_payload(iss="someone-else")), config, now=NOW)
    assert raised.value.code == "invalid_issuer"


def test_audience_list_is_rejected(config: VerifierConfig) -> None:
    with pytest.raises(tokenauth.InvalidAudience):
        verify_token(sign(editor_payload(aud=["brand-reviews-app"])), config, now=NOW)


def test_expiry_leeway(config: VerifierConfig) -> None:
    exp = datetime.fromtimestamp(example("editor.json")["payload"]["exp"], UTC)
    token = mock_token("editor")
    assert verify_token(token, config, now=exp + timedelta(seconds=29))
    with pytest.raises(tokenauth.ExpiredToken):
        verify_token(token, config, now=exp + timedelta(seconds=30))


def test_future_iat_is_rejected(config: VerifierConfig) -> None:
    iat = int(NOW.timestamp())
    assert verify_token(sign(editor_payload(iat=iat + 30, exp=iat + 630)), config, now=NOW)
    with pytest.raises(tokenauth.MalformedToken) as raised:
        verify_token(sign(editor_payload(iat=iat + 31, exp=iat + 631)), config, now=NOW)
    assert raised.value.code == "malformed"


def test_clock_defaults_to_now(config: VerifierConfig) -> None:
    with pytest.raises(tokenauth.ExpiredToken):
        verify_token(mock_token("editor"), config)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-jwt",
        "a.b.c",
        sign(editor_payload(v="1")),
        sign(editor_payload(iat=True)),
        sign(editor_payload(sub=1)),
        sign(editor_payload(roles="editor")),
        sign(editor_payload(exp=10**20)),
    ],
)
def test_malformed(token: str, config: VerifierConfig) -> None:
    with pytest.raises(tokenauth.MalformedToken):
        verify_token(token, config, now=NOW)


def test_missing_kid(config: VerifierConfig) -> None:
    token = _hand_signed(editor_payload(), {"alg": "EdDSA", "typ": "JWT"}) + "sig"
    with pytest.raises(tokenauth.UnknownKey):
        verify_token(token, config, now=NOW)


def test_claims_are_frozen(config: VerifierConfig) -> None:
    claims = verify_token(mock_token("editor"), config, now=NOW)
    with pytest.raises(AttributeError):
        claims.sub = "2"  # type: ignore[misc]


def test_constants() -> None:
    assert tokenauth.CLAIMS_VERSION == 1
    assert frozenset({1}) == tokenauth.SUPPORTED_VERSIONS
    assert [role.value for role in Role] == ["reader", "editor"]
    assert VerifierConfig(public_keys={}, issuer="i", audience="a").leeway_seconds == 30


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hand_signed(payload: dict[str, Any], header: dict[str, Any]) -> str:
    return f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}."


def _hmac(token: str, secret: bytes) -> str:
    return _b64(hmac.new(secret, token[:-1].encode(), hashlib.sha256).digest())
