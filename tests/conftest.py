from __future__ import annotations

from pathlib import Path
import importlib

import pytest


@pytest.fixture(autouse=True)
def _test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure each test run uses an isolated sqlite db.
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PORTCAST_DATABASE__URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("PORTCAST_REDIS__ENABLED", "false")
    
    # Reload config to pick up the new env var
    import app.config
    importlib.reload(app.config)
    
    # Update stale settings reference in database module so new engine uses new DB path
    import app.db.database as db_mod
    db_mod.settings = app.config.settings

    from app.db import reset_db
    reset_db()

    # Disable the global cache instance for test isolation
    from app.services.cache import cache
    cache.enabled = False
 
