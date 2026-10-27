from collections.abc import Sequence
from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.views import APIView

from api.errors import ApiError, invalid_parameter

MAX_PAGE_SIZE = 50


class BrandPagination(PageNumberPagination):
    """`page` and `page_size` as brands-api says: bad values are 400, a page past the end is 404."""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE

    def paginate_queryset(
        self,
        queryset: QuerySet[Any, Any] | Sequence[Any],
        request: Request,
        view: APIView | None = None,
    ) -> list[Any]:
        page_size = _positive_int(request, "page_size", self.page_size, MAX_PAGE_SIZE)
        number = _positive_int(request, "page", 1)
        paginator = Paginator(queryset, page_size)
        if number > paginator.num_pages:
            raise ApiError("not_found", "Page out of range.", status_code=404)
        self.request = request
        self.page: Page[Any] = paginator.page(number)
        return list(self.page)


def _positive_int(request: Request, name: str, default: int, maximum: int | None = None) -> int:
    raw = request.query_params.get(name)
    if raw is None:
        return default
    value = int(raw) if raw.isascii() and raw.isdigit() else 0
    if value < 1 or (maximum is not None and value > maximum):
        rule = f"an integer from 1 to {maximum}" if maximum else "an integer of at least 1"
        raise invalid_parameter({name: [f"Must be {rule}."]})
    return value
