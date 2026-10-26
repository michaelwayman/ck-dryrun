# Research

Brief: CHALLENGE.md. Last updated: 2026-10-26.

## Priorities

| ID | Priority | Kind | Weight | Source |
|---|---|---|---|---|
| C1 | Everything runs with Docker only | constraint | n/a | brief, `CHALLENGE.md:20` |
| C2 | Migration re-runnable without duplicates | constraint | n/a | brief, `CHALLENGE.md:51` |
| C3 | URL slugs match WP permalinks | constraint | n/a | brief, `CHALLENGE.md:52` |
| C4 | Auth service in its own container with its own DB; main app stores no passwords or roles | constraint | n/a | brief, `CHALLENGE.md:81-83` |
| C5 | Shared lib: own `pyproject.toml`, tests run without either Django project, kept small | constraint | n/a | brief, `CHALLENGE.md:93-98` |
| C6 | Single-repo deliverable with the README sections the brief lists | constraint | n/a | brief, `CHALLENGE.md:150-166` |
| P7 | Defensibility: every choice simple enough to explain and defend live | preference | high | user, 2026-10-26 |
| P8 | Production realism: built like it would ship (tests, a11y, CI, security hygiene) | preference | high | user, 2026-10-26 |
| P9 | Extensibility in the live session: easy to add a new requirement in ~25 min with AI | preference | medium | user, 2026-10-26 |
| P10 | Build speed: fewest moving parts and dependencies | preference | medium | user, 2026-10-26 |

## How it fits together

### The recommended combination
A monorepo on `origin` (`michaelwayman/ck-dryrun`). The WP stack stays untouched beside the new parts:
- **Two Django services:** `services/app` (port 8000, Postgres `app-db`) and `services/auth` (port 8001, Postgres `auth-db`).
- **One shared package:** `libs/<name>`.
- **Frontend:** `frontend/`, holding `<BrandList />` and the SCSS tree.

**Data and migration.** The main app models industries, brands and reviews keyed by a unique `wp_id`. Ratings and review counts are derived from reviews. `manage.py import_wp` reads the already-loaded WP `db` with plain SQL. In parallel, the auth service's `import_wp_users` imports the 9 users with a custom `$wp$` hasher and maps roles administrator→editor, subscriber→reader.

**Tokens.** Auth signs short-lived asymmetric JWTs carrying a `roles` claim. The main app verifies them locally through the shared library, which holds only verification, the claim schema and the DRF auth/permission classes. Python 3.14-slim images use a uv workspace with one hashed `uv.lock`, building from the repo root with a strict `.dockerignore`. The library is built with hatchling.

**API.** DRF + django-filter serves `GET /api/brands/` (page-number pagination, repeatable `industry`, whitelisted `ordering` with a tie-break) and an editor-only `PATCH`.

**Frontend build.** `<BrandList />` is a Vite library bundle built in a Docker `node:24-alpine` stage with `npm ci` and served by Django from the same origin. Its URL query is the source of truth. The SCSS tree compiles to the reference CSS structure.

**Checks.** `make check` runs `lint` (ruff, ESLint, stylelint), `fmt-check` (ruff format, Prettier), `typecheck` (mypy strict on the lib and gradual on the services, `tsc`) and `test` through compose. CI job `check` runs `make check`. There are no host pre-commit hooks.

The pieces fit because each boundary is small and explainable (P7). Auth outage affects only login and refresh. The library is the only code the services share. The frontend talks only to the public API.

| Topic | Recommendation | Serves | Costs |
|---|---|---|---|
| 1. WP data | Derive rating/count; promote 5 meta fields to columns; reviewer = opaque id + denormalized name/location; `wp_id` unique | C2, C3, C4, P7, P8 | Visual parity with the WP site's ACF ratings |
| 2. Migration | `import_wp` reads live `db` via SQL; auth imports users; upsert on `wp_id`; soft-delete unseen | C1, C2, C4, P7, P8 | P10 (one DB driver); runtime dependency on `db` |
| 3. Backend/API | Django + DRF + django-filter; annotated aggregates; page-number pagination; top review = highest rating then newest | C3, C4, P7, P8, P9 | P10 (two deps, serializer boilerplate) |
| 4. Auth | Asymmetric JWT, 5–10 min TTL, local verify, revocable refresh, `roles` claim, `$wp$` hasher | C4, C5, P7, P8 | Instant revocation (waits for TTL); P10 (hand-rolled login/refresh) |
| 5. Shared lib | src layout, PyJWT only, `drf` extra, `additional_contexts` path install, expand/contract with `v` claim | C1, C5, P7, P8 | P10 (a few compose lines; one unverified build feature) |
| 6. Frontend | Vite lib build in Docker; URL-state hook with fetch; single-select default; 7-1-lite SCSS with tokens | C1, P7, P8, P9, P10 | Clean diff vs reference (documented deltas) |
| 7. Repo/infra | Monorepo; two Postgres containers; `make check` via compose; CI `check` | C1, C4, C6, P8 | P10 (image build time in CI) |
| 9. Runtimes/packaging | Python 3.14-slim; uv workspace + hatchling; `psycopg[binary]` + PyMySQL; Node 24-alpine; npm `ci`; multi-stage non-root images; Dependabot | C1, P7, P8 | P10 (uv + root-context rework); P7 (explaining uv) |
| 8. Tooling | ruff; mypy + stubs (strict lib, gradual services); TS + ESLint 9 + jsx-a11y + Prettier; optional stylelint; `lint`/`fmt-check`/`typecheck` targets | C1, C5, P7, P8 | P10 (stubs + ~8 frontend packages) |

### Tensions
| Between | Where it bites | Options | Recommended resolution | What would flip it |
|---|---|---|---|---|
| P8 vs P10 | Migration source: live DB read needs a MariaDB driver and the `db` service; dump parsing needs a risky tokenizer | DB read / dump parse | DB read: less risky code, mirrors a real cutover | A rule that the migration must not depend on the running `db` |
| P8/C4 vs instant revocation | A role change or revoked user keeps access for one access TTL | JWT + TTL / introspection / `jti` denylist | JWT with 5–10 min TTL; name the denylist as the upgrade path | A requirement for instant revocation (would favour introspection) |
| P8 vs P10 | Keeping demo logins means bespoke `$wp$` hasher code | Custom hasher / forced reset | Hasher, pinned by test vectors from the dump (reset is out of scope, so nobody could log in) | Dropping the need to log in as migrated users |
| P7 vs P8 | Django version: LTS is the conservative shipping story, 6.1 is current | 5.2 LTS / 6.1 | 5.2 LTS leaned; both are compatible | Preferring "latest" over support window |
| P8 vs P10 | Frontend build in a Docker stage makes images slower and needs cache busting | Docker stage / committed bundle | Docker stage + manifest or hashed name | CI time becoming a problem |
| P8 vs WP parity | Derived ratings differ from what the WP site shows for 4 of 5 brands | Derived / ACF / both | Derived, document the discrepancy; optionally keep `legacy_average_rating` | A requirement to match WP output |
| P9 vs P10 | Multi-select industry filter needs repeatable params and more a11y work | Single / multi | API repeatable from day one (cheap in django-filter); UI choice open | Time pressure on the frontend |
| P8 vs P10 | Typing and lint toolchain: stubs and ~8 frontend packages with version pins (mypy <2.4, TS ~6.0, ESLint 9) | Full toolchain / ruff + tsc only | Full toolchain, pins recorded; drop stylelint first if time is short | Time pressure (P10 raised) |
| P7 vs P8/P10 | Python packaging: uv's single hashed lock and speed vs pip's familiarity; uv forces a repo-root context | uv workspace + root context / pip-compile + `additional_contexts` | uv + root context with strict `.dockerignore` (topic 9) | User prefers pip for explainability, or `.dockerignore` proves leaky |
| P8 vs P10 | Node 24 (Maintenance LTS, to 2028-04) vs Node 26 (LTS from 2026-10-28, longer window) | 24 / 26 | 24, the conservative choice | Preferring the longer window over a two-day-old LTS |

### If priorities change
- **P10 raised to high:** keep uv (it is also the fastest); parse the dump instead of reading `db` only if the driver dependency proves painful. Use simplejwt for login/refresh. Commit the built bundle instead of a Docker stage. Use a single-select-only API filter.
- **P8 lowered:** drop stylelint and mypy on the services (keep it strict on the lib), and the soft-delete pass (upsert only), the `kid`/rotation story, axe tests and the selector-diff script.
- **P9 raised to high:** add a JWKS endpoint (key rotation without redeploy) and the `Source` interface in the importer from day one. Keep the API filter repeatable.
- **P7 lowered:** consider Django Ninja for typed schemas and OpenAPI.

## Agenda

| # | Topic | Decisions it informs | Status |
|---|---|---|---|
| 1 | WP source data shape | Schema, postmeta strategy, rating source, reviewer model (decisions 1–2) | done |
| 2 | Migration approach | Source, idempotency, deletions, 100x (decision 3) | done |
| 3 | Django backend + API | Stack, API contract, top review, pages, PATCH (decision 4) | done |
| 4 | Auth service + tokens | Token format, verification, revocation, outage, user import (decision 7) | done |
| 5 | Shared library | Contents, packaging, pinning, breaking changes (decision 8) | done |
| 6 | React `<BrandList />` + SCSS | Build, state/URL sync, a11y, SCSS structure (decisions 5–6) | done |
| 7 | Repo, infra, CI | Layout, compose, DB engine, `make check`, CI, delivery remote | done |
| 8 | Code-quality tooling | Linters, formatters, type checkers, how they run in `make check` (added by follow-up) | done |
| 9 | Runtimes and package managers | Python/Node versions, uv vs pip, npm vs bun/pnpm, drivers, image strategy (added by follow-up) | done |

## Reconciliations

- **Em-dash count.** The previous pass said 17 reviews; topic 1 said 14. Checked: `grep '^INSERT INTO \`wp_posts\`' db/dump.sql | grep "'review'" | grep -c '—'` → 15, and 17 across all posts. Neither held exactly: 15 reviews, 17 posts.
- **Rating range.** Topic 3 said ratings run 2–5; topic 1 said 1–5. Checked: `grep -o ",'rating','[0-9]'" db/dump.sql | sort | uniq -c` → 1×1, 13×2, 14×3, 13×4, 19×5. Topic 1 held.
- **WP hash verification.** Topic 1 noted only admin had been tested earlier. Topic 4 re-ran the check on all 9 rows: admin matched `admin`, the other 8 matched `changeme`. Topic 4 held.
- **Remote.** The previous pass said origin was the read-only upstream. Topic 7 re-checked: origin is `michaelwayman/ck-dryrun` (private, ADMIN, Actions enabled). The previous pass was wrong.
- **ACF vs review mean.** Topic 3 didn't compute it; topic 1 did (4 of 5 brands differ). Topic 1 is the source.
- **"~30 fields per brand"** (`CHALLENGE.md:105`). Wrong for this dump: 10 keys per brand. Topic 1.

## 1. WP source data shape

### Findings
- **`wp_posts` has 71 rows.** By type: 60 review/publish, 5 brand/publish, 4 page/publish, 1 page/draft (`privacy-policy`), 1 post/publish (`hello-world`). There are no draft or trashed brands or reviews. Evidence: a throwaway tokenizer parse of `db/dump.sql` → `Counter({('review','publish'):60,('brand','publish'):5,('page','publish'):4,('post','publish'):1,('page','draft'):1})`.
- **Other table counts.** 532 `wp_postmeta`, 9 `wp_users`, 135 `wp_usermeta`, 6 `wp_terms`, 6 `wp_term_relationships`, and 1 stock `wp_comments` row (ignore it). Evidence: parser output.
- **Brands have 10 postmeta keys, not ~30.** The brief's "~30 fields per brand" (`CHALLENGE.md:105`) is wrong for this dump. The 10 are:
  - 4 data keys: `website_url`, `founded_year`, `headquarters`, `average_rating`
  - 4 ACF `_` twins that carry no data
  - 2 Yoast keys: `_yoast_wpseo_title`, `_yoast_wpseo_metadesc`

  Evidence: key histogram; `db/dump.sql:338-339`.
- **Reviews have 8 postmeta keys.** `rating`, `reviewer_name`, `reviewer_location` and `brand`, plus a `_` twin for each. All values are scalar; nothing is serialized. Evidence: histogram; `wp-content/mu-plugins/acf-fields.php:25-112`.
- **The ACF `average_rating` disagrees with the review mean for 4 of 5 brands.** Every brand has exactly 12 reviews. Review ratings run 1–5, distributed 1×1, 13×2, 14×3, 13×4, 19×5. Evidence: script output; `grep -o ",'rating','[0-9]'" | uniq -c`.

  | Brand | ACF | Review mean |
  |---|---|---|
  | Acme | 4.2 | 3.92 |
  | PrimePath | 4.0 | 3.83 |
  | HomeShield | 3.9 | 3.08 |
  | SwiftStream | 3.5 | 3.50 |
  | UrbanRetail | 4.4 | 3.67 |
- **The WP theme displays and sorts by the ACF value.** Evidence: `front-page.php:22,27`; `single-brand.php:6`; `archive-brand.php:16`.
- **Review → brand.** The `brand` meta holds the brand's post ID as a string (ACF `post_object`, `return_format => 'id'`). All 60 reviews resolve to a real brand. Evidence: `acf-fields.php`; parsed join.
- **Review → user.** `post_author` (users 2–9) maps 1:1 to `reviewer_name`, which equals the user's `display_name`, with 0 mismatches. Each user has 5–10 reviews. Admin (user 1) wrote none. `reviewer_location` is free text per review with 18 distinct values. Evidence: parsed join.
- **Industry taxonomy.** Flat (`hierarchical => false`), 5 terms plus the default "Uncategorized", no termmeta. Each brand has exactly one industry: Acme→Insurance, PrimePath→Finance, HomeShield→Home Services, SwiftStream→Telecom, UrbanRetail→Retail. Reviews carry no terms. Evidence: `cpt.php:46-52`; relationships `(7,2) (8,5) (9,4) (10,3) (11,6)`.
- **Slugs.** `post_name` is unique across all 71 rows. Some slugs are not plain slugified titles, so copy them verbatim. Permalinks are `/brand/<slug>/` and `/review/<slug>/`, and pages use `/%postname%/`. The front page is page 4 (`home`). Evidence: `cpt.php:25,43`; `wp_options.permalink_structure`; `scripts/seed.sh`.
- **Content.** Content is HTML (`<p>`), utf8mb4, and uses `\'` and `''` escapes. Brand `post_excerpt` is empty, so the short description has to be derived. All `post_date` values fall on 2026-05-19, seconds apart, so "recent" is effectively ID order. 15 review rows and 17 post rows contain an em dash (see Reconciliations). Only 3 lines contain an HTML entity. Evidence: parse; `grep -c '—'`; `grep -c "&amp;\|&#"` → 3.
- **Users.** 9 rows, all with `$wp$2y$10$…` hashes. Roles live in `wp_usermeta.wp_capabilities` as serialized PHP: admin is `administrator`, users 2–9 are `subscriber`. There is no editor. Evidence: parsed `wp_users`/`wp_usermeta`; `scripts/seed.sh`.
- **Dump format.** `--skip-extended-insert`, one INSERT per row, no column lists. Column order is defined only in `CREATE TABLE` (`wp_posts` at `db/dump.sql:872`).

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C2 | Every entity has a stable WP integer ID, so a unique `wp_id` makes a trivial upsert key | IDs; unique `post_name` |
| C3 | Copy `post_name` verbatim with a unique constraint | `cpt.php:25,43` |
| C4 | The reviewer is identified by a reference into auth, never by a main-app user with a password or role | usermeta; `CHALLENGE.md:81-83` |
| P7 | A derived average is a one-line aggregate. The stored ACF value is wrong for 4 of 5 brands | table above |
| P8 | Denormalized reviewer name and location fit a review as a point-in-time record. An unused ACF column is a stale-data hazard | ACF vs mean |
| P9/P10 | Few scalar fields, no JSON, a flat taxonomy: minimal mapping | histogram |

### Recommendation
- Treat reviews as the source of truth: derive average rating and review count. Either drop the ACF `average_rating` or import it as a documented, unused `legacy_average_rating`.
- Promote `website_url`, `founded_year`, `headquarters`, `seo_title` and `seo_description` to columns. Drop the `_` twins. No JSON.
- Model the reviewer as an opaque `reviewer_id` (the WP user ID, resolvable in auth) plus denormalized `reviewer_name` and `reviewer_location` on the review.
- Add a unique `wp_id` on industry, brand and review.
- This serves C2, C3, C4, P7 and P8. The cost is that ratings no longer match the WP cards.

### Options considered
| Option | For | Against |
|---|---|---|
| Derive average/count | Correct; trivial query | Differs from WP display for 4/5 brands |
| Store ACF only | Matches WP | Wrong vs data; stale on new reviews |
| Both (derived canonical, ACF `legacy_*`) | Discrepancy explainable live | Extra column nobody should read |
| Reviewer as main-app Django user | Familiar | Violates C4 |
| Reviewer id + denormalized name/location | Fits C4; review is a snapshot | Name can go stale |
| Separate Reviewer table | Normalized | Identity lives in auth anyway |
| Data/SEO meta → columns | Simple, queryable | Keeping Yoast is arguable |
| All meta as JSON | One generic column | Loses constraints |

### Risks
- A rating that differs from the legacy site looks like a bug unless the README explains it.
- A naive SQL splitter corrupts `\'`, `''` and utf8mb4 characters.
- Apart from admin, the source has no privileged user, so the protected-write demo needs one assigned.
- `reviewer_name == display_name` holds only for this dataset.
- Review dates are effectively identical. Order by date then ID, and say so.

### Open questions
- ACF `average_rating`: drop it, keep it as `legacy_average_rating`, or display it?
- Which user becomes `editor`?
- Keep `reviewer_location` and the Yoast fields as columns?
- What becomes the brand "short description" (truncated stripped content, or the first paragraph)?

### Follow-ups

## 2. Migration approach

### Findings
- **Dump format.** One `INSERT` per row, no column lists; column order comes only from `CREATE TABLE`. Evidence: `db/dump.sql:1323`; `grep -c "^INSERT INTO \`wp_posts\`"` → 71; `Makefile` `dump` uses `--skip-extended-insert`.
- **Parsing the dump needs a SQL-literal tokenizer.** Values contain `\'`/`\"` escapes, and serialized PHP appears in `wp_options` and `wp_usermeta.wp_capabilities` (`db/dump.sql:1162`). The header shows MariaDB 11.8.6, utf8mb4 (`db/dump.sql:2-11`). Size is 240 KB.
- **Post statuses.** No trash or auto-draft rows (`grep -c "'trash'\|auto-draft"` → 0); the only draft is a page. Filtering on `post_status='publish'` still makes "unpublished in WP" behave like a deletion.
- **The `db` service holds the same data as the dump.**
  - It is seeded from `./db/dump.sql` via `docker-entrypoint-initdb.d`.
  - It has a healthcheck (5 s interval, 20 retries).
  - It has no host port: `db:3306` is reachable only from the compose network. Credentials are `wp`/`wp`.
  - The importer can use `depends_on: db: condition: service_healthy`.
  
  Evidence: `docker-compose.yml:2-23`.
- **`wordpress` has no healthcheck of its own.** A REST-based importer would need a retry loop. Evidence: `docker-compose.yml:21-23`.
- **REST is incomplete for this job.** It exposes CPTs and ACF (`show_in_rest`, `cpt.php:21,38,50`; `acf-fields.php:24-82`). Unauthenticated `/wp/v2/users` returns only public author fields: no emails, roles or hashes. `per_page` is capped at 100, and Yoast data is available only as `yoast_head_json`. These REST limits come from WP docs and were not called live.
- **Users decide the source.** Only the dump or a direct DB read exposes email, password hash and role (`db/dump.sql:1162-1282,1323-1331`).
- **Import order.** Reviews reference brands by WP ID as a string, so industries and brands must be imported first, and the importer needs a `wp_id → pk` map.
- **`bulk_create(update_conflicts=True)`** (Django 5.2 docs):
  - It does not reliably return pks for upserted rows, so query the `wp_id → pk` map afterwards.
  - It is supported on all backends except Oracle.
  - `unique_fields` is required on PostgreSQL and SQLite; MySQL/MariaDB behaviour is not stated.
  - `iterator()` defaults to `chunk_size=2000`.
  
  Evidence: https://docs.djangoproject.com/en/5.2/ref/models/querysets/#bulk-create.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | Both the dump parser and the DB read run in a Django container. REST needs `wordpress` up, which has no healthcheck. wp-cli needs the `tools` profile. | `docker-compose.yml` |
| C2 | Every option works with a unique `wp_id` plus upsert. Deletions need a "seen" pass. | Django docs |
| C4 | Only a DB or dump read can provide hashes, emails and roles. REST can't. | `db/dump.sql:1323-1331` |
| P7 | "The dump is already loaded in `db`; I read it with plain SQL" is the simplest story. A hand-written tokenizer is the hardest to defend. | - |
| P8 | A DB read with keyset batches and a read-only user mirrors a real cutover. | - |
| P9 | A `Source` interface makes a new entity a new query. | - |
| P10 | The DB read costs one driver dependency. The dump parser needs about 100 lines of risky tokenizer. | - |

### Recommendation
Build `manage.py import_wp` in the main app. It reads the live `db` service with plain SQL through a thin source layer, runs in the app container after `db` reports healthy, and is exposed as `make migrate`.

The auth service gets its own `import_wp_users`, which reads `wp_users` and `wp_capabilities`. That keeps emails, hashes and roles out of the main app (C4).

Import rules:
- **Upsert key:** a unique `wp_id` on every row. Slugs stay unique separately for C3.
- **Order:** industries, then brands, then reviews, in one `transaction.atomic()`.
- **Meta:** an allow-list of keys, fetched with `post_id IN (…)` per batch.
- **Deletions:** soft-delete rows not seen in the run, by setting `is_active=False` or a `last_seen_run` marker. Abort if the source returns zero brands. Print created / updated / deactivated counts.

Scaling to 100x:
- keyset-paginate the source on ID;
- batch the meta fetches;
- use `bulk_create(update_conflicts=True, unique_fields=['wp_id'])` in batches of a few thousand;
- deactivate through a run marker rather than a huge IN list;
- add a `post_modified_gmt` watermark for incremental runs.

All of this is designed but not benchmarked. With 60 rows the simple per-row loop is just as correct.

This serves P7, P8 and C4, and costs a little P10 (one driver dependency). It would flip to parsing the dump only if no runtime `db` dependency is allowed.

### Options considered
| Option | For | Against |
|---|---|---|
| Parse `db/dump.sql` | No services at runtime; deterministic | Tokenizer for escapes and positional columns; snapshot only |
| Direct MariaDB read | Full data including users; SQL joins; keyset paging; same data as the dump | Needs `db` healthy; a driver dependency; coupled to WP's table layout |
| WP REST | Official shapes; ACF resolved; incremental | No emails, roles or hashes; 100 cap; needs `wordpress` up |
| wp-cli | Deserializes PHP | Separate container; awkward from Django |
| Hybrid (REST content + SQL users) | Matches the brief's hints | Two code paths to defend |

### Risks
- A hard delete of "not seen" rows would wipe content after a bad source query. Use soft delete plus the zero-rows guard.
- If the Django DB were MariaDB, the upsert key behaviour is unverified, which favours Postgres (topic 7).
- The importer can race `db` at startup. Use the healthcheck plus a retry.
- Importing the `_` ACF twins by mistake. The allow-list prevents it.
- `make reset` wipes every volume, so the importer must work against an empty DB.
- The default `wp` DB user can write. Consider a read-only user for the importer.

### Open questions
- Must the migration work from `db/dump.sql` alone, or is reading the live `db` service OK? This is the one answer that would flip the recommendation.
- Soft-delete rows missing from WP, or upsert only?
- Postgres or MariaDB for the Django DBs? It affects the `update_conflicts` behaviour.

### Follow-ups

## 3. Django backend + REST API

### Findings
- **Versions.** From PyPI JSON, fetched 2026-10-26:

  | Package | Version | Requires Python | Released |
  |---|---|---|---|
  | Django | 6.1.2 | ≥3.12 | 2026-10-06 |
  | Django (5.2 line) | 5.2.18 | | 2026-10-06 |
  | DRF | 3.18.3 | | |
  | django-filter | 26.2 | ≥3.11 | |
  | django-ninja | 1.7.1 | | |

  DRF and django-filter carry classifiers for Django 5.2, 6.0 and 6.1. The 5.2 "LTS" label comes from the release-line convention; the support end date was not fetched. Evidence: https://pypi.org/pypi/{django,djangorestframework,django-filter,django-ninja}/json.
- **Data size.** 5 brands, 60 reviews, integer ratings 2–5. Performance does not decide anything here. Evidence: `grep` counts on `db/dump.sql` (e.g. line 336 `(9,7,'average_rating','4.2')`).
- **Permalinks.** CPT slugs are `brand` and `review`, and the taxonomy slug is `industry`. Both CPTs have `has_archive`. Evidence: `wp-content/mu-plugins/cpt.php:24-25,41-42,51`.
- **Home** (`front-page.php:1-76`):
  - Hero h1 "Honest reviews of consumer brands".
  - "Featured Brands": 6 brands by stored `average_rating` desc. Each card has the industry badge (first term), title link, stars with value, HQ, and a 22-word excerpt.
  - "Recent Reviews": 6 reviews by date desc. Each has the brand link, title link, stars, a 24-word excerpt, and "— name, location".
- **Brand detail** (`single-brand.php:1-61`):
  - Hero: badge, h1, stars, "(N review(s))", and a meta block with HQ, Founded, and Website. The website link is host only, with `rel="nofollow noopener" target="_blank"`.
  - Then the content.
  - Then "Customer Reviews" by date desc. Each review has a title link, stars, a byline "name, location · M j, Y", and the body via `wp_kses_post(wpautop())`.
  - Empty state: "No reviews yet."
- **Review detail** (`single-review.php:1-32`): back link "← Brand", h1, stars, a byline "name, location · F j, Y · Posted by <author>", then the content.
- **Other pages.** `/brand/` and `/review/` archives are card grids with `paginate_links()`. The nav is Home / Brands / Reviews / About (`/about/` is a WP page), and there is a 404 template. Evidence: `archive-*.php`, `header.php:11-16`, `404.php`.
- **Stars.** The rating is clamped to 0–5, full stars are `floor()`, with `aria-label="Rating: X.X out of 5"` and ★/☆ glyphs. The theme displays the ACF rating. Evidence: `functions.php:27-39`; `single-brand.php:8,19`.
- **Industry.** Only the first term is used (`cr_brand_industry` returns `$terms[0]`), so a single FK fits. Evidence: `functions.php:65-70`.
- **HTML in content.** The dump contains no `<script>`, `onerror` or `<iframe>` (`grep -c` → 0). The theme still runs bodies through `wp_kses_post`, so the Django side needs equivalent sanitizing.
- **Auth classes.** Pillar 6 names "a DRF authentication class and permission class, or a decorator for plain views". Evidence: `CHALLENGE.md:95-97`.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | All pip-only. Django 6.1 needs a Python ≥3.12 image. | PyPI |
| C3 | `/brand/<slug>/` and `/review/<slug>/` with a unique slug; archives at `/brand/` and `/review/`. | `cpt.php` |
| C4/C5 | DRF matches the brief's wording. With Ninja or plain views the shared lib is less natural. | `CHALLENGE.md:95` |
| P7 | DRF + django-filter is the most common stack and the easiest to defend. Plain views mean hand-rolled validation. | - |
| P8 | DRF gives validation, permission classes, throttling, a browsable API, and optional OpenAPI. | - |
| P9 | A new filter or field is about one line in a FilterSet or serializer. | - |
| P10 | DRF adds 2 dependencies. Plain views add none but need about 100 more lines. | - |

### Recommendation
Use Django + DRF + django-filter. Django 5.2 LTS and 6.1 both work with the stack; the researcher leans toward 5.2 LTS as the shipping story. Compute `average_rating` and `review_count` by annotation (subqueries, or `Count(distinct=True)`), and do not store them.

**`GET /api/brands/` contract:**
- **Pagination:** `PageNumberPagination` with `?page=` and `?page_size=` (max 50). The response body is `{count,next,previous,results}`.
- **Industry filter:** `?industry=<slug>`, repeatable, via `ModelMultipleChoiceFilter`. An unknown slug returns 400.
- **Ordering:** `?ordering=`, whitelisted to `average_rating`, `review_count` and `name` (± each). Ties always break on `name` then `pk`. A null average sorts last.
- **Fields:** name, slug, industry `{slug,name}`, average_rating (1 dp or null), review_count, short_description, top_review `{title,slug,rating,snippet}` or null.
- **Top review:** highest rating, then newest, then pk. The snippet is plain text of about 22 words, stripped server-side.

**Pages:** home, brand detail and review detail are required. Add the brand and review archives (cheap, because the cards are reused) and a 404 page. Skip `/about/`.

**Stored HTML:** sanitize with an allowlist (`nh3`, approximating `wp_kses_post`) at import or at render, and mark it safe only after that.

**`PATCH /api/brands/<slug>/`:** a separate view with a write serializer limited to `short_description`, using the auth and permission classes from the shared lib. The list stays public.

### Options considered
| Option | For | Against |
|---|---|---|
| DRF + django-filter | Brief's idiom; browsable API; filters/ordering built in | Serializer boilerplate |
| Django Ninja 1.7.1 | Typed, auto OpenAPI | Not the brief's idiom; shared lib needs a Ninja variant |
| Plain JSON views | No deps | Hand-rolled pagination/filter/validation |
| Page-number pagination | Simple; `count`; matches page links | Offset drift at scale |
| Cursor pagination | Stable for mobile | Awkward with aggregate ordering; no count |
| Annotate aggregates | Always correct | Query cost at scale (irrelevant here) |
| Stored aggregates | Cheap reads | Staleness; sync logic |
| Django 5.2 LTS | Long support; Python 3.10+ | Not current |
| Django 6.1 | Current | Python ≥3.12; shorter support |

### Risks
- Aggregate ordering without a unique tie-break skips or duplicates rows across pages. Test by paging through the whole listing.
- `Avg`/`Count` across joins can inflate results. Use subqueries or `distinct`, and test filter + sort together.
- The ACF average and the computed average differ. The API and README must say which one is served.
- Rendering HTML with `|safe` without sanitizing it is an XSS risk.
- Rounding (1 dp) and `floor()` stars must stay consistent.
- The seed has no brand without reviews, so the null and empty cases need tests.

### Open questions
- Django 5.2 LTS or 6.1?
- Top review = highest rating then newest, newest only, or longest?
- Display the computed or the ACF average?
- Build archives/About or only the three required pages?
- Sanitize at import or at render?

### Follow-ups

## 4. Auth service + tokens

### Findings
- The brief asks for:
  - a separate Django project with its own DB;
  - no passwords or roles stored in the main app;
  - a login endpoint that returns a token, format chosen freely;
  - at least two roles;
  - one write endpoint restricted to editors;
  - a documented choice between local and remote token verification.

  Live probe 7 covers outage and revocation. Registration, password reset, MFA and a login UI are out of scope. Evidence: `CHALLENGE.md:81-89,110`, out-of-scope list.
- **WP password hashes are verifiable.** The scheme is `$wp` + bcrypt(base64(HMAC-SHA384(key="wp-sha384", password))). Tested in a scratch venv outside the repo (bcrypt 5.0.0) against all 9 `$wp$` rows in `db/dump.sql:1323-1331`: admin matches `admin`, and the other 8 users each match `changeme`. Seed passwords are at `scripts/seed.sh:11,55`.
- **What the official sources confirm.** WordPress's announcement confirms the `$wp$2y$` prefix and the SHA-384 pre-hash, and says legacy `$P$` hashes are still accepted and rehashed on login. It does not state the HMAC key; that key is confirmed only by the test above. The dump contains no `$P$` rows. Evidence: https://make.wordpress.org/core/2025/02/17/wordpress-6-8-will-use-bcrypt-for-password-hashing/ (Feb 2025).
- **Roles in the source data.** User 1 is `administrator`; the other 8 are `subscriber`. A WP "editor" role is defined but nobody holds it. Evidence: `db/dump.sql:1162,259`; `scripts/seed.sh:53`.
- **Import key.** `wp_users.user_login` is unique and works as a stable import key. The table also has `user_email`, `display_name` and `user_registered`. Evidence: `db/dump.sql:1298-1325`.
- **Library versions** (PyPI, 2026-10-26): PyJWT 2.15.1, djangorestframework-simplejwt 5.5.1, django-oauth-toolkit 3.4.1, cryptography 50.0.2, bcrypt 5.0.0.
- **Library fit:**
  - PyJWT pins algorithms, can require specific claims, has `PyJWKClient`, and does not depend on Django.
  - simplejwt's verifier is tied to Django and DRF.
  - oauth-toolkit implements full OAuth2.

  The PyJWT details are from known API and were not re-read this pass.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C2 | Upsert users on `user_login`. Set password and role only on create, so re-runs don't clobber changes. | `db/dump.sql:1298` |
| C4 | Roles travel as a claim, so the main app never holds a role table. | `CHALLENGE.md:81-83` |
| C5 | The lib holds claim validation and a role check. Login, refresh and the hasher stay in auth. | `CHALLENGE.md:93-98` |
| P7 | Asymmetric JWT with local verification is the standard answer. Introspection is simple but adds a runtime dependency. HS256 lets the main app forge editor tokens. | design |
| P8 | Alg pinning, required claims, `kid`, revocable refresh, re-hash on login. | - |
| P9 | A `roles` claim plus `require_role()` makes a new role or endpoint a small change. | - |
| P10 | Hand-rolled login/refresh on DRF + PyJWT is smaller than simplejwt plus verifier glue, and much smaller than oauth-toolkit. | - |

### Recommendation
Use a short-lived asymmetric JWT access token (5–10 min), signed with EdDSA or RS256 and the algorithm pinned in the lib.
- **Verification.** The main app verifies tokens locally with the public key, provided via env with a `kid` header. A JWKS endpoint is an optional extra.
- **Required claims.** `exp`, `iss`, `aud` (specific to the main app) and `sub`, with about 30 s leeway. Reject `none`.
- **Refresh.** A DB-backed refresh token that can be revoked.
- **Roles.** A `roles` claim. Map subscriber → reader and administrator → editor.
- **WP passwords.** Import `wp_users` with a custom `$wp$` hasher and re-hash to Django's default on first login.
- **Auth service down.** Existing access tokens keep working; login and refresh return 503.
- **Role change or revocation.** Takes effect within the access TTL, because refresh re-reads roles. A `jti` denylist is the upgrade path, at the cost of a runtime dependency.

### Options considered
| Option | For | Against |
|---|---|---|
| HS256 shared secret | Simplest | Main app could mint editor tokens |
| Asymmetric JWT + local verify | Works when auth is down; main app holds only a public key | Role change/revocation wait for TTL |
| Opaque + introspection | Instant revocation | Every write depends on auth |
| Session cookie | Built in | Needs a shared session store; no real boundary |
| `jti` denylist | Near-instant revoke | Runtime dependency again |
| Custom `$wp$` hasher | Demo logins keep working | Bespoke; needs test vectors |
| Force reset | No legacy code | Reset is out of scope, so nobody could log in |
| simplejwt | Ready login/refresh | Django-bound verifier |
| oauth-toolkit | Full OAuth2 | Overkill |

### Risks
- The HMAC key is not in the official post. Pin the dump rows as test vectors.
- Normalise PHP's `$2y$` to `$2b$` before calling Python bcrypt. Keep the 64-char pre-hash, which stays under bcrypt's 72-byte limit.
- Key rotation needs a `kid` and a cache policy.
- A claim-schema change affects both services (see topic 5).
- Clock skew needs leeway.
- Never commit private keys. Generate them on first start or load from `.env`.

### Open questions
- Is admin the only editor, or should a reviewer be promoted for the demo?
- Migrate hashes or force a reset? (Migrate is recommended.)
- Access TTL: 5, 10 or 15 min?
- When the auth service is down, is it acceptable that writes still work with valid tokens until they expire?
- JWKS endpoint, or public key in env?

### Follow-ups

## 5. Shared library

### Findings
- **Brief requirements.** A separate package with its own `pyproject.toml` and version number, installed into both services by path, git URL or private index. It must hold the token verification and permission code. Its tests run without either Django project. It stays small and every module must be justifiable. Decision 8 asks about pinning, upgrades, and how to ship a breaking change without deploying both services at once. Evidence: `CHALLENGE.md:93-98`, decision 8.
- **No container setup yet.** The repo has no `.dockerignore` and no Dockerfiles. Compose runs only WordPress, MariaDB, wpcli and phpMyAdmin. Evidence: `ls -a`; `docker-compose.yml`.
- **A repo-root build context would be heavy.** `du -sh db wp-content` → 236K and 46M.
- **Build contexts in Compose.** `context` resolves relative to the project directory. `additional_contexts` accepts a path or a git URL. Evidence: https://docs.docker.com/reference/compose-file/build/ (2026-10-26). Two things are unverified: the matching Dockerfile syntax (`COPY --from=<name>`), and whether a named context honours its own `.dockerignore`.
- **Where `.dockerignore` is read.** From the root of the build context; a `<Dockerfile>.dockerignore` file takes precedence. Evidence: https://docs.docker.com/build/concepts/context/.
- **Why a src layout.** Tests then run against the installed package, the working directory can't shadow it, and missing files show up as failures. Evidence: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ (2026-10-26).
- **Install mode.** A non-editable `pip install` copies the library into site-packages, so the image is self-contained. Editable installs can hide packaging bugs. The editable claim rests on the src-layout page; the rest is general knowledge.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | A path install via `additional_contexts` works with plain `docker compose build`. A git URL needs network access and a tag. A private index needs infrastructure. | Compose docs |
| C4 | Only verification code, claim constants and permission logic are shared. | `CHALLENGE.md:81-83` |
| C5 | The core imports only PyJWT. DRF code sits behind a `drf` extra. Tests install `.[test]` and need no Django settings. | `CHALLENGE.md:93-98` |
| P7 | A path install plus a version range is easy to explain. Git URL or an index can be described as the production path. | - |
| P8 | Non-editable install, src layout, a contract test, and the library's tests in CI. | PyPA |
| P10 | About 10 Dockerfile lines per service and a ~15-line `pyproject.toml`. | - |

### Recommendation
- **Layout.** `libs/<name>/` in src layout, with a static version and setuptools or hatchling as the build backend.
- **Dependencies.** PyJWT (with cryptography) is the only hard dependency. Extras: `drf` for the authentication and permission classes, and `test`.
- **Docker install.** Each service builds with its own directory as the context plus `additional_contexts: {lib: ./libs/<name>}`, then runs a non-editable `pip install "/tmp/lib[drf]"`. This keeps `wp-content` and `db` out of every build.
- **Fallback.** Use the repo root as the context with a `.dockerignore` excluding `wp-content`, `db`, `reference`, `.git` and `docs`.
- **What the library shares.** Token decode/verify, the claim schema with a `v` claim, role constants, and the DRF auth and permission classes.
- **What stays out.** Users, login, refresh, signing keys and the WP hasher.
- **Auth service use.** It imports the library only for claim constants and the schema. Its contract test mints a token and verifies it with the library.

**Pinning and breaking changes.**
1. Each service pins `>=X,<X+1`, and breaking changes bump the major version.
2. Release a version that accepts both the old and the new claim shape.
3. Deploy it to the main app, then switch auth to mint the new shape.
4. Drop the old shape once one access-token TTL has passed.

### Options considered
| Option | For | Against |
|---|---|---|
| Path install via `additional_contexts` | Small contexts; lib change and pins in one PR | `COPY --from` / ignore behaviour unverified |
| Repo-root context + `.dockerignore` | One simple `COPY` | Must exclude about 46M; a slip slows builds |
| Git URL pin | Explicit tag | Network and tag; awkward in a monorepo |
| Private index | Real semver | Overkill; describe as the production path |
| Vendored copy | None | Contradicts the brief |

### Risks
- The `additional_contexts` name must match the `COPY --from` target. Check this with one build.
- Scope creep.
- Editable installs in dev hide packaging bugs. CI should test a regular install.
- Algorithm pinning, required claims and `kid` all live here.
- Version drift between the two services. The contract test and CI catch it.

### Open questions
- Should the auth service import the library for constants and schema? (Recommended.)
- Package name?

### Follow-ups

**Recommendation updated (2026-10-26, from topic 9):** was a per-service build context plus `additional_contexts` with a non-editable `pip install "/tmp/lib[drf]"`. Now: a uv workspace with one root `uv.lock`, a repo-root build context, a strict `.dockerignore`, and hatchling as the lib's build backend. Reason: a uv workspace lock needs the root and the lib inside the build context. The fallback, if uv is declined, is the original plan with pip-compile hashed locks.


## 6. React `<BrandList />` + SCSS

### Findings
- `reference/theme.css` is 329 lines. Its `:root` holds 15 custom properties (10 colours, radius, 2 shadows, max-width, font-sans), and there is one breakpoint, `max-width: 640px`. Evidence: `reference/theme.css:15-31,324-329`.
- Comment-marked sections map one-to-one to partials: Header (56), Hero (88), Sections (107), Cards grid (125), Stars (163), Industry badge (180), Brand single (193), Review single (263), Footer (282), Page (292), Pagination (305). Evidence: `grep -n '^/\*' reference/theme.css`.
- Literals the reference repeats or never tokenizes:
  - `#ffffff` appears 10 times even though `--color-card` exists.
  - Greys `#374151 #1f2937 #111827 #9ca3af` and badge colours `#ecfdf5 #d1fae5 #134e4a` are untokenized.
  - Spacing values (18/22/24/48px) are untokenized.
  Evidence: `grep -o '#[0-9a-f]\{3,6\}' reference/theme.css | sort | uniq -c`.
- Selectors are plain descendant selectors (`.card h3 a`, `.stars .star-full`, `.pagination .page-numbers.current`), not BEM. There is no `:focus-visible` and no reduced-motion rule; the only transition is on `.card`. Evidence: `reference/theme.css:138,156-178`.
- `scripts/extract-theme-css.sh` only copies the theme's `style.css` (header stripped). Nothing in the repo compiles SCSS, so the equivalence check has to be built. Evidence: `scripts/extract-theme-css.sh:20-52`.
- Card markup: `article.card > span.badge, h3>a, cr_stars() + span.meta (count), p.meta (HQ), p.excerpt (22 words)`. Evidence: `archive-brand.php:15-33`.
- Stars: `span.stars[aria-label="Rating: 4.5 out of 5"]` with ★/☆ glyphs and `span.rating-value`. Glyphs are floored (4.5 shows 4 full stars) while the label shows the decimal. An aria-label on a role-less span is unreliable for assistive tech. Evidence: `functions.php:24-37`.
- There is no `frontend/` and no Node service in compose, and the host has no `sass` CLI. Under C1, building has to happen in Docker. Evidence: `ls frontend`; `docker-compose.yml`.
- npm latest versions (registry.npmjs.org, 2026-10-26):
  - react 19.3.1, vite 8.3.5, @vitejs/plugin-react 6.1.2, sass 1.106.1
  - vitest 5.0.5, @testing-library/react 16.3.3, msw 3.0.3, jsdom 30.1.3
  - vitest-axe 0.1.0, the least mature of the set
- A multi-stage Docker build (a Node stage running `npm ci && vite build && sass`, then `COPY --from` into Django static) is the standard pattern. It has not been tried in this repo.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | A Docker build stage needs no host Node. A committed bundle also passes C1 but can go stale. A dev server needs a running Node container. | No Node service in compose |
| P7 | A fetch+AbortController hook, the URL query as state and one Vite build each take a sentence to explain. TanStack adds a dependency for a single endpoint. | `CHALLENGE.md:119-121` |
| P8 | Needs explicit loading/empty/error states with retry, aria-live, `:focus-visible`, reduced motion, axe tests, and CI running Vitest and the SCSS build. | `theme.css:138` |
| P9 | A tokens map, a partial per component and a breakpoint mixin mean a new feature is a new partial. A new URL-synced filter is about one line. | Reference sections |
| P10 | A single fixed-name bundle built in Docker has the fewest parts. Avoid a dev proxy, TanStack, Tailwind and CSS Modules. | - |

### Recommendation
**Build.** Vite library build to a single bundle plus `sass` to CSS, both in a Docker Node stage. Django serves them as static files and a template mounts `<BrandList />`. Build output is not committed.

**State and data.** The URL query string is the source of truth for industry, sort and page (read on mount and on `popstate`, written with `pushState`). Data comes from a `useBrandList` hook using fetch and AbortController.

**Industry filter.** Single-select by default; multi-select only if the API supports repeated params.

**States and accessibility.**
- Loading: `aria-busy` with a skeleton.
- Empty: a message with "clear filters".
- Error: `role="alert"` with Retry.
- Results count announced in a polite `aria-live` region.
- Labelled sort `<select>`, pager as `<nav>` with `aria-current`, stars as `role="img"`.

**SCSS.** "7-1-lite" layout under `frontend/scss/`: `abstracts/` (a tokens map emitting `:root`, a breakpoint mixin), `base/`, `layout/`, `components/`, `pages/`, `main.scss`. Reference class names are kept so the selector diff stays meaningful; new parts use a BEM `brand-list__*` block. Repeated literals become tokens. The focus and reduced-motion rules are documented as deltas from the reference.

**Verification.** A css-tree/postcss script diffs selector sets and custom properties against the reference.

**Tests.** Vitest, RTL, msw and an axe matcher, run in Docker.

### Options considered
| Option | For | Against |
|---|---|---|
| Vite lib build served by Django, built in Docker | One origin, no CORS, C1-clean | Slower image builds; cache busting |
| Committed bundle | No Node stage | Stale; noisy diffs |
| Vite dev server + proxy | HMR | Second origin; dev only |
| fetch + AbortController hook | About 30 lines; defensible | Hand-rolled retry and caching |
| TanStack Query / SWR | Cache, retry, dedupe | A dependency for one endpoint |
| Single-select industry | Simple URL and API | Less flexible |
| Multi-select industry | Flexible | Repeated params in the API; more a11y work |
| Reference class names + BEM for new parts | Clean equivalence diff | Mixed conventions to explain |
| CSS Modules / Tailwind / styled-components | Scoping, speed | Second paradigm; duplicates tokens; clashes with Pillar 4 |

### Risks
- A fixed bundle filename gets cached stale. Mitigations: Vite manifest, `?v=`, or `ManifestStaticFilesStorage`.
- API param names must be fixed before the URL-sync keys.
- The extra tokens and focus/motion rules mean the compiled CSS will not diff clean, so the deltas must be documented.
- jsdom axe cannot check contrast, so contrast needs a manual or browser check.
- The reference floors the stars but labels the decimal. Pick a rounding rule and make it match the API precision.

### Open questions
- Single or multi-select industry?
- Should `<BrandList />` replace a server-rendered brand grid, or mount as an island on one page?
- Accept the focus/reduced-motion rules and new tokens as documented deltas?
- Docker build stage only, or also a committed `dist/` fallback?

### Follow-ups

## 7. Repo, infra, CI

### Findings
- Remote: origin = `git@github.com:michaelwayman/ck-dryrun.git` (private, ADMIN); upstream = `ConsumerAffairs/ca-code-challenge` (READ). The previous pass was wrong about origin. Evidence: `git remote -v`; `gh repo view michaelwayman/ck-dryrun --json viewerPermission,visibility,isFork` → `{"isFork":false,"viewerPermission":"ADMIN","visibility":"PRIVATE"}`.
- GitHub Actions is enabled on origin. Evidence: `gh api repos/michaelwayman/ck-dryrun/actions/permissions` → `{"enabled":true,"allowed_actions":"all"}`. Plan minutes were not checked.
- The repo is WP-only: no `services/`, `libs/`, `frontend/` or `.github/`. Evidence: `git ls-files`.
- Compose services: `db` (mariadb:11, healthcheck), `wordpress` (8080), `wpcli` (profile `tools`), `phpmyadmin` (8081); volumes `db_data` and `wp_files`. Avoid those names and ports. WP must stay on 8080 because the dump hardcodes `localhost:8080` (carried over from the previous pass, not re-verified). Evidence: `docker-compose.yml`.
- Makefile: `.PHONY` lists `restart` but no rule exists; `up` starts only `db wordpress phpmyadmin`; `reset` runs `down -v`, which wipes every volume; there is no `check`/`lint`/`test`. Evidence: `Makefile:1-43`.
- `.gitignore` has no Python/Node entries. There is no `.dockerignore`. `.env.example` has only WP/MariaDB vars. Evidence: `cat .gitignore .env.example`.
- `.claude/settings.local.json` is tracked and holds another person's absolute paths. `.claude/settings.json` and `docs/` are untracked. Evidence: `git ls-files`; `git status --short`.
- Host tools (context only): Python 3.14.2, Node v26.7.0, Docker 29.9.2. The brief requires Docker only. Evidence: `--version`; `CHALLENGE.md:20`.
- The brief is silent on the DB engine. Auth needs "its own database" (`CHALLENGE.md:81-83`).

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | `make check` via `docker compose run`, called by CI, is Docker-only. Host-tool linting breaks C1. | `CHALLENGE.md:20` |
| C4 | Separate `auth-db` container is the clearest "own DB". Two DBs on one server also passes but is weaker to defend. | `CHALLENGE.md:81-83` |
| C5 | `libs/<name>` with its own pyproject; its pytest runs in a bare Python image. | `CHALLENGE.md:93-98` |
| P7 | Separate Postgres containers for both Django services tell one consistent story. | `docker-compose.yml` |
| P8 | CI job `check`, `.dockerignore`, `.gitignore`, healthchecks. | Actions enabled |
| P9 | Uniform `make` interface (`check`, `test-app`, `test-auth`, `test-lib`, `lint`). | `Makefile` |
| P10 | One extra Postgres image is cheap; two containers cost about the same as one. | - |

### Recommendation
Monorepo with `services/app`, `services/auth`, `libs/<shared>` and `frontend/`, delivered from origin. Add `app-db` and `auth-db` as separate `postgres:16` containers with `pg_isready` healthchecks, `app` on 8000 and `auth` on 8001. `make check` runs ruff and pytest per Python package plus frontend lint/test via `docker compose run --rm`, and CI job `check` runs `make check`. Pin base images (e.g. `python:3.12-slim`, `node:22-alpine`, `postgres:16`). Fix `up`/`restart`/`reset`, extend `.gitignore`, add `.dockerignore` (`.git`, `wp-content`, `db`, `node_modules`, `docs`), and extend `.env.example`. Untrack `.claude/settings.local.json`. Serves C1, C4, C5, P7, P8; costs a little P10 in image builds.

### Options considered
| Option | For | Against |
|---|---|---|
| Postgres, separate app-db and auth-db | Clear C4 story; Django default | Two more containers |
| Postgres, one server, two DBs | Fewer containers | Shared failure domain; weaker "own DB" claim |
| MariaDB reusing WP `db` | No new image | Couples auth DB to WP stack; `reset` and dump init affect it |
| MariaDB, new containers | Same engine as WP | No benefit over Postgres for Django |
| Monorepo with `libs/` | One `make check` and CI job | Docker build contexts must include `libs/` |
| Lib in separate repo | Real release flow | More setup; brief allows a directory |
| `make check` on host | Fast | Breaks C1 |
| `make check` via compose | Same locally and in CI | Slower image builds |

### Risks
- `make reset` wipes the new DB volumes; migrated data and auth users must be recreatable with one command.
- A repo-root build context ships `wp-content` and `db/dump.sql` unless `.dockerignore` excludes them.
- Pushes go to origin only, never upstream.
- Private-repo Actions minutes depend on the plan (not checked).

### Open questions
- Postgres or MariaDB for the Django services?
- Commit `docs/` and `.claude/settings.json` in the delivery?
- Keep the delivery repo private, or share it with the interviewers?
- Should `make up` start everything, or keep WP-only `up` plus `up-all`?

### Follow-ups

**Recommendation updated (2026-10-26, from topic 9):** was pinned `python:3.12-slim` and `node:22-alpine`. Now: `python:3.14-slim` and `node:24-alpine`, with versions held in `.python-version`/`.nvmrc` and compose build args, plus Dependabot. Reason: Python 3.12 bugfix support ended 2025-04, Node 22 Active support ended 2026-10-20, and every dependency lists 3.14.


## 8. Code-quality tooling

### Findings
- **Python tool versions** (PyPI JSON, 2026-10-26): ruff 0.17.2, mypy 2.4.0, django-stubs 6.1.2, djangorestframework-stubs 3.18.1, black 26.10.1, pyright 1.1.414, ty 0.0.92. Evidence: https://pypi.org/pypi/{ruff,mypy,django-stubs,djangorestframework-stubs,black,pyright,ty}/json.
- **ty is not a candidate.** It is pre-stable (0.0.x) and has no Django plugin.
- **django-stubs 6.1.2** lists Django 5.2, 6.0 and 6.1 classifiers. Its `compatible-mypy` extra requires `mypy>=1.13,<2.5`. Evidence: https://pypi.org/pypi/django-stubs/json.
- **Pin trap: the DRF stubs cap mypy below the latest release.** djangorestframework-stubs 3.18.1's `compatible-mypy` extra requires `mypy<2.4,>=1.13`, while the latest mypy is 2.4.0. mypy 2.3.0 and 2.3.1 exist. Evidence: `curl https://pypi.org/pypi/djangorestframework-stubs/json` → `requires_dist` `mypy<2.4,>=1.13; extra == "compatible-mypy"`; `curl https://pypi.org/pypi/mypy/json` → releases include `2.3.0`, `2.3.1`.
- **django-stubs needs a settings module.** Its mypy plugin (`mypy_django_plugin.main` plus `django_settings_module`) imports the settings module, so settings must load without a database or secrets. This comes from the django-stubs README (https://github.com/typeddjango/django-stubs) and was not re-fetched this session.
- **npm versions** (registry.npmjs.org, 2026-10-26): eslint 10.13.0, typescript 7.0.2, typescript-eslint 8.72.1, eslint-plugin-react-hooks 7.1.1, eslint-plugin-jsx-a11y 6.10.2, @biomejs/biome 2.6.3, prettier 3.9.10, stylelint 17.16.0, stylelint-config-standard-scss 17.0.0. Evidence: `https://registry.npmjs.org/<pkg>/latest`.
- **Peer-dependency traps** (from each package's `peerDependencies` in the registry):
  - typescript-eslint 8.72.1 requires `typescript >=4.8.4 <6.1.0`, so TypeScript 7 is excluded.
  - eslint-plugin-jsx-a11y 6.10.2 supports up to eslint ^9, so ESLint 10 is excluded.
- **No existing config.** The repo has no lint, typecheck or test targets or config files. Evidence: `Makefile:1-43`.
- **Pre-commit conflicts with Docker-only.** The `pre-commit` framework needs Python on the host, which conflicts with C1. Evidence: `CHALLENGE.md:20`.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | All tools run in containers. The pre-commit framework needs host Python; a Docker-backed hook script or CI-only does not. | `CHALLENGE.md:20` |
| C5 | The library gets its own strict mypy run without Django, and the root ruff config must not make it uninstallable on its own. | topic 5 |
| P7 | ruff is one tool to explain. ESLint + jsx-a11y is the standard answer. Biome is simpler but harder to defend on a11y. | registries |
| P8 | ruff `S` rules, a strictly typed JWT library, `jsx-a11y`, `tsc` and stylelint all show shipping discipline. | registries |
| P9 | `make fmt` / `lint-fix` keep live edits clean, and TypeScript gives the AI type feedback. | n/a |
| P10 | ruff replaces three tools. The frontend toolchain is about 8 packages; stylelint is the first to cut. | registries |

### Recommendation
**Python linting and formatting.** Use ruff for both, with one root config.
- Rule set: `E,F,W,I,B,UP,DJ,S,C4,SIM,DTZ`.
- Ignore `S101` in tests.
- Line length 100, `target-version = "py312"`.
- Exclude `wp-content`, `db`, `reference`, `node_modules`, `dist`, `static` and `migrations`.
- Pin ruff to an exact version.

**Python type checking.** Use mypy with django-stubs and djangorestframework-stubs, installed through `[compatible-mypy]` so mypy resolves to 2.3.x.
- `strict = true` on the shared library.
- Gradual on the two services: plugin on, `check_untyped_defs`.
- A check-safe settings module.

**Frontend.**
- TypeScript, pinned `~6.0`, checked with `tsc --noEmit`.
- ESLint 9 flat config with typescript-eslint, react-hooks and jsx-a11y.
- Prettier for formatting.

**SCSS.** stylelint with `stylelint-config-standard-scss`. It is optional and the first thing to drop.

**Running it all.**
- Make targets: `lint`, `fmt-check`, `typecheck`, `test`. `make check` runs all of them. `make fmt` and `make lint-fix` apply fixes.
- Everything runs via `docker compose run`.
- No host pre-commit hooks. CI is the gate; an optional `.githooks` script can call make through Docker.

This serves P7, P8 and C1. It costs some P10 (stubs plus about 8 frontend packages).

### Options considered
| Option | For | Against |
|---|---|---|
| ruff lint + format | One fast tool replaces three | Rule churn between versions; pin it |
| black + flake8 + isort | Familiar | Three configs and deps |
| mypy + django-stubs | Mature Django plugin | Needs settings module; mypy capped `<2.4` by DRF stubs |
| pyright | Fast, good inference | No Django plugin; noisy on ORM |
| ty | Very fast | 0.0.x; no Django support |
| TS + ESLint 9 + Prettier | Standard; full a11y plugin | More packages; peer pins |
| Biome | One tool, fast | Weaker a11y/hooks parity; harder to defend |
| JS + JSDoc `checkJs` | Fewer files | Less conventional |
| stylelint-standard-scss | Cheap SCSS hygiene | Noise on mirrored reference CSS |
| pre-commit framework | Standard | Needs host Python (C1) |
| Docker-backed `.githooks` script | C1-compliant | Opt-in; slower |

### Risks
- A naive `pip install mypy django-stubs djangorestframework-stubs` resolves mypy 2.4 and breaks the DRF stubs. Pin mypy.
- TypeScript 7 conflicts with typescript-eslint, and ESLint 10 conflicts with jsx-a11y. Pin TypeScript `~6.0` and ESLint 9.
- ruff `S`, `DJ` and `UP` rules will flag generated migrations and test secrets. Exclude them deliberately.
- The django-stubs plugin fails if importing settings needs a database or secrets.
- CI time is dominated by image builds, not the linters. Use layer caching. Timings are unmeasured.

### Open questions
- TypeScript or JavaScript for `<BrandList />`? (TS is recommended.)
- Opt-in Docker-backed git hook, or CI only?
- Keep stylelint, or drop it to save time?

### Follow-ups

**Q (2026-10-26): What about tooling? type checking, linting, formatting?**
Answer: use ruff for Python linting and formatting, mypy with the Django and DRF stubs for Python typing (strict on the library, gradual on the services), TypeScript with ESLint 9, typescript-eslint, react-hooks, jsx-a11y and Prettier for the frontend, and optionally stylelint for SCSS. All of it runs through `make lint` / `fmt-check` / `typecheck` in Docker, and CI is the gate. Two version pins are required: mypy below 2.4 for the DRF stubs, and TypeScript `~6.0` plus ESLint 9 for the lint plugins. Evidence: PyPI and npm registry JSON above; `pip`/`curl` check of mypy releases.

## 9. Runtimes and package managers

### Findings
- **Python support windows** (endoflife.date, 2026-10-26):

  | Version | Bugfix support | Security support | Latest |
  |---|---|---|---|
  | 3.14 | to 2027-10-01 | to 2030-10-31 | 3.14.10 |
  | 3.13 | ended 2026-10-01 | to 2029-10-31 | |
  | 3.12 | ended 2025-04-02 | to 2028-10-31 | |

  Evidence: https://endoflife.date/api/python.json.
- **Django support windows:** 5.2 LTS ends 2028-04-30. 6.0 ends 2027-04-30. 6.1 (released 2026-08-05) ends 2027-12-31. Evidence: https://endoflife.date/api/django.json.
- **Python 3.12–3.14 is covered by every key package.** These all list 3.12, 3.13 and 3.14 in their classifiers: Django 6.1.2, DRF 3.18.3, django-filter 26.2, django-stubs 6.1.2, psycopg 3.3.6, mysqlclient 2.3.0, PyJWT 2.15.1, bcrypt 5.0.0. Evidence: PyPI JSON.
- **Verified here, not by the researcher:** Django 5.2.18 lists Python 3.10–3.14 (`curl https://pypi.org/pypi/Django/5.2.18/json`). psycopg-binary 3.3.6 ships manylinux x86_64 wheels for cp310–cp315 (`curl https://pypi.org/pypi/psycopg-binary/json`).
- **Official Python images:** `python:3.12-slim`, `3.13-slim` and `3.14-slim` exist, each with trixie and bookworm variants. Evidence: https://hub.docker.com/v2/repositories/library/python/tags?name=slim (2026-10-26).
- **Node release lines on 2026-10-26:**
  - 22 and 24 are both past Active support (ended 2026-10-20) and now in Maintenance. EOL is 2027-04-30 for 22 and 2028-04-30 for 24.
  - 26 is Current and becomes LTS on 2026-10-28, with Active support to 2027-10-27 and EOL 2029-04-30.
  - nodejs.org recommends Active or Maintenance LTS for production.
  
  Evidence: https://endoflife.date/api/nodejs.json; https://nodejs.org/en/about/previous-releases.
- **Node images:** `node:24-alpine`, `node:24-slim`, `node:26-alpine` and `lts-alpine` (= 24 "krypton") all exist. Evidence: Docker Hub library/node tags.
- **Engine requirements** (npm registry): vite 8.3.5 needs `^20.19.0 || >=22.12.0`, vitest 5.0.5 needs `^22.12.0 || ^24.0.0 || >=26.0.0`, and npm 12.2.1 needs `^22.22.2 || ^24.15.0 || >=26.0.0`. Node 24 and 26 satisfy all three.
- **Other tool versions:**
  - JavaScript (npm registry): pnpm 12.15.0, bun 1.4.4, corepack 0.36.0. Whether current Node images still bundle corepack is unverified.
  - Python (PyPI): uv and uv-build 0.13.5 (pre-1.0), hatchling 1.32.4, pip-tools 7.6.2, psycopg2-binary 2.9.13, PyMySQL 1.2.3 (pure Python).
- **uv in Docker** (official guide):
  - Install with `COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/`.
  - Use a cache mount on `/root/.cache/uv`.
  - Install dependencies in their own layer with `uv sync --frozen --no-install-project` (or `--no-install-workspace`), then run `uv sync --locked`.
  - Add `.venv` to `.dockerignore`.
  
  Evidence: https://docs.astral.sh/uv/guides/integration/docker/ (2026-10-26).
- **uv workspaces vs. the build-context plan.** A uv workspace has a single root `uv.lock`. Using it in a service build needs the root lock and the lib inside the build context, which conflicts with the per-service context plus `additional_contexts` plan from topic 5. This is the researcher's knowledge of uv and was not fetched.
- **Driver build dependencies.** `psycopg[binary]` needs no build dependencies, while `psycopg[c]` and mysqlclient need dev libraries and a compiler in slim images. That is from package knowledge, not fetched. PyMySQL is pure Python.

### Fit against priorities
| Priority | How the options compare | Evidence |
|---|---|---|
| C1 | All options are container-only. Host Python 3.14.2 and Node 26.7.0 are irrelevant but can drift from the images. | topic 7 |
| C5 | The lib's pyproject works with any manager. The proof that its tests run without Django is a bare `pip install .[test]` or `uv run --package`. | topic 5 |
| P7 | pip and npm are the easiest to explain. uv is one extra tool but easy to justify (lock, speed, hashes). bun and Poetry/PDM cost explanation. | PyPI, docs |
| P8 | `uv.lock` and `npm ci` give locked, hashed installs. pip needs pip-compile `--generate-hashes`. | uv docs |
| P9 | Adding a dependency is `uv add` or `npm i` plus a rebuild. | n/a |
| P10 | uv is the fastest, with built-in caching. pip has the fewest tools. npm adds nothing beyond Node. | uv docs |

### Recommendation
- **Python:** `python:3.14-slim` (trixie) for both services. It has the longest support window, every dependency lists it, and both Django 5.2 and 6.1 support it. Fall back to 3.13 if a wheel or stub problem appears.
- **Python packaging:** uv with one root workspace and a hashed `uv.lock`, with the uv image tag pinned. The lib's build backend is hatchling, so its pyproject stays independent of uv. Images build from the repo root context with a strict `.dockerignore`, which replaces topic 5's `additional_contexts` plan. The fallback is pip plus pip-compile with hashes, one lock per package.
- **Drivers:** `psycopg[binary]` for Postgres and PyMySQL for the WP importer. Neither needs build dependencies.
- **Node:** `node:24-alpine`, the conservative LTS choice, supported to 2028-04. Node 26 becomes LTS on 2026-10-28 and is also defensible.
- **JavaScript packaging:** npm with `package-lock.json` and `npm ci`. No bun, pnpm or corepack.
- **Pinning:** `.python-version` and `.nvmrc`/`engines` in the repo. Version build args come from compose so the Dockerfiles and CI share them. Use tags rather than digests. Dependabot covers uv/pip, npm, docker and github-actions.
- **Images:** multi-stage builds with a non-root user. A `dev` target carries ruff, mypy and pytest; the runtime target stays lean. Python images are slim, not alpine.

This serves C1, P7 and P8. It costs a little P10 (uv plus the root-context change) and a little P7 (explaining uv).

### Options considered
| Option | For | Against |
|---|---|---|
| Python 3.14-slim | Longest support; all deps list it; matches host | Newest; possible stub/wheel gaps |
| Python 3.13-slim | Mature; security to 2029 | Bugfix already ended |
| Python 3.12-slim | Minimum for Django 6.1 | Security-only; shortest window |
| pip + pip-compile | Fewest concepts | Hashes need flags; per-package locks; slower |
| uv workspace | One hashed lock; fast; cached layers | Pre-1.0; needs root context |
| Poetry/PDM | Mature locks | More to explain; no win over uv |
| npm + `npm ci` | Ships with Node; lockfile | Slower than pnpm/bun |
| pnpm/yarn | Faster; stricter | Corepack or install step |
| bun | Fast; all-in-one | Vite/Vitest compatibility unverified; hard to defend |
| `psycopg[binary]` + PyMySQL | No build deps | PyMySQL slower (irrelevant for a one-off import) |
| `psycopg[c]` / mysqlclient | Native speed | Compiler and dev libs in images |

### Risks
- uv is pre-1.0, so its CLI and lock format can change. Pin the image tag.
- The repo root context leaks files and slows builds without a strict `.dockerignore` (`wp-content` is 46M).
- 3.14 wheels or stubs may lag for a niche dependency. The 3.13 fallback is one line.
- Node 24 is in Maintenance, not Active, after 2026-10-20.
- Host versions differ from the images. Document that only Docker counts.

### Open questions
- Is a repo root build context acceptable in place of `additional_contexts`?
- uv, or pip + pip-tools for explainability?
- Node 24 (safe) or Node 26 (LTS from 2026-10-28)?

### Follow-ups

**Q (2026-10-26): What about packaging and tools like node, bun, npm, pip, uv, python etc?**

Answer: Python 3.14-slim, uv with a single workspace lock, hatchling for the lib, `psycopg[binary]` and PyMySQL as drivers, Node 24-alpine, and npm with `npm ci`. No bun, pnpm or Poetry. Versions are pinned via `.python-version`/`.nvmrc` and compose build args, and Dependabot keeps them current. This depends on accepting a repo root build context for uv's single lock; if that is unwanted, pip-compile with per-package locks keeps topic 5's `additional_contexts` plan. Evidence: endoflife.date, PyPI and npm JSON, Docker Hub tags, uv Docker guide (all 2026-10-26).

Recommendation updated (topics 5 and 7): was `python:3.12-slim` / `node:22-alpine`, pip, and per-service contexts with `additional_contexts`. Now Python 3.14-slim / Node 24-alpine, a uv workspace, and a repo root context with a strict `.dockerignore`. Reason: support windows (3.12 bugfix ended 2025-04, Node 22 Active ended 2026-10-20) and uv's single-lock workspace model.
