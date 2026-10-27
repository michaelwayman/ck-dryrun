import itertools
import random
from typing import Any
from urllib.parse import urlencode

import pytest
from django.test import Client

from api.filters import ORDERINGS
from api.tests.conftest import example
from catalog.models import Brand
from catalog.tests import factories

pytestmark = pytest.mark.django_db
HOST = "localhost:8000"  # the host the examples' absolute `next` links use


def get(client: Client, query: dict[str, Any]) -> Any:
    return client.get(f"/api/brands/?{urlencode(query, doseq=True)}", headers={"host": HOST})


@pytest.mark.parametrize(
    "name",
    [
        "list-default",
        "list-filter-sort",
        "list-empty",
        "list-invalid-ordering",
        "list-unknown-industry",
        "list-page-out-of-range",
    ],
)
def test_list_examples(client: Client, seeded: None, name: str) -> None:
    ex = example(name)
    if name == "list-empty":  # its note: every Retail brand was deactivated by a re-import
        Brand.objects.filter(industry__slug="retail").update(is_active=False)

    response = get(client, ex["request"]["query"])

    assert response.status_code == ex["response"]["status"]
    assert response.json() == ex["response"]["body"]


def test_list_is_public_and_ignores_any_authorization_header(client: Client, seeded: None) -> None:
    response = client.get("/api/brands/", headers={"authorization": "Bearer not-a-token"})

    assert response.status_code == 200


def test_previous_link_on_the_last_page(client: Client, seeded: None) -> None:
    body = get(client, {"page": 3, "page_size": 2}).json()

    assert body["next"] is None
    assert body["previous"] == f"http://{HOST}/api/brands/?page=2&page_size=2"
    assert len(body["results"]) == 1


@pytest.mark.parametrize(
    ("query", "field", "message"),
    [
        ({"page_size": "51"}, "page_size", "Must be an integer from 1 to 50."),
        ({"page_size": "0"}, "page_size", "Must be an integer from 1 to 50."),
        ({"page_size": "ten"}, "page_size", "Must be an integer from 1 to 50."),
        ({"page": "0"}, "page", "Must be an integer of at least 1."),
        ({"page": "-1"}, "page", "Must be an integer of at least 1."),
        ({"page": "last"}, "page", "Must be an integer of at least 1."),
        ({"industry": ["insurance", "pets"]}, "industry", "Unknown industry: pets."),
    ],
)
def test_bad_parameters_are_400_invalid_parameter(
    client: Client, seeded: None, query: dict[str, Any], field: str, message: str
) -> None:
    response = get(client, query)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_parameter",
            "message": "Invalid query parameter.",
            "fields": {field: [message]},
        }
    }


def test_page_size_50_is_allowed(client: Client, seeded: None) -> None:
    assert get(client, {"page_size": 50}).status_code == 200


def test_inactive_brands_and_reviews_are_hidden(client: Client) -> None:
    brand = factories.brand()
    factories.review(brand, 5, is_active=False)
    factories.brand(is_active=False)

    body = client.get("/api/brands/").json()

    assert body["count"] == 1
    assert body["results"][0]["review_count"] == 0
    assert body["results"][0]["average_rating"] is None
    assert body["results"][0]["top_review"] is None


@pytest.mark.parametrize("ordering", ["average_rating", "-average_rating"])
def test_null_average_sorts_last_in_both_directions(client: Client, ordering: str) -> None:
    unrated = factories.brand(name="Aardvark")
    for name, rating in [("Mid", 3), ("High", 5)]:
        factories.review(factories.brand(name=name), rating)

    names = [r["name"] for r in get(client, {"ordering": ordering}).json()["results"]]

    assert names[-1] == unrated.name
    assert names[:2] == (["Mid", "High"] if ordering == "average_rating" else ["High", "Mid"])


def test_ties_break_by_name_then_pk(client: Client) -> None:
    second = factories.brand(name="Same")
    first = factories.brand(name="Same")
    third = factories.brand(name="same")
    zed = factories.brand(name="Zed")
    for brand in (zed, first, second, third):
        factories.review(brand, 4)

    slugs = [r["slug"] for r in get(client, {"ordering": "-average_rating"}).json()["results"]]

    assert slugs == [second.slug, first.slug, third.slug, zed.slug]


@pytest.mark.parametrize("ordering", list(ORDERINGS))
@pytest.mark.parametrize("page_size", [1, 3, 7])
def test_paging_any_ordering_returns_each_active_brand_once(
    client: Client, ordering: str, page_size: int
) -> None:
    rng = random.Random(f"{ordering}{page_size}")  # noqa: S311 - seeded test data
    industries = [factories.industry() for _ in range(3)]
    brands = []
    for i in range(17):
        # Few distinct names and ratings, so ties are everywhere.
        brand = factories.brand(name=f"Brand {i % 4}", industry=rng.choice(industries))
        for _ in range(rng.randrange(4)):
            factories.review(brand, rng.choice([1, 3, 5]))
        brands.append(brand)
    factories.brand(is_active=False)

    seen: list[str] = []
    rows: list[dict[str, Any]] = []
    for page in itertools.count(1):
        body = get(client, {"ordering": ordering, "page_size": page_size, "page": page}).json()
        rows += body["results"]
        seen += [r["slug"] for r in body["results"]]
        if body["next"] is None:
            break

    assert sorted(seen) == sorted(b.slug for b in brands)
    key = ordering.lstrip("-")
    values = [r[key] if key != "name" else r["name"].lower() for r in rows]
    present = [v for v in values if v is not None]
    assert present == sorted(present, reverse=ordering.startswith("-"))
    assert values[len(present) :] == [None] * (len(values) - len(present))


def test_review_snippet_is_plain_text_of_at_most_22_words(client: Client) -> None:
    brand = factories.brand()
    words = " ".join(f"word{i}" for i in range(40))
    factories.review(brand, 4, content=f"<p><strong>Bold</strong> &amp; {words}</p>")

    top = client.get("/api/brands/").json()["results"][0]["top_review"]

    assert top["snippet"] == "Bold & " + " ".join(f"word{i}" for i in range(20)) + "…"
