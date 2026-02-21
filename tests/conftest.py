import os
import tempfile
import pytest

import config
import db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Use a fresh temp DB for every test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    db.init_db()
    yield db_path
