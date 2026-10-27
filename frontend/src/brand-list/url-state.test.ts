import { describe, expect, it } from "vitest";
import urlStates from "../../../docs/contracts/brandlist-mount/examples/url-states.json";
import { CONFIG } from "./test-server";
import type { ListState } from "./types";
import { apiRequestUrl, nextState, parseState, writeSearch } from "./url-state";

const search = (pageUrl: string) => new URL(pageUrl, "http://x").search;
const START: ListState = { industries: ["retail"], ordering: "name", page: 3 };
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
    expect(
      writeSearch("?page=9&utm_source=mail&industry=x&ref=1", START, CONFIG),
    ).toBe("?utm_source=mail&ref=1&industry=retail&ordering=name&page=3");
  });
});

describe("nextState", () => {
  it("resets the page when the filter or sort changes", () => {
    expect(nextState(START, { industries: ["telecom", "finance"] })).toEqual({
      industries: ["finance", "telecom"],
      ordering: "name",
      page: 1,
    });
    expect(nextState(START, { ordering: "-name" }).page).toBe(1);
    expect(nextState(START, { page: 4 })).toEqual({ ...START, page: 4 });
  });
});
