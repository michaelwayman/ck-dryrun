// Types for the brands-api list response and the brandlist-mount config (docs/contracts/).

export const ORDERINGS = [
  "-average_rating",
  "average_rating",
  "-review_count",
  "review_count",
  "name",
  "-name",
] as const;

export type Ordering = (typeof ORDERINGS)[number];

export function isOrdering(value: unknown): value is Ordering {
  return (ORDERINGS as readonly unknown[]).includes(value);
}

export interface Industry {
  slug: string;
  name: string;
}

export interface TopReview {
  title: string;
  slug: string;
  url: string;
  rating: number;
  snippet: string;
}

export interface BrandCard {
  name: string;
  slug: string;
  url: string;
  industry: Industry;
  short_description: string;
  average_rating: number | null;
  review_count: number;
  top_review: TopReview | null;
}

export interface BrandPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: BrandCard[];
}

// The brands-api error body, `{"error": {...}}`.
export interface ApiErrorBody {
  code: string;
  message: string;
  fields: Record<string, string[]> | null;
}

// A failed load: an API error (`status` is the HTTP status) or a network failure (`status` 0).
export class BrandsApiError extends Error implements ApiErrorBody {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string[]> | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "BrandsApiError";
    this.status = status;
    this.code = body.code;
    this.fields = body.fields;
  }
}

// The mount element's data attributes (brandlist-mount), parsed.
export interface MountConfig {
  apiUrl: string;
  industries: Industry[];
  pageSize: number;
  defaultOrdering: Ordering;
}

// The view state the component owns in the page URL.
export interface ListState {
  industries: string[];
  ordering: Ordering;
  page: number;
}
