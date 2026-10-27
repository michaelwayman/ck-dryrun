// The loading, empty and error states, and the live region that announces each result.
import type { BrandsApiError } from "./types";

const SKELETON_CARDS = 3;

// "1 brand", "12 brands": shared by the visible heading and the live region.
export function brandCount(count: number) {
  return `${count} ${count === 1 ? "brand" : "brands"}`;
}

// Static placeholder cards (no animation) shaped like a brand card: name, rating, badge, two
// lines of excerpt and the top review. The busy region around them carries the state.
export function Loading() {
  return (
    <>
      <p className="brand-list__sr-only">Loading brands…</p>
      <div className="grid" aria-hidden="true">
        {Array.from({ length: SKELETON_CARDS }, (_, i) => (
          <div key={i} className="card brand-list__skeleton">
            <span className="brand-list__skeleton-line brand-list__skeleton-line--title" />
            <span className="brand-list__skeleton-line brand-list__skeleton-line--rating" />
            <span className="brand-list__skeleton-line brand-list__skeleton-line--pill" />
            <span className="brand-list__skeleton-line" />
            <span className="brand-list__skeleton-line brand-list__skeleton-line--short" />
            <span className="brand-list__skeleton-block" />
          </div>
        ))}
      </div>
    </>
  );
}

// Without `onClear` nothing is filtered, so there is nothing to clear.
export function Empty({ onClear }: { onClear?: () => void }) {
  return (
    <div className="brand-list__empty">
      <p className="brand-list__state-title">No brands match these filters.</p>
      {onClear && (
        <button type="button" className="brand-list__button" onClick={onClear}>
          Clear filters
        </button>
      )}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  firstPageHref,
}: {
  error: BrandsApiError;
  onRetry: () => void;
  // Page 1 of the same view, offered for a page past the end (brands-api: 404 `not_found`).
  firstPageHref?: string;
}) {
  const message =
    error.code === "not_found"
      ? "That page of brands doesn't exist."
      : "The brands couldn't be loaded.";
  return (
    <div className="brand-list__error" role="alert">
      <p className="brand-list__state-title">{message}</p>
      <button type="button" className="brand-list__button" onClick={onRetry}>
        Retry
      </button>
      {firstPageHref && error.code === "not_found" && (
        <a
          className="brand-list__button brand-list__button--secondary"
          href={firstPageHref}
        >
          Go to page 1
        </a>
      )}
    </div>
  );
}

// Always in the DOM so screen readers track it; filled only after a successful load.
export function LiveRegion({ count }: { count: number | null }) {
  const text = count === null ? "" : `${brandCount(count)} found.`;
  return (
    <p className="brand-list__sr-only" aria-live="polite">
      {text}
    </p>
  );
}
