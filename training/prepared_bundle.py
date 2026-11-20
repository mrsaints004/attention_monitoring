"""Preserve prepared crops between CPU and GPU runtimes without repeating downloads."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile
from .common import load_manifest, read_spec, sha256


def validate_prepared(root):
    root = Path(root).resolve()
    report = json.loads((root / 'preparation.json').read_text())
    if report['spec'] != read_spec() or report['manifest_sha256'] != sha256(root / 'manifest.jsonl'):
        raise ValueError('Prepared data specification or manifest changed')
    rows = load_manifest(root / 'manifest.jsonl', verify_images=True)
    if {row['split'] for row in rows} != {'train', 'validation', 'test'}:
        raise ValueError('Prepared data needs all three official partitions')
    clips = json.loads((root / 'clips.json').read_text())
    if len(clips) != report['clip_count']:
        raise ValueError('Coverage inventory does not match preparation record')
    return rows


def pack(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    rows = validate_prepared(root)
    names = {'preparation.json', 'manifest.jsonl', 'clips.json', 'preparation_config.json'}
    names.update(row['image'] for row in rows)
    inventory = {}
    for name in sorted(names):
        path = (root / name).resolve()
        if root not in path.parents or path.is_symlink() or not path.is_file():
            raise ValueError('Missing or unsafe prepared file: ' + name)
        inventory[name] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for name in inventory:
                archive.write(root / name, name)
            archive.writestr('bundle_inventory.json', json.dumps(inventory))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print('Prepared-data bundle saved:', destination, 'bytes:', destination.stat().st_size)


def unpack(archive_path, destination):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Restore destination must be empty')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        names = [info.filename for info in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive members')
        if 'bundle_inventory.json' not in names or archive.getinfo('bundle_inventory.json').file_size > 128 * 1024**2:
            raise ValueError('Missing or oversized prepared bundle inventory')
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                    or stat.S_ISLNK(info.external_attr >> 16) or info.file_size > 512 * 1024**2):
                raise ValueError('Unsafe archive member: ' + info.filename)
        inventory = json.loads(archive.read('bundle_inventory.json'))
        if set(names) != set(inventory) | {'bundle_inventory.json'}:
            raise ValueError('Archive inventory mismatch')
        required = sum(info.file_size for info in archive.infolist())
        if required > 100 * 1024**3 or shutil.disk_usage(destination.parent).free < required + 1024**3:
            raise ValueError('Insufficient free disk for verified prepared data')
        with tempfile.TemporaryDirectory(prefix='prepared-restore-', dir=destination.parent) as temp:
            root = Path(temp) / 'prepared'
            root.mkdir()
            archive.extractall(root)
            for name, record in inventory.items():
                path = root / name
                if path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
                    raise ValueError('Prepared bundle integrity mismatch: ' + name)
            validate_prepared(root)
            (root / 'bundle_inventory.json').unlink()
            if destination.exists():
                destination.rmdir()
            root.replace(destination)
    print('Prepared-data bundle restored and verified:', destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['pack', 'unpack', 'verify'])
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if args.action == 'verify':
        validate_prepared(args.prepared)
        print('Prepared data verified')
    else:
        if args.archive is None:
            parser.error('--archive is required')
        (pack if args.action == 'pack' else lambda root, archive: unpack(archive, root))(args.prepared, args.archive)


if __name__ == '__main__':
    main()
