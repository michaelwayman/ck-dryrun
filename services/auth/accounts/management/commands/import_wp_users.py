"""Import WordPress users once, per the wp-source contract's Users section (R10).

Upserts on wp_user_id in one transaction. Passwords and roles are set on create only, so changes
made here after the import survive a re-run; username, email and display name follow WordPress.
"""

import re
import time
from dataclasses import dataclass
from typing import Any

import pymysql
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from accounts.models import Role, User

CONNECT_ATTEMPTS = 10
CONNECT_DELAY_SECONDS = 2
# Keys of the PHP-serialized capabilities array. The PHP is never unserialized.
CAPABILITY_KEY = re.compile(r's:\d+:"(\w+)"')
TABLE_PREFIX = re.compile(r"^\w+$")


@dataclass(frozen=True)
class WPUser:
    wp_user_id: int
    username: str
    email: str
    display_name: str
    wp_hash: str
    is_admin: bool


def connect_wp() -> Any:
    """A read-only-use PyMySQL connection to the WP `db`, retried while it starts up."""
    cfg = settings.WP_DB
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return pymysql.connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["name"],
                charset="utf8mb4",
            )
        except pymysql.err.OperationalError:
            if attempt == CONNECT_ATTEMPTS:
                raise
            time.sleep(CONNECT_DELAY_SECONDS)
    raise AssertionError("unreachable")  # pragma: no cover


def capabilities(meta_value: str | None) -> set[str]:
    return set(CAPABILITY_KEY.findall(meta_value or ""))


def read_wp_users(connection: Any, prefix: str) -> list[WPUser]:
    if not TABLE_PREFIX.match(prefix):
        raise CommandError(f"Invalid WORDPRESS_TABLE_PREFIX {prefix!r}.")
    cursor = connection.cursor()
    try:
        # The prefix is checked against \w+ above; it cannot be a bound parameter.
        cursor.execute(
            f"SELECT user_id, meta_value FROM {prefix}usermeta "  # noqa: S608
            f"WHERE meta_key = '{prefix}capabilities'"
        )
        caps = {int(user_id): capabilities(value) for user_id, value in cursor.fetchall()}
        cursor.execute(
            "SELECT ID, user_login, user_email, display_name, user_pass "  # noqa: S608
            f"FROM {prefix}users ORDER BY ID"
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return [
        WPUser(
            wp_user_id=int(wp_id),
            username=login,
            email=email,
            display_name=display_name,
            wp_hash=user_pass,
            is_admin="administrator" in caps.get(int(wp_id), set()),
        )
        for wp_id, login, email, display_name, user_pass in rows
    ]


def upsert(wp_users: list[WPUser]) -> tuple[int, int]:
    """Create or update every user; return (created, updated). Updated counts real changes."""
    roles = {role.name: role for role in Role.objects.all()}
    created = updated = 0
    with transaction.atomic():
        existing = {u.wp_user_id: u for u in User.objects.filter(wp_user_id__isnull=False)}
        for wp in wp_users:
            user = existing.get(wp.wp_user_id)
            if user is None:
                user = User.objects.create(
                    wp_user_id=wp.wp_user_id,
                    username=wp.username,
                    email=wp.email,
                    display_name=wp.display_name,
                    password="wp_bcrypt$" + wp.wp_hash,
                    is_staff=wp.is_admin,
                    is_superuser=wp.is_admin,
                )
                user.roles.set([roles["editor" if wp.is_admin else "reader"]])
                created += 1
                continue
            changes = {
                field: value
                for field, value in (
                    ("username", wp.username),
                    ("email", wp.email),
                    ("display_name", wp.display_name),
                )
                if getattr(user, field) != value
            }
            if changes:
                for field, value in changes.items():
                    setattr(user, field, value)
                user.save(update_fields=list(changes))
                updated += 1
    return created, updated


class Command(BaseCommand):
    help = "Import WordPress users and their roles from the WP database (wp-source contract)."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            connection = connect_wp()
        except pymysql.err.OperationalError as exc:
            raise CommandError(f"WordPress database unreachable: {exc}") from exc
        try:
            wp_users = read_wp_users(connection, settings.WP_DB["table_prefix"])
        finally:
            connection.close()
        try:
            created, updated = upsert(wp_users)
        except IntegrityError as exc:  # e.g. a WP user_login already taken by a local user
            raise CommandError(f"Import rolled back, nothing written: {exc}") from exc
        self.stdout.write(f"users: created {created}, updated {updated}")
