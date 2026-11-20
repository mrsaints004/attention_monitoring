#!/bin/sh
set -eu
# Run from backend/ with its virtual environment activated.
python -m alembic upgrade head
# Socket and alert state are in memory; run exactly one worker.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --ws-max-size 65536
