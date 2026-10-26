# Contract: auth-api

Provider: `auth` (`services/auth/`). Consumers: API clients (curl and the browsable API during the demo, and future clients).
Spec: R11, R17. Related: [access-token](access-token.md). Changes go through a `contract` issue.

## Purpose
- Exchange a username and password for an access token and a refresh token.
- Exchange a refresh token for a new access token. The old refresh token is rotated out and the user's current roles are re-read.
- Revoke a refresh token (logout).

## Conventions
- All endpoints are JSON over HTTP. The auth service listens on port 8001.
- Error bodies use the same shape as brands-api: `{"error": {"code", "message", "fields"}}`.
- Every token endpoint is `POST`. None of them needs an `Authorization` header.
- Responses carry `Cache-Control: no-store`.

## POST /api/token/ (login)
Request body:
| Field | Type | Nullable | Rules |
|---|---|---|---|
| `username` | string | no | Required. This is the WP `user_login`. |
| `password` | string | no | Required. |

200 response (a TokenPair):
| Field | Type | Nullable | Notes |
|---|---|---|---|
| `access` | string | no | A JWT. See [access-token](access-token.md). Lives for 600 s. |
| `refresh` | string | no | An opaque random string of at least 43 base64url characters. Only its hash is stored. Lives for 24 h. |
| `token_type` | string | no | Always `"Bearer"`. |
| `expires_in` | integer | no | Seconds until `access` expires (600). |

Errors:
| Status | `code` | When |
|---|---|---|
| 400 | `invalid_body` | `username` or `password` is missing or not a string. |
| 401 | `invalid_credentials` | Unknown user, wrong password, or an inactive user. The message is the same in every case. |
| 503 | `unavailable` | auth-db is unreachable. |

## POST /api/token/refresh/
Request body: `{"refresh": string}` (required, not null).

On success the response is 200 with a new TokenPair:
- `access` carries the user's current `roles`.
- `refresh` is a new token, and the submitted one is revoked (rotation).

Errors:
| Status | `code` | When |
|---|---|---|
| 400 | `invalid_body` | `refresh` is missing. |
| 401 | `invalid_refresh` | The token is unknown, expired or revoked, or its user is inactive. Reusing an already-rotated token also revokes every refresh token for that user. |

## POST /api/token/logout/
Request body: `{"refresh": string}` (required, not null).

Responses:
- 204, empty body: the refresh token has been revoked. Logout is idempotent, so an already-revoked or unknown token also returns 204.
- 400 `invalid_body`: `refresh` is missing.

Access tokens that are already issued stay valid until they expire, at most 600 s. See O9 in SPEC.md.

## Not in this contract
- `/admin/` is a Django admin UI for role management (R18). It is not an API.
- There is no endpoint that publishes keys. The app gets the public key from its environment, per [access-token](access-token.md).

## Examples
Stored in [auth-api/examples/](auth-api/examples/):
- `login-ok.json`
- `login-bad-credentials.json`
- `login-missing-field.json`
- `refresh-ok.json`
- `refresh-revoked.json`
- `logout-ok.json`
