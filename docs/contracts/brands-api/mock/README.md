# brands-api mock

[msw](https://mswjs.io/) 3 handlers that serve the [brands-api contract](../../brands-api.md) examples, so `<BrandList />` can be built and tested without the app.

- `handlers.ts` loads every `../examples/*.json` in place with `import.meta.glob` (no copied payloads; a new example is served as soon as it exists) and builds one handler per example.
- A request is answered only when it matches an example exactly: method, path, query (key and repeated-value order ignored), and for PATCH the `Authorization` and `Content-Type` headers and the JSON body. The handler returns that example's status, body and headers (e.g. `WWW-Authenticate`).
- Anything else is unhandled, so run the server with `onUnhandledFrame: "error"` (msw 3's name for msw 2's `onUnhandledRequest`) and a request the contract doesn't cover fails the test.
- Tokens are the contract's placeholder strings (`Bearer <access token from access-token/examples/editor.json>`), sent as-is.

## Using it

The frontend re-exports it as `src/mocks` (`resolve.dedupe` in `vite.config.ts` and `paths` in `tsconfig.json` make this file's `msw` import resolve from `frontend/node_modules`):

```ts
// @vitest-environment node
import { setupServer } from "msw/node";
import { handlers } from "../mocks";

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterAll(() => server.close());
```

Matching compares the path only, so any origin works. `frontend/src/mocks/brands-api.test.ts` replays every example through these handlers.
