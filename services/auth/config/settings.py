"""Settings for the auth service. Every difference between environments comes from env vars."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

DEBUG = env.bool("DJANGO_DEBUG", default=False)

# The insecure fallback exists only for local debug runs; anything else must set a real key.
_DEBUG_SECRET_KEY = "django-insecure-debug-only-auth"  # noqa: S105
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default=_DEBUG_SECRET_KEY if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
    "tokens",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Compose sets DATABASE_URL (auth-db). Only a debug run may fall back to a local SQLite file;
# tests run on pytest-django's in-memory SQLite test database.
if DEBUG:
    DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
else:
    DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_USER_MODEL = "accounts.User"

# Django's default first, so a login that matched the WP hash is re-hashed with it (T5).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "accounts.hashers.WPBcryptPasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Tokens (access-token and auth-api contracts) ---------------------------------------------

# PEM path of the Ed25519 private key. Read on first mint, not at startup, so manage.py commands
# that never mint (migrate, import_wp_users) run without it.
AUTH_SIGNING_KEY = env.str("AUTH_SIGNING_KEY", default="")
# Empty means derive "dev-" + sha256(SPKI DER)[:12], the same kid scripts/dev-keys.sh writes.
AUTH_SIGNING_KID = env.str("AUTH_SIGNING_KID", default="")
AUTH_ISSUER = env.str("AUTH_ISSUER", default="brand-reviews-auth")
AUTH_AUDIENCE = "brand-reviews-app"
ACCESS_TOKEN_TTL_SECONDS = 600
REFRESH_TOKEN_TTL_SECONDS = 24 * 60 * 60

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "tokens.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Brand reviews auth API",
    "DESCRIPTION": "Login, refresh and logout. See docs/contracts/auth-api.md.",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- WordPress source (import_wp_users, wp-source contract) -----------------------------------

WP_DB = {
    "host": env.str("WORDPRESS_DB_HOST", default="db"),
    "port": env.int("WORDPRESS_DB_PORT", default=3306),
    "name": env.str("WORDPRESS_DB_NAME", default="wp"),
    "user": env.str("WORDPRESS_DB_USER", default="wp"),
    "password": env.str("WORDPRESS_DB_PASSWORD", default=""),
    "table_prefix": env.str("WORDPRESS_TABLE_PREFIX", default="wp_"),
}
