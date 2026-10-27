// The page URL is the component's only view state (brandlist-mount: URL query keys). It owns
// `industry`, `ordering` and `page`, and leaves every other query key alone.
import { useCallback, useEffect, useState } from "react";
import { isOrdering, type ListState, type MountConfig } from "./types";

const KEYS = ["industry", "ordering", "page"] as const;

// Reads the view from a query string. Unknown industries are dropped, duplicates removed and
// the rest sorted; a bad ordering becomes the default and a bad page becomes 1.
export function parseState(search: string, config: MountConfig): ListState {
  const params = new URLSearchParams(search);
  const known = new Set(config.industries.map((i) => i.slug));
  const industries = [...new Set(params.getAll("industry"))]
    .filter((slug) => known.has(slug))
    .sort();
  const ordering = params.get("ordering");
  const page = Number(params.get("page") ?? "1");
  return {
    industries,
    ordering: isOrdering(ordering) ? ordering : config.defaultOrdering,
    page: Number.isInteger(page) && page >= 1 ? page : 1,
  };
}

// The query string for `state`: other keys first and unchanged, then ours in a fixed order with
// defaults omitted. Returns "" when nothing is left, or "?…".
export function writeSearch(
  search: string,
  state: ListState,
  config: MountConfig,
): string {
  const params = new URLSearchParams(search);
  for (const key of KEYS) params.delete(key);
  for (const slug of state.industries) params.append("industry", slug);
  if (state.ordering !== config.defaultOrdering) {
    params.set("ordering", state.ordering);
  }
  if (state.page !== 1) params.set("page", String(state.page));
  const query = params.toString();
  return query ? `?${query}` : "";
}

// The brands-api request for `state`, absolute against `base` (fetch in jsdom needs one). The
// ordering is always sent, the page only past 1, the page size always.
export function apiRequestUrl(
  state: ListState,
  config: MountConfig,
  base: string,
): URL {
  const url = new URL(config.apiUrl, base);
  const params = new URLSearchParams();
  for (const slug of state.industries) params.append("industry", slug);
  params.set("ordering", state.ordering);
  if (state.page !== 1) params.set("page", String(state.page));
  params.set("page_size", String(config.pageSize));
  url.search = params.toString();
  return url;
}

// A change to the view. Changing the filter or the sort goes back to page 1.
export type StatePatch = Partial<ListState>;

export function nextState(state: ListState, patch: StatePatch): ListState {
  const resets = patch.industries !== undefined || patch.ordering !== undefined;
  return {
    ...state,
    ...patch,
    industries: [...new Set(patch.industries ?? state.industries)].sort(),
    page: patch.page ?? (resets ? 1 : state.page),
  };
}

function currentState(config: MountConfig): ListState {
  return parseState(window.location.search, config);
}

// The page URL (path, query, hash) that shows `state`; also the href of links that work without JS.
export function hrefFor(state: ListState, config: MountConfig): string {
  const { pathname, search, hash } = window.location;
  return `${pathname}${writeSearch(search, state, config)}${hash}`;
}

// The view state, read from the URL and kept in sync with it: `navigate` pushes a history entry,
// back/forward (popstate) reads the URL again. On mount the URL is normalised in place.
export function useUrlState(
  config: MountConfig,
): [ListState, (patch: StatePatch) => void] {
  const [state, setState] = useState(() => currentState(config));

  useEffect(() => {
    const normalised = hrefFor(currentState(config), config);
    const { pathname, search, hash } = window.location;
    if (normalised !== `${pathname}${search}${hash}`) {
      window.history.replaceState(window.history.state, "", normalised);
    }
    const onPopState = () => setState(currentState(config));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [config]);

  const navigate = useCallback(
    (patch: StatePatch) => {
      const next = nextState(currentState(config), patch);
      window.history.pushState(null, "", hrefFor(next, config));
      setState(next);
    },
    [config],
  );

  return [state, navigate];
}
