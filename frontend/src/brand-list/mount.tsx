// Mounts <BrandList /> into `#brand-list` (brandlist-mount contract), replacing the server-
// rendered fallback. With no mount element, or config it can't read, it leaves the page alone.
import { createRoot, type Root } from "react-dom/client";
import { BrandList } from "./BrandList";
import { isOrdering, type Industry, type MountConfig } from "./types";

// brands-api answers 400 above this, so a larger value is config the component can't use.
const MAX_PAGE_SIZE = 50;

function isIndustry(value: unknown): value is Industry {
  const { slug, name } = (value ?? {}) as Partial<Industry>;
  return typeof slug === "string" && typeof name === "string";
}

export function readConfig(element: HTMLElement): MountConfig | null {
  const { apiUrl, industries, pageSize, defaultOrdering } = element.dataset;
  let parsed: unknown;
  try {
    parsed = JSON.parse(industries ?? "");
  } catch {
    return null;
  }
  const size = Number(pageSize);
  if (
    !apiUrl ||
    !Array.isArray(parsed) ||
    !parsed.every(isIndustry) ||
    !Number.isInteger(size) ||
    size < 1 ||
    size > MAX_PAGE_SIZE ||
    !isOrdering(defaultOrdering)
  ) {
    return null;
  }
  return { apiUrl, industries: parsed, pageSize: size, defaultOrdering };
}

export function mountBrandList(doc: Document = document): Root | null {
  const element = doc.getElementById("brand-list");
  const config = element && readConfig(element);
  if (!element || !config) return null;
  element.replaceChildren();
  const root = createRoot(element);
  root.render(<BrandList config={config} />);
  return root;
}
