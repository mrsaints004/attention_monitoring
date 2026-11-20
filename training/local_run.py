"""Run the full local DAiSEE protocol and install the numerically verified release."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .common import discover_clips, read_spec, sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'datasets/DAiSEE')
    parser.add_argument('--prepared', type=Path, default=ROOT / 'training/prepared/full-local-2fps-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'training/runs/full-local-2fps-v1')
    parser.add_argument('--pretrained', type=Path, default=ROOT / 'training/artifacts/pretrained/mobilenet_7.h5')
    parser.add_argument('--allow-cpu', action='store_true', help='Explicitly allow slow CPU training if no GPU is visible')
    parser.add_argument('--seeds', type=int, nargs='+', default=[42])
    args = parser.parse_args()
    os.chdir(ROOT)
    args.output.mkdir(parents=True, exist_ok=True)
    logs = args.output / 'logs'; logs.mkdir(exist_ok=True)
    status_path = ROOT / 'training/artifacts/local_full_run_status.json'
    cache = ROOT / 'training/artifacts/runtime-cache'
    cache.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONUNBUFFERED': '1',
                   'MPLCONFIGDIR': str(cache / 'matplotlib'), 'XDG_CACHE_HOME': str(cache)}
    def status(phase, **details):
        value = {'phase': phase, 'updated_at': datetime.now(timezone.utc).isoformat(),
                 'run': str(args.output), 'dataset': str(args.dataset), **details}
        temporary = status_path.with_suffix('.partial')
        temporary.write_text(json.dumps(value, indent=2) + '\n'); temporary.replace(status_path)
        print(json.dumps(value), flush=True)
    def command(arguments, name):
        status(name, log=str(logs / (name + '.log')))
        with (logs / (name + '.log')).open('a') as log:
            process = subprocess.Popen([str(v) for v in arguments], env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            try:
                for line in process.stdout:
                    print(line, end='', flush=True); log.write(line); log.flush()
                if process.wait():
                    raise RuntimeError(f'{name} failed; inspect {logs / (name + ".log")}')
            except BaseException:
                if process.poll() is None: process.terminate(); process.wait()
                raise
    def run(module, *arguments, name=None):
        command([sys.executable, '-m', module, *arguments], name or module.replace('.', '-'))
    import fcntl
    lock = (args.output / '.local-training.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError('This training run is already active in another process')
    try:
        status('validating_dataset')
        clips = discover_clips(args.dataset)
        manifest = json.loads((args.dataset / 'download_manifest.json').read_text())
        if manifest['status'] != 'complete' or manifest['labelled_clips'] != len(clips):
            raise ValueError('The complete verified local dataset inventory is required')
        by_id = {(r['split'], r['clip_id']): r for r in manifest['clips']}
        for clip in clips:
            record = by_id.get((clip.split, clip.clip_id))
            if not record or record['subject_id'] != clip.subject_id or record['sha256'] != sha256(clip.video):
                raise ValueError('Dataset video differs from its verified extraction inventory: ' + clip.clip_id)
        with (args.output / 'installed-packages.txt').open('w') as packages:
            subprocess.run([sys.executable, '-m', 'pip', 'freeze'], stdout=packages, check=True)
        config = {'spec': read_spec(), 'seeds': args.seeds, 'head_epochs': 30,
                  'fine_tune_epochs': 20, 'batch_size': 32, 'patience': 5}
        from .experiment_plan import save_plan
        save_plan(args.output, config)
        print('Planned training seeds:', args.seeds, flush=True)
        from .common import tensorflow_runtime
        tf = tensorflow_runtime()
        import cv2
        devices = tf.config.get_visible_devices('GPU')
        print('TensorFlow:', tf.__version__, 'GPU devices:', devices, flush=True)
        (args.output / 'execution_environment.json').write_text(json.dumps({'tensorflow': tf.__version__, 'device_policy': environment.get('DAISEE_TF_DEVICE', 'auto'), 'visible_gpu_devices': [d.name for d in devices]}, indent=2) + '\n')
        if not devices and not args.allow_cpu:
            raise RuntimeError('No local TensorFlow GPU detected. For slow CPU training rerun with --allow-cpu; otherwise use the cloud GPU notebook')
        anomaly_results = []
        for member, receipt in manifest.get('source_crc_exceptions', {}).items():
            identifier = Path(member).stem
            clip = next(c for c in clips if c.clip_id == identifier)
            if sha256(clip.video) != receipt['sha256']:
                raise ValueError('Source-verified anomalous clip was modified')
            capture = cv2.VideoCapture(str(clip.video))
            declared = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)); decoded = 0
            while capture.isOpened():
                ok, frame = capture.read()
                if not ok: break
                decoded += 1
            capture.release()
            anomaly_results.append({'clip_id': identifier, 'declared_frames': declared,
                'decoded_frames': decoded, 'status': 'decodable' if decoded else 'decode_failed',
                'note': 'ZIP CRC mismatch also exists in the original published archive; preserved source bytes are SHA-256 verified'})
        (args.output / 'source_anomaly_decode_report.json').write_text(json.dumps(anomaly_results, indent=2) + '\n')
        run('training.fetch_pretrained', '--output', args.pretrained.parent)
        run('training.smoke_test', '--pretrained', args.pretrained, '--output', args.output / 'environment_smoke.json')
        run('training.prepare', '--dataset', args.dataset, '--output', args.prepared, '--resume')
        candidates = []
        for seed in args.seeds:
            directory = args.output / f'seed-{seed}'
            run('training.train', '--prepared', args.prepared, '--pretrained', args.pretrained,
                '--output', directory, '--head-epochs', 30, '--fine-tune-epochs', 20,
                '--batch-size', 32, '--patience', 5, '--seed', seed, '--resume',
                *(['--require-gpu'] if devices else []), name=f'train-seed-{seed}')
            if not (directory / 'validation_report.json').exists():
                run('training.evaluate', '--prepared', args.prepared, '--run', directory, '--split', 'validation', name=f'validate-seed-{seed}')
            trained = json.loads((directory / 'training.json').read_text())
            validation = json.loads((directory / 'validation_report.json').read_text())
            if validation['model_sha256'] != trained['model_sha256']:
                raise ValueError('Validation evidence belongs to a different checkpoint')
            candidates.append({'run': directory.name, 'model_sha256': trained['model_sha256'],
                'validation_macro_f1': validation['heads']['engagement']['scorable_macro_f1']})
        selected = max(candidates, key=lambda row: row['validation_macro_f1'])
        selection_path = args.output / 'frozen_selection.json'
        if selection_path.exists() and json.loads(selection_path.read_text()) != selected:
            raise ValueError('Model selection changed after freezing')
        selection_path.write_text(json.dumps(selected, indent=2) + '\n')
        final = args.output / selected['run']
        if not (final / 'test_report.json').exists():
            run('training.evaluate', '--prepared', args.prepared, '--run', final, '--split', 'test', '--confirm-final-test')
        if json.loads((final / 'test_report.json').read_text())['model_sha256'] != selected['model_sha256']:
            raise ValueError('Held-out evidence belongs to a different checkpoint')
        release = args.output / 'browser_release/fer'
        if not (release / 'metadata.json').exists():
            run('training.export', '--run', final, '--output', release)
        run('training.readiness', '--dataset', args.dataset, '--run', final, '--release', release,
            '--output', args.output / 'final_readiness.json')
        bundle = args.output / 'release-bundle'; bundle.mkdir(exist_ok=True)
        shutil.copytree(release, bundle / 'fer', dirs_exist_ok=True)
        for name in ('training.json','validation_report.json','validation_predictions.csv',
                     'test_report.json','test_predictions.csv','affect.h5','source.json','UPSTREAM-LICENSE.txt'):
            shutil.copy2(final / name, bundle / name)
        for name in ('preparation.json','clips.json'):
            shutil.copy2(args.prepared / name, bundle / name)
        shutil.copy2(args.dataset / 'download_manifest.json', bundle / 'download_manifest.json')
        for name in ('experiment_settings.json','frozen_selection.json','final_readiness.json','source_anomaly_decode_report.json'):
            shutil.copy2(args.output / name, bundle / name)
        hashes = {p.relative_to(bundle).as_posix(): sha256(p) for p in bundle.rglob('*')
                  if p.is_file() and p.name != 'release_inventory.json'}
        (bundle / 'release_inventory.json').write_text(json.dumps(hashes, indent=2) + '\n')
        archive = shutil.make_archive(str(args.output / 'daisee-full-trained-release'), 'zip', bundle)
        destination = ROOT / 'frontend/public/models/fer'
        existing = destination / 'metadata.json'
        if existing.exists():
            if json.loads(existing.read_text())['training']['model_sha256'] != selected['model_sha256']:
                raise ValueError('A different full model is already installed; preserve it before replacing')
        else:
            run('training.install_release', '--archive', archive, '--output', destination)
        # Next builds must run from frontend, not the training repository root.
        status('building_frontend')
        with (logs / 'frontend-build.log').open('a') as log:
            subprocess.run(['npm','run','build'], cwd=ROOT / 'frontend', env=environment,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        status('complete', release=archive, model_sha256=selected['model_sha256'],
               test_report=str(final / 'test_report.json'), installed_model=str(destination))
    except BaseException as error:
        status('failed', error=str(error), error_type=type(error).__name__)
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    main()
