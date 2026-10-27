// Shared test setup for the brand-list tests: the brands-api contract mock, DOM cleanup and the
// axe matcher. Import it first in each test file (there is no vitest setupFiles entry).
import { cleanup } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect } from "vitest";
import type { AxeMatchers } from "vitest-axe";
import * as axeMatchers from "vitest-axe/matchers";
import { examples, handlers } from "../mocks";
import mountAttributes from "../../../docs/contracts/brandlist-mount/examples/mount-attributes.json";
import type { MountConfig, Ordering } from "./types";

declare module "vitest" {
  // vitest-axe 0.1 augments the old `Vi` namespace; vitest 5 reads custom matchers from here.
  // The type parameters must repeat vitest's to merge.
  /* eslint-disable @typescript-eslint/no-empty-object-type, @typescript-eslint/no-unused-vars */
  interface Matchers<
    R extends void | Promise<void> = void | Promise<void>,
    T = unknown,
  > extends AxeMatchers {}
  /* eslint-enable @typescript-eslint/no-empty-object-type, @typescript-eslint/no-unused-vars */
}

expect.extend(axeMatchers);

export const PAGE_PATH = "/brand/";

// The config from the contract's mount-attributes example.
export const CONFIG: MountConfig = {
  apiUrl: mountAttributes["data-api-url"],
  industries: mountAttributes["data-industries"],
  pageSize: Number(mountAttributes["data-page-size"]),
  defaultOrdering: mountAttributes["data-default-ordering"] as Ordering,
};

export const server = setupServer(...handlers);

// The shared handlers answer only an example's exact query, and the component always sends
// `ordering` and `page_size`. This answers `apiRequest` (path and query, exactly) with an
// example's status and body instead.
export function respond(apiRequest: string, exampleFile: string) {
  const { response } = examples[exampleFile]!;
  server.use(
    http.get(
      ({ request }) => {
        const url = new URL(request.url);
        return `${url.pathname}${url.search}` === apiRequest;
      },
      () =>
        HttpResponse.json(response.body as never, { status: response.status }),
    ),
  );
}

// The page URL a test starts on.
export function visit(search = "") {
  window.history.replaceState(null, "", `${PAGE_PATH}${search}`);
}

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  server.events.removeAllListeners();
  visit();
});
afterAll(() => server.close());
