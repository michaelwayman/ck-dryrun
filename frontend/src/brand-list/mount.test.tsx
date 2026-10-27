import { act, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import mountAttributes from "../../../docs/contracts/brandlist-mount/examples/mount-attributes.json";
import { mountBrandList } from "./mount";
import { respond } from "./test-server";

const FALLBACK =
  '<div class="grid"><article class="card">Fallback</article></div>';

function section(overrides: Record<string, string> = {}) {
  const el = document.createElement("section");
  const { id, ...attributes } = mountAttributes;
  el.id = id;
  for (const [name, value] of Object.entries({ ...attributes, ...overrides })) {
    el.setAttribute(
      name,
      typeof value === "string" ? value : JSON.stringify(value),
    );
  }
  el.innerHTML = FALLBACK;
  document.body.append(el);
  return el;
}

afterEach(() => document.body.replaceChildren());

describe("mountBrandList", () => {
  it("replaces the fallback with the component, keeping the section", async () => {
    respond(
      "/api/brands/?ordering=-average_rating&page_size=12",
      "list-default.json",
    );
    const el = section();
    let root: ReturnType<typeof mountBrandList> = null;

    await act(async () => {
      root = mountBrandList();
    });

    expect(root).not.toBeNull();
    expect(document.getElementById("brand-list")).toBe(el);
    expect(el.textContent).not.toContain("Fallback");
    expect(screen.getAllByRole("checkbox")).toHaveLength(5);
    expect(
      await screen.findByRole("link", { name: "Acme Insurance Co." }),
    ).toBeTruthy();
    act(() => root!.unmount());
  });

  it("does nothing without a mount element", () => {
    expect(mountBrandList()).toBeNull();
    expect(document.body.innerHTML).toBe("");
  });

  it.each([
    ["data-industries", "[not json"],
    ["data-page-size", "twelve"],
    ["data-page-size", "51"],
    ["data-default-ordering", "founded_year"],
  ])("leaves the fallback when %s is %s", (name, value) => {
    const el = section({ [name]: value });

    expect(mountBrandList()).toBeNull();
    expect(el.innerHTML).toBe(FALLBACK);
  });
});
