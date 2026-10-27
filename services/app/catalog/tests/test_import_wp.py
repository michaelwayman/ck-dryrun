import logging
import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pymysql
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from catalog.importer import source
from catalog.models import Brand, Industry, Review

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).resolve().parents[4] / "docs/contracts/wp-source/mock/fixture.sql"
FIRST_RUN = [
    "industries: created 2, updated 0, deactivated 0",
    "brands: created 2, updated 0, deactivated 0",
    "reviews: created 1, updated 0, deactivated 0",
]
NOTHING = [
    "industries: created 0, updated 0, deactivated 0",
    "brands: created 0, updated 0, deactivated 0",
    "reviews: created 0, updated 0, deactivated 0",
]


@pytest.fixture
def wp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sqlite3.Connection]:
    """The contract's mock WP db in a sqlite file; import_wp connects to it instead of MariaDB.

    Tests change the source through the yielded connection.
    """
    path = tmp_path / "wp.sqlite3"
    conn = sqlite3.connect(path, autocommit=True)
    conn.executescript(FIXTURE.read_text())
    monkeypatch.setattr(source, "connect", lambda: sqlite3.connect(path))
    yield conn
    conn.close()


def run() -> list[str]:
    out = StringIO()
    call_command("import_wp", stdout=out)
    return out.getvalue().splitlines()


def test_first_run_imports_the_mock_as_the_contract_expects(
    wp: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="catalog.importer"):
        assert run() == FIRST_RUN

    assert {(i.wp_id, i.name, i.slug) for i in Industry.objects.all()} == {
        (1, "Mock Insurance", "ins-mock"),
        (2, "Mock Banking", "bank-mock"),
    }
    alpha, beta = Brand.objects.order_by("wp_id")
    assert alpha.slug == "alpha-mock" and alpha.industry.wp_id == 1
    assert alpha.short_description == "Alpha Mock Co. is a synthetic insurer."
    assert alpha.content.startswith("<p>Alpha Mock Co. is a <strong>synthetic</strong>")
    assert (alpha.website_url, alpha.founded_year, alpha.headquarters) == (
        "https://alpha-mock.example.com", 1990, "Springfield, ZZ",
    )  # fmt: skip
    assert alpha.legacy_average_rating == Decimal("4.5")
    assert (alpha.seo_title, alpha.seo_description) == (
        "Alpha Mock Co. Reviews", "Synthetic reviews of Alpha Mock Co.",
    )  # fmt: skip
    assert (beta.name, beta.slug, beta.industry.wp_id) == ("Beta & Sons", "beta-and-sons", 2)
    assert beta.short_description == "Beta & Sons is a synthetic bank."
    assert (beta.website_url, beta.founded_year, beta.legacy_average_rating) == ("", None, None)
    assert (beta.seo_title, beta.seo_description) == ("", "")

    review = Review.objects.get()
    assert (review.wp_id, review.brand, review.slug, review.rating) == (
        201,
        alpha,
        "quick-claim",
        4,
    )
    assert (review.title, review.reviewer_wp_id) == ("Quick claim", 2)
    assert (review.reviewer_name, review.reviewer_location) == ("Mock Reader", "Springfield, ZZ")
    assert review.published_at == datetime(2026, 2, 1, 12, 30, tzinfo=UTC)
    assert review.content == "<p>Claim paid in a week.</p>"

    warnings = [r.getMessage() for r in caplog.records]
    assert any("review 202" in w and "'9999'" in w for w in warnings)
    assert any("review 203" in w and "'7'" in w for w in warnings)
    assert not any("103" in w for w in warnings)  # the draft is never selected


def test_second_run_changes_nothing(wp: sqlite3.Connection) -> None:
    run()
    before = list(Brand.all_objects.values()) + list(Review.all_objects.values())

    assert run() == NOTHING
    assert list(Brand.all_objects.values()) + list(Review.all_objects.values()) == before


def test_a_removed_row_is_deactivated_and_comes_back_when_re_added(
    wp: sqlite3.Connection,
) -> None:
    run()
    row = wp.execute("SELECT * FROM wp_posts WHERE ID = 201").fetchone()
    wp.execute("DELETE FROM wp_posts WHERE ID = 201")

    assert run()[2] == "reviews: created 0, updated 0, deactivated 1"
    assert not Review.objects.exists()
    assert Review.all_objects.get(wp_id=201).is_active is False

    wp.execute("INSERT INTO wp_posts VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)

    assert run()[2] == "reviews: created 0, updated 1, deactivated 0"
    assert Review.objects.get().wp_id == 201


def test_unpublishing_a_brand_deactivates_it_and_skips_its_reviews(
    wp: sqlite3.Connection,
) -> None:
    run()
    wp.execute("UPDATE wp_posts SET post_status = 'draft' WHERE ID = 101")

    assert run()[1:] == [
        "brands: created 0, updated 0, deactivated 1",
        "reviews: created 0, updated 0, deactivated 1",
    ]
    assert list(Brand.objects.values_list("wp_id", flat=True)) == [102]


def test_changed_source_fields_are_updated(wp: sqlite3.Connection) -> None:
    run()
    wp.execute("UPDATE wp_posts SET post_title = 'Alpha Renamed' WHERE ID = 101")
    wp.execute("UPDATE wp_postmeta SET meta_value = '5' WHERE meta_id = 13")

    assert run() == [
        "industries: created 0, updated 0, deactivated 0",
        "brands: created 0, updated 1, deactivated 0",
        "reviews: created 0, updated 1, deactivated 0",
    ]
    assert Brand.objects.get(wp_id=101).name == "Alpha Renamed"
    assert Review.objects.get().rating == 5


def test_new_content_refreshes_an_unedited_short_description(wp: sqlite3.Connection) -> None:
    run()
    wp.execute("UPDATE wp_posts SET post_content = '<p>New intro.</p>' WHERE ID = 101")

    run()

    assert Brand.objects.get(wp_id=101).short_description == "New intro."


def test_an_editor_changed_short_description_survives_re_import(wp: sqlite3.Connection) -> None:
    run()
    Brand.objects.filter(wp_id=101).update(short_description="Edited by an editor.")
    wp.execute("UPDATE wp_posts SET post_content = '<p>New intro.</p>' WHERE ID = 101")

    run()

    brand = Brand.objects.get(wp_id=101)
    assert (brand.short_description, brand.content) == ("Edited by an editor.", "<p>New intro.</p>")


def test_zero_brands_aborts_without_writing(wp: sqlite3.Connection) -> None:
    run()
    wp.execute("DELETE FROM wp_posts WHERE post_type = 'brand'")
    wp.execute("UPDATE wp_terms SET name = 'Changed' WHERE term_id = 1")

    with pytest.raises(CommandError, match="0 brands"):
        run()

    assert Brand.objects.count() == 2
    assert Review.objects.count() == 1
    assert Industry.objects.get(wp_id=1).name == "Mock Insurance"


def test_zero_brands_on_an_empty_db_writes_nothing(wp: sqlite3.Connection) -> None:
    wp.execute("DELETE FROM wp_posts WHERE post_type = 'brand'")

    with pytest.raises(CommandError):
        run()

    assert not Industry.objects.exists()


def test_every_brand_skipped_aborts_without_writing(wp: sqlite3.Connection) -> None:
    wp.execute("DELETE FROM wp_term_relationships")

    with pytest.raises(CommandError, match="Every WP brand was skipped"):
        run()

    assert not Industry.objects.exists()
    assert not Brand.all_objects.exists()


@pytest.mark.parametrize("year", ["32768", "-5"])
def test_an_out_of_range_founded_year_is_stored_as_null(
    wp: sqlite3.Connection, caplog: pytest.LogCaptureFixture, year: str
) -> None:
    wp.execute(
        "UPDATE wp_postmeta SET meta_value = ? WHERE post_id = 101 AND meta_key = 'founded_year'",
        (year,),
    )

    with caplog.at_level(logging.WARNING, logger="catalog.importer"):
        assert run() == FIRST_RUN

    assert Brand.objects.get(wp_id=101).founded_year is None
    assert any("Brand 101" in w and "founded_year" in w for w in caplog.messages)


def test_an_over_long_website_url_is_stored_as_blank(
    wp: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    url = "https://alpha-mock.example.com/" + "a" * 2048
    wp.execute(
        "UPDATE wp_postmeta SET meta_value = ? WHERE post_id = 101 AND meta_key = 'website_url'",
        (url,),
    )

    with caplog.at_level(logging.WARNING, logger="catalog.importer"):
        assert run() == FIRST_RUN

    assert Brand.objects.get(wp_id=101).website_url == ""
    assert any("Brand 101" in w and "website_url" in w for w in caplog.messages)


def test_a_failure_mid_run_rolls_everything_back(
    wp: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from catalog.importer import upsert

    def boom(*args: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(upsert, "_reviews", boom)

    with pytest.raises(RuntimeError):
        run()

    assert not Industry.objects.exists()
    assert not Brand.all_objects.exists()


def test_brand_with_several_industries_takes_the_lowest_term_taxonomy_id(
    wp: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    wp.execute("INSERT INTO wp_term_relationships VALUES (102, 11)")

    with caplog.at_level(logging.WARNING, logger="catalog.importer"):
        run()

    assert Brand.objects.get(wp_id=102).industry.wp_id == 1
    assert any("Brand 102" in r.getMessage() for r in caplog.records)


def test_brand_without_an_industry_is_skipped(
    wp: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    wp.execute("DELETE FROM wp_term_relationships WHERE object_id = 102")

    with caplog.at_level(logging.WARNING, logger="catalog.importer"):
        assert run()[1] == "brands: created 1, updated 0, deactivated 0"

    assert any("brand 102" in r.getMessage() for r in caplog.records)


@pytest.fixture
def no_db(monkeypatch: pytest.MonkeyPatch) -> Callable[[], list[float]]:
    calls: list[float] = []
    sleeps: list[float] = []

    def refuse(**kwargs: object) -> None:
        calls.append(1)
        raise pymysql.err.OperationalError(2003, "Can't connect")

    monkeypatch.setattr(pymysql, "connect", refuse)
    monkeypatch.setattr(source.time, "sleep", sleeps.append)
    return lambda: [len(calls), *sleeps]


def test_connection_is_tried_10_times_2_seconds_apart_then_exits_1(
    no_db: Callable[[], list[float]],
) -> None:
    with pytest.raises(CommandError) as excinfo:
        run()

    assert excinfo.value.returncode == 1
    assert no_db() == [10] + [2] * 9
