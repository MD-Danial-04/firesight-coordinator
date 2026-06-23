from app.config import settings
from app.storage.memory import create_memory_storage
from app.storage.protocol import StorageBackend
from app.storage.supabase import create_supabase_storage

_storage: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _storage
    if _storage is None:
        if settings.use_fake_storage:
            _storage = create_memory_storage()
        else:
            _storage = create_supabase_storage(settings)
    return _storage


def reset_storage_for_tests() -> None:
    global _storage
    _storage = None
