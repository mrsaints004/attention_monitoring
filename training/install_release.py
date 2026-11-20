"""Verify a completed Colab evidence bundle before installing its browser model."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile
from .common import HEADS, read_spec, sha256


def install(archive_path, output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Preserve the existing model first; installation requires an empty destination')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-release-', dir=output.parent) as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive_path) as archive:
            files = [i for i in archive.infolist() if not i.is_dir()]
            names = [i.filename for i in files]
            if len(names) != len(set(names)) or sum(i.file_size for i in files) > 2 * 1024**3:
                raise ValueError('Duplicate or oversized release archive')
            for info in archive.infolist():
                name = PurePosixPath(info.filename)
                if (name.is_absolute() or '..' in name.parts or '\\' in info.filename
                        or stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError('Unsafe release archive member')
            if 'release_inventory.json' not in names or archive.getinfo('release_inventory.json').file_size > 4 * 1024**2:
                raise ValueError('Release integrity inventory missing; use the current export notebook')
            archive.extractall(root)
        inventory = json.loads((root / 'release_inventory.json').read_text())
        if set(inventory) != set(names) - {'release_inventory.json'}:
            raise ValueError('Release inventory does not cover every file')
        for name, digest in inventory.items():
            if sha256(root / name) != digest:
                raise ValueError('Release file hash mismatch: ' + name)
        trained = json.loads((root / 'training.json').read_text())
        if trained.get('status') != 'fine_tuned' or trained.get('dataset') != 'DAiSEE' or trained.get('spec') != read_spec():
            raise ValueError('No completed compatible DAiSEE run')
        digest = sha256(root / 'affect.h5')
        if digest != trained['model_sha256']:
            raise ValueError('Training checkpoint does not match the model record')
        downloaded = json.loads((root / 'download_manifest.json').read_text())
        prepared = json.loads((root / 'preparation.json').read_text())
        coverage = json.loads((root / 'clips.json').read_text())
        if (downloaded.get('status') != 'complete' or prepared['spec'] != read_spec()
                or downloaded['labelled_clips'] != prepared['clip_count']
                or len(coverage) != prepared['clip_count']):
            raise ValueError('Incomplete dataset/preparation evidence')
        if {(c['split'], c['clip_id']) for c in coverage} != {(c['split'], c['clip_id']) for c in downloaded['clips']}:
            raise ValueError('Prepared clips differ from downloaded clips')
        for split in ('validation', 'test'):
            report = json.loads((root / f'{split}_report.json').read_text())
            if (report['split'] != split or report['model_sha256'] != digest
                    or report['total_clips'] != downloaded['splits'][split]
                    or not 0 < report['scorable_clips'] <= report['total_clips']
                    or set(report['heads']) != set(HEADS)):
                raise ValueError('Incomplete or mismatched held-out/validation evidence')
            if not (root / f'{split}_predictions.csv').is_file():
                raise ValueError('Per-clip prediction evidence missing')
        browser = root / 'fer'
        metadata = json.loads((browser / 'metadata.json').read_text())
        if (metadata['training']['model_sha256'] != digest or metadata['training']['status'] != 'fine_tuned'
                or metadata['parity']['status'] != 'passed'
                or any(metadata.get(key) != value for key, value in read_spec().items())):
            raise ValueError('Browser model contract, checkpoint or conversion evidence differs')
        model = json.loads((browser / 'model.json').read_text())
        shards = [p for group in model['weightsManifest'] for p in group['paths']]
        if not shards:
            raise ValueError('Browser model contains no weights')
        for shard in shards:
            path = (browser / shard).resolve()
            if browser not in path.parents or not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Missing or unsafe browser weight shard')
        if output.exists():
            output.rmdir()
        browser.replace(output)
    print('Verified browser model installed:', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('frontend/public/models/fer'))
    args = parser.parse_args()
    install(args.archive, args.output)


if __name__ == '__main__':
    main()
