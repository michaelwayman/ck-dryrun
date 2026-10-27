// msw handlers that serve the brands-api contract examples in place (../examples/*.json).
// A request is answered only when it matches an example exactly; anything else is unhandled,
// so a test with onUnhandledFrame: "error" fails on a request the contract doesn't cover.
import { http, HttpResponse } from "msw";

type Query = Record<string, string | string[]>;

export interface Example {
  request: {
    method: "GET" | "PATCH";
    path: string;
    query?: Query;
    headers?: Record<string, string>;
    body?: unknown;
  };
  response: {
    status: number;
    headers?: Record<string, string>;
    body: unknown;
  };
}

const modules = import.meta.glob<Example>("../examples/*.json", {
  eager: true,
  import: "default",
});

// Keyed by file name, e.g. "list-default.json".
export const examples: Record<string, Example> = Object.fromEntries(
  Object.entries(modules).map(([path, example]) => [
    path.split("/").pop(),
    example,
  ]),
);

// Key order and repeated-value order don't matter: ?industry=a&industry=b == ?industry=b&industry=a.
function canonical(value: unknown): string {
  return JSON.stringify(value, (_key, v: unknown) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(
          Object.entries(v).sort(([a], [b]) => a.localeCompare(b)),
        )
      : v,
  );
}

function queryKey(query: Query): string {
  const lists = Object.entries(query).map(([k, v]) => [k, [v].flat().sort()]);
  return canonical(Object.fromEntries(lists));
}

function searchKey(params: URLSearchParams): string {
  const query: Query = {};
  for (const key of new Set(params.keys())) query[key] = params.getAll(key);
  return queryKey(query);
}

// Does the request match the example's method, path, query, headers and JSON body?
async function matches(request: Request, ex: Example["request"]) {
  const url = new URL(request.url);
  if (request.method !== ex.method || url.pathname !== ex.path) return false;
  if (searchKey(url.searchParams) !== queryKey(ex.query ?? {})) return false;
  if (ex.method === "GET") return true;
  for (const name of ["Authorization", "Content-Type"]) {
    if ((request.headers.get(name) ?? undefined) !== ex.headers?.[name])
      return false;
  }
  try {
    return canonical(await request.clone().json()) === canonical(ex.body);
  } catch {
    return false;
  }
}

// One handler per example. The match is in the predicate, not the resolver: msw 3 counts a
// request whose predicate matched as handled, so a resolver that declines would still bypass.
export const handlers = Object.values(examples).map((ex) =>
  http[ex.request.method === "GET" ? "get" : "patch"](
    ({ request }) => matches(request, ex.request),
    () =>
      HttpResponse.json(ex.response.body as never, {
        status: ex.response.status,
        headers: ex.response.headers,
      }),
  ),
);
