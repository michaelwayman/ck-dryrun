from typing import Any

from django.core.management.base import BaseCommand

from catalog.importer import source
from catalog.importer.upsert import import_source


class Command(BaseCommand):
    help = "Import industries, brands and reviews from the WordPress db (wp-source contract)."

    def handle(self, *args: Any, **options: Any) -> None:
        conn = source.connect()
        try:
            data = source.read(conn)
        finally:
            conn.close()
        for name, counts in import_source(data).items():
            self.stdout.write(f"{name}: {counts}")
