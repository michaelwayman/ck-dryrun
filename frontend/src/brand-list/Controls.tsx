// The filter, sort and pager. Pager links carry real hrefs, so they also open in a new tab.
import { useId, type MouseEvent } from "react";
import { hrefFor } from "./url-state";
import {
  ORDERINGS,
  isOrdering,
  type ListState,
  type MountConfig,
  type Ordering,
} from "./types";

const ORDERING_LABELS: Record<Ordering, string> = {
  "-average_rating": "Highest rated",
  average_rating: "Lowest rated",
  "-review_count": "Most reviewed",
  review_count: "Fewest reviews",
  name: "Name, A to Z",
  "-name": "Name, Z to A",
};

interface FiltersProps {
  config: MountConfig;
  state: ListState;
  onChange: (industries: string[]) => void;
}

export function Filters({ config, state, onChange }: FiltersProps) {
  const toggle = (slug: string, checked: boolean) =>
    onChange(
      checked
        ? [...state.industries, slug]
        : state.industries.filter((s) => s !== slug),
    );
  return (
    <fieldset className="brand-list__filters">
      <legend className="brand-list__legend">Industry</legend>
      {config.industries.map((industry) => (
        <label key={industry.slug} className="brand-list__option">
          <input
            type="checkbox"
            name="industry"
            value={industry.slug}
            checked={state.industries.includes(industry.slug)}
            onChange={(e) => toggle(industry.slug, e.target.checked)}
          />{" "}
          {industry.name}
        </label>
      ))}
    </fieldset>
  );
}

interface SortProps {
  ordering: Ordering;
  onChange: (ordering: Ordering) => void;
}

export function Sort({ ordering, onChange }: SortProps) {
  const id = useId();
  return (
    <div className="brand-list__sort">
      <label htmlFor={id}>Sort by</label>
      <select
        id={id}
        name="ordering"
        value={ordering}
        onChange={(e) => {
          if (isOrdering(e.target.value)) onChange(e.target.value);
        }}
      >
        {ORDERINGS.map((value) => (
          <option key={value} value={value}>
            {ORDERING_LABELS[value]}
          </option>
        ))}
      </select>
    </div>
  );
}

interface PagerProps {
  config: MountConfig;
  state: ListState;
  count: number;
  onPage: (page: number) => void;
}

function opensElsewhere(e: MouseEvent) {
  return e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey;
}

export function Pager({ config, state, count, onPage }: PagerProps) {
  const pages = Math.ceil(count / config.pageSize);
  if (pages <= 1) return null;
  const link = (page: number, label: string, className = "page-numbers") => (
    <a
      key={label}
      className={className}
      href={hrefFor({ ...state, page }, config)}
      onClick={(e) => {
        if (opensElsewhere(e)) return;
        e.preventDefault();
        onPage(page);
      }}
    >
      {label}
    </a>
  );
  return (
    <nav className="pagination" aria-label="Brand pages">
      {state.page > 1 && link(state.page - 1, "Previous", "prev page-numbers")}
      {Array.from({ length: pages }, (_, i) => i + 1).map((page) =>
        page === state.page ? (
          <span key={page} className="page-numbers current" aria-current="page">
            {page}
          </span>
        ) : (
          link(page, String(page))
        ),
      )}
      {state.page < pages && link(state.page + 1, "Next", "next page-numbers")}
    </nav>
  );
}
