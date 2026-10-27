import django_filters
from django.db.models import F, OrderBy, QuerySet
from django.db.models.functions import Lower

from catalog.models import Brand, Industry

DEFAULT_ORDERING = "-average_rating"
# Each ordering ends with name then pk, so the order is total and paging never skips or repeats.
ORDERINGS: dict[str, list[OrderBy]] = {
    "average_rating": [F("average_tenths").asc(nulls_last=True)],
    "-average_rating": [F("average_tenths").desc(nulls_last=True)],
    "review_count": [F("review_count").asc()],
    "-review_count": [F("review_count").desc()],
    "name": [],
    "-name": [Lower("name").desc(), F("name").desc()],
}
_TIEBREAK = [Lower("name").asc(), F("name").asc(), F("pk").asc()]


class BrandFilter(django_filters.FilterSet):
    industry = django_filters.ModelMultipleChoiceFilter(
        field_name="industry__slug",
        to_field_name="slug",
        queryset=Industry.objects.all(),
        error_messages={"invalid_choice": "Unknown industry: %(value)s."},
    )
    ordering = django_filters.ChoiceFilter(
        choices=[(key, key) for key in ORDERINGS],
        method="filter_ordering",
        error_messages={"invalid_choice": f"Must be one of: {', '.join(ORDERINGS)}."},
    )

    class Meta:
        model = Brand
        fields = ["industry", "ordering"]

    def filter_ordering(self, queryset: QuerySet[Brand], name: str, value: str) -> QuerySet[Brand]:
        return queryset  # applied in filter_queryset, so the default applies when it's absent

    def filter_queryset(self, queryset: QuerySet[Brand]) -> QuerySet[Brand]:
        queryset = super().filter_queryset(queryset)
        key = self.form.cleaned_data.get("ordering") or DEFAULT_ORDERING
        return queryset.order_by(*ORDERINGS[key], *_TIEBREAK)
