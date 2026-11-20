"""Read only committed epoch snapshots and preserve first-on-tie model selection."""
import json
from pathlib import Path


def completed_snapshots(directory, config):
    records = []
    for path in sorted(Path(directory).glob('*/state.json')):
        record = json.loads(path.read_text())
        if record.get('config') != config:
            raise ValueError('Snapshot configuration differs from the current run')
        if record.get('stage') not in ('head', 'fine_tune') or type(record.get('epoch')) is not int or record['epoch'] < 1:
            raise ValueError('Invalid checkpoint stage/epoch')
        if record.get('directory') != path.parent.name or path.parent.name != f"{record['stage']}-{record['epoch']:04d}":
            raise ValueError('Snapshot directory is inconsistent')
        checkpoint = path.parent / 'model.keras'
        if not checkpoint.is_file():
            raise ValueError('Committed checkpoint is missing its model')
        score = record.get('validation_macro_f1')
        if not isinstance(score, (float, int)) or not 0 <= score <= 1:
            raise ValueError('Invalid validation selection score')
        records.append(record)
    return sorted(records, key=lambda r: (0 if r['stage'] == 'head' else 1, r['epoch']))


def best_snapshot(records):
    if not records:
        raise ValueError('No completed training checkpoints')
    ordered = sorted(records, key=lambda r: (0 if r['stage'] == 'head' else 1, r['epoch']))
    return max(ordered, key=lambda r: r['validation_macro_f1'])
