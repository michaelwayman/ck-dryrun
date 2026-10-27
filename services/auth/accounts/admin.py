from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpRequest

from accounts.models import Role, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django's user admin plus the WordPress fields and token roles (R18).

    A role change takes effect in the user's next minted or refreshed access token.
    """

    fieldsets = (
        *(DjangoUserAdmin.fieldsets or ()),
        ("WordPress and token roles", {"fields": ("wp_user_id", "display_name", "roles")}),
    )
    filter_horizontal = ("roles", *DjangoUserAdmin.filter_horizontal)
    list_display = ("username", "display_name", "email", "wp_user_id", "is_active", "is_staff")
    list_filter = ("roles", *DjangoUserAdmin.list_filter)
    search_fields = ("username", "display_name", "email")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Roles are fixed by tokenauth.Role and seeded by a migration, so they are read-only here."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
