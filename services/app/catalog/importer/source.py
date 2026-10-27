"""Read-only access to the WordPress database, exactly as docs/contracts/wp-source.md maps it.

The SQL is plain and parameter-free (ids are integers we read ourselves, keys are constants), so
the same statements run on PyMySQL in production and on sqlite3 against the contract's mock.
"""

import logging
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

import pymysql
from django.conf import settings
from django.core.management.base import CommandError

log = logging.getLogger("catalog.importer")

CONNECT_ATTEMPTS = 10
CONNECT_DELAY_SECONDS = 2
BRAND_META_KEYS = (
    "website_url",
    "founded_year",
    "headquarters",
    "average_rating",
    "_yoast_wpseo_title",
    "_yoast_wpseo_metadesc",
)
REVIEW_META_KEYS = ("rating", "reviewer_name", "reviewer_location", "brand")


class Connection(Protocol):
    def cursor(self) -> Any: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class IndustryRow:
    wp_id: int
    name: str
    slug: str


@dataclass(frozen=True)
class PostRow:
    wp_id: int
    author: int
    date_gmt: datetime | None
    title: str
    slug: str
    content: str
    meta: dict[str, str] = field(default_factory=dict)
    # Industry term ids, lowest term_taxonomy_id first. Brands only.
    industry_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Source:
    industries: list[IndustryRow]
    brands: list[PostRow]
    reviews: list[PostRow]


def connect() -> Connection:
    """Connect to WP `db`, retrying CONNECT_ATTEMPTS times, CONNECT_DELAY_SECONDS apart."""
    cfg = settings.WP_SOURCE
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return pymysql.connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                charset="utf8mb4",
            )
        except pymysql.err.OperationalError as exc:
            log.warning("WP db connection attempt %d/%d failed: %s", attempt, CONNECT_ATTEMPTS, exc)
            if attempt < CONNECT_ATTEMPTS:
                time.sleep(CONNECT_DELAY_SECONDS)
    raise CommandError(f"Could not connect to the WP db after {CONNECT_ATTEMPTS} attempts.")


def read(conn: Connection) -> Source:
    prefix = settings.WP_SOURCE["table_prefix"]
    if not re.fullmatch(r"\w+", prefix):
        raise CommandError(f"WORDPRESS_TABLE_PREFIX {prefix!r} is not a plain identifier.")
    sql = _Sql(conn, prefix)

    industries = [
        IndustryRow(int(term_id), name, slug)
        for term_id, name, slug in sql.rows(
            "SELECT t.term_id, t.name, t.slug FROM {p}terms t"
            " JOIN {p}term_taxonomy tt ON tt.term_id = t.term_id"
            " WHERE tt.taxonomy = 'industry' ORDER BY t.term_id"
        )
    ]
    brands = sql.posts("brand", BRAND_META_KEYS)
    terms: dict[int, list[int]] = {}
    for object_id, term_id in sql.rows(
        "SELECT tr.object_id, tt.term_id FROM {p}term_relationships tr"  # noqa: S608 - int() ids
        " JOIN {p}term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id"
        f" WHERE tt.taxonomy = 'industry' AND tr.object_id IN ({_ids(b.wp_id for b in brands)})"
        " ORDER BY tr.object_id, tt.term_taxonomy_id"
    ):
        terms.setdefault(int(object_id), []).append(int(term_id))
    brands = [replace(b, industry_ids=tuple(terms.get(b.wp_id, ()))) for b in brands]
    reviews = sql.posts("review", REVIEW_META_KEYS)
    return Source(industries, brands, reviews)


class _Sql:
    def __init__(self, conn: Connection, prefix: str) -> None:
        self.conn, self.prefix = conn, prefix

    def rows(self, statement: str) -> list[Sequence[Any]]:
        cursor = self.conn.cursor()
        try:
            cursor.execute(statement.replace("{p}", self.prefix))
            return list(cursor.fetchall())
        finally:
            cursor.close()

    def posts(self, post_type: str, meta_keys: Sequence[str]) -> list[PostRow]:
        rows = self.rows(
            "SELECT ID, post_author, post_date_gmt, post_title, post_name, post_content"  # noqa: S608
            f" FROM {{p}}posts WHERE post_type = '{post_type}' AND post_status = 'publish'"
            " ORDER BY ID"
        )
        meta: dict[int, dict[str, str]] = {}
        keys = ", ".join(f"'{key}'" for key in meta_keys)
        for post_id, key, value in self.rows(
            "SELECT post_id, meta_key, meta_value FROM {p}postmeta"  # noqa: S608 - int() ids
            f" WHERE post_id IN ({_ids(row[0] for row in rows)}) AND meta_key IN ({keys})"
            " ORDER BY meta_id"
        ):
            # Like get_post_meta(..., single=true): the first value of a repeated key wins.
            meta.setdefault(int(post_id), {}).setdefault(key, value or "")
        return [
            PostRow(
                wp_id=int(pk),
                author=int(author),
                date_gmt=_utc(date_gmt),
                title=title,
                slug=slug,
                content=content,
                meta=meta.get(int(pk), {}),
            )
            for pk, author, date_gmt, title, slug, content in rows
        ]


def _ids(values: Iterable[Any]) -> str:
    # int() keeps the IN list to integers; NULL keeps it valid SQL when there are none.
    return ", ".join(str(int(v)) for v in values) or "NULL"


def _utc(value: datetime | str | None) -> datetime | None:
    """post_date_gmt as an aware UTC datetime; None for WP's zero date or anything unparseable."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC)
