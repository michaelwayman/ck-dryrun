"""Settings for the app service. Every difference between environments comes from env vars."""

import json
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

DEBUG = env.bool("DJANGO_DEBUG", default=False)

# The insecure fallback exists only for local debug runs; anything else must set a real key.
_DEBUG_SECRET_KEY = "django-insecure-debug-only-app"  # noqa: S105
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default=_DEBUG_SECRET_KEY if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# No django.contrib.auth: the app holds no users, passwords or roles (R1, R12).
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "catalog",
    "api.apps.ApiConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# App templates only for now: drf-spectacular's Swagger UI page at /api/docs/.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Compose sets DATABASE_URL (app-db). The SQLite fallback exists only for debug runs and tests.
if DEBUG:
    DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
else:
    DATABASES = {"default": env.db("DATABASE_URL")}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API -----------------------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    # Without django.contrib.auth there is no AnonymousUser model to fall back on.
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "api.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Brand Reviews API",
    "DESCRIPTION": "Brand listing and editor-only short-description edits (brands-api contract).",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # PATCH bodies use the full component: short_description is required (brands-api).
    "COMPONENT_SPLIT_PATCH": False,
    # Pinned rather than @latest so /api/docs/ doesn't change under us.
    "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.33.1",
}

# --- Access tokens (docs/contracts/shared-lib.md) ------------------------------------------------

# AUTH_PUBLIC_KEYS is a JSON object {kid: PEM}. Empty means no key is trusted, so every token fails.
_public_keys_json = env.str("AUTH_PUBLIC_KEYS", default="").strip()
try:
    TOKENAUTH_PUBLIC_KEYS: dict[str, str] = json.loads(_public_keys_json or "{}")
except json.JSONDecodeError as exc:
    raise ImproperlyConfigured(f"AUTH_PUBLIC_KEYS is not valid JSON: {exc}") from None
if not isinstance(TOKENAUTH_PUBLIC_KEYS, dict) or not all(
    isinstance(k, str) and isinstance(v, str) for k, v in TOKENAUTH_PUBLIC_KEYS.items()
):
    raise ImproperlyConfigured("AUTH_PUBLIC_KEYS must be a JSON object of kid -> PEM strings.")
TOKENAUTH_ISSUER = env.str("AUTH_ISSUER", default="brand-reviews-auth")
TOKENAUTH_AUDIENCE = "brand-reviews-app"

# --- WordPress source for import_wp (docs/contracts/wp-source.md) --------------------------------

_wp_host, _, _wp_port = env.str("WORDPRESS_DB_HOST", default="db:3306").partition(":")
WP_SOURCE = {
    "host": _wp_host,
    "port": int(_wp_port or 3306),
    "database": env.str("WORDPRESS_DB_NAME", default="wp"),
    "user": env.str("WORDPRESS_DB_USER", default="wp"),
    "password": env.str("WORDPRESS_DB_PASSWORD", default=""),
    "table_prefix": env.str("WORDPRESS_TABLE_PREFIX", default="wp_"),
}
