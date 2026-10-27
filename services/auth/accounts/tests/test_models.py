import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from tokenauth import Role as RoleName

from accounts.models import Role, User

pytestmark = pytest.mark.django_db


def test_user_is_the_auth_user_model() -> None:
    assert get_user_model() is User


def test_seeded_roles_match_tokenauth() -> None:
    assert set(Role.objects.values_list("name", flat=True)) == {r.value for r in RoleName}


def test_role_name_must_be_a_tokenauth_role() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(name="admin")


def test_role_name_is_unique() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(name="reader")


def test_wp_user_id_is_unique_but_may_be_null() -> None:
    User.objects.create_user("a", wp_user_id=None)
    User.objects.create_user("b", wp_user_id=None)
    User.objects.create_user("c", wp_user_id=7)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("d", wp_user_id=7)


def test_user_holds_several_roles_sorted_in_the_claim() -> None:
    user = User.objects.create_user("sam", display_name="Sam")
    user.roles.set(Role.objects.all())

    assert user.role_names() == ["editor", "reader"]
    user.roles.remove(Role.objects.get(name="editor"))
    assert user.role_names() == ["reader"]
