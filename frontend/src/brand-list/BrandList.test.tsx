import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { BrandList } from "./BrandList";
import { CONFIG, respond, visit } from "./test-server";

// list-filter-sort.json is served by the shared handlers: two industries, -review_count, one per
// page, two brands in all.
const FILTER_SORT =
  "?industry=telecom&industry=insurance&ordering=-review_count";
const ONE_PER_PAGE = { ...CONFIG, pageSize: 1 };
const PAGE_2 =
  "/api/brands/?industry=insurance&industry=telecom&ordering=-review_count&page=2&page_size=1";

const search = () => window.location.search;

describe("<BrandList />", () => {
  it("renders the controls from the URL and normalises it", async () => {
    visit(FILTER_SORT);
    render(<BrandList config={ONE_PER_PAGE} />);

    expect(search()).toBe(
      "?industry=insurance&industry=telecom&ordering=-review_count",
    );
    const fieldset = screen.getByRole("group", { name: "Industry" });
    const checked = within(fieldset)
      .getAllByRole("checkbox")
      .map((c) => [c.getAttribute("value"), (c as HTMLInputElement).checked]);
    expect(Object.fromEntries(checked)).toEqual({
      finance: false,
      "home-services": false,
      insurance: true,
      retail: false,
      telecom: true,
    });
    const select = screen.getByRole("combobox", { name: "Sort by" });
    expect(within(select).getAllByRole("option")).toHaveLength(6);
    expect((select as HTMLSelectElement).value).toBe("-review_count");
    const nav = await screen.findByRole("navigation", { name: "Brand pages" });
    expect(within(nav).getByText("1").getAttribute("aria-current")).toBe(
      "page",
    );
    expect(
      within(nav).getByRole("link", { name: "2" }).getAttribute("href"),
    ).toBe(
      "/brand/?industry=insurance&industry=telecom&ordering=-review_count&page=2",
    );
  });

  it("pages, moves focus to the heading, and goes back and forward", async () => {
    respond(PAGE_2, "list-filter-sort.json");
    visit(FILTER_SORT);
    const user = userEvent.setup();
    render(<BrandList config={ONE_PER_PAGE} />);

    await user.click(await screen.findByRole("link", { name: "Next" }));

    expect(search()).toContain("page=2");
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 2 }),
    );
    const nav = await screen.findByRole("navigation", { name: "Brand pages" });
    expect(within(nav).getByText("2").getAttribute("aria-current")).toBe(
      "page",
    );

    await act(async () => window.history.back());
    await waitFor(() => expect(search()).not.toContain("page=2"));
    await waitFor(() =>
      expect(screen.getByText("1").getAttribute("aria-current")).toBe("page"),
    );

    await act(async () => window.history.forward());
    await waitFor(() =>
      expect(screen.getByText("2").getAttribute("aria-current")).toBe("page"),
    );
  });

  it("resets to page 1 and keeps focus when the filter changes", async () => {
    respond(PAGE_2, "list-filter-sort.json");
    respond(
      "/api/brands/?industry=insurance&ordering=-review_count&page_size=1",
      "list-filter-sort.json",
    );
    visit(`${FILTER_SORT}&page=2`);
    const user = userEvent.setup();
    render(<BrandList config={ONE_PER_PAGE} />);

    const telecom = screen.getByRole("checkbox", { name: "Telecom" });
    await user.click(telecom);
    expect(search()).toBe("?industry=insurance&ordering=-review_count");
    expect(document.activeElement).toBe(telecom);
    await screen.findByRole("navigation", { name: "Brand pages" });
  });
});
