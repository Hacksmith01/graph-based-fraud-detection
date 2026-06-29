from __future__ import annotations

import pytest

from backend.services import database


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    database_path = tmp_path / "users.db"
    monkeypatch.setattr(database, "DATABASE_DIR", tmp_path)
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    database.init_db()
    return database_path

