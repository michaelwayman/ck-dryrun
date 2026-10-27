# brandlist-mount mock

A static host page for `<BrandList />`, so the component can be developed and tested without Django. It follows the [brandlist-mount contract](../../brandlist-mount.md).

- `index.html`: the `<section id="brand-list">` mount element with the five attributes from [`../examples/mount-attributes.json`](../examples/mount-attributes.json), plus a no-JS fallback grid (3 synthetic brands, reference class names: `.grid > article.card` with `.badge`, `h3 > a`, `.stars`, `.meta`, `.excerpt`; `nav.pagination` with `.page-numbers` and `aria-current`).
- Asset paths are Vite-style (`/src/main.tsx`, `/css/main.css`, with `frontend/` as Vite root). The real template uses `{% static %}` instead.

## Using it

- **Vite dev**: point Vite at this file as the HTML entry (wired in M6, not here).
- **Component tests**: import the values from the example file, not from this HTML:
  `import mount from "../docs/contracts/brandlist-mount/examples/mount-attributes.json";`

## Check the attributes still match the example

The values are hand-copied. After the example changes, this prints `ok` or the first mismatch:

```bash
python3 -c 'import json,html.parser as h;e=json.load(open("docs/contracts/brandlist-mount/examples/mount-attributes.json"));e["data-industries"]=json.dumps(e["data-industries"],separators=(",",":"));a={};p=h.HTMLParser();p.handle_starttag=lambda t,s:a.update(s) if dict(s).get("id")=="brand-list" else None;p.feed(open("docs/contracts/brandlist-mount/mock/index.html").read());print(next((f"{k}: {a.get(k)!r} != {v!r}" for k,v in e.items() if a.get(k)!=v),"ok"))'
```
