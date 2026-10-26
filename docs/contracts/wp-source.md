# Contract: wp-source

**Provider:** the WordPress MariaDB service `db`. It is seeded from `db/dump.sql` and is read-only for us.
**Consumers:** `import_wp` (app) and `import_wp_users` (auth).
**Spec:** R2, R10, T6. Research: [§1](../research.md#1-wp-source-data-shape), [§2](../research.md#2-migration-approach).
Changes to the mapping go through a `contract` issue.

## Purpose
Defines exactly what each importer reads from WordPress and how each field maps to the target. Nothing outside this list is read.

## Connection
- Host `db:3306`, reachable on the compose network only. Database `${WORDPRESS_DB_NAME:-wp}`, credentials from `.env`. Table prefix `${WORDPRESS_TABLE_PREFIX:-wp_}`.
- Driver: PyMySQL. Charset `utf8mb4`. Use read-only SQL only (`SELECT`).
- Startup: compose `depends_on: db: condition: service_healthy`. The importer retries the connection 10 times, 2 s apart, then exits with code 1.

## Content (`import_wp`, app)
### Industries
`wp_terms t JOIN wp_term_taxonomy tt ON tt.term_id = t.term_id WHERE tt.taxonomy = 'industry'`

| Source | Target | Notes |
|---|---|---|
| `t.term_id` | `Industry.wp_id` | Upsert key. |
| `t.name` | `Industry.name` | |
| `t.slug` | `Industry.slug` | Copied verbatim. |

### Brands
`wp_posts WHERE post_type = 'brand' AND post_status = 'publish'`. The industry comes from `wp_term_relationships`, joined on `object_id = ID` and taking the `industry` taxonomy. A brand has at most one industry; if there are several, the lowest `term_taxonomy_id` wins and a warning is logged.

| Source | Target | Notes |
|---|---|---|
| `ID` | `Brand.wp_id` | Upsert key. |
| `post_title` | `name` | |
| `post_name` | `slug` | Copied verbatim (C3). |
| `post_content` | `content` | Raw HTML. Sanitized at render (T13). |
| first `<p>` of `post_content`, tag-stripped | `short_description` | Set on create. On update it is overwritten only if the stored value still equals the previously imported value, so editor edits survive. |
| meta `website_url` | `website_url` | Empty string → `""`. |
| meta `founded_year` | `founded_year` | Integer or null. |
| meta `headquarters` | `headquarters` | |
| meta `average_rating` | `legacy_average_rating` | Decimal or null. Never displayed. |
| meta `_yoast_wpseo_title` | `seo_title` | May be empty. |
| meta `_yoast_wpseo_metadesc` | `seo_description` | May be empty. |

### Reviews
`wp_posts WHERE post_type = 'review' AND post_status = 'publish'`

| Source | Target | Notes |
|---|---|---|
| `ID` | `Review.wp_id` | Upsert key. |
| `post_title` | `title` | |
| `post_name` | `slug` | Copied verbatim. |
| `post_content` | `content` | Raw HTML. |
| `post_date_gmt` | `published_at` | Stored as UTC. |
| `post_author` | `reviewer_wp_id` | Opaque reference. Resolved only in auth (`wp_user_id`). |
| meta `rating` | `rating` | Integer 1–5. Out-of-range values cause the row to be skipped and logged. |
| meta `reviewer_name` | `reviewer_name` | |
| meta `reviewer_location` | `reviewer_location` | |
| meta `brand` | FK `brand` via `Brand.wp_id` | A string post ID. If the brand is unknown or inactive, the review is skipped and logged. |

Meta is read from `wp_postmeta WHERE post_id IN (…) AND meta_key IN (<allow-list above>)`. Keys starting with `_` other than the two Yoast keys are never read.

### Deletions and safety
- Rows whose `wp_id` was not seen in this run are set to `is_active = False`. Rows seen again are set back to `True`.
- If the brand query returns 0 rows, the run aborts before writing anything.
- The whole run happens in one transaction. At the end it prints `industries/brands/reviews: created N, updated N, deactivated N`.

## Users (`import_wp_users`, auth)
The importer reads:
- `wp_users`: `ID`, `user_login`, `user_email`, `display_name`, `user_pass`.
- `wp_usermeta`: `meta_value` where `meta_key = '<prefix>capabilities'`. This is a PHP-serialized array; only its keys are parsed, with a regex on `s:\d+:"(\w+)"`, and the PHP is never unserialized.

| Source | Target | Notes |
|---|---|---|
| `ID` | `User.wp_user_id` | Upsert key. |
| `user_login` | `username` | |
| `user_email` | `email` | |
| `display_name` | `display_name` | |
| `user_pass` (`$wp$2y$…`) | `password` as `wp_bcrypt$…` | Set on create only. The hasher is T5. |
| capabilities contain `administrator` | roles `{editor}` plus `is_staff` and `is_superuser` | Set on create only. |
| any other capability | roles `{reader}` | Set on create only. |

## Expected counts on the committed dump
Industries 5, brands 5, reviews 60, users 9 (1 editor, 8 readers).

## Examples
In [wp-source/examples/](wp-source/examples/):
- `brand-row.json`: one brand's source columns and meta, with the resulting `Brand` fields.
- `review-row.json`: the same for one review.
- `user-row.json`: the same for one user.
- `import-summary.json`: the output of a first run and of a re-run.
