"""Extract and verify all officially labelled clips from a local DAiSEE ZIP."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import shutil
import hashlib
import struct
import zipfile
import zlib
from .common import discover_clips, read_labels, sha256
from .download_dataset import planned_members, crc32


def extract(source, output, resume=False, source_exceptions=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()) and not resume:
        raise ValueError('Use a new output directory or --resume')
    output.mkdir(parents=True, exist_ok=True)
    print('Hashing local archive:', source.name, flush=True)
    signature = {'archive_sha256': sha256(source), 'archive_bytes': source.stat().st_size,
                 'scope': 'all clips referenced by supplied official label CSVs', 'source': 'local ZIP'}
    config = output / 'download_config.json'
    if config.exists() and json.loads(config.read_text()) != signature:
        raise ValueError('Archive changed or output belongs to another source')
    config.write_text(json.dumps(signature, indent=2) + '\n')
    exceptions = {}
    if source_exceptions:
        receipt = json.loads(Path(source_exceptions).read_text())
        if receipt['archive_sha256'] != signature['archive_sha256']:
            raise ValueError('Source exception record belongs to a different archive')
        exceptions = receipt['members']
    reused = 0
    with zipfile.ZipFile(source) as archive:
        labels, videos = planned_members(archive.infolist())
        def write(info, destination):
            nonlocal reused
            exception = exceptions.get(info.filename)
            if exception:
                # Preserve original publisher bytes only when independently re-fetched and fingerprinted.
                # This explicitly records the bad ZIP CRC instead of claiming a successful CRC check.
                if exception['declared_crc32'] != info.CRC:
                    raise ValueError('Source exception CRC record changed')
                if destination.exists() and sha256(destination) == exception['sha256']:
                    reused += 1
                    return
                with source.open('rb') as original:
                    original.seek(info.header_offset)
                    header = struct.unpack('<4s5H3I2H', original.read(30))
                    if header[0] != b'PK\x03\x04':
                        raise ValueError('Invalid local member header')
                    start = info.header_offset + 30 + header[-2] + header[-1]
                    original.seek(start)
                    compressed = original.read(info.compress_size)
                if (exception['source_range'] != [start, start + info.compress_size - 1]
                        or hashlib.sha256(compressed).hexdigest() != exception['compressed_sha256']
                        or info.file_size > 128 * 1024**2 or info.compress_type != zipfile.ZIP_DEFLATED):
                    raise ValueError('Source exception bytes differ from verified remote range')
                decoder = zlib.decompressobj(-15)
                data = decoder.decompress(compressed, info.file_size + 1)
                if (not decoder.eof or len(data) != info.file_size
                        or hashlib.sha256(data).hexdigest() != exception['sha256']
                        or zlib.crc32(data) & 0xffffffff != exception['actual_crc32']):
                    raise ValueError('Source exception decompression/hash mismatch')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                return
            if destination.exists() and destination.stat().st_size == info.file_size and crc32(destination) == info.CRC:
                reused += 1
                return
            if info.file_size > 128 * 1024**2:
                raise ValueError('Unexpectedly large individual member')
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + '.partial')
            with archive.open(info) as stream, temporary.open('wb') as target:
                shutil.copyfileobj(stream, target, 4 * 1024**2)
            if crc32(temporary) != info.CRC:
                raise ValueError('Archive member CRC mismatch')
            temporary.replace(destination)
        for split, member in labels.items():
            if member.file_size > 8 * 1024**2:
                raise ValueError('Oversized label file')
            write(member, output / 'Labels' / f'{split}Labels.csv')
        targets, subjects, seen = [], {}, set()
        for split in ('Train', 'Validation', 'Test'):
            for clip_id in sorted(read_labels(output / 'Labels' / f'{split}Labels.csv')):
                if clip_id in seen:
                    raise ValueError('Clip appears in multiple partitions')
                seen.add(clip_id)
                if (split, clip_id) not in videos:
                    raise ValueError('Labelled video missing: ' + clip_id)
                subject, member = videos[split, clip_id]
                if subject in subjects and subjects[subject] != split:
                    raise ValueError('Subject leakage across official partitions: ' + subject)
                subjects[subject] = split
                destination = output / 'DataSet' / split / subject / clip_id / (clip_id + PurePosixPath(member.filename).suffix.lower())
                targets.append((split, subject, clip_id, member, destination))
        remaining = sum(m.file_size for _, _, _, m, p in targets if not p.exists())
        if shutil.disk_usage(output).free < remaining + 5 * 1024**3:
            raise ValueError('Insufficient disk for extraction plus reserve')
        print('Labelled video inventory:', len(targets), 'unlabelled videos excluded:', len(videos) - len(targets), flush=True)
        records, failures = [], []
        for number, (split, subject, clip_id, member, destination) in enumerate(targets, 1):
            try:
                write(member, destination)
            except (zipfile.BadZipFile, EOFError, zlib.error) as error:
                destination.with_suffix(destination.suffix + '.partial').unlink(missing_ok=True)
                failures.append(dict(split=split.lower(), subject_id=subject, clip_id=clip_id,
                    member=member.filename, reason=str(error), expected_crc32=member.CRC,
                    expected_bytes=member.file_size))
                print(f'{number}/{len(targets)} CORRUPT: {member.filename}', flush=True)
                continue
            records.append(dict(split=split.lower(), subject_id=subject, clip_id=clip_id,
                file=destination.relative_to(output).as_posix(), bytes=member.file_size,
                crc32=crc32(destination), sha256=sha256(destination),
                integrity='original_source_bytes_verified_with_declared_zip_crc_mismatch' if member.filename in exceptions else 'zip_crc_verified'))
            if number % 250 == 0 or number == len(targets):
                print(f'{number}/{len(targets)} clips extracted and verified', flush=True)
    clips = discover_clips(output) if not failures else []
    report = {**signature, 'status': 'incomplete' if failures else 'complete',
        'labelled_clips': len(records), 'declared_labelled_clips': len(targets),
        'splits': dict(Counter(c['split'] for c in records)), 'subjects': len(subjects),
        'failed_members': failures,
        'archive_unlabelled_videos_excluded': len(videos) - len(targets),
        'existing_members_verified': reused, 'source_crc_exceptions': exceptions, 'clips': records}
    (output / 'download_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Verified extracted partitions:', report['splits'], 'subjects:', report['subjects'], flush=True)
    if failures:
        raise ValueError(f"{len(failures)} corrupt labelled members. See {output / 'download_manifest.json'}; training must wait for repair")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--source-exceptions', type=Path, help='Fingerprint-bound record of independently verified source ZIP CRC anomalies')
    args = parser.parse_args()
    extract(args.archive, args.output, args.resume, args.source_exceptions)


if __name__ == '__main__':
    main()
