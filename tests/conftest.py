import pytest

from app.config import settings
from app.storage import reset_storage_for_tests


@pytest.fixture(autouse=True)
def _reset_storage(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "use_fake_storage", True)
    reset_storage_for_tests()
    yield
    reset_storage_for_tests()
