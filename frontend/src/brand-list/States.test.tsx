import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { configureAxe } from "vitest-axe";
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
    expect(liveRegion().textContent).toBe("");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("success: cards, stars as images, and the count announced", async () => {
    respond(DEFAULT_REQUEST, "list-default.json");
    const { container } = render(<BrandList config={CONFIG} />);

    await screen.findAllByRole("article");
    expect(results().getAttribute("aria-busy")).toBe("false");
    expect(liveRegion().textContent).toBe("5 brands found.");
    expect(
      screen.getByRole("img", { name: "Rated 3.9 out of 5" }),
    ).toBeTruthy();
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
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(window.location.search).toBe("");
    expect(await screen.findAllByRole("article")).toHaveLength(5);
  });

  it("error: an alert whose Retry repeats the request", async () => {
    respond(PAGE_9_REQUEST, "list-page-out-of-range.json");
    const requests = countRequests(PAGE_9_REQUEST);
    visit("?page=9");
    const user = userEvent.setup();
    const { container } = render(<BrandList config={CONFIG} />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Page out of range.");
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(requests()).toBe(2));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("error: a network failure also offers Retry", async () => {
    server.use(http.get("*/api/brands/", () => HttpResponse.error()));
    render(<BrandList config={CONFIG} />);

    expect((await screen.findByRole("alert")).textContent).toContain(
      "couldn't be loaded",
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("brands without reviews say so instead of showing stars", async () => {
    server.use(
      http.get("*/api/brands/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              name: "Stand-in Brand",
              slug: "stand-in-brand",
              url: "/brand/stand-in-brand/",
              industry: { slug: "retail", name: "Retail" },
              short_description: "",
              average_rating: null,
              review_count: 0,
              top_review: null,
            },
          ],
        }),
      ),
    );
    render(<BrandList config={CONFIG} />);

    expect(await screen.findByText("No reviews yet")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });
});

describe("<BrandList /> by keyboard", () => {
  it("reaches and operates every control", async () => {
    // list-filter-sort.json (shared handlers): two brands, one per page.
    visit("?industry=insurance&industry=telecom&ordering=-review_count");
    respond(
      "/api/brands/?industry=insurance&industry=telecom&ordering=-review_count&page=2&page_size=1",
      "list-filter-sort.json",
    );
    respond(
      "/api/brands/?industry=finance&industry=insurance&industry=telecom&ordering=-review_count&page_size=1",
      "list-filter-sort.json",
    );
    const user = userEvent.setup();
    render(<BrandList config={{ ...CONFIG, pageSize: 1 }} />);
    await screen.findByRole("navigation", { name: "Brand pages" });

    for (const industry of CONFIG.industries) {
      await user.tab();
      expect(document.activeElement).toBe(
        screen.getByRole("checkbox", { name: industry.name }),
      );
    }
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("combobox", { name: "Sort by" }),
    );
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
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { name: "Results" }),
    );

    // Back from the heading: the sort, then the checkboxes in reverse.
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(
      screen.getByRole("combobox", { name: "Sort by" }),
    );
    for (let i = 0; i < CONFIG.industries.length; i++) {
      await user.tab({ shift: true });
    }
    expect(document.activeElement).toBe(
      screen.getByRole("checkbox", { name: "Finance" }),
    );
    await user.keyboard(" ");
    expect(window.location.search).toBe(
      "?industry=finance&industry=insurance&industry=telecom&ordering=-review_count",
    );
  });
});
