"""Template helpers shared by every page: stars, sanitized WP HTML and plain-text snippets."""

import math
from typing import Any
from urllib.parse import urlsplit

import nh3
from django import template
from django.utils.safestring import SafeString, mark_safe

from catalog import text

register = template.Library()

# Roughly wp_kses_post: nh3's default tags (structure, text, lists, tables, images), the
# attributes WP content uses, and only web and mail links. Scripts, styles, iframes, forms and
# every on* handler are dropped; nh3 also removes <script>/<style> content and HTML comments.
_ATTRIBUTES: dict[str, set[str]] = {
    **{tag: set(attrs) for tag, attrs in nh3.ALLOWED_ATTRIBUTES.items()},
    # No `id`: a stored id could collide with page ids such as #brand-list (brandlist-mount).
    "*": {"class", "title", "lang", "dir"},
}
_CLEANER = nh3.Cleaner(
    attributes=_ATTRIBUTES,
    url_schemes={"http", "https", "mailto"},
    link_rel="noopener noreferrer",
)


@register.filter
def sanitize_html(value: str | None) -> SafeString:
    """Stored WordPress HTML, cleaned to the allow-list above and safe to output (T13)."""
    return mark_safe(_CLEANER.clean(value or ""))  # noqa: S308 (nh3 output is the safe form)


@register.filter
def snippet(value: str | None, words: int = text.SNIPPET_WORDS) -> str:
    """Plain-text excerpt of stored HTML; the template escapes it."""
    return text.snippet(value or "", words)


@register.filter
def url_host(value: str) -> str:
    """The host of a URL, as the theme shows brand websites; the URL itself if it has none."""
    try:
        return urlsplit(value).hostname or value
    except ValueError:  # malformed, e.g. "http://[bad"
        return value


@register.filter
def web_href(value: str) -> str:
    """The URL when it is safe as a link (http/https with a host), else "" for plain text."""
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    return value if parts.scheme in {"http", "https"} and parts.hostname else ""


@register.inclusion_tag("catalog/partials/stars.html")
def stars(rating: float | None, show_value: bool = True) -> dict[str, Any]:
    """Five glyphs, floored like the theme's cr_stars(); a missing rating shows as 0.0."""
    value = max(0.0, min(5.0, float(rating or 0)))
    full = math.floor(value)
    return {
        "label": f"{value:.1f}",
        "full": range(full),
        "empty": range(5 - full),
        "show_value": show_value,
    }
