// One brand, in the reference theme's card markup (`article.card`, `.badge`, `.stars`, `.meta`,
// `.excerpt`); parts the theme never had are `brand-list__*`.
import type { BrandCard as Brand } from "./types";

function Stars({ rating }: { rating: number }) {
  const full = Math.round(rating);
  return (
    <span
      className="stars"
      role="img"
      aria-label={`Rated ${rating.toFixed(1)} out of 5`}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= full ? "star-full" : "star-empty"}>
          {n <= full ? "★" : "☆"}
        </span>
      ))}
      <span className="rating-value">{rating.toFixed(1)}</span>
    </span>
  );
}

export function BrandCard({ brand }: { brand: Brand }) {
  const reviews = `${brand.review_count} ${brand.review_count === 1 ? "review" : "reviews"}`;
  return (
    <article className="card">
      <h3>
        <a href={brand.url}>{brand.name}</a>
      </h3>
      <div className="brand-list__rating">
        {brand.average_rating === null ? (
          <span className="meta">No reviews yet</span>
        ) : (
          <>
            <Stars rating={brand.average_rating} />{" "}
            <span className="meta">({reviews})</span>
          </>
        )}
      </div>
      <div>
        <span className="badge">{brand.industry.name}</span>
      </div>
      {brand.short_description && (
        <p className="excerpt">{brand.short_description}</p>
      )}
      {brand.top_review && (
        <div className="brand-list__top-review">
          <p className="brand-list__top-review-label">Top review</p>
          <p className="brand-list__top-review-title">
            <a href={brand.top_review.url}>{brand.top_review.title}</a>
          </p>
          <p className="brand-list__top-review-snippet">
            {brand.top_review.snippet}
          </p>
        </div>
      )}
    </article>
  );
}
