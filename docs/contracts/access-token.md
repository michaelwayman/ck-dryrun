# Contract: access-token

Provider: `auth`, which mints tokens. Consumers: the `tokenauth` library, which verifies them, and `app` through that library.
Spec: R11, R12, R13, R14, T4. Changes go through a `contract` issue and follow the versioning rule below.

## Purpose
This contract defines the JWT the auth service issues and the rules a verifier applies. If both sides follow it, the app can authorize requests without calling the auth service.

## Format
A compact JWS (RFC 7519), signed with Ed25519.

### Header
| Field | Value | Nullable | Rule |
|---|---|---|---|
| `alg` | `"EdDSA"` | no | Verifiers accept only this value. They reject `none`, every HS* or RS* algorithm, and anything else. |
| `typ` | `"JWT"` | no | |
| `kid` | string | no | Selects the public key. An unknown `kid` is rejected. |

### Claims
| Claim | Type | Nullable | Rule |
|---|---|---|---|
| `iss` | string | no | Must equal `AUTH_ISSUER` (default `"brand-reviews-auth"`). |
| `aud` | string | no | Must equal `"brand-reviews-app"`. |
| `sub` | string | no | Auth service user id (stringified integer). Stable and opaque. |
| `username` | string | no | WP `user_login`. For display and logs only, never for authorization. |
| `roles` | array of string | no | A subset of `["reader", "editor"]`. May be empty. Unknown values are ignored. |
| `v` | integer | no | Claim schema version. It is `1` today. Verifiers reject any version outside their supported set. |
| `iat` | integer (epoch seconds) | no | |
| `exp` | integer (epoch seconds) | no | `exp - iat` is 600. |

## Verification rules (all required)
1. Decode the header. Look up the public key by `kid` in the configured key set. If none matches, the error is `unknown_key`.
2. Verify the signature with `algorithms=["EdDSA"]`, pinned. The `alg` in the header is never trusted.
3. Require `iss`, `aud`, `sub`, `exp`, `iat`, `v` and `roles`. Any missing claim gives `missing_claim`.
4. Check `iss` and `aud`. Check `exp` with 30 s leeway (otherwise `expired`). Reject an `iat` more than 30 s in the future.
5. Check that `v` is in the supported set, which is `{1}` for library 1.x.

## Keys
- The auth service holds the private key, `AUTH_SIGNING_KEY`, a PEM file mounted from `.env` or a generated dev key. The private key is never committed.
- The app gets `AUTH_PUBLIC_KEYS`, a JSON object `{"<kid>": "<PEM public key>"}` from env. It may hold several keys at once to support rotation.
- To rotate:
  1. Add the new public key to the app.
  2. Switch auth to the new private key and `kid`.
  3. After 600 s plus the leeway, remove the old public key.

## Versioning (claim schema)
- A change that is additive and that old verifiers can ignore, such as a new optional claim, keeps `v`.
- A breaking change bumps `v` and uses an expand/contract rollout:
  1. Release a tokenauth major version that accepts both versions.
  2. Deploy it to the app.
  3. Switch auth to mint the new `v`.
  4. After one TTL, release a version that drops the old `v`.

## Examples
Decoded header and payload pairs are in [access-token/examples/](access-token/examples/). Signed test tokens are produced from the M1 test keypair fixture, not stored here.

| File | Case | Expected outcome |
|---|---|---|
| `editor.json` | valid editor | accepted |
| `reader.json` | valid reader | accepted |
| `expired.json` | expired | `expired` |
| `wrong-audience.json` | wrong audience | `invalid_audience` |
| `alg-none.json` | `alg=none` | `invalid_algorithm` |
| `unknown-kid.json` | unknown `kid` | `unknown_key` |
| `unsupported-version.json` | unsupported `v` | `unsupported_version` |
