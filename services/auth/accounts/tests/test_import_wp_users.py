import sqlite3
from io import StringIO
from pathlib import Path

import pymysql
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.management.commands import import_wp_users
from accounts.models import Role, User

pytestmark = pytest.mark.django_db

FIXTURE = (
    Path(__file__).resolve().parents[4] / "docs" / "contracts" / "wp-source" / "mock" / "fixture.sql"
)


@pytest.fixture(autouse=True)
def mock_wp(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """The wp-source mock fixture in in-memory SQLite, standing in for the WP MariaDB."""
    connection = sqlite3.connect(":memory:")
    connection.executescript(FIXTURE.read_text())
    # The command closes its connection; the wrapper keeps this one open for the test's edits.
    monkeypatch.setattr(import_wp_users, "connect_wp", lambda: _Unclosable(connection))
    return connection


class _Unclosable:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def cursor(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def close(self) -> None:
        pass


def run() -> str:
    out = StringIO()
    call_command("import_wp_users", stdout=out)
    return out.getvalue().strip()


def test_first_run_imports_the_fixture_users() -> None:
    assert run() == "users: created 2, updated 0"

    admin = User.objects.get(wp_user_id=1)
    reader = User.objects.get(wp_user_id=2)
    assert (admin.username, admin.email, admin.display_name) == (
        "mock_admin",
        "mock_admin@example.com",
        "Mock Admin",
    )
    assert admin.role_names() == ["editor"] and admin.is_staff and admin.is_superuser
    assert reader.role_names() == ["reader"] and not reader.is_staff and not reader.is_superuser
    assert admin.password.startswith("wp_bcrypt$$wp$2y$10$")
    assert admin.check_password("mock-admin-pw-1")
    assert reader.check_password("mock-reader-pw-2")


def test_rerun_creates_and_updates_nothing() -> None:
    run()
    assert run() == "users: created 0, updated 0"
    assert User.objects.count() == 2


def test_changes_made_here_survive_a_reimport() -> None:
    run()
    reader = User.objects.get(wp_user_id=2)
    reader.set_password("changed-here")
    reader.save()
    reader.roles.add(Role.objects.get(name="editor"))

    run()

    reader.refresh_from_db()
    assert reader.check_password("changed-here")
    assert reader.role_names() == ["editor", "reader"]


def test_profile_fields_follow_wordpress(mock_wp: sqlite3.Connection) -> None:
    run()
    mock_wp.execute("UPDATE wp_users SET display_name = 'Renamed' WHERE ID = 2")

    assert run() == "users: created 0, updated 1"
    assert User.objects.get(wp_user_id=2).display_name == "Renamed"


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ('a:1:{s:13:"administrator";b:1;}', {"administrator"}),
        ('a:2:{s:6:"editor";b:1;s:10:"subscriber";b:1;}', {"editor", "subscriber"}),
        ('O:8:"Exploit":0:{}', set()),
        (None, set()),
    ],
)
def test_capabilities_are_read_with_a_regex(meta: str | None, expected: set[str]) -> None:
    assert import_wp_users.capabilities(meta) == expected


def test_unreachable_db_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # the real connect_wp
    attempts = []

    def refuse(**kwargs: object) -> None:
        attempts.append(kwargs)
        raise pymysql.err.OperationalError(2003, "refused")

    monkeypatch.setattr(pymysql, "connect", refuse)
    monkeypatch.setattr(import_wp_users.time, "sleep", lambda seconds: None)

    with pytest.raises(CommandError, match="unreachable"):
        run()
    assert len(attempts) == 10
