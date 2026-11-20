import tempfile
from pathlib import Path
import unittest

from training.metrics import binary_engagement_metrics
from training.readiness import audit


class EvidenceTests(unittest.TestCase):
    def test_empty_project_cannot_pass_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            report = audit(release=Path(directory))
        self.assertFalse(report["affect_model_evidence_complete"])
        self.assertTrue(all(not check["passed"] for check in report["checks"]))

    def test_binary_metric_does_not_count_abstentions_as_disengagement(self):
        metrics = binary_engagement_metrics([0, 1, 2, 3], [0, -1, 1, 3])
        self.assertEqual(metrics["confusion_matrix_scorable"], [[1, 0], [1, 1]])
        self.assertEqual(metrics["unavailable_by_true_class"], [1, 0])
        self.assertAlmostEqual(metrics["scorable_accuracy"], 2 / 3)
        self.assertEqual(metrics["all_clip_accuracy_failures_counted_incorrect"], 0.5)

    def test_binary_metric_uses_documented_label_boundary(self):
        metrics = binary_engagement_metrics([0, 1, 2, 3], [1, 0, 3, 2])
        self.assertEqual(metrics["scorable_accuracy"], 1)
        self.assertEqual(metrics["scorable_macro_f1"], 1)

    def test_no_usable_predictions_are_not_reported_as_measured_accuracy(self):
        metrics = binary_engagement_metrics([0, 3], [-1, -1])
        self.assertIsNone(metrics["scorable_accuracy"])
        self.assertEqual(metrics["all_clip_accuracy_failures_counted_incorrect"], 0)

    def test_invalid_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            binary_engagement_metrics([4], [1])


if __name__ == "__main__":
    unittest.main()
