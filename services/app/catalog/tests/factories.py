"""Stand-in rows for tests. Every value is generated; nothing comes from the WP dump."""

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

from catalog.models import Brand, Industry, Review

_ids = itertools.count(1)
_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def industry(**fields: Any) -> Industry:
    n = next(_ids)
    defaults: dict[str, Any] = {"wp_id": n, "name": f"Industry {n}", "slug": f"industry-{n}"}
    return Industry.objects.create(**(defaults | fields))


def brand(**fields: Any) -> Brand:
    n = next(_ids)
    if "industry" not in fields:
        fields["industry"] = industry()
    defaults: dict[str, Any] = {"wp_id": n, "name": f"Brand {n}", "slug": f"brand-{n}"}
    return Brand.all_objects.create(**(defaults | fields))


def review(brand: Brand, rating: int = 3, **fields: Any) -> Review:
    n = next(_ids)
    defaults: dict[str, Any] = {
        "wp_id": n,
        "title": f"Review {n}",
        "slug": f"review-{n}",
        "content": f"<p>Stand-in review {n}.</p>",
        "rating": rating,
        "reviewer_wp_id": 1,
        "reviewer_name": "Test Reviewer",
        "reviewer_location": "Testville, ZZ",
        "published_at": _BASE_TIME + timedelta(days=n),
    }
    return Review.all_objects.create(brand=brand, **(defaults | fields))
