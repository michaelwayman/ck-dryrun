"""The server-rendered public pages (R3, R4, R5, R16). Everything shown is active-only."""

import json
from typing import Any
from urllib.parse import urlencode

from django.db.models import F, QuerySet
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from api.filters import DEFAULT_ORDERING, ORDERINGS, BrandFilter
from catalog.models import Brand, Industry, Review
from catalog.pages import paginate

FEATURED_BRANDS = 6
RECENT_REVIEWS = 6
BRANDS_PER_PAGE = 12  # data-page-size, so the fallback grid pages like <BrandList />
REVIEWS_PER_PAGE = 12
# The keys <BrandList /> owns on /brand/ (brandlist-mount); any other key passes through.
BRAND_LIST_KEYS = ("industry", "ordering", "page")


def _brand_cards() -> QuerySet[Brand]:
    return Brand.objects.with_stats().select_related("industry")


def _reviews() -> QuerySet[Review]:
    """Active reviews of active brands, newest first (R3: published_at, then wp_id)."""
    return (
        Review.objects.filter(brand__is_active=True)
        .select_related("brand")
        .order_by("-published_at", "-wp_id")
    )


@require_safe
def home(request: HttpRequest) -> HttpResponse:
    featured = _brand_cards().order_by(F("average_tenths").desc(nulls_last=True), "name", "pk")[
        :FEATURED_BRANDS
    ]
    return render(
        request,
        "catalog/home.html",
        {"featured": featured, "recent": _reviews()[:RECENT_REVIEWS]},
    )


@require_safe
def brand_detail(request: HttpRequest, slug: str) -> HttpResponse:
    brand = get_object_or_404(_brand_cards(), slug=slug)
    reviews = brand.reviews.order_by("-published_at", "-wp_id")
    return render(request, "catalog/brand_detail.html", {"brand": brand, "reviews": reviews})


@require_safe
def review_detail(request: HttpRequest, slug: str) -> HttpResponse:
    review = get_object_or_404(_reviews(), slug=slug)
    return render(request, "catalog/review_detail.html", {"review": review})


def _brand_list_query(params: QueryDict, industries: set[str]) -> tuple[list[str], str]:
    """`industry` and `ordering` normalised as brandlist-mount says the component does."""
    chosen = sorted({slug for slug in params.getlist("industry") if slug in industries})
    ordering = params.get("ordering", "")
    return chosen, ordering if ordering in ORDERINGS else DEFAULT_ORDERING


def _brand_list_url(params: QueryDict, chosen: list[str], ordering: str, page: int) -> str:
    """A /brand/ link in normalised form: defaults omitted, unknown keys kept as they were."""
    query: list[tuple[str, str]] = [
        (key, value)
        for key, values in params.lists()
        if key not in BRAND_LIST_KEYS
        for value in values
    ]
    query += [("industry", slug) for slug in chosen]
    if ordering != DEFAULT_ORDERING:
        query.append(("ordering", ordering))
    if page != 1:
        query.append(("page", str(page)))
    path = reverse("catalog:brand-archive")
    return f"{path}?{urlencode(query)}" if query else path


@require_safe
def brand_archive(request: HttpRequest) -> HttpResponse:
    """/brand/: the <BrandList /> mount over a no-JS grid that reads the same query keys (R16)."""
    industries = list(Industry.objects.all())
    chosen, ordering = _brand_list_query(request.GET, {i.slug for i in industries})
    filterset = BrandFilter({"industry": chosen, "ordering": ordering}, queryset=_brand_cards())
    page, links = paginate(
        filterset.qs,
        BRANDS_PER_PAGE,
        request.GET.get("page"),
        lambda n: _brand_list_url(request.GET, chosen, ordering, n),
    )
    mount: dict[str, Any] = {
        "api_url": reverse("brand-list"),
        "industries": json.dumps(
            [{"slug": i.slug, "name": i.name} for i in industries], separators=(",", ":")
        ),
        "page_size": BRANDS_PER_PAGE,
        "default_ordering": DEFAULT_ORDERING,
    }
    return render(request, "catalog/brand_archive.html", {"page": page, "mount": mount, **links})


@require_safe
def review_archive(request: HttpRequest) -> HttpResponse:
    path = reverse("catalog:review-archive")
    page, links = paginate(
        _reviews(),
        REVIEWS_PER_PAGE,
        request.GET.get("page"),
        lambda n: f"{path}?page={n}" if n != 1 else path,
    )
    return render(request, "catalog/review_archive.html", {"page": page, **links})
