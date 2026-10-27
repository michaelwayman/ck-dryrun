from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "api"

    def ready(self) -> None:
        from api import schema  # noqa: F401 - registers the Bearer auth extension with spectacular
