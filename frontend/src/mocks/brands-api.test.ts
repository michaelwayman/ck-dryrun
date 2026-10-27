// @vitest-environment node

import { readdirSync } from "node:fs";
import { setupServer } from "msw/node";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { examples, handlers, type Example } from ".";

const EXAMPLES_DIR = new URL(
  "../../../docs/contracts/brands-api/examples/",
  import.meta.url,
);
const ORIGIN = "http://localhost";

// Read from disk, not from the glob, so a file the glob missed still fails here.
const files = readdirSync(EXAMPLES_DIR).filter((f) => f.endsWith(".json"));

const server = setupServer(...handlers);
const unhandled: string[] = [];
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
  server.events.on("request:unhandled", ({ request }) => {
    unhandled.push(request.url);
  });
});
afterAll(() => server.close());

function toFetch({ request }: Example): [string, RequestInit] {
  const url = new URL(request.path, ORIGIN);
  for (const [key, value] of Object.entries(request.query ?? {})) {
    for (const v of [value].flat()) url.searchParams.append(key, v);
  }
  return [
    url.href,
    {
      method: request.method,
      headers: request.headers,
      body:
        request.body === undefined ? undefined : JSON.stringify(request.body),
    },
  ];
}

describe("brands-api mock", () => {
  it("loads every example file", () => {
    expect(files.length).toBeGreaterThanOrEqual(12);
    expect(Object.keys(examples).sort()).toEqual([...files].sort());
    expect(handlers).toHaveLength(files.length);
  });

  it.each(files)("serves %s", async (file) => {
    const example = examples[file]!;
    const res = await fetch(...toFetch(example));

    expect(res.status).toBe(example.response.status);
    expect(await res.json()).toEqual(example.response.body);
    for (const [name, value] of Object.entries(
      example.response.headers ?? {},
    )) {
      expect(res.headers.get(name)).toBe(value);
    }
  });

  it("leaves a query no example covers unhandled", async () => {
    await expect(fetch(`${ORIGIN}/api/brands/?page=2`)).rejects.toThrow();
    expect(unhandled).toEqual([`${ORIGIN}/api/brands/?page=2`]);
  });

  it("leaves a PATCH with a token no example uses unhandled", async () => {
    const [url, init] = toFetch(examples["patch-ok.json"]!);
    const headers = { ...init.headers, Authorization: "Bearer other" };

    await expect(fetch(url, { ...init, headers })).rejects.toThrow();
    expect(unhandled).toContain(url);
  });
});
