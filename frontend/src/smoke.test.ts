import { describe, expect, it } from "vitest";

describe("test environment", () => {
  it("provides a DOM", () => {
    document.body.innerHTML = '<section id="brand-list"></section>';

    expect(document.getElementById("brand-list")).not.toBeNull();
  });
});
