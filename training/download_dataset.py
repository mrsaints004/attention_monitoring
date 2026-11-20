"""Download every labelled DAiSEE clip directly from the approved ZIP, with resume."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import shutil
import zlib
import zipfile
from .common import discover_clips, read_labels, sha256
from .download_subset import DriveRanges, RangeFile, FILE_ID


def crc32(path):
    value = 0
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            value = zlib.crc32(block, value)
    return value & 0xffffffff


def planned_members(infos):
    """Whitelist official partition videos and label files; never extract arbitrary paths."""
    labels, videos = {}, {}
    for info in infos:
        path = PurePosixPath(info.filename)
        lower = [part.lower() for part in path.parts]
        for split, filename in [('Train', 'TrainLabels.csv'), ('Validation', 'ValidationLabels.csv'), ('Test', 'TestLabels.csv')]:
            if path.name.lower() == filename.lower():
                if split in labels:
                    raise ValueError('Ambiguous label CSV: ' + filename)
                labels[split] = info
            if path.suffix.lower() in ('.avi', '.mp4', '.mov') and 'dataset' in lower:
                index = lower.index('dataset')
                if len(path.parts) > index + 3 and lower[index + 1] == split.lower():
                    subject = path.parts[index + 2]
                    if any(part in ('', '.', '..') for part in (subject, path.stem)):
                        raise ValueError('Unsafe archive identifier')
                    key = split, path.stem
                    if key in videos:
                        raise ValueError('Duplicate archive ClipID: ' + path.stem)
                    videos[key] = (subject, info)
    if set(labels) != {'Train', 'Validation', 'Test'}:
        raise ValueError('Official label CSVs not found in the ZIP')
    return labels, videos


def retrieve(file_id, output, max_gib=32, resume=False):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()) and not resume:
        raise ValueError('Output is not empty; use --resume to verify and continue')
    output.mkdir(parents=True, exist_ok=True)
    source = DriveRanges(file_id, max_gib * 1024**3)
    configuration = {'file_id': file_id, 'archive_bytes': source.size, 'scope': 'all clips referenced by supplied official label CSVs'}
    config_path = output / 'download_config.json'
    if config_path.exists() and json.loads(config_path.read_text()) != configuration:
        raise ValueError('Archive changed or output belongs to a different dataset')
    config_path.write_text(json.dumps(configuration, indent=2) + '\n')
    records, skipped = [], 0
    with zipfile.ZipFile(RangeFile(source)) as archive:
        labels, videos = planned_members(archive.infolist())
        def write(info, destination):
            nonlocal skipped
            if destination.exists() and destination.stat().st_size == info.file_size and crc32(destination) == info.CRC:
                skipped += 1
                return
            if info.file_size > 128 * 1024**2:
                raise ValueError('Unexpectedly large individual dataset member')
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + '.partial')
            # One clip per range request avoids downloading the archive or buffering it on disk.
            with archive.open(info) as stream, temporary.open('wb') as target:
                while block := stream.read(8 * 1024**2):
                    target.write(block)
            temporary.replace(destination)
        for split, info in labels.items():
            if info.file_size > 8 * 1024**2:
                raise ValueError('Unexpected label CSV size')
            write(info, output / 'Labels' / f'{split}Labels.csv')
        targets = []
        for split in ('Train', 'Validation', 'Test'):
            for identifier in sorted(read_labels(output / 'Labels' / f'{split}Labels.csv')):
                if (split, identifier) not in videos:
                    raise ValueError(f'Archive lacks labelled clip: {split}/{identifier}')
                subject, info = videos[split, identifier]
                destination = output / 'DataSet' / split / subject / identifier / (identifier + PurePosixPath(info.filename).suffix.lower())
                targets.append((split, subject, identifier, info, destination))
        required = sum(info.file_size for _, _, _, info, path in targets if not path.exists())
        if shutil.disk_usage(output).free < required + 5 * 1024**3:
            raise ValueError('Insufficient runtime disk for labelled videos plus 5 GiB reserve; choose a larger cloud disk')
        print(f'Archive inventory: {len(targets)} labelled clips; {len(videos) - len(targets)} unlabelled archive videos excluded', flush=True)
        for number, (split, subject, identifier, info, destination) in enumerate(targets, 1):
            write(info, destination)
            records.append({'split': split.lower(), 'subject_id': subject, 'clip_id': identifier,
                            'file': destination.relative_to(output).as_posix(), 'bytes': info.file_size,
                            'crc32': info.CRC, 'sha256': sha256(destination)})
            if number % 25 == 0 or number == len(targets):
                print(f'{number}/{len(targets)} verified; transferred this invocation {source.received / 1024**3:.2f} GiB', flush=True)
    verified = discover_clips(output)
    report = {**configuration, 'status': 'complete', 'labelled_clips': len(verified),
              'splits': dict(Counter(c.split for c in verified)), 'archive_unlabelled_videos_excluded': len(videos) - len(targets),
              'transferred_bytes_this_invocation': source.received, 'existing_members_verified': skipped, 'clips': records}
    (output / 'download_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Complete labelled release verified:', report['splits'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file-id', default=FILE_ID)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-gib', type=int, default=32)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.max_gib <= 128:
        parser.error('Transfer budget must be 1..128 GiB')
    retrieve(args.file_id, args.output, args.max_gib, args.resume)


if __name__ == '__main__':
    main()
