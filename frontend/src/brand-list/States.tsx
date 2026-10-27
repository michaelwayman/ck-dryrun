// The loading, empty and error states, and the live region that announces each result.
import type { MouseEvent } from "react";
import type { BrandsApiError } from "./types";

const SKELETON_CARDS = 3;

// Static placeholder cards (no animation); the busy region around them carries the state.
export function Loading() {
  return (
    <>
      <p className="brand-list__sr-only">Loading brands…</p>
      <div className="grid" aria-hidden="true">
        {Array.from({ length: SKELETON_CARDS }, (_, i) => (
          <div key={i} className="card">
            <span className="brand-list__skeleton-line" />
            <span className="brand-list__skeleton-line" />
            <span className="brand-list__skeleton-line" />
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
      <p>
        {onClear ? "No brands match these filters." : "No brands to show yet."}
      </p>
      {onClear && (
        <button type="button" className="brand-list__button" onClick={onClear}>
          Clear filters
        </button>
      )}
    </div>
  );
}

function opensElsewhere(e: MouseEvent) {
  return e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey;
}

export function ErrorState({
  error,
  onRetry,
  firstPage,
}: {
  error: BrandsApiError;
  onRetry: () => void;
  // Page 1 of the same view, offered for a page past the end (brands-api: 404 `not_found`).
  firstPage?: { href: string; onClick: () => void };
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
      {firstPage && error.code === "not_found" && (
        <a
          className="brand-list__button"
          href={firstPage.href}
          onClick={(e) => {
            if (opensElsewhere(e)) return;
            e.preventDefault();
            firstPage.onClick();
          }}
        >
          Go to page 1
        </a>
      )}
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
