import os

# Settings require DJANGO_SECRET_KEY unless debug is on. The settings module is named here rather
# than in pytest config so pytest-django loads it only after this file has set DJANGO_DEBUG.
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Set Django up now, so test modules that import models at collection time can load. pytest-django
# would only do it before collection if the settings module were named in pytest config.
import django  # noqa: E402

django.setup()
