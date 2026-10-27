"""Write a WordPress Source into the catalog: upsert by wp_id, soft-delete what wasn't seen (R2)."""

import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from django.core.management.base import CommandError
from django.db import models, transaction

from catalog.importer.source import PostRow, Source
from catalog.models import Brand, Industry, Review
from catalog.text import first_paragraph_text

log = logging.getLogger("catalog.importer")


@dataclass
class Counts:
    created: int = 0
    updated: int = 0
    deactivated: int = 0

    def __str__(self) -> str:
        return f"created {self.created}, updated {self.updated}, deactivated {self.deactivated}"


def import_source(source: Source) -> dict[str, Counts]:
    """Apply `source` in one transaction and return counts per model, in print order."""
    if not source.brands:
        raise CommandError("The WP source returned 0 brands; aborting without writing anything.")
    with transaction.atomic():
        industries, industry_counts = _industries(source)
        brand_ids, brand_counts = _brands(source, industries)
        review_counts = _reviews(source, brand_ids)
    return {"industries": industry_counts, "brands": brand_counts, "reviews": review_counts}


def _industries(source: Source) -> tuple[dict[int, int], Counts]:
    """Industries are never deactivated: the model has no is_active (R1)."""
    counts = Counts()
    existing = {i.wp_id: i for i in Industry.objects.all()}
    for row in source.industries:
        _save(
            Industry,
            existing.get(row.wp_id),
            {"name": row.name, "slug": row.slug},
            row.wp_id,
            counts,
        )
    return {i.wp_id: i.pk for i in Industry.objects.all()}, counts


def _brands(source: Source, industries: dict[int, int]) -> tuple[dict[int, int], Counts]:
    counts = Counts()
    existing = {b.wp_id: b for b in Brand.all_objects.all()}
    seen: dict[int, int] = {}
    for row in source.brands:
        industry_ids = [i for i in row.industry_ids if i in industries]
        if not industry_ids:
            log.warning("Skipped brand %d (%s): it has no industry.", row.wp_id, row.slug)
            continue
        if len(row.industry_ids) > 1:
            log.warning(
                "Brand %d (%s) has %d industries; using term %d.",
                row.wp_id, row.slug, len(row.industry_ids), industry_ids[0],
            )  # fmt: skip
        current = existing.get(row.wp_id)
        fields = _brand_fields(row, industries[industry_ids[0]], current)
        seen[row.wp_id] = _save(Brand, current, fields, row.wp_id, counts).pk
    counts.deactivated = _deactivate(Brand, seen)
    return seen, counts


def _brand_fields(row: PostRow, industry_pk: int, current: Brand | None) -> dict[str, Any]:
    short_description = first_paragraph_text(row.content)
    # Keep an editor's edit (R13): overwrite only while the stored value is still the imported one.
    if current is not None and current.short_description != first_paragraph_text(current.content):
        short_description = current.short_description
    meta = row.meta
    return {
        "name": row.title,
        "slug": row.slug,
        "industry_id": industry_pk,
        "content": row.content,
        "short_description": short_description,
        "website_url": meta.get("website_url", ""),
        "founded_year": _int_or_none(meta.get("founded_year", ""), row, "founded_year"),
        "headquarters": meta.get("headquarters", ""),
        "legacy_average_rating": _rating_or_none(meta.get("average_rating", ""), row),
        "seo_title": meta.get("_yoast_wpseo_title", ""),
        "seo_description": meta.get("_yoast_wpseo_metadesc", ""),
        "is_active": True,
    }


def _reviews(source: Source, brand_ids: dict[int, int]) -> Counts:
    counts = Counts()
    existing = {r.wp_id: r for r in Review.all_objects.all()}
    seen: dict[int, int] = {}
    for row in source.reviews:
        brand_wp_id = _int_or_none(row.meta.get("brand", ""), row, "brand")
        if brand_wp_id not in brand_ids:
            log.warning(
                "Skipped review %d (%s): brand %r is unknown or inactive.",
                row.wp_id, row.slug, row.meta.get("brand"),
            )  # fmt: skip
            continue
        rating = _int_or_none(row.meta.get("rating", ""), row, "rating")
        if rating is None or not 1 <= rating <= 5:
            log.warning(
                "Skipped review %d (%s): rating %r is not 1-5.",
                row.wp_id, row.slug, row.meta.get("rating"),
            )  # fmt: skip
            continue
        if row.date_gmt is None:
            log.warning("Skipped review %d (%s): no valid post_date_gmt.", row.wp_id, row.slug)
            continue
        fields = {
            "brand_id": brand_ids[brand_wp_id],
            "title": row.title,
            "slug": row.slug,
            "content": row.content,
            "rating": rating,
            "reviewer_wp_id": row.author,
            "reviewer_name": row.meta.get("reviewer_name", ""),
            "reviewer_location": row.meta.get("reviewer_location", ""),
            "published_at": row.date_gmt,
            "is_active": True,
        }
        seen[row.wp_id] = _save(Review, existing.get(row.wp_id), fields, row.wp_id, counts).pk
    counts.deactivated = _deactivate(Review, seen)
    return counts


def _save[M: models.Model](
    model: type[M], current: M | None, fields: dict[str, Any], wp_id: int, counts: Counts
) -> M:
    """Create, or save only the fields that changed, so an unchanged re-run writes nothing."""
    if current is None:
        counts.created += 1
        return model._base_manager.create(wp_id=wp_id, **fields)
    changed = [name for name, value in fields.items() if getattr(current, name) != value]
    if changed:
        for name in changed:
            setattr(current, name, fields[name])
        current.save(update_fields=changed)
        counts.updated += 1
    return current


def _deactivate(model: type[Brand] | type[Review], seen: dict[int, int]) -> int:
    return model.all_objects.filter(is_active=True).exclude(wp_id__in=seen).update(is_active=False)


def _int_or_none(value: str, row: PostRow, key: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        log.warning("Post %d (%s): meta %s %r is not an integer.", row.wp_id, row.slug, key, value)
        return None


def _rating_or_none(value: str, row: PostRow) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    try:
        return Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        log.warning("Brand %d (%s): average_rating %r is not a number.", row.wp_id, row.slug, value)
        return None
