import os

# Settings require DJANGO_SECRET_KEY unless debug is on. The settings module is named here rather
# than in pytest config so pytest-django loads it only after this file has set DJANGO_DEBUG.
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
