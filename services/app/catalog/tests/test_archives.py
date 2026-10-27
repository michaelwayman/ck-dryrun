import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client, override_settings
from pytest_django import DjangoAssertNumQueries

from catalog.models import Industry
from catalog.tests import factories
from catalog.tests.test_pages import titles

pytestmark = pytest.mark.django_db

EXAMPLES = Path(__file__).resolve().parents[4] / "docs/contracts/brandlist-mount/examples"


def example(name: str) -> Any:
    return json.loads((EXAMPLES / name).read_text())


def mount_attributes(html: str) -> dict[str, str | None]:
    found: dict[str, str | None] = {}

    class Parser(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if dict(attrs).get("id") == "brand-list" and not found:
                found.update(attrs)

    Parser().feed(html)
    return found


def page_links(html: str) -> list[str]:
    nav = html.split('<nav class="pagination"', 1)[1].split("</nav>", 1)[0]
    return [h.replace("&amp;", "&") for h in re.findall(r'href="([^"]+)"', nav)]


@pytest.fixture
def seeded_industries() -> dict[str, Industry]:
    """The five industries of mount-attributes.json, created out of display order."""
    rows = example("mount-attributes.json")["data-industries"]
    return {row["slug"]: factories.industry(**row) for row in reversed(rows)}


def seed_brands(industries: dict[str, Industry], count: int) -> None:
    """`count` brands named B00.., cycling through the industries; brand n has n % 5 + 1 stars."""
    slugs = sorted(industries)
    for n in range(count):
        brand = factories.brand(name=f"B{n:02}", industry=industries[slugs[n % len(slugs)]])
        factories.review(brand, n % 5 + 1)


# --- /brand/ (R16, brandlist-mount) ---------------------------------------------------------------


def test_brand_archive_mount_matches_the_contract_example(
    client: Client,
    seeded_industries: dict[str, Industry],
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    expected = example("mount-attributes.json")
    seed_brands(seeded_industries, 1)

    with django_assert_num_queries(3):  # industries, count, page
        html = client.get("/brand/").content.decode()

    attrs = mount_attributes(html)
    assert attrs["id"] == expected["id"]
    assert json.loads(attrs["data-industries"] or "") == expected["data-industries"]
    for key in ("data-api-url", "data-page-size", "data-default-ordering"):
        assert attrs[key] == expected[key]
    assert '<script type="module" src="/static/brandlist/brand-list.js"></script>' in html


@pytest.mark.parametrize("state", example("url-states.json"), ids=lambda s: s["page_url"])
def test_brand_archive_url_states_match_the_api_request(
    client: Client, seeded_industries: dict[str, Industry], state: dict[str, str]
) -> None:
    """Each page URL shows what its brands-api request returns, and links use the normal form."""
    seed_brands(seeded_industries, 40)
    api = client.get(state["api_request"]).json()

    html = client.get(state["page_url"]).content.decode()

    assert titles(html, "card") == [card["name"] for card in api["results"]]
    # Every page link is the normalised URL with only `page` changed (and omitted for page 1).
    normalised = parse_qs(urlsplit(state.get("normalised_page_url", state["page_url"])).query)
    normalised.pop("page", None)
    links = page_links(html)
    assert links
    for link in links:
        query = parse_qs(urlsplit(link).query)
        assert query.pop("page", None) != ["1"]
        assert query == normalised


def test_brand_archive_normalises_invalid_values(
    client: Client, seeded_industries: dict[str, Industry]
) -> None:
    seed_brands(seeded_industries, 40)

    html = client.get(
        "/brand/?industry=telecom&industry=nope&industry=finance&ordering=bogus&page=0&utm=x"
    ).content.decode()

    expected = client.get("/api/brands/?industry=finance&industry=telecom&page_size=12").json()[
        "results"
    ]
    assert titles(html, "card") == [card["name"] for card in expected]
    assert page_links(html) == [
        "/brand/?utm=x&industry=finance&industry=telecom&page=2",
        "/brand/?utm=x&industry=finance&industry=telecom&page=2",
    ]


def test_brand_archive_page_past_the_end_shows_the_last_page(
    client: Client, seeded_industries: dict[str, Industry]
) -> None:
    seed_brands(seeded_industries, 13)

    html = client.get("/brand/?ordering=name&page=9").content.decode()

    assert titles(html, "card") == ["B12"]
    assert page_links(html) == ["/brand/?ordering=name", "/brand/?ordering=name"]


def test_brand_archive_hides_inactive_brands_and_handles_no_results(
    client: Client, seeded_industries: dict[str, Industry]
) -> None:
    factories.brand(name="Gone", industry=seeded_industries["retail"], is_active=False)

    html = client.get("/brand/?industry=retail").content.decode()

    assert titles(html, "card") == []
    assert "No brands found." in html
    assert '<nav class="pagination"' not in html


# --- /review/ (R16) -------------------------------------------------------------------------------


def test_review_archive_paginates_newest_first(
    client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    brand = factories.brand(name="Acme", slug="acme")
    for n in range(14):
        factories.review(brand, title=f"R{n:02}", content="<p>word " * 50 + "</p>")
    factories.review(brand, title="Inactive", is_active=False)

    with django_assert_num_queries(2):
        first = client.get("/review/").content.decode()
    second = client.get("/review/?page=2").content.decode()

    assert titles(first, "review-item") == [f"R{n:02}" for n in range(13, 1, -1)]
    assert titles(second, "review-item") == ["R01", "R00"]
    assert '<a href="/brand/acme/">Acme</a>' in first
    assert "word " * 39 + "word…" in first
    assert page_links(first) == ["/review/?page=2", "/review/?page=2"]
    assert page_links(second) == ["/review/", "/review/"]


# --- 404 (R16) ------------------------------------------------------------------------------------


@override_settings(DEBUG=False)
def test_unknown_url_renders_the_styled_404(client: Client) -> None:
    response = client.get("/no-such-page/")

    html = response.content.decode()
    assert response.status_code == 404
    assert "<h1>Page not found</h1>" in html
    assert '<nav class="site-nav" aria-label="Primary">' in html
    assert '<link rel="stylesheet" href="/static/css/main.css">' in html
