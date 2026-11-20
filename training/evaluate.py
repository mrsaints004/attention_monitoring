"""Evaluate the affect classifier per clip; report failed-face coverage explicitly."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from .common import HEADS, load_manifest, sha256
from .train import dataset_for
from .metrics import binary_engagement_metrics, subject_bootstrap_metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--confirm-final-test", action="store_true")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument('--bootstrap-samples', type=int, default=1000)
    parser.add_argument('--bootstrap-seed', type=int, default=42)
    args = parser.parse_args()
    if not 1 <= args.bootstrap_samples <= 10000:
        parser.error('Bootstrap repetitions must be 1..10000')
    if args.split == "test" and not args.confirm_final_test:
        parser.error("Freeze model selection first, then pass --confirm-final-test for held-out evaluation")
    report_path = args.run / f"{args.split}_report.json"
    if report_path.exists():
        parser.error("Evaluation already recorded for this run; keep the report rather than overwriting it")
    training = json.loads((args.run / "training.json").read_text())
    if sha256(args.run / "affect.h5") != training["model_sha256"]:
        parser.error("Checkpoint changed after training")
    if sha256(args.prepared / "manifest.jsonl") != training["manifest_sha256"]:
        parser.error("Prepared dataset changed after training")
    rows = [r for r in load_manifest(args.prepared / "manifest.jsonl", verify_images=True) if r["split"] == args.split]
    inventory = [r for r in json.loads((args.prepared / "clips.json").read_text()) if r["split"] == args.split]
    if not rows or not inventory:
        parser.error("No data for selected partition")
    import numpy as np
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, roc_auc_score, classification_report
    model = tf.keras.models.load_model(str(args.run / "affect.h5"), compile=False)
    data = dataset_for(rows, args.prepared.resolve(), args.batch_size)
    outputs = model.predict(data.map(lambda x, y: x), verbose=0)
    groups = {}
    for index, row in enumerate(rows):
        group = groups.setdefault(row["clip_id"], {head: [] for head in HEADS})
        for head_index, head in enumerate(HEADS):
            group[head].append(outputs[head_index][index])
    report = {"split": args.split, "model_sha256": training["model_sha256"],
              "total_clips": len(inventory), "scorable_clips": len(groups),
              "coverage": len(groups) / len(inventory), "heads": {},
              "scope": "Direct CNN classifier only, not the fused-system hypothesis test"}
    for head in HEADS:
        labels, predictions, scores = [], [], []
        for clip in inventory:
            labels.append(clip[head])
            if clip["clip_id"] not in groups:
                predictions.append(-1)
                scores.append(None)
                continue
            probabilities = np.mean(groups[clip["clip_id"]][head], axis=0)
            predictions.append(int(np.argmax(probabilities)))
            scores.append(float(np.dot(probabilities, np.arange(4)) / 3))
        usable = [i for i, prediction in enumerate(predictions) if prediction >= 0]
        actual = [labels[i] for i in usable]
        predicted = [predictions[i] for i in usable]
        metrics = {
            "scorable_accuracy": float(accuracy_score(actual, predicted)),
            "scorable_macro_f1": float(f1_score(actual, predicted, labels=[0, 1, 2, 3], average="macro", zero_division=0)),
            "all_clip_accuracy_failures_counted_incorrect": float(accuracy_score(labels, predictions)),
            "all_clip_macro_f1": float(f1_score(labels, predictions, labels=[0, 1, 2, 3], average="macro", zero_division=0)),
            "confusion_matrix_scorable": confusion_matrix(actual, predicted, labels=[0, 1, 2, 3]).tolist(),
            "per_class_scorable": classification_report(actual, predicted, labels=[0, 1, 2, 3],
                                                        output_dict=True, zero_division=0),
        }
        metrics['confidence_intervals'] = subject_bootstrap_metrics(
            actual, predicted, [inventory[i]['subject_id'] for i in usable],
            args.bootstrap_samples, args.bootstrap_seed)
        training_counts = training.get('training_label_counts', {}).get(head)
        if training_counts:
            majority = max(range(4), key=lambda label: training_counts.get(str(label), 0))
            metrics['training_majority_baseline'] = {
                'class': majority, 'all_clip_accuracy': sum(label == majority for label in labels) / len(labels)}
        if head == "engagement":
            metrics["binary_engagement"] = binary_engagement_metrics(labels, predictions)
            binary = [int(label >= 2) for label in actual]
            if len(set(binary)) == 2:
                metrics["binary_auc_scorable"] = float(roc_auc_score(binary, [scores[i] for i in usable]))
        report["heads"][head] = metrics
    with (args.run / f"{args.split}_predictions.csv").open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["clip_id", "subject_id", "scorable", *[f"{head}_{field}" for head in HEADS for field in ("label", "probabilities")]])
        for clip in inventory:
            group = groups.get(clip["clip_id"])
            values = []
            for head in HEADS:
                values.extend([clip[head], json.dumps(np.mean(group[head], axis=0).tolist()) if group else ""])
            writer.writerow([clip["clip_id"], clip["subject_id"], bool(group), *values])
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
