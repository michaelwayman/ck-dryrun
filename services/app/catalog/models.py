"""Industries, brands and reviews imported from WordPress (R1). Ratings are computed, not stored."""

from collections.abc import Iterable
from typing import Any, ClassVar

from django.db import models
from django.db.models import Count, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce


class ActiveManager(models.Manager[Any]):
    """The default manager: inactive (soft-deleted) rows are hidden from pages and the API."""

    def get_queryset(self) -> models.QuerySet[Any]:
        return super().get_queryset().filter(is_active=True)


class Industry(models.Model):
    wp_id = models.PositiveBigIntegerField(unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True)

    class Meta:
        ordering = ["name", "pk"]
        verbose_name_plural = "industries"

    def __str__(self) -> str:
        return self.name


class BrandQuerySet(models.QuerySet["Brand"]):
    def with_stats(self) -> BrandQuerySet:
        """Annotate `review_count`, `average_tenths` and `top_review_id` from active reviews.

        Correlated subqueries rather than joins, so other annotations and filters can't inflate
        the counts. `average_tenths` is the mean rating times ten, rounded half-up, in integer
        arithmetic so SQLite and Postgres agree; it is null when the brand has no active reviews.
        """
        reviews = Review.objects.filter(brand=OuterRef("pk")).order_by().values("brand")
        count = Subquery(reviews.annotate(n=Count("pk")).values("n"))
        total = Subquery(reviews.annotate(s=Sum("rating")).values("s"))
        top = Review.objects.filter(brand=OuterRef("pk")).order_by(
            "-rating", "-published_at", "-pk"
        )
        return self.annotate(
            review_count=Coalesce(count, Value(0)),
            # floor((20 * sum + n) / (2 * n)) == round_half_up(10 * sum / n); null when n is null.
            average_tenths=models.ExpressionWrapper(
                (Value(20) * total + count) / (Value(2) * count),
                output_field=models.IntegerField(),
            ),
            top_review_id=Subquery(top.values("pk")[:1]),
        )


class BrandManager(models.Manager["Brand"]):
    """Like ActiveManager, but its querysets have `with_stats()`."""

    def get_queryset(self) -> BrandQuerySet:
        return BrandQuerySet(self.model, using=self._db).filter(is_active=True)

    def with_stats(self) -> BrandQuerySet:
        return self.get_queryset().with_stats()


class Brand(models.Model):
    wp_id = models.PositiveBigIntegerField(unique=True)
    name = models.TextField()
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True)
    industry = models.ForeignKey(Industry, on_delete=models.PROTECT, related_name="brands")
    website_url = models.URLField(max_length=2048, blank=True, default="")
    # Required by R1, but the source allows an empty value (wp-source mock brand 102).
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    headquarters = models.TextField(blank=True, default="")
    seo_title = models.TextField(blank=True, default="")
    seo_description = models.TextField(blank=True, default="")
    short_description = models.TextField(blank=True, default="")
    content = models.TextField(blank=True, default="")
    # The WP plugin's stored average. Kept for reference, never displayed.
    legacy_average_rating = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    # Set only on rows from with_stats() and attach_top_reviews().
    review_count: int
    average_tenths: int | None
    top_review_id: int | None
    top_review: Review | None

    objects: ClassVar[BrandManager] = BrandManager()
    all_objects: ClassVar[models.Manager[Brand]] = models.Manager()

    class Meta:
        base_manager_name = "all_objects"
        ordering = ["name", "pk"]

    def __str__(self) -> str:
        return self.name

    @property
    def average_rating(self) -> float | None:
        """The mean of active ratings to one decimal; needs `with_stats()`."""
        tenths = getattr(self, "average_tenths", None)
        return None if tenths is None else tenths / 10


class Review(models.Model):
    wp_id = models.PositiveBigIntegerField(unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="reviews")
    title = models.TextField()
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True)
    content = models.TextField(blank=True, default="")
    rating = models.PositiveSmallIntegerField()
    # The WP post_author: an opaque reference only the auth service can resolve.
    reviewer_wp_id = models.PositiveBigIntegerField()
    reviewer_name = models.TextField(blank=True, default="")
    reviewer_location = models.TextField(blank=True, default="")
    published_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    objects: ClassVar[models.Manager[Review]] = ActiveManager()
    all_objects: ClassVar[models.Manager[Review]] = models.Manager()

    class Meta:
        base_manager_name = "all_objects"
        ordering = ["-published_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"
            ),
        ]

    def __str__(self) -> str:
        return self.title


def attach_top_reviews(brands: Iterable[Brand]) -> list[Brand]:
    """Set `brand.top_review` (or None) from `with_stats()`'s `top_review_id`, in one query."""
    brands = list(brands)
    ids = [i for b in brands if (i := getattr(b, "top_review_id", None)) is not None]
    reviews = Review.all_objects.in_bulk(ids)
    for brand in brands:
        brand.top_review = reviews.get(getattr(brand, "top_review_id", None))
    return brands
