"""Minimal Django settings for the drf tests; conftest passes them to settings.configure()."""

from tests.conftest import public_keys

SECRET_KEY = "tokenauth-tests-only"  # noqa: S105 - test settings, protects nothing
INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "rest_framework"]
DATABASES: dict[str, object] = {}
USE_TZ = True

TOKENAUTH_PUBLIC_KEYS = public_keys()
TOKENAUTH_ISSUER = "brand-reviews-auth"
TOKENAUTH_AUDIENCE = "brand-reviews-app"
