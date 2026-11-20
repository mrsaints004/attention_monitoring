"""Build a self-contained full-corpus Colab notebook from the current training sources."""
from pathlib import Path
import ast
import base64
import hashlib
import io
import json
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parents[1]
payload = io.BytesIO()
with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((ROOT / 'training').rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.cjs', '.txt', '.json') and not any(
                part in path.parts for part in ('prepared', 'runs', 'artifacts', '__pycache__', '.venv')):
            archive.write(path, path.relative_to(ROOT))
    for name in ('package.json', 'package-lock.json'):
        archive.write(ROOT / 'frontend' / name, 'frontend/' + name)
encoded = base64.b64encode(payload.getvalue()).decode()
digest = hashlib.sha256(payload.getvalue()).hexdigest()
cells = []


def markdown(text):
    cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': textwrap.dedent(text).strip().splitlines(True)})


def code(text):
    text = textwrap.dedent(text).strip() + '\n'
    ast.parse(text)
    cells.append({'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': text.splitlines(True)})


markdown('''
# Full DAiSEE MobileNet training — Google Colab GPU
This notebook trains the planned **face-pretrained MobileNet with three four-level heads: engagement, boredom and confusion**. It uses every video referenced by the official label files in your approved archive, with the supplied participant-disjoint partitions. It is separate from the previous twelve-clip pilot.

Select **Runtime → Change runtime type → GPU** before running. A T4 or L4 is a suitable starting hardware choice for this pinned TensorFlow environment; the smoke test must pass on the assigned device. Your approved archive ID is already filled in.

Run the cells in order. The first cells expose setup errors and verify GPU inference, checkpoint reload and JavaScript conversion **before the large dataset transfer**. No results are pre-filled. Multiple seeds and all-frame preparation can require more than one runtime session. Free GPU capacity, runtime length and disk space are not guaranteed.

**Storage:** only models, reports, logs and epoch checkpoints go to Drive by default. Raw video and prepared frames use `/content`, which is temporary. Resuming preprocessing requires the same retained workspace; after a runtime reset those files must be recreated unless you choose a persistent workspace with sufficient quota. Expect substantial crop storage at 2 FPS; the archive is not stored as a second 15GB copy.
''')
code('''
from pathlib import Path
import os, sys, subprocess, shutil, json, hashlib, base64, io, zipfile
ROOT = Path('/content/attention_monitoring_full')
ROOT.mkdir(parents=True, exist_ok=True)
PAYLOAD = "'''+encoded+'''"
raw = base64.b64decode(PAYLOAD)
assert hashlib.sha256(raw).hexdigest() == "'''+digest+'''", 'Notebook source payload is damaged'
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    archive.extractall(ROOT)
os.chdir(ROOT)
LOGS = Path('/content/daisee-full-logs')
LOGS.mkdir(exist_ok=True)
ENV = dict(os.environ)
ENV['PYTHONUNBUFFERED'] = '1'
# Training subprocesses do not use Colab's notebook-only plotting backend.
ENV['MPLBACKEND'] = 'Agg'
ENV['PYTHONPYCACHEPREFIX'] = '/content/daisee-pycache'
def logged(arguments, name):
    path = LOGS / (name + '.log')
    print('Running', name, '— log:', path, flush=True)
    with path.open('a') as log:
        process = subprocess.Popen([str(x) for x in arguments], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1, env=ENV)
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
            result = process.wait()
        except BaseException:
            process.terminate()
            process.wait()
            raise
    if result:
        raise RuntimeError(f'{name} failed with exit code {result}. The actual error is printed above and saved in {path}. Stop here until it is resolved.')
print('Source installed; cloud disk free:', round(shutil.disk_usage('/content').free / 1024**3, 1), 'GiB')
''')
markdown('''
## 1. Check that Colab actually assigned a GPU
If this fails, choose a GPU runtime and rerun this cell. Installing packages will not supply a GPU to a CPU runtime.
''')
code('''
logged(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'], 'gpu-assignment')
''')
markdown('''
## 2. Isolated Python environment and visible dependency diagnostics
The notebook kernel can remain on its default Python version. All training commands use the separate Python 3.11 environment below. Version pins include the older JAX/SciPy dependencies needed by this TensorFlow/TF.js converter combination.
''')
code('''
logged([sys.executable, '-m', 'pip', 'install', 'uv'], 'install-uv')
logged(['uv', 'venv', '--python', '3.11', '/content/daisee-full-env', '--allow-existing'], 'create-python-environment')
PYTHON = '/content/daisee-full-env/bin/python'
logged(['uv', 'pip', 'install', '--python', PYTHON, '-r', 'training/requirements-export.txt',
        'tensorflow[and-cuda]==2.15.1'], 'install-training-dependencies')
# Help the older TensorFlow runtime locate the CUDA libraries installed inside its own environment.
site_packages = Path('/content/daisee-full-env/lib/python3.11/site-packages')
cuda_libraries = sorted((site_packages / 'nvidia').glob('*/lib'))
ENV['LD_LIBRARY_PATH'] = ':'.join([*(str(p) for p in cuda_libraries), ENV.get('LD_LIBRARY_PATH', '')])
cuda_bins = sorted((site_packages / 'nvidia').glob('*/bin'))
ENV['PATH'] = ':'.join([*(str(p) for p in cuda_bins), ENV.get('PATH', '')])
logged([PYTHON, '-c', "import tensorflow as tf; print('TensorFlow:', tf.__version__); print('GPUs:', tf.config.list_physical_devices('GPU')); assert tf.config.list_physical_devices('GPU'), 'TensorFlow cannot see the GPU; inspect the CUDA/import messages above'; print('GPU operation:', tf.matmul(tf.ones([2,2]), tf.ones([2,2])))"], 'tensorflow-gpu-diagnostic')
# Reconcile platform-specific optional dependencies missing from the embedded Mac lockfile.
logged(['npm', 'install', '--prefix', 'frontend', '--ignore-scripts', '--no-audit', '--no-fund'], 'install-javascript-verifier')
def run(module, *arguments, name=None):
    logged([PYTHON, '-m', module, *arguments], name or module.replace('.', '-'))
run('unittest', 'discover', '-s', 'training/tests', name='data-and-protocol-tests')
''')
markdown('''
## 3. Persistent run location and experiment configuration
Drive access is used to save research artifacts. Use a new `EXPERIMENT_NAME` for a new protocol; preserve its value when resuming. Three seeds are specified to measure validation variability. They increase runtime substantially. Checkpoint selection and run selection use validation only; only the selected run receives final held-out testing.
''')
code('''
from google.colab import drive
drive.mount('/content/drive')
EXPERIMENT_NAME = 'daisee-full-2fps-v3'
PERSIST = Path('/content/drive/MyDrive/attention_monitoring_full') / EXPERIMENT_NAME
PERSIST.mkdir(parents=True, exist_ok=True)
LOGS = PERSIST / 'logs'
LOGS.mkdir(exist_ok=True)
# /content is ephemeral. Change WORKSPACE to a sufficiently large persistent mounted disk if available.
WORKSPACE = Path('/content/daisee-full-workspace')
WORKSPACE.mkdir(parents=True, exist_ok=True)
DATASET = WORKSPACE / 'dataset'
PREPARED = WORKSPACE / 'prepared'
PRETRAINED = PERSIST / 'pretrained'
SEEDS = [42, 52, 62]
HEAD_EPOCHS = 30
FINE_TUNE_EPOCHS = 20
BATCH_SIZE = 32
PATIENCE = 5
settings = dict(seeds=SEEDS, head_epochs=HEAD_EPOCHS, fine_tune_epochs=FINE_TUNE_EPOCHS,
                batch_size=BATCH_SIZE, patience=PATIENCE, source_payload_sha256=hashlib.sha256(raw).hexdigest())
settings_path = PERSIST / 'experiment_settings.json'
if settings_path.exists():
    assert json.loads(settings_path.read_text()) == settings, 'Configuration changed; choose a new EXPERIMENT_NAME'
else:
    settings_path.write_text(json.dumps(settings, indent=2))
logged(['uv', 'pip', 'freeze', '--python', PYTHON], 'installed-package-versions')
print('Checkpoint/report location:', PERSIST)
print('Video/crop location:', WORKSPACE)
print('Workspace free GiB:', round(shutil.disk_usage(WORKSPACE).free / 1024**3, 1))
''')
markdown('''
## 4. Smoke test the complete software path before transferring the dataset
This uses synthetic inputs solely to check infrastructure. It loads the actual pretrained backbone, performs weighted updates, saves/reloads an optimizer checkpoint, and verifies JavaScript inference against Python. It does **not** create a trained DAISEE release or accuracy report. If it fails, stop and share this cell's log.
''')
code('''
run('training.fetch_pretrained', '--output', PRETRAINED)
run('training.smoke_test', '--pretrained', PRETRAINED / 'mobilenet_7.h5',
    '--output', PERSIST / 'environment_smoke.json')
''')
markdown('''
## 5. Retrieve the full labelled release directly into Colab
The approved archive is inspected using byte ranges. The downloader retrieves every video referenced by each official label CSV, preserving its participant/clip layout. Extra videos without labels are counted and excluded. Existing files are CRC-verified before reuse; an interruption can be continued with the same workspace. Drive must still allow access/range requests. A local computer download is not involved.
''')
code('''
if (PERSIST / 'prepared-2fps.zip').exists():
    print('Prepared data is already preserved; video retrieval is skipped.')
else:
    run('training.download_dataset', '--file-id', '1yrk_wyhZ-c7q0Mcyyi888ylFkl_JDELi',
        '--output', DATASET, '--max-gib', '32', '--resume')
    summary = json.loads((DATASET / 'download_manifest.json').read_text())
    print('Complete labelled partitions:', summary['splits'])
    print('Unlabelled archive videos excluded:', summary['archive_unlabelled_videos_excluded'])
    shutil.copy2(DATASET / 'download_manifest.json', PERSIST / 'download_manifest.json')
''')
markdown('''
## 6. Prepare ordered facial crops at 2 FPS
The source clips and preprocessing configuration are fingerprinted. Per-clip receipts allow completed crops to be verified and reused on interruption. Exactly one reliably tracked face is required. Failed clips remain in the coverage inventory. This step can take a long time and use tens of gigabytes; do not reduce it to the twelve-clip pilot or silently change the sampling rate.
''')
code('''
if (PREPARED / 'preparation.json').exists():
    print('Using existing prepared workspace')
elif (PERSIST / 'prepared-2fps.zip').exists():
    run('training.prepared_bundle', 'unpack', '--prepared', PREPARED, '--archive', PERSIST / 'prepared-2fps.zip')
else:
    run('training.prepare', '--dataset', DATASET, '--output', PREPARED, '--resume')
run('training.prepared_bundle', 'verify', '--prepared', PREPARED)
if not (PERSIST / 'prepared-2fps.zip').exists():
    run('training.prepared_bundle', 'pack', '--prepared', PREPARED, '--archive', PERSIST / 'prepared-2fps.zip')
for name in ('preparation.json', 'clips.json', 'preparation_config.json'):
    shutil.copy2(PREPARED / name, PERSIST / name)
print('Preparation complete; free workspace GiB:', round(shutil.disk_usage(WORKSPACE).free / 1024**3, 1))
''')
markdown('''
## 7. Full training and validation across seeds
Each run first trains the classifier heads, then fine-tunes the late backbone layers. Training-only class/clip balancing is applied to all three heads. The best checkpoint is chosen by validation clip-level engagement macro-F1. Every completed epoch stores the model, optimizer and state record on Drive. Re-running this cell resumes completed epochs. Stochastic random-state continuation is not bit-exact after a restart.

The limits are 30 head epochs and 20 fine-tuning epochs per seed, with early stopping after five epochs without global validation improvement. A successful early-stopped run is a completed training protocol; every run need not consume the maximum epochs.
''')
code('''
RUNS = []
for seed in SEEDS:
    directory = PERSIST / f'seed-{seed}'
    run('training.train', '--prepared', PREPARED, '--pretrained', PRETRAINED / 'mobilenet_7.h5',
        '--output', directory, '--head-epochs', HEAD_EPOCHS, '--fine-tune-epochs', FINE_TUNE_EPOCHS,
        '--batch-size', BATCH_SIZE, '--seed', seed, '--patience', PATIENCE, '--resume', '--require-gpu',
        name=f'train-seed-{seed}')
    validation_file = directory / 'validation_report.json'
    if not validation_file.exists():
        run('training.evaluate', '--prepared', PREPARED, '--run', directory, '--split', 'validation',
            name=f'validate-seed-{seed}')
    record = json.loads((directory / 'training.json').read_text())
    validation = json.loads(validation_file.read_text())
    assert validation['model_sha256'] == record['model_sha256'], 'Stale validation report'
    RUNS.append(directory)
''')
markdown('''
## 8. Summarise validation variability and freeze run selection
The summary reports the mean and population standard deviation of validation metrics across the configured seeds. These are validation statistics, not repeated held-out test scores. The highest validation engagement macro-F1 selects one final model; ties favour the earlier configured seed. The selection is saved before test predictions are requested.
''')
code('''
import statistics
candidates = []
for directory in RUNS:
    trained = json.loads((directory / 'training.json').read_text())
    validation = json.loads((directory / 'validation_report.json').read_text())
    assert trained['model_sha256'] == validation['model_sha256']
    candidates.append(dict(run=directory.name, model_sha256=trained['model_sha256'],
        validation_macro_f1=validation['heads']['engagement']['scorable_macro_f1'],
        validation_accuracy=validation['heads']['engagement']['scorable_accuracy']))
summary = {'runs': candidates, 'scope': 'Validation metrics only; no test-based model selection',
           'validation_macro_f1_mean': statistics.mean(c['validation_macro_f1'] for c in candidates),
           'validation_macro_f1_std': statistics.pstdev(c['validation_macro_f1'] for c in candidates)}
(PERSIST / 'validation_seed_summary.json').write_text(json.dumps(summary, indent=2))
selected = max(candidates, key=lambda c: c['validation_macro_f1'])
selection = {'criterion': 'highest validation clip-level engagement macro-F1; first seed on ties', **selected}
selection_path = PERSIST / 'frozen_selection.json'
if selection_path.exists():
    assert json.loads(selection_path.read_text()) == selection, 'Model selection changed after freezing; use a new experiment'
else:
    selection_path.write_text(json.dumps(selection, indent=2))
FINAL_RUN = PERSIST / selected['run']
print(json.dumps(summary, indent=2))
print('Frozen final model:', FINAL_RUN)
''')
markdown('''
## 9. Final held-out evaluation of the frozen model
This uses only the selected run. Reports include all three heads, per-class metrics, confusion matrices, failed-face coverage, binary engagement metrics, training-majority baselines, and participant-bootstrap confidence intervals. A previously recorded test report is preserved. Do not tune the model after inspecting this test result and still describe that test as untouched.
''')
code('''
test_file = FINAL_RUN / 'test_report.json'
if not test_file.exists():
    run('training.evaluate', '--prepared', PREPARED, '--run', FINAL_RUN, '--split', 'test',
        '--confirm-final-test', name='final-held-out-test')
else:
    existing = json.loads(test_file.read_text())
    assert existing['model_sha256'] == selected['model_sha256'], 'Test report belongs to another checkpoint'
    print('Preserving existing held-out evaluation')
print(test_file.read_text())
''')
markdown('''
## 10. Browser model export and evidence bundle
Exports are accepted only after completed training, matching validation evidence and Python/JavaScript parity checks. The download contains model weights and reports; raw videos and facial crops are excluded. The full fused-versus-affect research comparison, volunteer trials and measured live-system performance remain separate experiments.
''')
code('''
RELEASE = PERSIST / 'browser_release' / 'fer'
if RELEASE.exists() and any(RELEASE.iterdir()):
    metadata = json.loads((RELEASE / 'metadata.json').read_text())
    assert metadata['training']['model_sha256'] == selected['model_sha256'], 'Browser release belongs to another model'
    assert metadata['parity']['status'] == 'passed'
    print('Preserving matching browser release')
else:
    run('training.export', '--run', FINAL_RUN, '--output', RELEASE, name='export-final-browser-model')
run('training.readiness', '--prepared', PREPARED, '--download-manifest', PERSIST / 'download_manifest.json',
    '--run', FINAL_RUN, '--release', RELEASE,
    '--output', PERSIST / 'final_readiness.json', name='final-evidence-audit')
bundle = WORKSPACE / 'final-release-bundle'
bundle.mkdir(exist_ok=True)
shutil.copytree(RELEASE, bundle / 'fer', dirs_exist_ok=True)
for name in ('training.json', 'validation_report.json', 'validation_predictions.csv', 'test_report.json',
             'test_predictions.csv', 'affect.h5', 'environment.json', 'run_config.json', 'source.json', 'UPSTREAM-LICENSE.txt'):
    shutil.copy2(FINAL_RUN / name, bundle / name)
for name in ('frozen_selection.json', 'validation_seed_summary.json', 'download_manifest.json',
             'preparation.json', 'clips.json', 'final_readiness.json', 'environment_smoke.json', 'experiment_settings.json'):
    shutil.copy2(PERSIST / name, bundle / name)
inventory = {path.relative_to(bundle).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in bundle.rglob('*') if path.is_file() and path.name != 'release_inventory.json'}
(bundle / 'release_inventory.json').write_text(json.dumps(inventory, indent=2))
archive_path = shutil.make_archive(str(WORKSPACE / 'daisee-full-trained-release'), 'zip', bundle)
shutil.copy2(archive_path, PERSIST / 'daisee-full-trained-release.zip')
print('Completed release bundle:', PERSIST / 'daisee-full-trained-release.zip')
print('Bundle MiB:', round(Path(archive_path).stat().st_size / 1024**2, 1))
''')
code('''
# Download only the trained model and reports to your computer.
from google.colab import files
release_zip = PERSIST / 'daisee-full-trained-release.zip'
assert release_zip.is_file(), 'Finish the export cell first; inspect its log if it failed'
files.download(str(release_zip))
''')
notebook = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                      'language_info': {'name': 'python'}, 'accelerator': 'GPU'},
            'nbformat': 4, 'nbformat_minor': 4}
# A CPU-only companion stops after preserving prepared data; it never consumes a GPU allocation.
import copy
cpu_cells = copy.deepcopy(cells)
stop = next(i for i, cell in enumerate(cpu_cells) if cell['cell_type'] == 'markdown' and '## 7.' in ''.join(cell['source']))
cpu_cells = cpu_cells[:stop]
for cell in cpu_cells:
    text = ''.join(cell['source'])
    if cell['cell_type'] == 'markdown' and text.startswith('# Full DAiSEE'):
        text = '# Full DAiSEE data preparation — CPU runtime\nSelect Runtime → Change runtime type → CPU. This notebook retrieves all labelled videos and prepares 2 FPS crops, then saves prepared-2fps.zip in Drive. Allow enough Drive quota for the prepared crops. Switch to the GPU notebook with the same experiment name afterward; it restores this bundle and skips video downloads.\n'
    elif cell['cell_type'] == 'markdown' and '## 1.' in text:
        text = '## 1. CPU preparation runtime\nA GPU is not required for download or face-crop preparation.\n'
    elif cell['cell_type'] == 'code' and 'gpu-assignment' in text:
        text = "print('CPU-only data preparation; no GPU allocation required')\n"
    elif cell['cell_type'] == 'code' and 'install-training-dependencies' in text:
        text = text.replace("'tensorflow[and-cuda]==2.15.1'", "'tensorflow==2.15.1'")
        text = '\n'.join(line for line in text.splitlines() if "'tensorflow-gpu-diagnostic'" not in line) + '\n'
    if cell['cell_type'] == 'code':
        ast.parse(text)
    cell['source'] = text.splitlines(True)
cpu_cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': ['Preparation is preserved in Drive. Disconnect this CPU runtime, upload full_daisee_colab.ipynb, select GPU, keep the same experiment name and run the GPU notebook in order. Do not change the 2 FPS model specification mid-experiment.']})
cpu_notebook = {**notebook, 'cells': cpu_cells, 'metadata': {k: v for k, v in notebook['metadata'].items() if k != 'accelerator'}}
(ROOT / 'training' / 'prepare_daisee_colab.ipynb').write_text(json.dumps(cpu_notebook, indent=2) + '\n')
output = ROOT / 'training' / 'full_daisee_colab.ipynb'
output.write_text(json.dumps(notebook, indent=2) + '\n')
print('Built:', output)
print('Bytes:', output.stat().st_size, 'code cells syntax-checked:', sum(c['cell_type'] == 'code' for c in cells))
