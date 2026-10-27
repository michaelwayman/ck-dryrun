// Compares the compiled scss/main.scss with reference/theme.css: the set of selectors (keyed
// by their @media context) and the set of custom properties with their values. Extra items
// pass only when css-diff.allow.json lists them with a reason. Exits 1 on any other drift.
import { readFileSync } from "node:fs";
import process from "node:process";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import * as sass from "sass";

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

// Whitespace is not structure: collapse runs and drop it inside parentheses and around
// punctuation. Selectors keep the space before "(", after ")" and around ":", which can be a
// descendant combinator.
const squash = (text, punctuation) =>
  text
    .replace(/\s+/g, " ")
    .replace(new RegExp(`\\s*([${punctuation}])\\s*`, "g"), "$1")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .trim();
const normaliseSelector = (selector) => squash(selector, ",>+~");
const normaliseValue = (value) => squash(value, ",:");

function collect(css) {
  const selectors = new Set();
  const properties = new Map();
  postcss.parse(css).walk((node) => {
    if (node.type === "rule") {
      const context = [];
      for (let p = node.parent; p && p.type !== "root"; p = p.parent) {
        if (p.type === "atrule") {
          context.unshift(`@${p.name} ${normaliseValue(p.params)}`);
        }
      }
      for (const selector of node.selectors) {
        selectors.add([...context, normaliseSelector(selector)].join(" "));
      }
    } else if (node.type === "decl" && node.prop.startsWith("--")) {
      properties.set(node.prop, normaliseValue(node.value));
    }
  });
  return { selectors, properties };
}

const globToRegExp = (glob) =>
  new RegExp(
    `^${glob.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*")}$`,
  );

/**
 * Diffs `actual` CSS against `reference` CSS. `allow.selectors` holds globs matched against
 * extra keyed selectors; `allow.customProperties` holds names of extra custom properties.
 */
export function diff(reference, actual, allow = {}) {
  const ref = collect(reference);
  const got = collect(actual);
  const selectorAllow = (allow.selectors ?? []).map((entry) => ({
    ...entry,
    regexp: globToRegExp(entry.match),
  }));
  const propertyAllow = allow.customProperties ?? [];
  const used = new Set();

  const missingSelectors = [...ref.selectors].filter(
    (s) => !got.selectors.has(s),
  );
  const extraSelectors = [...got.selectors].filter((s) => {
    if (ref.selectors.has(s)) return false;
    const entry = selectorAllow.find((e) => e.regexp.test(s));
    if (entry) used.add(entry);
    return !entry;
  });

  const missingProperties = [...ref.properties.keys()].filter(
    (name) => !got.properties.has(name),
  );
  const changedProperties = [...ref.properties]
    .filter(
      ([name, value]) =>
        got.properties.has(name) && got.properties.get(name) !== value,
    )
    .map(([name, value]) => ({
      name,
      expected: value,
      actual: got.properties.get(name),
    }));
  const extraProperties = [...got.properties.keys()].filter((name) => {
    if (ref.properties.has(name)) return false;
    const entry = propertyAllow.find((e) => e.name === name);
    if (entry) used.add(entry);
    return !entry;
  });

  const unusedAllow = [...selectorAllow, ...propertyAllow]
    .filter((entry) => !used.has(entry))
    .map((entry) => entry.match ?? entry.name);

  return {
    missingSelectors,
    extraSelectors,
    missingProperties,
    changedProperties,
    extraProperties,
    unusedAllow,
    ok:
      missingSelectors.length +
        extraSelectors.length +
        missingProperties.length +
        changedProperties.length +
        extraProperties.length ===
      0,
  };
}

function main() {
  const reference = readFileSync(here("../../reference/theme.css"), "utf8");
  const { css } = sass.compile(here("../scss/main.scss"));
  const allow = JSON.parse(readFileSync(here("./css-diff.allow.json"), "utf8"));
  const result = diff(reference, css, allow);

  const report = (label, items) => {
    for (const item of items) console.error(`${label} ${item}`);
  };
  report("missing selector:", result.missingSelectors);
  report("extra selector:", result.extraSelectors);
  report("missing custom property:", result.missingProperties);
  report("extra custom property:", result.extraProperties);
  for (const { name, expected, actual } of result.changedProperties) {
    console.error(
      `changed custom property: ${name}: ${actual} (reference: ${expected})`,
    );
  }
  for (const entry of result.unusedAllow) {
    console.warn(`warning: allow-list entry matched nothing: ${entry}`);
  }
  if (!result.ok) {
    console.error(
      "css-diff: compiled scss/main.scss drifts from reference/theme.css",
    );
    process.exit(1);
  }
  console.log(
    "css-diff: selectors and custom properties match reference/theme.css",
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
