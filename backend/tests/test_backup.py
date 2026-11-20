import os
import sqlite3
import pytest
from app.backup import backup


def test_backup_is_consistent_private_and_does_not_modify_source(tmp_path):
    database = tmp_path / 'live.sqlite'
    with sqlite3.connect(database) as source:
        source.execute('CREATE TABLE evidence (value TEXT)')
        source.execute("INSERT INTO evidence VALUES ('preserved')")
    result = backup(database, tmp_path / 'backups')
    assert os.stat(result).st_mode & 0o077 == 0
    with sqlite3.connect(result) as saved:
        assert saved.execute('SELECT value FROM evidence').fetchone() == ('preserved',)
    with sqlite3.connect(database) as live:
        assert live.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 1


def test_backup_refuses_missing_database_instead_of_creating_empty_one(tmp_path):
    missing = tmp_path / 'missing.sqlite'
    with pytest.raises(ValueError, match='does not exist'):
        backup(missing, tmp_path / 'backups')
    assert not missing.exists()
