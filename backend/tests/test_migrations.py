"""Verify migration of a legacy table on a separate temporary database."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_migration_preserves_legacy_readings(tmp_path):
    database = tmp_path / 'legacy.sqlite'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE students (student_id VARCHAR(36) PRIMARY KEY)')
        db.execute('CREATE TABLE attentiveness_readings (reading_id VARCHAR(36) PRIMARY KEY, attention_index FLOAT NOT NULL, quality_flag VARCHAR(32))')
        db.execute("INSERT INTO attentiveness_readings VALUES ('valid', 80, 'normal')")
        db.execute("INSERT INTO attentiveness_readings VALUES ('missing', 0, 'face_not_detected')")
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=backend,
                            env={**os.environ, 'DATABASE_URL': f'sqlite+aiosqlite:///{database}'}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as db:
        assert dict(db.execute('SELECT reading_id, attention_index FROM attentiveness_readings')) == {'valid': 80, 'missing': None}
        assert {'consented_at', 'consent_version'} <= {row[1] for row in db.execute('PRAGMA table_info(students)')}
        assert db.execute('SELECT inference_mode FROM attentiveness_readings').fetchone()[0] == 'geometric'
