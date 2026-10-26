"""Sign every access-token example into tokens/<example>.jwt, or check that they match.

    uv run --no-project --with "pyjwt[crypto]" python <this file> [--check]

(Full commands in README.md.)

Uses the TEST-ONLY key in test-keypair/ and never generates one. Ed25519 signatures are
deterministic and each example carries its own iat/exp, so the output is byte-stable.
Header and payload are taken from the example as-is: the unknown kid is signed with the
real test key, and alg=none (which PyJWT refuses to encode) is built by hand, unsigned.
"""

import json
import sys
from pathlib import Path

from jwt.api_jws import PyJWS
from jwt.utils import base64url_encode

MOCK = Path(__file__).parent
EXAMPLES = MOCK.parent / "examples"
TOKENS = MOCK / "tokens"
PRIVATE_KEY = MOCK / "test-keypair" / "TEST-ONLY-private.pem"


def compact(obj: dict, sort_keys: bool = False) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=sort_keys).encode()


def sign(example: dict, key: bytes) -> str:
    header, payload = example["header"], compact(example["payload"])
    if header["alg"] == "none":
        # Same header encoding as PyJWT (compact, sorted keys); empty signature.
        segments = [compact(header, sort_keys=True), payload]
        return b".".join(base64url_encode(s) for s in segments).decode() + "."
    return PyJWS().encode(payload, key, algorithm=header["alg"], headers=header)


def build() -> dict[str, str]:
    key = PRIVATE_KEY.read_bytes()
    return {
        path.stem + ".jwt": sign(json.loads(path.read_text()), key) + "\n"
        for path in sorted(EXAMPLES.glob("*.json"))
    }


def main() -> int:
    tokens = build()
    if "--check" in sys.argv[1:]:
        on_disk = {p.name: p.read_text() for p in TOKENS.glob("*.jwt")}
        bad = sorted(n for n in tokens.keys() | on_disk.keys() if tokens.get(n) != on_disk.get(n))
        for name in bad:
            print(f"differs: tokens/{name}")
        print(f"checked {len(tokens)} tokens, {len(bad)} differ")
        return 1 if bad else 0
    TOKENS.mkdir(exist_ok=True)
    for name, token in tokens.items():
        (TOKENS / name).write_text(token)
    print(f"wrote {len(tokens)} tokens to {TOKENS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
