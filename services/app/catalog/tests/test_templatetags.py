import pytest
from django.template import Context, Template

from catalog.templatetags.catalog_tags import sanitize_html, url_host


def render(source: str, **context: object) -> str:
    return Template("{% load catalog_tags %}" + source).render(Context(context))


@pytest.mark.parametrize(
    ("rating", "label", "full"),
    [(4.5, "4.5", 4), (3.7, "3.7", 3), (5, "5.0", 5), (1, "1.0", 1), (None, "0.0", 0)],
)
def test_stars_floor_the_glyphs_and_label_the_value(
    rating: float | None, label: str, full: int
) -> None:
    html = render("{% stars rating %}", rating=rating)

    assert html.startswith(f'<span class="stars" role="img" aria-label="Rating: {label} out of 5">')
    assert html.count('<span class="star-full" aria-hidden="true">') == full
    assert html.count('<span class="star-empty" aria-hidden="true">') == 5 - full
    assert f'<span class="rating-value" aria-hidden="true">{label}</span>' in html


def test_stars_can_hide_the_value() -> None:
    assert "rating-value" not in render("{% stars 3 False %}")


def test_sanitize_strips_scripts_handlers_and_unsafe_urls() -> None:
    html = sanitize_html(
        '<p onclick="steal()">Hi <script>alert(1)</script><a href="javascript:alert(1)">x</a>'
        '<img src="https://example.test/a.png" onerror="steal()"><!-- wp:paragraph --></p>'
        "<style>p{}</style><iframe src='https://example.test'></iframe>"
    )

    assert "script" not in html
    assert "alert" not in html
    assert "on" + "click" not in html
    assert "onerror" not in html
    assert "javascript:" not in html
    assert "iframe" not in html
    assert "<!--" not in html
    assert "<style" not in html
    assert '<img src="https://example.test/a.png">' in html


def test_sanitize_keeps_post_markup_and_marks_links() -> None:
    html = sanitize_html(
        '<h2 class="wp-block-heading">Plans</h2><ul><li><strong>Fast</strong></li></ul>'
        '<p><a href="https://example.test/" title="t">site</a> '
        '<a href="mailto:a@example.test">m</a></p>'
    )

    assert '<h2 class="wp-block-heading">Plans</h2>' in html
    assert "<ul><li><strong>Fast</strong></li></ul>" in html
    assert '<a href="https://example.test/" title="t" rel="noopener noreferrer">site</a>' in html
    assert 'href="mailto:a@example.test"' in html


def test_sanitize_output_is_not_escaped_again() -> None:
    assert render("{{ html|sanitize_html }}", html="<p>a &amp; b</p>") == "<p>a &amp; b</p>"


def test_snippet_filter_cuts_plain_text() -> None:
    assert render("{{ html|snippet:3 }}", html="<p>one <b>two</b> three four</p>") == (
        "one two three…"
    )


@pytest.mark.parametrize(
    ("url", "host"),
    [("https://www.example.test/path?q=1", "www.example.test"), ("not a url", "not a url")],
)
def test_url_host(url: str, host: str) -> None:
    assert url_host(url) == host
