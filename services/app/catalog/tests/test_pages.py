import re
from datetime import UTC, datetime

import pytest
from django.test import Client
from pytest_django import DjangoAssertNumQueries

from catalog.tests import factories

pytestmark = pytest.mark.django_db


def titles(html: str, cls: str) -> list[str]:
    """The link text of each `<h3>` inside an `article.<cls>`, in page order."""
    blocks = re.findall(rf'<article class="{cls}">(.*?)</article>', html, re.S)
    return [re.findall(r"<h3>.*?>([^<]+)</a>\s*</h3>", b, re.S)[0] for b in blocks]


def section(html: str, heading_id: str) -> str:
    return html.split(f'id="{heading_id}"', 1)[1].split("</section>", 1)[0]


# --- layout ---------------------------------------------------------------------------------------


def test_layout_links_the_stylesheet_and_the_primary_nav(client: Client) -> None:
    html = client.get("/").content.decode()

    assert '<link rel="stylesheet" href="/static/css/main.css">' in html
    nav = html.split('<nav class="site-nav" aria-label="Primary">', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'<a href="([^"]+)">(\w+)</a>', nav) == [
        ("/", "Home"),
        ("/brand/", "Brands"),
        ("/review/", "Reviews"),
    ]
    assert '<main id="main">' in html


# --- home (R3) ------------------------------------------------------------------------------------


def test_home_features_six_brands_by_computed_average(
    client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    ratings = {"Alpha": [3], "Bravo": [5, 4], "Charlie": [5, 4], "Delta": [], "Echo": [1]}
    ratings |= {"Foxtrot": [2], "Golf": [4], "Hidden": [5]}
    for name, values in ratings.items():
        brand = factories.brand(name=name, is_active=name != "Hidden")
        for value in values:
            factories.review(brand, value)

    with django_assert_num_queries(2):
        html = client.get("/").content.decode()

    featured = section(html, "featured-brands")
    # Bravo and Charlie tie on 4.5 and fall back to name; Delta (no reviews) and Echo drop off.
    assert titles(featured, "card") == ["Bravo", "Charlie", "Golf", "Alpha", "Foxtrot", "Echo"]
    assert 'aria-label="Rating: 4.5 out of 5"' in featured


def test_home_lists_six_newest_reviews_with_brand_title_stars_and_byline(
    client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    brand = factories.brand(name="Acme", slug="acme")
    hidden = factories.brand(is_active=False)
    same_time = datetime(2100, 1, 1, tzinfo=UTC)
    for n in range(7):
        factories.review(brand, title=f"Old {n}")
    factories.review(brand, title="Tie low", wp_id=9001, published_at=same_time)
    factories.review(brand, title="Tie high", wp_id=9002, published_at=same_time)
    factories.review(brand, title="Inactive", is_active=False, published_at=same_time)
    factories.review(hidden, title="Hidden brand", published_at=same_time)
    factories.review(
        brand,
        title="Newest",
        slug="newest",
        rating=2,
        content="<p>Plenty to say <script>x()</script>here.</p>",
        reviewer_name="Pat",
        reviewer_location="Nowhere, ZZ",
        published_at=datetime(2100, 2, 1, tzinfo=UTC),
    )

    with django_assert_num_queries(2):
        html = client.get("/").content.decode()

    recent = section(html, "recent-reviews")
    assert titles(recent, "card") == ["Newest", "Tie high", "Tie low", "Old 6", "Old 5", "Old 4"]
    first = recent.split("</article>", 1)[0]
    assert '<a href="/brand/acme/">Acme</a>' in first
    assert '<a href="/review/newest/">Newest</a>' in first
    assert 'aria-label="Rating: 2.0 out of 5"' in first
    assert '<p class="excerpt">Plenty to say here.</p>' in first
    assert "— Pat, Nowhere, ZZ" in first


# --- brand detail (R4) ----------------------------------------------------------------------------


def test_brand_page_shows_details_content_and_reviews_newest_first(
    client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    brand = factories.brand(
        name="Acme",
        slug="acme",
        industry=factories.industry(name="Telecom"),
        headquarters="Springfield, ZZ",
        founded_year=1999,
        website_url="https://www.acme.example/plans?x=1",
        seo_title="Acme reviews and ratings",
        seo_description="What customers say about Acme.",
        content="<p>About Acme.</p><script>steal()</script>",
    )
    factories.review(brand, 4, title="Older", content="<p>Fine <b>overall</b>.</p>")
    factories.review(brand, 5, title="Newer")
    factories.review(brand, 1, title="Gone", is_active=False)

    with django_assert_num_queries(2):
        response = client.get("/brand/acme/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "<title>Acme reviews and ratings</title>" in html
    assert '<meta name="description" content="What customers say about Acme.">' in html
    assert '<span class="badge">Telecom</span>' in html
    assert "<h1>Acme</h1>" in html
    assert 'aria-label="Rating: 4.5 out of 5"' in html
    assert "(2 reviews)" in html
    assert "<strong>HQ:</strong> Springfield, ZZ" in html
    assert "<strong>Founded:</strong> 1999" in html
    assert (
        '<a href="https://www.acme.example/plans?x=1" rel="nofollow noopener" target="_blank">'
        "www.acme.example</a>"
    ) in html
    assert "<p>About Acme.</p>" in html
    assert "steal" not in html
    assert titles(html, "review-item") == ["Newer", "Older"]
    assert "<p>Fine <b>overall</b>.</p>" in html


def test_brand_page_without_seo_fields_or_reviews(client: Client) -> None:
    factories.brand(name="Plain & Simple", slug="plain")

    html = client.get("/brand/plain/").content.decode()

    assert "<title>Plain &amp; Simple</title>" in html
    assert 'name="description"' not in html
    assert "(0 reviews)" in html
    assert "No reviews yet." in html
    assert "Website:" not in html


@pytest.mark.parametrize("slug", ["missing", "inactive"])
def test_brand_page_404s_for_unknown_or_inactive(client: Client, slug: str) -> None:
    factories.brand(slug="inactive", is_active=False)

    assert client.get(f"/brand/{slug}/").status_code == 404


# --- review detail (R5) ---------------------------------------------------------------------------


def test_review_page_shows_back_link_byline_and_sanitized_body(
    client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    brand = factories.brand(name="Acme", slug="acme")
    factories.review(
        brand,
        4,
        title="Solid service",
        slug="solid",
        content='<p>Good.</p><script>document.cookie</script><p onmouseover="x()">More.</p>',
        reviewer_name="Pat",
        reviewer_location="Nowhere, ZZ",
        published_at=datetime(2026, 3, 9, 12, tzinfo=UTC),
    )

    with django_assert_num_queries(1):
        response = client.get("/review/solid/")

    html = response.content.decode()
    assert response.status_code == 200
    assert '<a href="/brand/acme/">&larr; Acme</a>' in html
    assert "<h1>Solid service</h1>" in html
    assert 'aria-label="Rating: 4.0 out of 5"' in html
    assert "Pat, Nowhere, ZZ" in html
    assert ">March 9, 2026</time>" in html
    assert "<p>Good.</p>" in html
    assert "<p>More.</p>" in html
    assert "<script" not in html.split("<main", 1)[1]
    assert "document.cookie" not in html
    assert "onmouseover" not in html


@pytest.mark.parametrize("slug", ["missing", "inactive", "inactive-brand"])
def test_review_page_404s_for_unknown_inactive_or_inactive_brand(client: Client, slug: str) -> None:
    factories.review(factories.brand(), slug="inactive", is_active=False)
    factories.review(factories.brand(is_active=False), slug="inactive-brand")

    assert client.get(f"/review/{slug}/").status_code == 404
