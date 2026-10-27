import { describe, expect, it } from "vitest";
import urlStates from "../../../docs/contracts/brandlist-mount/examples/url-states.json";
import { CONFIG } from "./test-server";
import { apiRequestUrl, nextState, parseState, writeSearch } from "./url-state";

const search = (pageUrl: string) => new URL(pageUrl, "http://x").search;
const pathAndQuery = (url: URL) => `${url.pathname}${url.search}`;

describe("url-states.json", () => {
  it.each(urlStates)("$page_url", (example) => {
    const state = parseState(search(example.page_url), CONFIG);
    const normalised =
      "normalised_page_url" in example
        ? example.normalised_page_url
        : example.page_url;

    expect(pathAndQuery(apiRequestUrl(state, CONFIG, "http://x"))).toBe(
      example.api_request,
    );
    expect(
      `/brand/${writeSearch(search(example.page_url), state, CONFIG)}`,
    ).toBe(normalised);
  });
});

describe("parseState", () => {
  it("normalises bad values", () => {
    expect(
      parseState(
        "?industry=telecom&industry=nope&industry=telecom&ordering=founded_year&page=0",
        CONFIG,
      ),
    ).toEqual({
      industries: ["telecom"],
      ordering: "-average_rating",
      page: 1,
    });
    expect(parseState("?page=2.5", CONFIG).page).toBe(1);
    expect(parseState("?page=abc", CONFIG).page).toBe(1);
  });
});

describe("writeSearch", () => {
  it("keeps other keys and rewrites ours after them", () => {
    const state = {
      industries: ["retail"],
      ordering: "name",
      page: 3,
    } as const;

    expect(
      writeSearch(
        "?page=9&utm_source=mail&industry=x&ref=1",
        { ...state, industries: [...state.industries] },
        CONFIG,
      ),
    ).toBe("?utm_source=mail&ref=1&industry=retail&ordering=name&page=3");
  });
});

describe("nextState", () => {
  const state = { industries: ["retail"], ordering: "name", page: 3 } as const;
  const start = { ...state, industries: [...state.industries] };

  it("resets the page when the filter or sort changes", () => {
    expect(nextState(start, { industries: ["telecom", "finance"] })).toEqual({
      industries: ["finance", "telecom"],
      ordering: "name",
      page: 1,
    });
    expect(nextState(start, { ordering: "-name" }).page).toBe(1);
  });

  it("keeps the filter and sort when the page changes", () => {
    expect(nextState(start, { page: 4 })).toEqual({ ...start, page: 4 });
  });
});
