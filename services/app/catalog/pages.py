"""Page-number links for the server-rendered archives, in the brandlist-mount URL form."""

from collections.abc import Callable, Sequence
from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import QuerySet


def page_number(raw: str | None) -> int:
    """`page` as brandlist-mount normalises it: anything but a positive integer is 1."""
    if raw and raw.isascii() and raw.isdigit() and int(raw) >= 1:
        return int(raw)
    return 1


def paginate(
    items: QuerySet[Any, Any] | Sequence[Any],
    per_page: int,
    raw_page: str | None,
    url: Callable[[int], str],
) -> tuple[Page[Any], dict[str, Any]]:
    """The requested page (a page past the end shows the last one) and the pagination context."""
    paginator = Paginator(items, per_page)
    page = paginator.page(min(page_number(raw_page), paginator.num_pages))
    links = {
        "pages": [
            {"number": n, "url": url(n), "current": n == page.number} for n in paginator.page_range
        ],
        "previous_url": url(page.previous_page_number()) if page.has_previous() else None,
        "next_url": url(page.next_page_number()) if page.has_next() else None,
    }
    return page, links
