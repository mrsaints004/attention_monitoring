"""Binary DAiSEE metrics: labels 0/1 are not engaged; labels 2/3 are engaged."""


def binary_engagement_metrics(labels, predictions):
    if not labels or len(labels) != len(predictions):
        raise ValueError("Non-empty aligned labels and predictions are required")
    if any(type(x) is not int or x not in range(4) for x in labels):
        raise ValueError("Labels must be integers in 0..3")
    if any(type(x) is not int or x not in (-1, 0, 1, 2, 3) for x in predictions):
        raise ValueError("Predictions must be 0..3 or -1 for an unavailable reading")
    matrix = [[0, 0], [0, 0]]
    unavailable = [0, 0]
    for label, prediction in zip(labels, predictions):
        actual = int(label >= 2)
        if prediction == -1:
            unavailable[actual] += 1
        else:
            matrix[actual][int(prediction >= 2)] += 1
    usable = sum(map(sum, matrix))
    correct = matrix[0][0] + matrix[1][1]
    per_class = []
    for label in (0, 1):
        tp = matrix[label][label]
        fp = matrix[1 - label][label]
        fn = matrix[label][1 - label]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class.append({"label": label, "precision_scorable": precision,
                          "recall_scorable": recall,
                          "f1_scorable": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
                          "f1_all_clips": 2 * tp / (2 * tp + fp + fn + unavailable[label])
                          if 2 * tp + fp + fn + unavailable[label] else 0.0,
                          "support_all_clips": sum(matrix[label]) + unavailable[label]})
    return {"definition": "0/1 = not engaged; 2/3 = engaged; unavailable = abstention",
            "scorable_accuracy": correct / usable if usable else None,
            "all_clip_accuracy_failures_counted_incorrect": correct / len(labels),
            "scorable_macro_f1": sum(x["f1_scorable"] for x in per_class) / 2 if usable else None,
            "all_clip_macro_f1": sum(x["f1_all_clips"] for x in per_class) / 2,
            "confusion_matrix_scorable": matrix, "unavailable_by_true_class": unavailable,
            "per_class": per_class}


def subject_bootstrap_metrics(labels, predictions, subjects, repetitions=1000, seed=42):
    """Percentile intervals resample participants, keeping each participant's clips together."""
    import numpy as np
    if not labels or len(labels) != len(predictions) or len(labels) != len(subjects):
        raise ValueError('Aligned non-empty labels, predictions and participants are required')
    if repetitions < 1:
        raise ValueError('Bootstrap repetitions must be positive')
    if any(type(v) is not int or v not in range(4) for v in [*labels, *predictions]):
        raise ValueError('Bootstrap requires scorable four-level labels and predictions')
    identities = sorted(set(subjects))
    grouped = np.zeros((len(identities), 4, 4), dtype=np.int64)
    lookup = {subject: i for i, subject in enumerate(identities)}
    for truth, prediction, subject in zip(labels, predictions, subjects):
        grouped[lookup[subject], truth, prediction] += 1
    generator = np.random.default_rng(seed)
    accuracies, scores = [], []
    for _ in range(repetitions):
        sampled = grouped[generator.integers(0, len(identities), size=len(identities))].sum(axis=0)
        tp = np.diag(sampled).astype(float)
        denominator = sampled.sum(axis=0) + sampled.sum(axis=1)
        f1 = np.divide(2 * tp, denominator, out=np.zeros(4), where=denominator != 0)
        accuracies.append(float(tp.sum() / sampled.sum()))
        scores.append(float(f1.mean()))
    return {'method': 'participant-cluster percentile bootstrap', 'confidence': 0.95,
            'participants': len(identities), 'repetitions': repetitions, 'seed': seed,
            'scorable_accuracy_interval': np.quantile(accuracies, [0.025, 0.975]).tolist(),
            'scorable_macro_f1_interval': np.quantile(scores, [0.025, 0.975]).tolist()}
