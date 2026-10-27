from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import Brand, Review
from catalog.text import snippet


class IndustryRefSerializer(serializers.Serializer[object]):
    slug = serializers.CharField()
    name = serializers.CharField()


class TopReviewSerializer(serializers.Serializer[Review]):
    title = serializers.CharField()
    slug = serializers.CharField()
    url = serializers.SerializerMethodField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    snippet = serializers.SerializerMethodField()

    def get_url(self, review: Review) -> str:
        return f"/review/{review.slug}/"

    def get_snippet(self, review: Review) -> str:
        return snippet(review.content)


class BrandCardSerializer(serializers.Serializer[Brand]):
    """A brand from `Brand.objects.with_stats()` after `attach_top_reviews()`."""

    name = serializers.CharField()
    slug = serializers.CharField()
    url = serializers.SerializerMethodField()
    industry = IndustryRefSerializer()
    short_description = serializers.CharField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(min_value=0)
    top_review = TopReviewSerializer(allow_null=True)

    def get_url(self, brand: Brand) -> str:
        return f"/brand/{brand.slug}/"

    @extend_schema_field(serializers.FloatField(allow_null=True, min_value=1, max_value=5))
    def get_average_rating(self, brand: Brand) -> float | None:
        return brand.average_rating


class StrictCharField(serializers.CharField):
    """A CharField that refuses numbers and booleans instead of converting them to text."""

    default_error_messages = {"invalid": "Must be a string."}

    def to_internal_value(self, data: object) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class ShortDescriptionSerializer(serializers.Serializer[Brand]):
    short_description = StrictCharField(max_length=500, allow_blank=True, trim_whitespace=True)
