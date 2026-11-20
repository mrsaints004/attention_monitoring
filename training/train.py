"""Fine-tune a face-pretrained MobileNet on the official DAiSEE training split."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
import shutil
from pathlib import Path
from .common import HEADS, load_manifest, read_spec, sha256


def frame_weights(rows):
    """Give clips equal mass, then balance each head using training clips only."""
    clips = {r["clip_id"]: r for r in rows}
    counts = Counter(r["clip_id"] for r in rows)
    class_weights = {}
    for head in HEADS:
        labels = Counter(r[head] for r in clips.values())
        if set(labels) != set(range(4)):
            raise ValueError(f"Training partition needs all four {head} classes")
        class_weights[head] = {label: len(clips) / (4 * count) for label, count in labels.items()}
    scale = len(rows) / len(clips)
    return [{head: scale * class_weights[head][r[head]] / counts[r["clip_id"]]
             for head in HEADS} for r in rows]


def dataset_for(rows, root, batch_size, training=False, seed=42):
    import numpy as np
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    spec = read_spec()
    paths = [str(root / r["image"]) for r in rows]
    labels = {head: np.asarray([r[head] for r in rows], dtype="int32") for head in HEADS}
    if training:
        weights = frame_weights(rows)
        values = (paths, labels, {head: np.asarray([w[head] for w in weights], dtype="float32") for head in HEADS})
    else:
        values = (paths, labels)
    data = tf.data.Dataset.from_tensor_slices(values)
    mean = tf.constant(spec["input"]["mean"], dtype=tf.float32)
    shape = spec["input"]["shape"]

    def decode(path, targets, weights=None):
        image = tf.io.decode_png(tf.io.read_file(path), channels=3)
        image = tf.ensure_shape(image, shape)
        pixels = tf.cast(image, tf.float32)
        # No flips or random crops: keep training and live face preprocessing aligned.
        pixels -= mean
        return (pixels, targets, weights) if weights is not None else (pixels, targets)

    if training:
        data = data.shuffle(min(len(rows), 10000), seed=seed, reshuffle_each_iteration=True)
    workers = int(os.environ.get('DAISEE_DATA_THREADS', '0'))
    if workers < 0:
        raise ValueError('DAISEE_DATA_THREADS must be zero (automatic) or positive')
    if workers:
        options = tf.data.Options()
        options.threading.private_threadpool_size = workers
        options.threading.max_intra_op_parallelism = 1
        data = data.with_options(options)
    data = data.map(decode, num_parallel_calls=workers or tf.data.AUTOTUNE)
    return data.batch(batch_size).prefetch(1 if workers else tf.data.AUTOTUNE)


def make_model(checkpoint):
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    spec = read_spec()
    source = tf.keras.models.load_model(checkpoint, compile=False, custom_objects={"relu6": tf.nn.relu6})
    if list(source.input_shape[1:]) != spec["input"]["shape"]:
        raise ValueError(f"Unexpected pretrained input shape: {source.input_shape}")
    if not any("conv_dw" in layer.name for layer in source.layers):
        raise ValueError("Expected the published MobileNet face-analysis backbone")
    features = source.get_layer(spec["source"]["feature_layer"]).output
    if len(features.shape) == 4:
        features = tf.keras.layers.GlobalAveragePooling2D(name="affect_pool")(features)
    if len(features.shape) != 2:
        raise ValueError("The selected pretrained feature layer is not a feature vector")
    dropped = tf.keras.layers.Dropout(0.25, name="affect_dropout")(features)
    outputs = [tf.keras.layers.Dense(4, activation="softmax", name=head)(dropped) for head in HEADS]
    model = tf.keras.Model(source.input, outputs, name="mobilenet_daisee_affect")
    for layer in model.layers:
        layer.trainable = layer.name in HEADS
    return model


def aggregate_clip_predictions(rows, probabilities):
    """Use one vote per video, not one vote per extracted frame."""
    import numpy as np
    groups = {}
    for row, prediction in zip(rows, probabilities):
        group = groups.setdefault(row["clip_id"], {"label": row["engagement"], "values": []})
        group["values"].append(prediction)
    labels = [group["label"] for group in groups.values()]
    predictions = [int(np.argmax(np.mean(group["values"], axis=0))) for group in groups.values()]
    return labels, predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--pretrained", type=Path, default=Path("training/artifacts/pretrained/mobilenet_7.h5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-epochs", type=int, default=30)
    parser.add_argument("--fine-tune-epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()
    if min(args.head_epochs, args.fine_tune_epochs, args.batch_size, args.patience) < 1:
        parser.error("Epoch counts, patience and batch size must be positive")
    if not args.pretrained.is_file():
        parser.error("Pretrained checkpoint missing. Run python -m training.fetch_pretrained first")
    if args.output.exists() and any(args.output.iterdir()) and not args.resume:
        parser.error("Use --resume for an interrupted run or choose a new output directory")
    provenance_file = args.pretrained.parent / "source.json"
    licence_file = args.pretrained.parent / "UPSTREAM-LICENSE.txt"
    if not provenance_file.is_file() or not licence_file.is_file():
        parser.error("Checkpoint provenance/licence missing. Run training.fetch_pretrained first")
    provenance = json.loads(provenance_file.read_text())
    if provenance.get("sha256") != sha256(args.pretrained) or provenance.get("url") != read_spec()["source"]["url"]:
        parser.error("Pretrained checkpoint does not match recorded provenance")
    preparation = json.loads((args.prepared / "preparation.json").read_text())
    manifest_hash = sha256(args.prepared / "manifest.jsonl")
    if preparation.get("manifest_sha256") != manifest_hash or preparation.get("spec") != read_spec():
        parser.error("Preparation is incomplete, modified or uses a different model specification")
    rows = load_manifest(args.prepared / "manifest.jsonl", verify_images=True)
    training = [r for r in rows if r["split"] == "train"]
    validation = [r for r in rows if r["split"] == "validation"]
    if not training or not validation:
        parser.error("Prepared training and validation frames are required")
    frame_weights(training)
    config = {"manifest_sha256": manifest_hash, "source_sha256": sha256(args.pretrained),
              "spec": read_spec(), "seed": args.seed, "batch_size": args.batch_size,
              "head_epochs": args.head_epochs, "fine_tune_epochs": args.fine_tune_epochs,
              "patience": args.patience}
    args.output.mkdir(parents=True, exist_ok=True)
    config_path = args.output / "run_config.json"
    if config_path.exists():
        if json.loads(config_path.read_text()) != config:
            parser.error("Run configuration/data changed; create a new output directory")
    elif args.resume and any(args.output.iterdir()):
        parser.error("This output has no resumable run configuration")
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    if (args.output / "training.json").exists():
        record = json.loads((args.output / "training.json").read_text())
        if sha256(args.output / "affect.h5") != record["model_sha256"]:
            parser.error("Completed checkpoint was modified")
        print("Training already complete; existing checkpoint preserved")
        return
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    import numpy as np
    import platform
    from datetime import datetime, timezone
    from sklearn.metrics import f1_score, accuracy_score
    from .run_state import completed_snapshots, best_snapshot
    tf.keras.utils.set_random_seed(args.seed)
    devices = tf.config.get_visible_devices("GPU")
    if args.require_gpu and not devices:
        parser.error("TensorFlow reports no GPU. Check the environment diagnostic log before training")
    for device in devices:
        tf.config.experimental.set_memory_growth(device, True)
    shutil.copy2(licence_file, args.output / "UPSTREAM-LICENSE.txt")
    shutil.copy2(provenance_file, args.output / "source.json")
    (args.output / "environment.json").write_text(json.dumps({
        "python": platform.python_version(), "tensorflow": tf.__version__,
        "gpu_devices": [d.name for d in devices], "platform": platform.platform(),
        "seed": args.seed, "resume_reproducibility": "Optimizer and epoch are restored; stochastic RNG continuation is not bit-exact",
    }, indent=2) + "\n")
    train_data = dataset_for(training, args.prepared.resolve(), args.batch_size, True, args.seed)
    validation_data = dataset_for(validation, args.prepared.resolve(), args.batch_size)
    snapshots_dir = args.output / "checkpoints"
    snapshots_dir.mkdir(exist_ok=True)
    records = completed_snapshots(snapshots_dir, config)
    for stage, epochs, learning_rate in (("head", args.head_epochs, 1e-3), ("fine_tune", args.fine_tune_epochs, 1e-5)):
        previous = [r for r in records if r["stage"] == stage]
        previous.sort(key=lambda r: r["epoch"])
        if previous and previous[-1]["stage_finished"]:
            print(f"{stage}: stage already complete", flush=True)
            continue
        if previous:
            latest = previous[-1]
            checkpoint = snapshots_dir / latest["directory"] / "model.keras"
            if sha256(checkpoint) != latest["checkpoint_sha256"]:
                raise ValueError("Resume checkpoint hash mismatch")
            model = tf.keras.models.load_model(checkpoint, custom_objects={"relu6": tf.nn.relu6})
            initial_epoch, wait = latest["epoch"], latest["wait"]
        else:
            initial_epoch, wait = 0, 0
            if stage == "head":
                model = make_model(str(args.pretrained))
            else:
                best = best_snapshot(records)
                checkpoint = snapshots_dir / best["directory"] / "model.keras"
                if sha256(checkpoint) != best["checkpoint_sha256"]:
                    raise ValueError("Best head checkpoint hash mismatch")
                model = tf.keras.models.load_model(checkpoint, compile=False, custom_objects={"relu6": tf.nn.relu6})
                for layer in model.layers[-30:]:
                    if not isinstance(layer, tf.keras.layers.BatchNormalization):
                        layer.trainable = True
            model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate),
                          loss={head: "sparse_categorical_crossentropy" for head in HEADS})
        for epoch in range(initial_epoch + 1, epochs + 1):
            fitted = model.fit(train_data, epochs=1, verbose=2)
            outputs = model.predict(validation_data.map(lambda x, y: x), verbose=0)
            validation_metrics = {}
            for index, head in enumerate(HEADS):
                # Aggregate one prediction per clip; never use test data for checkpoint selection.
                groups = {}
                for row, probabilities in zip(validation, outputs[index]):
                    group = groups.setdefault(row["clip_id"], {"label": row[head], "values": []})
                    group["values"].append(probabilities)
                actual = [g["label"] for g in groups.values()]
                predicted = [int(np.argmax(np.mean(g["values"], axis=0))) for g in groups.values()]
                validation_metrics[head] = {
                    "accuracy": float(accuracy_score(actual, predicted)),
                    "macro_f1": float(f1_score(actual, predicted, labels=[0, 1, 2, 3], average="macro", zero_division=0))}
            score = validation_metrics["engagement"]["macro_f1"]
            global_best = best_snapshot(records)["validation_macro_f1"] if records else -1
            wait = 0 if score > global_best else wait + 1
            finished = epoch >= epochs or wait >= args.patience
            directory = f"{stage}-{epoch:04d}"
            snapshot = snapshots_dir / directory
            snapshot.mkdir(exist_ok=True)
            checkpoint = snapshot / "model.keras"
            temporary = snapshot / "pending.keras"
            model.save(temporary)
            temporary.replace(checkpoint)
            entry = {"stage": stage, "epoch": epoch, "directory": directory, "wait": wait,
                     "stage_finished": finished, "validation_macro_f1": score,
                     "validation_heads": validation_metrics, "config": config,
                     "training_losses": {key: float(values[-1]) for key, values in fitted.history.items()},
                     "checkpoint_sha256": sha256(checkpoint), "recorded_at": datetime.now(timezone.utc).isoformat()}
            temporary_record = snapshot / "state.partial"
            temporary_record.write_text(json.dumps(entry, indent=2) + "\n")
            temporary_record.replace(snapshot / "state.json")
            records.append(entry)
            print(f"{stage} epoch {epoch}: validation engagement macro-F1={score:.4f}; checkpoint committed", flush=True)
            # Rest only after checkpoint + receipt are safely committed, including
            # the final epoch before another stage or seed starts.
            from .runtime_controls import epoch_cooldown
            epoch_cooldown()
            if finished:
                break
        del model
        tf.keras.backend.clear_session()
    selected = best_snapshot(records)
    checkpoint = snapshots_dir / selected["directory"] / "model.keras"
    if sha256(checkpoint) != selected["checkpoint_sha256"]:
        raise ValueError("Selected checkpoint hash mismatch")
    model = tf.keras.models.load_model(checkpoint, compile=False, custom_objects={"relu6": tf.nn.relu6})
    temporary = args.output / "affect.partial.h5"
    model.save(temporary, include_optimizer=False)
    temporary.replace(args.output / "affect.h5")
    (args.output / "training.json").write_text(json.dumps({
        "status": "fine_tuned", "dataset": "DAiSEE", "seed": args.seed,
        "source_sha256": config["source_sha256"], "manifest_sha256": manifest_hash,
        "model_sha256": sha256(args.output / "affect.h5"),
        "selection": "validation clip-level engagement macro-F1; first checkpoint on ties; test partition not used",
        "selected_checkpoint": selected["directory"], "selected_validation_macro_f1": selected["validation_macro_f1"],
        "train_clips": len({r['clip_id'] for r in training}),
        "validation_clips": len({r['clip_id'] for r in validation}),
        "training_label_counts": {head: dict(Counter(row[head] for row in
            {r['clip_id']: r for r in training}.values())) for head in HEADS},
        "spec": read_spec(), "config": config, "stages": records,
    }, indent=2) + "\n")
    print(f"Fine-tuned checkpoint: {args.output / 'affect.h5'}")


if __name__ == "__main__":
    main()
