import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { configureAxe } from "vitest-axe";
import { examples } from "../mocks";
import { BrandList } from "./BrandList";
import { CONFIG, respond, server, visit } from "./test-server";

// jsdom has no layout or computed colours, so axe can't judge contrast here.
const axe = configureAxe({ rules: { "color-contrast": { enabled: false } } });

const DEFAULT_REQUEST = "/api/brands/?ordering=-average_rating&page_size=12";
const RETAIL_REQUEST =
  "/api/brands/?industry=retail&ordering=-average_rating&page_size=12";
const PAGE_9_REQUEST =
  "/api/brands/?ordering=-average_rating&page=9&page_size=12";

const results = () => document.querySelector(".brand-list__results")!;
const heading = () => screen.getByRole("heading", { level: 2 });
const liveRegion = () => document.querySelector("[aria-live=polite]")!;

function countRequests(apiRequest: string) {
  let n = 0;
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    if (`${url.pathname}${url.search}` === apiRequest) n += 1;
  });
  return () => n;
}

describe("<BrandList /> states", () => {
  it("loading: busy region with a skeleton", async () => {
    server.use(http.get("*/api/brands/", () => delay("infinite")));
    const { container } = render(<BrandList config={CONFIG} />);

    expect(results().getAttribute("aria-busy")).toBe("true");
    expect(results().querySelectorAll(".card")).toHaveLength(3);
    expect(
      results().querySelector(".brand-list__skeleton-line--title"),
    ).toBeTruthy();
    expect(heading().textContent).toBe("Brands");
    expect(liveRegion().textContent).toBe("");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("success: cards, stars as images, and the count announced", async () => {
    respond(DEFAULT_REQUEST, "list-default.json");
    const { container } = render(<BrandList config={CONFIG} />);

    await screen.findAllByRole("article");
    expect(results().getAttribute("aria-busy")).toBe("false");
    expect(liveRegion().textContent).toBe("5 brands found.");
    expect(heading().textContent).toBe("5 brands");
    expect(
      screen.getByRole("img", { name: "Rated 3.9 out of 5" }),
    ).toBeTruthy();
    // The name leads, then the rating row, then the industry badge.
    const card = screen.getAllByRole("article")[0]!;
    const parts = [...card.children].map((el) => el.className || el.tagName);
    expect(parts.slice(0, 3)).toEqual(["H3", "brand-list__rating", "DIV"]);
    expect(card.children[2]!.querySelector(".badge")).toBeTruthy();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("empty: a message and Clear filters", async () => {
    respond(RETAIL_REQUEST, "list-empty.json");
    respond(DEFAULT_REQUEST, "list-default.json");
    visit("?industry=retail");
    const user = userEvent.setup();
    const { container } = render(<BrandList config={CONFIG} />);

    expect(
      await screen.findByText("No brands match these filters."),
    ).toBeTruthy();
    expect(liveRegion().textContent).toBe("0 brands found.");
    expect(heading().textContent).toBe("No brands");
    expect(screen.getByText("Filtered by Retail.")).toBeTruthy();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(window.location.search).toBe("");
    expect(await screen.findAllByRole("article")).toHaveLength(5);
    expect(document.activeElement).toBe(heading());
  });

  it("empty and unfiltered: no Clear filters", async () => {
    respond(DEFAULT_REQUEST, "list-empty.json");
    render(<BrandList config={CONFIG} />);

    expect(
      await screen.findByText("No brands match these filters."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
  });

  it("error: an alert whose Retry repeats the request", async () => {
    respond(PAGE_9_REQUEST, "list-page-out-of-range.json");
    const requests = countRequests(PAGE_9_REQUEST);
    visit("?page=9");
    const user = userEvent.setup();
    const { container } = render(<BrandList config={CONFIG} />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("That page of brands doesn't exist.");
    expect(alert.textContent).not.toContain("Page out of range.");
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(requests()).toBe(2));
    expect(await screen.findByRole("alert")).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(heading()));
  });

  it("error: a page past the end links to page 1, keeping the view", async () => {
    respond(
      "/api/brands/?industry=retail&ordering=name&page=9&page_size=12",
      "list-page-out-of-range.json",
    );
    visit("?industry=retail&ordering=name&page=9");
    render(<BrandList config={CONFIG} />);

    const link = await screen.findByRole("link", { name: "Go to page 1" });
    expect(link.getAttribute("href")).toBe(
      "/brand/?industry=retail&ordering=name",
    );
  });

  it("error: a 200 that isn't a brand page", async () => {
    server.use(http.get("*/api/brands/", () => HttpResponse.text("<html>")));
    render(<BrandList config={CONFIG} />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("The brands couldn't be loaded.");
    expect(alert.textContent).not.toContain("could not be read");
  });

  it("brands without reviews say so instead of showing stars", async () => {
    const body = structuredClone(examples["list-default.json"]!.response.body);
    const page = body as { count: number; results: Record<string, unknown>[] };
    page.count = 1;
    page.results = [
      {
        ...page.results[0],
        average_rating: null,
        review_count: 0,
        top_review: null,
      },
    ];
    server.use(http.get("*/api/brands/", () => HttpResponse.json(page)));
    render(<BrandList config={CONFIG} />);

    expect(await screen.findByText("No reviews yet")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });
});

describe("<BrandList /> by keyboard", () => {
  it("reaches and operates every control", async () => {
    // list-filter-sort.json (shared handlers): two brands, one per page.
    visit("?industry=insurance&industry=telecom&ordering=-review_count");
    const all =
      "industry=finance&industry=insurance&industry=telecom&ordering=-review_count";
    respond(`/api/brands/?${all}&page_size=1`, "list-filter-sort.json");
    respond(`/api/brands/?${all}&page=2&page_size=1`, "list-filter-sort.json");
    const user = userEvent.setup();
    render(<BrandList config={{ ...CONFIG, pageSize: 1 }} />);
    await screen.findByRole("navigation", { name: "Brand pages" });

    // Space toggles the first checkbox; focus stays on it while the list reloads.
    await user.tab();
    await user.keyboard(" ");
    expect(window.location.search).toBe(
      "?industry=finance&industry=insurance&industry=telecom&ordering=-review_count",
    );
    for (const industry of CONFIG.industries.slice(1)) {
      await user.tab();
      expect(document.activeElement).toBe(
        screen.getByRole("checkbox", { name: industry.name }),
      );
    }
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("combobox", { name: "Sort by" }),
    );
    await screen.findByRole("navigation", { name: "Brand pages" });
    for (const name of [
      "Acme Insurance Co.",
      "Umbrella policy was easy to add",
      "2",
      "Next",
    ]) {
      await user.tab();
      expect(document.activeElement).toBe(screen.getByRole("link", { name }));
    }

    await user.keyboard("{Enter}");
    expect(window.location.search).toContain("page=2");
    expect(document.activeElement).toBe(heading());
  });
});
