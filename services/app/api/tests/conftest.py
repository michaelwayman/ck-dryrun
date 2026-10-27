import json
from pathlib import Path
from typing import Any

import pytest

from catalog.models import Brand, Industry, Review
from catalog.tests import factories

CONTRACTS = Path(__file__).resolve().parents[4] / "docs/contracts"
EXAMPLES = CONTRACTS / "brands-api/examples"


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / f"{name}.json").read_text())
    return data


def ratings_for(average: float, count: int) -> list[int]:
    """`count` ratings: one 5 (the top review), the rest ≤ 4, whose mean rounds to `average`."""
    rest_total = round(average * count) - 5
    base, extra = divmod(rest_total, count - 1)
    return [5] + [base + 1] * extra + [base] * (count - 1 - extra)


def seed_from_cards(cards: list[dict[str, Any]]) -> None:
    """Generate brands, industries and reviews that reproduce brands-api BrandCards exactly.

    Each top review gets the newest date and the only 5; its content is the snippet's words
    followed by more text, so the API has to cut it back to the same snippet.
    """
    for card in cards:
        industry = Industry.objects.filter(slug=card["industry"]["slug"]).first()
        if industry is None:
            industry = factories.industry(**card["industry"])
        brand = factories.brand(
            name=card["name"],
            slug=card["slug"],
            industry=industry,
            short_description=card["short_description"],
        )
        top = card["top_review"]
        ratings = ratings_for(card["average_rating"], card["review_count"])
        for rating in ratings[1:]:
            factories.review(brand, rating)
        words = top["snippet"].removesuffix("…")
        factories.review(
            brand,
            top["rating"],
            title=top["title"],
            slug=top["slug"],
            content=f"<p>{words}</p><p>Stand-in text past the snippet.</p>",
            published_at=Review.all_objects.order_by("-published_at")[0].published_at,
        )
        assert Brand.objects.with_stats().get(pk=brand.pk).average_rating == card["average_rating"]


@pytest.fixture
def default_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = example("list-default")["response"]["body"]["results"]
    return cards


@pytest.fixture
def seeded(db: None, default_cards: list[dict[str, Any]]) -> None:
    seed_from_cards(default_cards)
