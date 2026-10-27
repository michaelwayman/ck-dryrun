from datetime import UTC, datetime

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from catalog.models import Brand, Review, attach_top_reviews
from catalog.tests import factories

pytestmark = pytest.mark.django_db


def stats(brand: Brand) -> Brand:
    return attach_top_reviews([Brand.objects.with_stats().get(pk=brand.pk)])[0]


def test_brand_without_reviews_has_null_average_and_zero_count() -> None:
    brand = stats(factories.brand())

    assert brand.review_count == 0
    assert brand.average_rating is None
    assert brand.top_review is None


@pytest.mark.parametrize(
    ("ratings", "expected"),
    [
        ([5], 5.0),
        ([4, 5], 4.5),
        ([3, 4, 4], 3.7),  # 3.666… rounds up
        ([1, 2, 2, 2, 2, 2, 2, 2], 1.9),  # 1.875 rounds up
        ([1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2], 1.8),  # exactly 1.80
        ([1, 2, 2, 2], 1.8),  # 1.75: half rounds up, not to even
        ([1, 1, 1, 2], 1.3),  # 1.25: half rounds up
    ],
)
def test_average_is_mean_of_ratings_rounded_half_up(ratings: list[int], expected: float) -> None:
    brand = factories.brand()
    for rating in ratings:
        factories.review(brand, rating)

    result = stats(brand)

    assert result.average_rating == expected
    assert result.review_count == len(ratings)


def test_inactive_reviews_are_left_out_of_stats() -> None:
    brand = factories.brand()
    kept = factories.review(brand, 2)
    factories.review(brand, 5, is_active=False)

    result = stats(brand)

    assert (result.review_count, result.average_rating) == (1, 2.0)
    assert result.top_review == kept


def test_top_review_is_highest_rating_then_newest_then_highest_pk() -> None:
    brand = factories.brand()
    when = datetime(2026, 3, 1, tzinfo=UTC)
    factories.review(brand, 4, published_at=datetime(2026, 9, 1, tzinfo=UTC))
    factories.review(brand, 5, published_at=datetime(2026, 1, 1, tzinfo=UTC))
    factories.review(brand, 5, published_at=when)
    tie_newest_highest_pk = factories.review(brand, 5, published_at=when)

    assert stats(brand).top_review == tie_newest_highest_pk


def test_stats_are_not_inflated_by_other_brands_or_joins() -> None:
    one, two = factories.brand(), factories.brand()
    for rating in (1, 2, 3):
        factories.review(one, rating)
    factories.review(two, 5)

    rows = {b.pk: b for b in Brand.objects.with_stats().select_related("industry")}

    assert (rows[one.pk].review_count, rows[one.pk].average_rating) == (3, 2.0)
    assert (rows[two.pk].review_count, rows[two.pk].average_rating) == (1, 5.0)


def test_default_managers_hide_inactive_rows_and_all_objects_keeps_them() -> None:
    active, inactive = factories.brand(), factories.brand(is_active=False)
    hidden_review = factories.review(active, is_active=False)

    assert list(Brand.objects.all()) == [active]
    assert set(Brand.all_objects.all()) == {active, inactive}
    assert list(active.reviews.all()) == []
    assert Review.all_objects.get(pk=hidden_review.pk).brand == active


def test_review_of_an_inactive_brand_still_reaches_its_brand() -> None:
    brand = factories.brand(is_active=False)
    review = factories.review(brand)

    assert Review.all_objects.get(pk=review.pk).brand == brand


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_outside_1_to_5_is_rejected_by_the_database(rating: int) -> None:
    brand = factories.brand()

    with pytest.raises(IntegrityError), transaction.atomic():
        factories.review(brand, rating)


@pytest.mark.parametrize("field", ["slug", "wp_id"])
def test_brand_slug_and_wp_id_are_unique(field: str) -> None:
    first = factories.brand()

    with pytest.raises(IntegrityError), transaction.atomic():
        factories.brand(**{field: getattr(first, field)})


def test_industry_with_brands_cannot_be_deleted() -> None:
    brand = factories.brand()

    with pytest.raises(ProtectedError):
        brand.industry.delete()


def test_deleting_a_brand_deletes_its_reviews() -> None:
    brand = factories.brand()
    factories.review(brand)

    brand.delete()

    assert not Review.all_objects.exists()
