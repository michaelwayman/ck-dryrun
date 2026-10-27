import { describe, expect, it } from "vitest";
import { diff } from "./css-diff.mjs";

const reference = `
:root { --color-bg: #f7f7f5; --shadow: 0 2px 8px rgba(0,0,0,0.06); }
html, body { margin: 0; }
.card .meta { color: var(--color-bg); }
@media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
`;

describe("diff", () => {
  it("ignores whitespace, selector-list splitting and declaration values", () => {
    const actual = `
:root {
  --color-bg: #f7f7f5;
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
html,
body { padding: 0; }
.card  .meta { color: red; }
@media (max-width:640px) {
  .grid { display: block; }
}
`;
    expect(diff(reference, actual).ok).toBe(true);
  });

  it("reports missing and extra selectors, keyed by @media context", () => {
    const actual = `
:root { --color-bg: #f7f7f5; --shadow: 0 2px 8px rgba(0,0,0,0.06); }
html, body {}
.card .meta {}
.grid {}
`;
    const result = diff(reference, actual);
    expect(result.ok).toBe(false);
    expect(result.missingSelectors).toEqual(["@media (max-width:640px) .grid"]);
    expect(result.extraSelectors).toEqual([".grid"]);
  });

  it("reports missing, changed and extra custom properties", () => {
    const actual = `
:root { --color-bg: #fff; --color-new: red; }
html, body {}
.card .meta {}
@media (max-width: 640px) { .grid {} }
`;
    const result = diff(reference, actual);
    expect(result.missingProperties).toEqual(["--shadow"]);
    expect(result.changedProperties).toEqual([
      { name: "--color-bg", expected: "#f7f7f5", actual: "#fff" },
    ]);
    expect(result.extraProperties).toEqual(["--color-new"]);
  });

  it("passes allow-listed extras and lists entries that matched nothing", () => {
    const actual = `${reference}
:root { --color-new: red; }
.brand-list__item:focus-visible {}
`;
    const result = diff(reference, actual, {
      selectors: [
        { match: "*:focus-visible*", reason: "focus" },
        { match: "@media*prefers-reduced-motion*", reason: "motion" },
      ],
      customProperties: [{ name: "--color-new", reason: "new token" }],
    });
    expect(result.ok).toBe(true);
    expect(result.unusedAllow).toEqual(["@media*prefers-reduced-motion*"]);
  });
});
