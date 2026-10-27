from typing import Any

from django.db.models import QuerySet
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response

from api.errors import invalid_parameter
from api.filters import BrandFilter
from api.pagination import BrandPagination
from api.serializers import BrandCardSerializer
from catalog.models import Brand, attach_top_reviews


def brand_cards() -> QuerySet[Brand]:
    return Brand.objects.with_stats().select_related("industry")


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
