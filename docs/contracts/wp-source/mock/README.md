# wp-source mock

A tiny synthetic WordPress database for testing `import_wp` and `import_wp_users` against the [wp-source contract](../../wp-source.md) without the real dump. Every row is made up; nothing is copied from `db/dump.sql`.

- `fixture.sql`: the 7 tables the contract reads (`wp_` prefix), read columns only, and the rows below.
- `make_hashes.py`: makes and checks the `$wp$2y$10$` password hashes in `fixture.sql`.

## Load it

The SQL is a portable subset (no `ENGINE=`, `UNSIGNED`, `AUTO_INCREMENT`, backslash escapes or `/*! */`), so it loads into MariaDB 11 and into `sqlite3`.

```bash
docker run -d --name wp-mock -e MARIADB_ROOT_PASSWORD=mock -e MARIADB_DATABASE=wp -p 3307:3306 mariadb:11
docker exec -i wp-mock mariadb -uroot -pmock wp < docs/contracts/wp-source/mock/fixture.sql
```

Or mount it as an init script: `-v $PWD/docs/contracts/wp-source/mock/fixture.sql:/docker-entrypoint-initdb.d/fixture.sql:ro`. Quick lint: `sqlite3 :memory: < docs/contracts/wp-source/mock/fixture.sql`.

## Test passwords

| `user_login` | Password |
|---|---|
| `mock_admin` | `mock-admin-pw-1` |
| `mock_reader` | `mock-reader-pw-2` |

The hashes are committed as literals. To regenerate them (new salts each run) or check them:

```bash
uv run --no-project --with bcrypt python docs/contracts/wp-source/mock/make_hashes.py
uv run --no-project --with bcrypt python docs/contracts/wp-source/mock/make_hashes.py --verify
```

## Rows and what each one tests

| Row | What it is | Tests |
|---|---|---|
| term 1 / tt 11 | industry "Mock Insurance", slug `ins-mock` | slug copied verbatim; join on `term_id`, not `term_taxonomy_id` |
| term 2 / tt 12 | industry "Mock Banking", slug `bank-mock` | same |
| term 3 / tt 13 | `category` term attached to brand 101 | not an industry; ignored |
| post 101 (A) | brand, publish, industry 1, every data meta key, both Yoast keys, `_website_url` ACF twin | full mapping; `_` keys ignored; first `<p>` only, tags stripped |
| post 102 (B) | brand, publish, industry 2, empty `website_url`, `founded_year`, `average_rating`; `&amp;` in content | empty → `""` / null; no Yoast meta → empty SEO fields |
| post 103 (D) | brand, **draft**, industry 1 | not imported |
| post 201 (R1) | review of 101, rating `4`, `_rating` ACF twin, author user 2 | the one valid review |
| post 202 (R2) | review of brand `9999` (missing) | skipped and logged |
| post 203 (R3) | review of 101, rating `7` | skipped and logged |
| user 1 | `mock_admin`, `administrator` | roles `{editor}`, staff, superuser |
| user 2 | `mock_reader`, `subscriber` | roles `{reader}` |

## Expected import result

First run of `import_wp`:

```
industries: created 2, updated 0, deactivated 0
brands: created 2, updated 0, deactivated 0
reviews: created 1, updated 0, deactivated 0
```

plus one log line each for review 202 (unknown brand `9999`) and review 203 (rating `7` out of range). Brand 103 is not selected, so it is neither imported nor logged.

| Model | `wp_id` | Fields |
|---|---|---|
| Industry | 1 | name `Mock Insurance`, slug `ins-mock` |
| Industry | 2 | name `Mock Banking`, slug `bank-mock` |
| Brand | 101 | name `Alpha Mock Co.`, slug `alpha-mock`, industry 1, short_description `Alpha Mock Co. is a synthetic insurer.`, website_url `https://alpha-mock.example.com`, founded_year `1990`, headquarters `Springfield, ZZ`, legacy_average_rating `4.5`, seo_title `Alpha Mock Co. Reviews`, seo_description `Synthetic reviews of Alpha Mock Co.` |
| Brand | 102 | name `Beta & Sons`, slug `beta-and-sons`, industry 2, short_description is the first `<p>` tag-stripped (`Beta &amp; Sons is a synthetic bank.`; the contract doesn't say whether entities are decoded), website_url `""`, founded_year null, headquarters `Shelbyville, ZZ`, legacy_average_rating null, seo_title `""`, seo_description `""` |
| Review | 201 | brand 101, title `Quick claim`, slug `quick-claim`, rating `4`, reviewer_wp_id `2`, reviewer_name `Mock Reader`, reviewer_location `Springfield, ZZ`, published_at `2026-02-01T12:30:00Z` |

`content` on each Brand and Review is its raw `post_content` from `fixture.sql`. All rows `is_active = True`. `import_wp_users` creates 2 users:

| `wp_user_id` | username | email | display_name | roles | is_staff | is_superuser |
|---|---|---|---|---|---|---|
| 1 | `mock_admin` | `mock_admin@example.com` | Mock Admin | `{editor}` | true | true |
| 2 | `mock_reader` | `mock_reader@example.com` | Mock Reader | `{reader}` | false | false |

Each password is `wp_bcrypt$` + the stored hash and checks against the password in the table above.

A re-run of either importer on the unchanged fixture creates, updates and deactivates 0 rows.
