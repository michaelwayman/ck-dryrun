# access-token mock

> **TEST-ONLY KEY.** `test-keypair/TEST-ONLY-private.pem` is committed on purpose and protects nothing. It is never used outside tests: not as `AUTH_SIGNING_KEY`, not in dev, not in any deployed environment. Runtime keys come from `.env` or `scripts/dev-keys.sh` (kid `dev-<sha12>`), never from here.

A fixed Ed25519 keypair and one signed JWT per [access-token contract](../../access-token.md) example, so tokenauth, auth and app tests verify real tokens without sharing code.

- `test-keypair/TEST-ONLY-private.pem`: PKCS8 PEM, unencrypted, kid `test-2026-10`.
- `test-keypair/TEST-ONLY-public.pem`: the SPKI PEM public key.
- `test-keypair/public-keys.json`: `{"test-2026-10": "<public PEM>"}`, usable directly as `AUTH_PUBLIC_KEYS`.
- `sign_examples.py`: signs `../examples/*.json` into `tokens/<example>.jwt`.
- `tokens/*.jwt`: one compact token per line, with a trailing newline (`.strip()` it).

Both PEM files start with a `# TEST-ONLY KEY …` comment line; `cryptography` and PyJWT load them as they are.

## Regenerate or check

The key was generated once and is only read. Ed25519 is deterministic and every example carries its own `iat`/`exp`, so the tokens are byte-stable.

```bash
uv run --no-project --with "pyjwt[crypto]" python docs/contracts/access-token/mock/sign_examples.py
uv run --no-project --with "pyjwt[crypto]" python docs/contracts/access-token/mock/sign_examples.py --check
```

`--check` regenerates in memory and exits 1 if any token differs, is missing or is extra.

## Tokens and what each one tests

Each example's header and payload are signed as-is. Verify at the example's `verify_at`, not wall-clock time, or every token is expired.

| Token | How it's built | `verify_at` | Expected |
|---|---|---|---|
| `editor.jwt` | signed, kid `test-2026-10` | 1793000060 | accepted, roles `["editor"]` |
| `reader.jwt` | signed, kid `test-2026-10` | 1793000060 | accepted, roles `["reader"]` |
| `expired.jwt` | signed; `exp` 1793000600 | 1793000631 (past `exp` + 30 s leeway) | `expired` |
| `wrong-audience.jwt` | signed; `aud` `some-other-service` | 1793000060 | `invalid_audience` |
| `alg-none.jwt` | hand-built, header `alg: none`, empty signature (ends in `.`) | 1793000060 | `invalid_algorithm` |
| `unknown-kid.jwt` | signed with the test key, header kid `retired-2025-01` | 1793000060 | `unknown_key` |
| `unsupported-version.jwt` | signed; `v` 2 | 1793000060 | `unsupported_version` |

Each token fails for one reason only: apart from the field named, it is a valid token.

## Not here

Bad signatures, HS256/RS256 headers, missing claims, a future `iat` and malformed tokens have no example. Build those in tokenauth's own tests, from these tokens or the test key.
