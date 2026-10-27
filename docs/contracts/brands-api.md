# Contract: brands-api

Provider: `app` (`services/app/`). Consumers: `<BrandList />` (frontend), API clients (curl, a future mobile client).
Spec: R6, R13, R19. Changes go through a `contract` issue.

## Purpose
`GET /api/brands/` returns brand-card data for listings. Anyone can call it.
`PATCH /api/brands/<slug>/` lets an editor change a brand's short description.

## Conventions
- JSON over HTTP, UTF-8. Base path is `/api/`, served from the same origin as the pages.
- All timestamps are ISO 8601 with a timezone. All slugs are WP `post_name` values.
- Every error body has this shape: `{"error": {"code": string, "message": string, "fields": object|null}}`. `fields` maps a parameter or field name to a list of messages. It is `null` when the error isn't about a specific field.
- The OpenAPI schema (`/api/schema/`) and Swagger UI (`/api/docs/`) are served beside this API (R19). They describe it but are not part of this contract.

## GET /api/brands/

### Query parameters
| Name | Type | Default | Rules |
|---|---|---|---|
| `page` | integer ≥ 1 | 1 | A page past the last one returns 404 `not_found`. |
| `page_size` | integer 1–50 | 12 | A value over 50 returns 400. |
| `industry` | industry slug, repeatable | none (all) | `?industry=a&industry=b` returns brands in any of the listed industries. An unknown slug returns 400. |
| `ordering` | one of `average_rating`, `-average_rating`, `review_count`, `-review_count`, `name`, `-name` | `-average_rating` | Any other value returns 400. A leading `-` means descending. |

Ordering is always total:
- Rows are sorted by the requested key, then `name` ascending, then `pk` ascending.
- A `null` `average_rating` sorts last in both directions.
- Each active brand therefore appears exactly once across all pages.

### 200 response
| Field | Type | Nullable | Notes |
|---|---|---|---|
| `count` | integer | no | Total matching brands. |
| `next` | string (absolute URL) | yes | Keeps the current filter and ordering params. `null` on the last page. |
| `previous` | string (absolute URL) | yes | `null` on page 1. |
| `results` | array of BrandCard | no | Can be empty. |

**BrandCard**
| Field | Type | Nullable | Notes |
|---|---|---|---|
| `name` | string | no | |
| `slug` | string | no | |
| `url` | string (path) | no | `/brand/<slug>/` |
| `industry` | `{slug: string, name: string}` | no | |
| `short_description` | string | no | Plain text. May be `""`. |
| `average_rating` | number | yes | Mean of active review ratings, rounded half-up to 1 decimal. `null` when the brand has no reviews. |
| `review_count` | integer | no | Number of active reviews. `0` when there are none. |
| `top_review` | TopReview | yes | `null` when the brand has no reviews. |

**TopReview**: the brand's highest-rated active review. Ties go to the latest `published_at`, then the highest pk.
| Field | Type | Nullable | Notes |
|---|---|---|---|
| `title` | string | no | |
| `slug` | string | no | |
| `url` | string (path) | no | `/review/<slug>/` |
| `rating` | integer 1–5 | no | |
| `snippet` | string | no | Plain text with HTML stripped, at most 22 words, ending in `…` if it was cut. |

### Errors
| Status | `code` | When |
|---|---|---|
| 400 | `invalid_parameter` | Bad `page_size`, unknown `industry`, or `ordering` outside the allowed list. `fields` names the parameter. |
| 404 | `not_found` | `page` is past the last page. |

## PATCH /api/brands/&lt;slug&gt;/

### Request
- Header `Authorization: Bearer <access token>` is required. See [access-token](access-token.md).
- Header `Content-Type: application/json`.
- Body:

| Field | Type | Nullable | Rules |
|---|---|---|---|
| `short_description` | string | no | Required. 0–500 characters after trimming. Stored as plain text. |

Any other body field returns 400 `unknown_field`.

### 200 response
The updated BrandCard, in the same shape as the GET result.

### Errors
| Status | `code` | When |
|---|---|---|
| 400 | `invalid_body` | `short_description` is missing, not a string, or too long. |
| 400 | `unknown_field` | The body has fields other than `short_description`. |
| 401 | `not_authenticated` | No `Authorization` header, or it isn't `Bearer`. Response includes `WWW-Authenticate: Bearer`. |
| 401 | `invalid_token` | The token is expired, has a bad signature, the wrong `iss`/`aud`, an unknown `kid`, or an unsupported `v`. Response includes `WWW-Authenticate: Bearer error="invalid_token"`. |
| 403 | `permission_denied` | The token is valid but `roles` does not contain `editor`. |
| 404 | `not_found` | Unknown or inactive slug. |
| 405 | `method_not_allowed` | `GET`, `PUT`, `DELETE`, or `POST` on the detail URL. Returned before authentication. |

## Examples
Every file is in [brands-api/examples/](brands-api/examples/). Each one holds a `request` and a `response`.
- `list-default.json`: no parameters.
- `list-filter-sort.json`: two industries, `ordering=-review_count`, `page_size=1`.
- `list-empty.json`: valid filter, no matches.
- `list-invalid-ordering.json`: 400.
- `list-unknown-industry.json`: 400.
- `list-page-out-of-range.json`: 404.
- `patch-ok.json`: editor token.
- `patch-reader-forbidden.json`: 403.
- `patch-no-token.json`: 401.
- `patch-expired-token.json`: 401.
- `patch-unknown-field.json`: 400.
- `patch-unknown-slug.json`: 404.
