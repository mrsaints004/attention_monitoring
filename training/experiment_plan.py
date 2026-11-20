"""Record a reduced repetition plan without changing a seed's training protocol."""
import json
from pathlib import Path


def save_plan(output, config):
    output = Path(output)
    path = output / 'experiment_settings.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if previous != config:
            only_repetitions = {k: v for k, v in previous.items() if k != 'seeds'} == {k: v for k, v in config.items() if k != 'seeds'}
            safe_reduction = previous.get('seeds') == [42, 52, 62] and config.get('seeds') == [42]
            frozen = (output / 'frozen_selection.json').exists() or any(output.glob('seed-*/test_report.json'))
            if not only_repetitions or not safe_reduction or frozen:
                raise ValueError('Protocol changed or model selection is frozen; choose a new output directory')
            original = output / 'original_experiment_settings.json'
            if not original.exists():
                original.write_text(json.dumps(previous, indent=2) + '\n')
            (output / 'repetition_plan_change.json').write_text(json.dumps({
                'reason': 'User requested one complete run first to reduce local training time',
                'previous_seeds': previous['seeds'], 'seeds': config['seeds'],
                'per_seed_training_protocol_changed': False,
                'held_out_evaluation_started': False}, indent=2) + '\n')
    temporary = path.with_suffix('.partial')
    temporary.write_text(json.dumps(config, indent=2) + '\n')
    temporary.replace(path)
