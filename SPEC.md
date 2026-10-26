# Brand Reviews, WordPress → Django: Spec

<!--
Single source of truth for what gets built. Written by /challenge-kit:kickoff, changed only through /challenge-kit:change-spec.
IDs (R, O, T, M) are stable: never renumber, never reuse. A removed requirement stays, marked removed.
Brief: CHALLENGE.md (read-only). Research: docs/research.md.
-->

GitHub Project: {{PROJECT_URL}} (number {{PROJECT_NUMBER}})

## Requirements

### R1. Content lives in a clean relational model
- Source: CHALLENGE.md § Pillar 1 (Models); § Decisions 1–2
- Priority: P0
- Status: active
- Milestone: M4
- Acceptance:
  - Tables `Industry`, `Brand` and `Review` exist. There is no key/value meta table.
  - `Brand` fields:
    - Required: `name`, unique `slug`, FK `industry`, `website_url`, `founded_year`, `headquarters`, `seo_title`, `seo_description`, `short_description`, `content`.
    - Nullable: `legacy_average_rating`, never displayed.
    - Bookkeeping: unique `wp_id`, `is_active`.
  - `Review` fields:
    - Required: FK `brand`, unique `slug`, `title`, `content`, `rating` (1–5, enforced by a DB check constraint), `reviewer_wp_id`, `reviewer_name`, `reviewer_location`, `published_at`.
    - Bookkeeping: unique `wp_id`, `is_active`.
  - `Industry` fields: `name`, unique `slug`, unique `wp_id`.
  - Average rating and review count are computed from active reviews, not stored. A brand with no reviews has average `null` and count `0`.
  - The main app has no password or role columns. `reviewer_wp_id` is an opaque reference resolvable only in the auth service.
  - Inactive brands and reviews are hidden from every page and API response.

### R2. A re-runnable WordPress content import
- Source: CHALLENGE.md § Pillar 1 (data migration); § Decision 3
- Priority: P0
- Status: active
- Milestone: M9
- Acceptance:
  - `make migrate` runs `manage.py import_wp` in the app container. It reads the WP `db` service with plain SQL (see the wp-source contract).
  - On an empty DB it creates 5 industries, 5 brands and 60 reviews, with slugs equal to WP `post_name`.
  - A second run creates 0 rows and leaves every field unchanged. It prints `created/updated/deactivated` counts.
  - Matching between runs is by `wp_id`. A row whose `wp_id` no longer appears among published WP posts is set `is_active=False` (soft delete).
  - If the source returns zero brands, the command aborts without writing. The whole run is one transaction, so a failure leaves the previous state.
  - Re-import never overwrites a `short_description` that an editor changed through R13.
  - Imported `short_description` is the plain text of the first `<p>` of the brand content.

### R3. Homepage
- Source: CHALLENGE.md § Pillar 1 (Server-rendered pages)
- Priority: P1
- Status: active
- Milestone: M4
- Acceptance:
  - `GET /` returns 200, server-rendered.
  - The page has a hero, a "Featured Brands" grid of up to 6 brands ordered by computed average rating, and a "Recent Reviews" list of the 6 newest reviews (by `published_at`, then `wp_id`).
  - Each review in the list shows a brand link, a title link, stars, an excerpt, and the reviewer's name and location.

### R4. Brand detail page
- Source: CHALLENGE.md § Pillar 1 (Server-rendered pages)
- Priority: P1
- Status: active
- Milestone: M4
- Acceptance:
  - `GET /brand/<slug>/` returns 200 for all 5 WP brand slugs and 404 for unknown or inactive slugs.
  - The page shows industry, name, stars with the computed average, "(N reviews)", HQ, founded year, and a website link showing the host only, with `rel="nofollow noopener"`.
  - The content and the brand's reviews (newest first) follow. With no reviews, it shows "No reviews yet."
  - `<title>` and the meta description come from `seo_title` / `seo_description` when set.

### R5. Review detail page
- Source: CHALLENGE.md § Pillar 1 (Server-rendered pages)
- Priority: P1
- Status: active
- Milestone: M4
- Acceptance:
  - `GET /review/<slug>/` returns 200 for all 60 WP review slugs and 404 for unknown or inactive slugs.
  - The page shows a back link to the brand, the title, stars, a byline (name, location, date) and the body.
  - Stored HTML is sanitized with an allowlist at render time (T13). A `<script>` in content never reaches the response.

### R6. Brand listing API
- Source: CHALLENGE.md § Pillar 2; § Decision 4
- Priority: P0
- Status: active
- Milestone: M5
- Acceptance:
  - `GET /api/brands/` is public and returns `{count, next, previous, results}`.
  - **Pagination:** `?page=` (default 1) and `?page_size=` (default 12, max 50).
  - **Industry filter:** `?industry=<slug>` is repeatable; results match any of the given slugs. An unknown slug returns 400.
  - **Sorting:** `?ordering=` accepts only `average_rating`, `-average_rating`, `review_count`, `-review_count`, `name` and `-name`. Any other value returns 400. Ties always break by `name` then `pk`, and a null average sorts last in both directions.
  - Paging through every page with any sort returns each active brand exactly once.
  - **Row shape:**
    - `name`, `slug`, `industry {slug, name}`, `short_description`, `url`
    - `average_rating`: one decimal, or `null`
    - `review_count`
    - `top_review`: `{title, slug, rating, snippet}` or `null`
  - **Top review:** the highest-rated review, then the newest, then the highest pk. Its `snippet` is plain text of at most 22 words.

### R7. `<BrandList />` loads, filters and sorts brands
- Source: CHALLENGE.md § Pillar 3; § Decision 5
- Priority: P1
- Status: active
- Milestone: M6
- Acceptance:
  - The component reads its config from the mount element (see the brandlist-mount contract) and calls `GET /api/brands/`.
  - The industry filter is a `<fieldset>` of checkboxes (multi-select). Sort is a labelled `<select>`. The pager is a `<nav>` that marks the current page with `aria-current`.
  - Industry, ordering and page are reflected in the page URL's query string. Loading a URL with those params restores the same view, and browser back/forward moves between views.
  - Changing the filter or the sort resets to page 1 and cancels any in-flight request.

### R8. `<BrandList />` states, accessibility and responsiveness
- Source: CHALLENGE.md § Pillar 3
- Priority: P1
- Status: active
- Milestone: M6
- Acceptance:
  - **Loading:** the list region has `aria-busy="true"` and a skeleton.
  - **Empty:** a message with a "Clear filters" button.
  - **Error:** `role="alert"` with a "Retry" button that repeats the request.
  - A polite `aria-live` region announces the result count after each load.
  - Every control works by keyboard with a visible `:focus-visible` style. Stars use `role="img"` with an accessible label. The axe check in Vitest reports no violations in each state.
  - The layout is a single column at 375px and a multi-column grid on desktop, with no horizontal scroll at 320px.

### R9. SCSS source tree for the theme
- Source: CHALLENGE.md § Pillar 4; § Decision 6
- Priority: P1
- Status: active
- Milestone: M7
- Acceptance:
  - `frontend/scss/` has `abstracts/` (tokens, breakpoint mixin), `base/`, `layout/`, `components/`, `pages/` and `main.scss`.
  - Design tokens are a Sass map that emits the `:root` custom properties of `reference/theme.css`, plus tokens for the literals repeated in it.
  - `make css` compiles `main.scss` in Docker. A check script (part of `make check`) compares the compiled selector set and custom-property set against `reference/theme.css`. The check passes when the only differences are the listed deliberate deltas (`:focus-visible`, `prefers-reduced-motion`, `brand-list__*`).
  - The README says how to compile and how to add a component partial.

### R10. WordPress users exist in the auth service
- Source: CHALLENGE.md § Pillar 5 (Users)
- Priority: P0
- Status: active
- Milestone: M9
- Acceptance:
  - `make migrate` also runs `manage.py import_wp_users` in the auth container. It imports all 9 `wp_users`, keyed by unique `wp_user_id`.
  - Re-running creates no duplicates and never overwrites a password or role changed since import.
  - Role mapping: WP `administrator` → `editor`, every other role → `reader`. After import, only `admin` is an editor.
  - Migrated users log in with their WP passwords (`admin`/`admin`, reviewers/`changeme`) via the `$wp$` hasher (T5). The hash is upgraded to Django's default on first successful login.

### R11. Login returns tokens
- Source: CHALLENGE.md § Pillar 5 (Login)
- Priority: P0
- Status: active
- Milestone: M3
- Acceptance:
  - `POST /api/token/` with valid `{username, password}` returns 200 with `{access, refresh, token_type: "Bearer", expires_in}`.
  - Invalid credentials return 401 with no hint about which field was wrong.
  - The access token verifies with the shared library against the auth public key (see the access-token contract).

### R12. Roles are owned by the auth service
- Source: CHALLENGE.md § Pillar 5 (Authorization)
- Priority: P0
- Status: active
- Milestone: M3
- Acceptance:
  - Roles `reader` and `editor` exist only in the auth DB. A user has one or more roles.
  - The access token's `roles` claim lists the user's roles at issue time.
  - The main app's DB has no table or column holding roles.

### R13. Editors can edit a brand's short description
- Source: CHALLENGE.md § Pillar 5 (Protected endpoint)
- Priority: P0
- Status: active
- Milestone: M5
- Acceptance:
  - `PATCH /api/brands/<slug>/` with `{short_description}` and an editor's Bearer token returns 200 with the updated row (R6 shape). The change shows on `/brand/<slug>/`.
  - A reader token returns 403. A missing, expired, wrongly signed or wrong-audience token returns 401. An unknown slug returns 404.
  - Fields other than `short_description` are rejected with 400.
  - `GET /api/brands/` and all pages stay public.
  - The app verifies tokens locally with the shared library and makes no call to the auth service.

### R14. Shared library for token verification and permissions
- Source: CHALLENGE.md § Pillar 6; § Decision 8
- Priority: P0
- Status: active
- Milestone: M2
- Acceptance:
  - `libs/tokenauth/` has its own `pyproject.toml` with a semver version, a src layout, PyJWT (with cryptography) as the only core dependency, and extras `drf` and `test`.
  - Both services declare it as a workspace dependency with a `>=X,<X+1` range and install it non-editable in their images.
  - It exposes the interface in the shared-lib contract: token verification, the claims type, a role check, and DRF authentication and permission classes.
  - Its tests run with `pip install ./libs/tokenauth[test] && pytest` in a bare Python image with no Django installed (except the DRF-class tests, which are marked and need the `drf` extra).
  - Tests cover expired, wrong `aud`, wrong `iss`, wrong `alg`, `alg=none`, unknown `kid`, missing claim, and an unsupported `v`.

### R15. README covers everything the brief asks for
- Source: CHALLENGE.md § What to deliver
- Priority: P1
- Status: active
- Milestone: M8
- Acceptance:
  - The README covers how to run the app, the auth service and the component.
  - It shows how to get a token and call the PATCH endpoint, with curl commands.
  - It covers the shared library's tests and how a new version reaches each service.
  - It covers running and re-running the migration.
  - It has a modeling-decisions section (rating discrepancy, postmeta mapping, reviewer model), a "with more time" list, and the places where AI defaults were chosen.
  - Every command in it runs as written on a fresh clone with Docker only.

### R16. Archive pages and 404
- Source: user (kickoff 2026-10-26); theme `archive-brand.php`, `archive-review.php`, `404.php`
- Priority: P2
- Status: active
- Milestone: M4
- Acceptance:
  - `GET /brand/` renders a server-side card grid of active brands with page links, and mounts `<BrandList />` over it. Without JS, the server grid still works.
  - `GET /review/` renders a paginated list of active reviews.
  - Unknown URLs render a styled 404 page with status 404.

### R17. Token refresh and logout
- Source: CHALLENGE.md § Decision 7; user (kickoff 2026-10-26)
- Priority: P1
- Status: active
- Milestone: M3
- Acceptance:
  - `POST /api/token/refresh/` with a valid, unrevoked refresh token returns a new access token whose `roles` claim reflects the user's current roles. It also rotates the refresh token.
  - `POST /api/token/logout/` revokes the given refresh token. Refreshing with it afterwards returns 401.
  - Access tokens expire 10 minutes after issue and refresh tokens 24 hours after issue.

### R18. Roles are managed in the auth service admin
- Source: CHALLENGE.md § Decision 7; user (kickoff 2026-10-26)
- Priority: P2
- Status: active
- Milestone: M3
- Acceptance:
  - An editor-role superuser can sign in to the auth service's `/admin/` and change a user's roles.
  - The change appears in that user's next refreshed access token.

### R19. OpenAPI schemas for both APIs
- Source: user (kickoff 2026-10-26)
- Priority: P2
- Status: active
- Milestone: M5
- Acceptance:
  - `GET /api/schema/` on app and on auth returns an OpenAPI 3 document matching the brands-api and auth-api contracts.
  - `/api/docs/` serves Swagger UI on both. A CI test fails if the schema drifts from the contract examples.

## Out of scope

- **O1.** Migrating the WP admin/editor experience. Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O2.** Yoast SEO frontend output (we only use the imported title/description in `<head>`). Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O3.** WP plugin parity beyond data structure. Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O4.** User-facing review submission and search. Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O5.** Registration, password reset, social login, MFA. Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O6.** A login UI; tokens come from curl or the browsable API. Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O7.** Image uploads; placeholders only. Why: excluded by the brief. Source: CHALLENGE.md § Out of scope
- **O8.** Pixel-matching the WP theme. Why: excluded by the brief (structure, not identical output). Source: CHALLENGE.md § Out of scope
- **O9.** Instant token revocation (`jti` denylist) and a JWKS endpoint. Why: both add a runtime dependency on auth or a shared store. Revocation is bounded by the 10-minute access TTL plus revocable refresh (R17). Both are documented as the upgrade path. Source: user
- **O10.** The WP `/about/` page and local git hooks. Why: not needed; CI `check` is the gate. Source: user

## Services and boundaries

| Service | Path | Owns | Calls | Trusts callers how | Port | When a provider is down |
|---|---|---|---|---|---|---|
| app | `services/app/` | Industries, brands and reviews in `app-db`; server-rendered pages; `/api/brands/`; `import_wp`; serves the frontend bundle and CSS | WP `db` (importer only, wp-source); tokenauth lib in-process | Public for GET and pages. PATCH needs a Bearer access token verified locally with the auth public key (env `AUTH_PUBLIC_KEYS`, by `kid`) via tokenauth. No call to auth. | 8000 | **auth down:** pages, GET, and PATCH with an unexpired token keep working; only new logins and refreshes fail. **WP db down:** `import_wp` retries the connection, then exits non-zero having written nothing. |
| auth | `services/auth/` | Users, password hashes, roles, refresh tokens and the signing key, in `auth-db`; `/api/token/*`; `/admin/`; `import_wp_users` | WP `db` (importer only, wp-source); tokenauth lib (claim schema, constants) | Login: username and password. Refresh and logout: refresh token. Admin: Django session, superuser. | 8001 | **WP db down:** `import_wp_users` exits non-zero having written nothing. |
| frontend | `frontend/` | `<BrandList />` source, SCSS tree, Vite and sass build (output copied into the app image) | app `GET /api/brands/` (same origin) | n/a (static assets) | none (build-only) | **app API down or erroring:** error state with Retry (R8). |
| tokenauth | `libs/tokenauth/` | Token verification, claim schema, role constants, DRF auth and permission classes | none | n/a (in-process library) | n/a | n/a |
| app-db / auth-db | compose services | Postgres data for app and for auth, separately | none | Credentials from `.env`, compose network only | none (internal) | The owning service fails its healthcheck and returns 503. |
| WP stack (`db`, `wordpress`, `phpmyadmin`) | existing | Source data; untouched | none | existing | 8080, 8081 | n/a |

## Contracts

- **brands-api** ([doc](docs/contracts/brands-api.md)): app → frontend and API clients. `GET /api/brands/` paginated listing with repeatable industry filter, whitelisted ordering and card fields. `PATCH /api/brands/<slug>/` editor-only short-description edit. Error bodies and status codes.
- **auth-api** ([doc](docs/contracts/auth-api.md)): auth → API clients (curl, demo). Login, refresh (rotating) and logout (revoking) endpoints, request and response bodies, errors.
- **access-token** ([doc](docs/contracts/access-token.md)): auth → tokenauth/app. JWT header (`alg=EdDSA`, `typ`, `kid`) and claims (`iss`, `aud`, `sub`, `iat`, `exp`, `v`, `roles`, `username`), validation rules, key distribution and rotation.
- **shared-lib** ([doc](docs/contracts/shared-lib.md)): tokenauth → app and auth. The Python public API: `verify_token`, `Claims`, `Role`, `has_role`, `TokenError` subclasses, `BearerTokenAuthentication`, `HasRole`; settings it reads; versioning policy.
- **brandlist-mount** ([doc](docs/contracts/brandlist-mount.md)): app template → frontend bundle. Mount element id and data attributes, asset paths, and the URL query keys `<BrandList />` owns.
- **wp-source** ([doc](docs/contracts/wp-source.md)): WP `db` → app and auth importers. Tables, columns, meta keys, filters and the field mapping each importer reads.

## Technology choices

| ID | Area | Choice | Why | Alternative considered | Research |
|---|---|---|---|---|---|
| T1 | Framework | Django 5.2 LTS for both services | Supported to 2028-04; conservative shipping story; works with DRF, django-filter, stubs and Python 3.14 | Django 6.1 (EOL 2027-12) | [3](docs/research.md#3-django-backend--rest-api), [9](docs/research.md#9-runtimes-and-package-managers) |
| T2 | API | DRF 3.18 + django-filter 26 + drf-spectacular | Matches the brief's "DRF authentication class and permission class"; repeatable filter and ordering built in; OpenAPI for R19 | Django Ninja; plain JSON views | [3](docs/research.md#3-django-backend--rest-api) |
| T3 | Databases | Separate Postgres containers `app-db` and `auth-db`; `psycopg[binary]` | Clear "own database"; Django's usual engine; no build deps | One server with two DBs; MariaDB | [7](docs/research.md#7-repo-infra-ci), [9](docs/research.md#9-runtimes-and-package-managers) |
| T4 | Tokens | PyJWT, EdDSA (Ed25519) access JWT, 10-minute TTL; opaque refresh token stored in auth-db, 24 hours, rotated; public key to app by env with `kid` | App can verify but never mint; works with auth down; role change applies within one TTL | HS256 shared secret; opaque token + introspection; simplejwt | [4](docs/research.md#4-auth-service--tokens) |
| T5 | Passwords | Custom Django hasher for WP `$wp$2y$` (bcrypt over base64 HMAC-SHA384), re-hash on login | Demo logins keep working; verified on all 9 dump hashes | Forced reset (no reset flow in scope); one demo password | [4](docs/research.md#4-auth-service--tokens) |
| T6 | Import | Importers read WP `db` with plain SQL via PyMySQL; `wp_id` upsert; soft delete | No SQL-dump tokenizer; has users and roles; pure-Python driver | Parse `db/dump.sql`; WP REST; wp-cli | [2](docs/research.md#2-migration-approach) |
| T7 | Python runtime and packaging | `python:3.14-slim`; uv workspace with one hashed `uv.lock`; repo-root build context with strict `.dockerignore`; hatchling for tokenauth; multi-stage, non-root images | Longest Python support; reproducible, fast, cached installs; lib stays tool-agnostic | pip + pip-compile with per-service contexts | [5](docs/research.md#5-shared-library), [9](docs/research.md#9-runtimes-and-package-managers) |
| T8 | Node runtime | `node:26-alpine`, npm with `package-lock.json` and `npm ci` | LTS from 2026-10-28, supported to 2029-04; npm needs no extra tool | Node 24; pnpm; bun | [9](docs/research.md#9-runtimes-and-package-managers) |
| T9 | Frontend | React 19 + TypeScript ~6.0 + Vite 8 library build (in a Docker stage, served by Django as static); `useBrandList` hook with fetch + AbortController; URL query as state | One origin, no CORS; small and explainable | TanStack Query; Vite dev server + proxy; committed bundle | [6](docs/research.md#6-react-brandlist--scss) |
| T10 | Styles | `sass` CLI; 7-1-lite partials; Sass token map emitting `:root`; one breakpoint mixin; reference class names kept, BEM `brand-list__*` for new parts | The structure the brief grades; the selector diff stays meaningful | CSS Modules; Tailwind; styled-components | [6](docs/research.md#6-react-brandlist--scss) |
| T11 | Code quality | ruff (lint + format, pinned); mypy <2.4 with django-stubs and DRF stubs (strict on tokenauth, gradual on services); ESLint 9 + typescript-eslint + react-hooks + jsx-a11y; Prettier; stylelint-config-standard-scss | One Python tool; a11y linting; strict types on security code; version pins avoid known peer conflicts | black + flake8 + isort; pyright; Biome | [8](docs/research.md#8-code-quality-tooling) |
| T12 | Tests | pytest + pytest-django; Vitest + React Testing Library + msw + vitest-axe | Standard for each stack; msw mocks the brands-api contract | Jest; Cypress | [6](docs/research.md#6-react-brandlist--scss), [8](docs/research.md#8-code-quality-tooling) |
| T13 | HTML safety | `nh3` allowlist (≈ `wp_kses_post`) applied at render via a template filter | Safe even if stored rows change later | Sanitize at import | [3](docs/research.md#3-django-backend--rest-api) |
| T14 | Build and CI | Makefile + docker compose (`make up` starts everything; `check`, `lint`, `fmt-check`, `typecheck`, `test`, `css`, `migrate`, `fmt`); GitHub Actions workflow with job `check` running `make check`; Dependabot for uv, npm, docker, actions | Docker-only (C1); identical locally and in CI | Host tooling; pre-commit framework | [7](docs/research.md#7-repo-infra-ci), [8](docs/research.md#8-code-quality-tooling) |

## Milestones

| ID | Milestone | Kind | Delivers | Priority | Depends on |
|---|---|---|---|---|---|
| M1 | Integration | scaffolding, contracts, CI | Repo layout, Dockerfiles, compose services (app, auth, app-db, auth-db, frontend build), uv workspace, npm project, Makefile targets, CI `check`, Dependabot, `.dockerignore`/`.gitignore`/`.env.example`, contract mocks (msw handlers, test keypair and token fixtures, fake WP source rows) | P0 | none |
| M2 | Shared library | library | R14 | P0 | M1 |
| M3 | Auth service | service | R11, R12, R17, R18 | P0 | M1, M2 |
| M4 | App models and pages | service | R1, R3, R4, R5, R16 | P0 | M1 |
| M5 | Brands API | service | R6, R13, R19 | P0 | M2, M4 |
| M6 | `<BrandList />` | frontend | R7, R8 | P1 | M1 (mocks), M5 for integration |
| M7 | SCSS tree | frontend | R9 | P1 | M1 |
| M8 | Integration, smoke and README | integration | R15, plus an end-to-end smoke test (login at auth → PATCH at app → change visible on page) | P1 | M3, M5, M6, M7 |
| M9 | Data migration | migration | R2, R10 | P0 | M3, M4 |

## Changelog

| Date | Change | By |
|---|---|---|
| 2026-10-26 | Initial spec | kickoff |
