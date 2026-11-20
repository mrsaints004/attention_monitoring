"""Verify the supplied DAiSEE sample and decode a separate exploratory CNN input set."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import struct
from .common import read_labels, sha256


def prepare(root, output, ffmpeg):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty preparation directory')
    manifest = json.loads((root / 'sample_manifest.json').read_text())
    labels = {split: read_labels(root / 'Labels' / name) for split, name in (
        ('Train', 'TrainLabels.csv'), ('Validation', 'ValidationLabels.csv'), ('Test', 'TestLabels.csv'))}
    subjects = {}
    seen = set()
    clips = []
    for row in manifest['clips']:
        path = (root / row['file']).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError('Missing or unsafe sample path')
        if sha256(path) != row['sha256'] or path.stat().st_size != row['bytes']:
            raise ValueError('Clip content differs from retrieval manifest: ' + row['clip_id'])
        split, identifier = row['split'], row['clip_id']
        if split not in labels or identifier in seen or path.stem != identifier:
            raise ValueError('Invalid partition or duplicate ClipID')
        seen.add(identifier)
        actual = labels[split][identifier]
        if any(actual[head] != int(row['labels'][head]) for head in ('engagement', 'boredom', 'confusion')):
            raise ValueError('Manifest label disagrees with original CSV: ' + identifier)
        parts = PurePosixPath(row['source_member']).parts
        subject = parts[parts.index('DataSet') + 2]
        if subject in subjects and subjects[subject] != split:
            raise ValueError('Participant leakage across partitions')
        subjects[subject] = split
        clips.append({**row, 'subject_id': subject})
    if set(c['split'] for c in clips) != {'Train', 'Validation', 'Test'}:
        raise ValueError('All sample partitions are required')
    if {int(c['labels']['engagement']) for c in clips if c['split'] == 'Train'} != set(range(4)):
        raise ValueError('All engagement classes are required in the training subset')
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['DYLD_LIBRARY_PATH'] = str(Path(ffmpeg).resolve().parent)
    for clip in clips:
        # Full-frame, 32px RGB pilot input. This is deliberately not the face-crop MobileNet pipeline.
        result = subprocess.run([str(ffmpeg), '-v', 'error', '-i', str(root / clip['file']),
            '-an', '-vf', 'scale=32:32', '-pix_fmt', 'rgb24', '-c:v', 'rawvideo', '-f', 'image2pipe', 'pipe:1'],
            capture_output=True, env=env, check=True)
        raw = result.stdout
        if len(raw) == 0 or len(raw) % (32 * 32 * 3):
            raise ValueError('Video decoding produced no complete RGB frames')
        header = (root / clip['file']).read_bytes()[:2048]
        offset = header.find(b'avih')
        if offset < 0:
            raise ValueError('AVI frame timing header missing')
        microseconds = struct.unpack_from('<I', header, offset + 8)[0]
        if microseconds <= 0:
            raise ValueError('Invalid AVI frame rate')
        frame_size = 32 * 32 * 3
        stride = max(1, round(1_000_000 / microseconds / 2))
        clip['source_frames'] = len(raw) // frame_size
        clip['source_fps'] = 1_000_000 / microseconds
        raw = b''.join(raw[i * frame_size:(i + 1) * frame_size] for i in range(0, clip['source_frames'], stride))
        dest = output / (clip['clip_id'] + '.rgb')
        dest.write_bytes(raw)
        clip['prepared_file'] = dest.name
        clip['decoded_frames'] = len(raw) // (32 * 32 * 3)
        clip['prepared_sha256'] = hashlib.sha256(raw).hexdigest()
        print(clip['split'], clip['clip_id'], clip['decoded_frames'], 'decoded frames', flush=True)
    partitions = {split: {
        'sample_clips': sum(c['split'] == split for c in clips),
        'subjects': len({c['subject_id'] for c in clips if c['split'] == split}),
        'prepared_frames': sum(c['decoded_frames'] for c in clips if c['split'] == split),
        'full_csv_rows': len(labels[split]),
        'label_counts': {head: dict(Counter(int(c['labels'][head]) for c in clips if c['split'] == split))
                         for head in ('engagement', 'boredom', 'confusion')},
    } for split in ('Train', 'Validation', 'Test')}
    report = {'dataset': 'DAiSEE', 'scope': '12-clip selected sample; not the complete benchmark',
        'verified_at': datetime.now(timezone.utc).isoformat(), 'manifest_sha256': sha256(root / 'sample_manifest.json'),
        'raw_bytes': sum(c['bytes'] for c in clips), 'partitions': partitions,
        'preprocessing': {'region': 'full_frame', 'shape': [32, 32, 3], 'sampling_fps': 2,
                          'normalization': 'divide_by_255', 'purpose': 'exploratory engagement-only CNN'},
        'clips': clips}
    (output / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', type=Path, default=Path('daisee_sample'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.sample, args.output, args.ffmpeg)


if __name__ == '__main__':
    main()
