"""Create a consistent, private SQLite backup without stopping the application."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from sqlalchemy.engine import make_url
from app.config import settings


def backup(database, output):
    database, output = Path(database).resolve(), Path(output).resolve()
    if not database.is_file():
        raise ValueError('Source database does not exist')
    output.mkdir(parents=True, exist_ok=True)
    name = 'attention-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.sqlite'
    destination = output / name
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(destination) as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith('sqlite') or not url.database or url.database == ':memory:':
        parser.error('This backup command requires a file-backed SQLite database')
    print('Verified database backup:', backup(url.database, args.output))


if __name__ == '__main__':
    main()
