import os

# Settings require DJANGO_SECRET_KEY unless debug is on. The settings module is named here rather
# than in pytest config so pytest-django loads it only after this file has set DJANGO_DEBUG.
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def pytest_configure() -> None:
    # pytest-django sets Django up only once settings are loaded; load them here, before test
    # modules that import models are collected.
    from django.conf import settings

    settings.INSTALLED_APPS  # noqa: B018
