# Contract: shared-lib (`tokenauth`)

- **Provider:** `libs/tokenauth/`.
- **Consumers:** `app` (verification and the DRF classes) and `auth` (the claim schema and role constants it uses when minting).
- **Spec:** R14, T4, T7. **Implements:** [access-token](access-token.md).
- **Changes:** go through a `contract` issue.

## Purpose
The only code both services share. It contains token verification, the claim type, the role constants, and a thin DRF layer.

It does not contain users, login, refresh, signing keys, token minting, or the WP password hasher. Those belong to `auth`.

## Package
- **Distribution:** `tokenauth`, src layout, semver, `version` set statically in `pyproject.toml`. The first release is `1.0.0`.
- **Dependencies:** PyJWT with the `crypto` extra is the only core dependency, and it imports no Django.
- **Extras:**
  - `drf`: djangorestframework and Django.
  - `test`: pytest and cryptography.
- **How services depend on it:** both declare `tokenauth>=1,<2` through the uv workspace. Breaking changes bump the major version and follow the expand/contract rule in access-token.

## Public API (`import tokenauth`)
| Name | Kind | Signature / fields | Notes |
|---|---|---|---|
| `Role` | `StrEnum` | `READER = "reader"`, `EDITOR = "editor"` | The single definition of role names, used by both services. |
| `CLAIMS_VERSION` | `int` | `1` | The schema version the auth service mints. |
| `SUPPORTED_VERSIONS` | `frozenset[int]` | `{1}` | The versions the verifier accepts. |
| `Claims` | frozen dataclass | `sub: str`, `username: str`, `roles: frozenset[Role]`, `issued_at: datetime`, `expires_at: datetime`, `version: int` | Datetimes are timezone-aware UTC. Unknown role strings are dropped. |
| `VerifierConfig` | frozen dataclass | `public_keys: Mapping[str, str]` (kid → PEM), `issuer: str`, `audience: str`, `leeway_seconds: int = 30` | |
| `verify_token(token: str, config: VerifierConfig, *, now: datetime \| None = None) -> Claims` | function | | Applies every rule in access-token. Raises a `TokenError` subclass on failure and never returns partial claims. `now` exists for tests. |
| `has_role(claims: Claims, role: Role) -> bool` | function | | |
| `TokenError` | exception | `.code: str` | Base class for all verification errors. |
| `ExpiredToken`, `InvalidSignature`, `InvalidAlgorithm`, `InvalidIssuer`, `InvalidAudience`, `UnknownKey`, `MissingClaim`, `UnsupportedVersion`, `MalformedToken` | `TokenError` subclasses | `.code` is respectively `expired`, `invalid_signature`, `invalid_algorithm`, `invalid_issuer`, `invalid_audience`, `unknown_key`, `missing_claim`, `unsupported_version`, `malformed` | |

## DRF layer (`tokenauth.drf`; needs the `drf` extra)
| Name | Kind | Behaviour |
|---|---|---|
| `BearerTokenAuthentication` | DRF `BaseAuthentication` | Reads `Authorization: Bearer <token>`.<br>No header: returns `None` (anonymous).<br>Malformed header or a `TokenError`: raises `AuthenticationFailed` with code `invalid_token`.<br>Success: returns `(TokenUser, Claims)`.<br>`authenticate_header` returns `Bearer`, so DRF sends 401 rather than 403. |
| `TokenUser` | plain object | `.id` and `.pk` = `sub`, `.username`, `.roles`, `.is_authenticated = True`, `.is_anonymous = False`. Never saved to a database. |
| `HasRole` | DRF `BasePermission` factory | `HasRole(Role.EDITOR)` returns a permission class. It denies anonymous requests (DRF turns that into 401) and returns `False` when the role is missing (403). |

Settings the DRF layer reads, through `django.conf.settings`:
| Setting | Value |
|---|---|
| `TOKENAUTH_PUBLIC_KEYS` | dict of kid → PEM, normally parsed from env `AUTH_PUBLIC_KEYS` |
| `TOKENAUTH_ISSUER` | issuer string |
| `TOKENAUTH_AUDIENCE` | audience string |
| `TOKENAUTH_LEEWAY_SECONDS` | optional, default 30 |

## Tests the library must ship
- Every error class, raised from the matching access-token example.
- A happy path for reader and for editor.
- Pinning: `alg=none` and an HS256 token signed with the public key as the secret are both rejected.
- `has_role`.
- The DRF classes (marked `drf`): no header, bad header, a valid reader, a valid editor.

The core tests run with no Django installed.

## Examples
Found in [shared-lib/examples/](shared-lib/examples/):
- `verifier-config.json`: a sample `VerifierConfig` with a test public key placeholder.
- `claims-editor.json`: the `Claims` produced from `access-token/examples/editor.json`.
- `errors.json`: maps each access-token example to the exception class and `.code` it produces.
