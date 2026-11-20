import json
from pathlib import Path
import tempfile
import unittest
from training.experiment_plan import save_plan


class PlanTests(unittest.TestCase):
    def test_reduce_repetitions_preserves_original_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            original = {'seeds': [42, 52, 62], 'head_epochs': 30}
            save_plan(p, original)
            checkpoint = p / 'seed-42/checkpoints/model.keras'
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b'preserved')
            save_plan(p, {**original, 'seeds': [42]})
            self.assertEqual(json.loads((p / 'original_experiment_settings.json').read_text()), original)
            self.assertEqual(checkpoint.read_bytes(), b'preserved')
            save_plan(p, {**original, 'seeds': [42]})

    def test_reduction_after_test_evaluation_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            save_plan(p, {'seeds': [42, 52, 62]})
            (p / 'seed-42').mkdir()
            (p / 'seed-42/test_report.json').write_text('{}')
            with self.assertRaises(ValueError):
                save_plan(p, {'seeds': [42]})

    def test_epoch_protocol_cannot_change_during_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            save_plan(p, {'seeds': [42, 52, 62], 'head_epochs': 30})
            with self.assertRaises(ValueError):
                save_plan(p, {'seeds': [42], 'head_epochs': 5})
