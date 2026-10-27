from typing import Any

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions, generics, views
from rest_framework.request import Request
from rest_framework.response import Response
from tokenauth import Role
from tokenauth.drf import BearerTokenAuthentication, HasRole

from api.errors import ApiError, invalid_parameter
from api.filters import DEFAULT_ORDERING, ORDERINGS, BrandFilter
from api.pagination import MAX_PAGE_SIZE, BrandPagination
from api.schema import ErrorSerializer
from api.serializers import BrandCardSerializer, ShortDescriptionSerializer
from catalog.models import Brand, attach_top_reviews

EDITABLE_FIELDS = frozenset(ShortDescriptionSerializer().fields)


def brand_cards() -> QuerySet[Brand]:
    return Brand.objects.with_stats().select_related("industry")


LIST_PARAMETERS = [
    OpenApiParameter(
        "page",
        {"type": "integer", "minimum": 1, "default": 1},
        description="1-based. A page past the last one is 404.",
    ),
    OpenApiParameter(
        "page_size",
        {"type": "integer", "minimum": 1, "maximum": MAX_PAGE_SIZE, "default": 12},
        description=f"1 to {MAX_PAGE_SIZE}; more is 400.",
    ),
    OpenApiParameter(
        "industry",
        str,
        many=True,
        explode=True,
        description="Industry slug, repeatable: brands in any of them. An unknown slug is 400.",
    ),
    OpenApiParameter(
        "ordering",
        str,
        enum=list(ORDERINGS),
        default=DEFAULT_ORDERING,
        description="Then name, then pk. A null average_rating sorts last both ways.",
    ),
]


@extend_schema(
    parameters=LIST_PARAMETERS,
    responses={200: BrandCardSerializer(many=True), 400: ErrorSerializer, 404: ErrorSerializer},
)
class BrandListView(generics.ListAPIView[Brand]):
    """GET /api/brands/: public, so it reads no credentials at all."""

    serializer_class = BrandCardSerializer
    pagination_class = BrandPagination
    authentication_classes = ()
    permission_classes = ()

    def get_queryset(self) -> QuerySet[Brand]:
        return brand_cards()

    def filter_queryset(self, queryset: QuerySet[Brand, Any]) -> QuerySet[Brand, Any]:
        filterset = BrandFilter(self.request.query_params, queryset=queryset, request=self.request)
        if not filterset.is_valid():
            raise invalid_parameter({k: [str(m) for m in v] for k, v in filterset.errors.items()})
        return filterset.qs

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        page = attach_top_reviews(self.paginate_queryset(queryset) or [])
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class BrandDetailView(views.APIView):
    """PATCH /api/brands/<slug>/: editors change a brand's short description (R13).

    Tokens are verified locally by tokenauth against AUTH_PUBLIC_KEYS; auth is never called.
    Errors come in the contract's order: 401, 403, 404, then 400.
    """

    http_method_names = ["patch", "options"]
    authentication_classes = (BearerTokenAuthentication,)
    permission_classes = (HasRole(Role.EDITOR),)

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        # DRF checks credentials before it looks for a handler; a wrong method is 405 regardless.
        method = request.method or ""
        if method.upper() not in self.allowed_methods:
            raise exceptions.MethodNotAllowed(method)
        super().initial(request, *args, **kwargs)

    @extend_schema(
        request=ShortDescriptionSerializer,
        responses={
            200: BrandCardSerializer,
            **dict.fromkeys([400, 401, 403, 404, 405], ErrorSerializer),
        },
        parameters=[OpenApiParameter("slug", OpenApiTypes.STR, OpenApiParameter.PATH)],
    )
    def patch(self, request: Request, slug: str) -> Response:
        brand = Brand.objects.filter(slug=slug).first()
        if brand is None:
            raise ApiError("not_found", "Brand not found.", status_code=404)
        body = request.data
        if not isinstance(body, dict):
            raise ApiError("invalid_body", "Body must be a JSON object.")
        unknown = sorted(set(body) - EDITABLE_FIELDS)
        if unknown:
            raise ApiError(
                "unknown_field",
                "Only short_description may be changed.",
                {name: ["Unknown field."] for name in unknown},
            )
        serializer = ShortDescriptionSerializer(data=body)
        if not serializer.is_valid():
            fields = {k: [str(m) for m in v] for k, v in serializer.errors.items()}
            raise ApiError("invalid_body", "Invalid request body.", fields)
        brand.short_description = serializer.validated_data["short_description"]
        brand.save(update_fields=["short_description"])
        card = attach_top_reviews([brand_cards().get(pk=brand.pk)])[0]
        return Response(BrandCardSerializer(card).data)
