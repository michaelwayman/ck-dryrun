from collections.abc import Callable
from functools import partial

import django
import pytest
from django.conf import settings

from tests.conftest import verify_at
from tests.drf import settings as test_settings

if not settings.configured:
    settings.configure(
        **{name: getattr(test_settings, name) for name in dir(test_settings) if name.isupper()}
    )
    django.setup()


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Verify mock tokens at an example's verify_at, not wall-clock time (editor's by default)."""
    import tokenauth.drf  # after settings.configure(): DRF reads settings on import

    def at(example: str) -> None:
        verify = partial(tokenauth.verify_token, now=verify_at(example))
        monkeypatch.setattr(tokenauth.drf, "verify_token", verify)

    at("editor")
    return at
