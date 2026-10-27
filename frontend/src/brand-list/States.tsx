// The loading, empty and error states, and the live region that announces each result.
import type { BrandsApiError } from "./types";

const SKELETON_CARDS = 3;

// Static placeholder cards (no animation); the busy region around them carries the state.
export function Loading() {
  return (
    <>
      <p className="brand-list__sr-only">Loading brands…</p>
      <div className="grid" aria-hidden="true">
        {Array.from({ length: SKELETON_CARDS }, (_, i) => (
          <div key={i} className="card brand-list__skeleton">
            <span className="brand-list__skeleton-line" />
            <span className="brand-list__skeleton-line" />
            <span className="brand-list__skeleton-line" />
          </div>
        ))}
      </div>
    </>
  );
}

export function Empty({ onClear }: { onClear: () => void }) {
  return (
    <div className="brand-list__empty">
      <p>No brands match these filters.</p>
      <button type="button" className="brand-list__button" onClick={onClear}>
        Clear filters
      </button>
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: BrandsApiError;
  onRetry: () => void;
}) {
  const message =
    error.code === "not_found"
      ? "That page of brands doesn't exist."
      : "The brands couldn't be loaded.";
  return (
    <div className="brand-list__error" role="alert">
      <p>
        {message} <span className="meta">({error.message})</span>
      </p>
      <button type="button" className="brand-list__button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

// Always in the DOM so screen readers track it; filled only after a successful load.
export function LiveRegion({ count }: { count: number | null }) {
  const text =
    count === null ? "" : `${count} ${count === 1 ? "brand" : "brands"} found.`;
  return (
    <p className="brand-list__sr-only" aria-live="polite">
      {text}
    </p>
  );
}
