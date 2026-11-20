#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p training/artifacts
# This command runs in your own Terminal, which can reach the package index.
if [[ ! -x training/.venv/bin/python ]]; then
  python3 -m venv training/.venv
fi
PYTHON=training/.venv/bin/python
$PYTHON -c 'import sys; assert (3,9) <= sys.version_info[:2] <= (3,11), "TensorFlow 2.15 needs Python 3.9–3.11. Create training/.venv with a supported interpreter."'
# Prefer the verified local wheels; use the package index only if a dependency is missing.
if ! $PYTHON -m pip install --no-index --find-links training/artifacts/offline-packages -r training/requirements.txt 'setuptools==80.9.0'; then
  $PYTHON -m pip install --cache-dir training/artifacts/pip-cache --find-links training/artifacts/offline-packages -r training/requirements.txt 'setuptools==80.9.0'
fi
# The portable Keras writer does not need SavedModel/Decision Forest dependencies.
if ! $PYTHON -m pip install --no-index --find-links training/artifacts/offline-packages --no-deps 'tensorflowjs==4.17.0'; then
  $PYTHON -m pip install --cache-dir training/artifacts/pip-cache --no-deps 'tensorflowjs==4.17.0'
fi
# The pinned Metal runtime failed strict browser parity on this Mac.
# CPU TensorFlow retains native MediaPipe/OpenGL access in a normal Terminal.
if [[ "$(uname -s)" == Darwin ]]; then
  export DAISEE_TF_DEVICE=cpu
fi
# Lower-load defaults; these controls do not change the dataset or epoch protocol.
export TF_NUM_INTRAOP_THREADS=4
export TF_NUM_INTEROP_THREADS=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=2
export DAISEE_DATA_THREADS=1
export DAISEE_EPOCH_COOLDOWN_SECONDS=60
printf 'Training mode: 4 compute threads, 1 data worker, 1-minute break after each saved epoch.\n'
export MPLBACKEND=Agg
export PYTHONUNBUFFERED=1
$PYTHON -m training.local_run "$@" 2>&1 | tee -a training/artifacts/local-training-console.log
