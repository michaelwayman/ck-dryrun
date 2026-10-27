from datetime import UTC, datetime

import jwt
import pytest
from django.test import Client

from accounts.models import Role, User
from tokens.signing import mint_access_token

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser_client() -> Client:
    admin = User.objects.create_superuser("root", password="pw")
    client = Client()
    client.force_login(admin)
    return client


def roles_claim(user: User) -> list[str]:
    token = mint_access_token(user, datetime.now(UTC))
    roles: list[str] = jwt.decode(token, options={"verify_signature": False})["roles"]
    return roles


def test_change_page_shows_wp_fields_and_roles(superuser_client: Client) -> None:
    user = User.objects.create_user("sarah", wp_user_id=2, display_name="Sarah K.")

    page = superuser_client.get(f"/admin/accounts/user/{user.pk}/change/").content.decode()

    for field in ("wp_user_id", "display_name", "roles"):
        assert f'name="{field}"' in page
    assert "Sarah K." in page


def test_role_change_in_admin_reaches_the_next_token(superuser_client: Client) -> None:
    user = User.objects.create_user("sarah", wp_user_id=2, display_name="Sarah K.")
    user.roles.set([Role.objects.get(name="reader")])
    assert roles_claim(user) == ["reader"]

    response = superuser_client.post(
        f"/admin/accounts/user/{user.pk}/change/",
        {
            "username": "sarah",
            "display_name": "Sarah K.",
            "wp_user_id": "2",
            "is_active": "on",
            "roles": [str(r.pk) for r in Role.objects.all()],
            "date_joined_0": "2026-10-26",
            "date_joined_1": "12:00:00",
        },
    )

    assert response.status_code == 302, response.content
    assert roles_claim(user) == ["editor", "reader"]


def test_roles_are_read_only(superuser_client: Client) -> None:
    assert superuser_client.get("/admin/accounts/role/add/").status_code == 403
    assert superuser_client.get("/admin/accounts/role/").status_code == 200
