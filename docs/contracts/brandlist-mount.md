# Contract: brandlist-mount

Provider: the `app` template for `/brand/` (`services/app/`). Consumer: the `<BrandList />` bundle (`frontend/`).
Spec: R7, R16, T9. Changes go through a `contract` issue.

## Purpose
Defines how the Django page and the JS bundle find each other: where the bundle mounts, which config it reads, which assets the page loads, and which URL query keys the component controls.

## Mount element
```html
<section id="brand-list"
         data-api-url="/api/brands/"
         data-industries='[{"slug":"insurance","name":"Insurance"}, ...]'
         data-page-size="12"
         data-default-ordering="-average_rating">
  <!-- server-rendered card grid + page links (no-JS fallback, R16) -->
</section>
```

| Attribute | Type | Nullable | Rules |
|---|---|---|---|
| `id` | `"brand-list"` | no | The bundle mounts into the first element with this id. If there is none, it does nothing and logs nothing. |
| `data-api-url` | string (path) | no | Base URL of the brands-api list endpoint. |
| `data-industries` | JSON array of `{slug, name}` | no | Every active industry in display order. The industry checkboxes are built from this list, so the component never calls a separate industries endpoint. |
| `data-page-size` | integer string | no | Value sent as `page_size`. |
| `data-default-ordering` | ordering value from brands-api | no | Used when the URL has no `ordering` key. |

When the component mounts it replaces the fallback markup inside the section. The `<section>` element and its `id` stay.

## Assets
- JS: `{% static 'brandlist/brand-list.js' %}`, an ES module that mounts itself on load.
- CSS: `{% static 'css/main.css' %}` (compiled SCSS, R9). `<BrandList />` adds no stylesheet of its own; its `brand-list__*` styles live in `frontend/scss/components/`.
- Cache busting: Django `ManifestStaticFilesStorage` hashes file names, so the template uses `{% static %}` and never hard-codes a path.

## URL query keys (owned by `<BrandList />` on `/brand/`)
| Key | Maps to brands-api | Notes |
|---|---|---|
| `industry` | `industry` (repeatable) | Order does not matter; the component normalises keys to sorted order. |
| `ordering` | `ordering` | Omitted from the URL when it equals `data-default-ordering`. |
| `page` | `page` | Omitted when it is 1. |

The server-rendered fallback understands the same keys, so the same URL gives the same view with or without JS. The component writes these keys with `history.pushState` and reads them again on `popstate`. It leaves any other query keys untouched. Invalid values are normalised and written back: industry slugs not in `data-industries` are dropped, an `ordering` outside the six allowed values becomes the default, and a `page` that isn't a positive integer becomes 1.

## Examples
These live in [brandlist-mount/examples/](brandlist-mount/examples/):
- `mount-attributes.json`: the attribute values for the 5 seeded industries.
- `url-states.json`: URL query strings and the brands-api request each one produces.
