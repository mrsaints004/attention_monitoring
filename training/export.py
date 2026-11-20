"""Export only a fine-tuned, validation-evaluated model and check Python/JS parity."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from .common import HEADS, read_spec, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("frontend/public/models/fer"))
    args = parser.parse_args()
    training = json.loads((args.run / "training.json").read_text())
    report = json.loads((args.run / "validation_report.json").read_text())
    checkpoint = args.run / "affect.h5"
    if training.get("status") != "fine_tuned" or training.get("dataset") != "DAiSEE":
        parser.error("A completed DAiSEE fine-tuning run is required")
    if sha256(checkpoint) != training["model_sha256"] or report["model_sha256"] != training["model_sha256"]:
        parser.error("Training/evaluation report does not match the checkpoint")
    spec = read_spec()
    if training.get("spec") != spec:
        parser.error("Model specification changed since training; do not export with different preprocessing")
    if report.get("scorable_clips", 0) < 1:
        parser.error("A validation report with scorable clips is required")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Output must be empty. Move the previous release aside before exporting")
    import numpy as np
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    from .keras_export import keras_converter
    converter = keras_converter()
    model = tf.keras.models.load_model(str(checkpoint), compile=False, custom_objects={"relu6": tf.nn.relu6})
    if model.output_names != list(HEADS) or list(model.input_shape[1:]) != spec["input"]["shape"]:
        parser.error("Checkpoint has an incompatible input or head order")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="affect-export-", dir=args.output.parent) as temporary:
        staging = Path(temporary) / "model"
        converter.save_keras_model(model, str(staging))
        shape = spec["input"]["shape"]
        rng = np.random.default_rng(42)
        probes = [np.zeros(shape, dtype=np.uint8), np.full(shape, 255, dtype=np.uint8), rng.integers(0, 256, size=shape, dtype=np.uint8)]
        cases = []
        for pixels in probes:
            values = pixels.astype("float32") - np.asarray(spec["input"]["mean"], dtype="float32")
            probabilities = model.predict(values[None], verbose=0)
            cases.append({"pixels": pixels.flatten().tolist(), "expected": [p[0].tolist() for p in probabilities]})
        probe_file = Path(temporary) / "parity.json"
        probe_file.write_text(json.dumps({"input": spec["input"], "cases": cases}))
        verifier = Path(__file__).with_name("verify_export.cjs")
        # Failing to run the browser-compatible model must prevent publication.
        subprocess.run(["node", str(verifier), str(staging), str(probe_file)], check=True)
        metadata = {**spec, "training": {key: training[key] for key in (
            "status", "dataset", "source_sha256", "model_sha256", "manifest_sha256")},
            "validation": {"coverage": report["coverage"], "heads": report["heads"]},
            "parity": {"status": "passed", "absolute_tolerance": 0.0001}}
        (staging / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        shutil.copy2(args.run / "UPSTREAM-LICENSE.txt", staging / "UPSTREAM-LICENSE.txt")
        shutil.copy2(args.run / "source.json", staging / "source.json")
        (staging / "SOURCE.txt").write_text(
            "Backbone: EmotiEffLib mobilenet_7.h5, face-pretrained then adapted to DAiSEE.\n"
            + spec["source"]["reference"] + "\n"
            "Savchenko et al., Classifying emotions and engagement in online learning based on a single facial expression recognition neural network (2022).\n"
            "Gupta et al., DAiSEE: Towards User Engagement Recognition in the Wild.\n"
            "Review upstream checkpoint/dataset redistribution terms before publishing weights.\n")
        if args.output.exists():
            args.output.rmdir()
        shutil.copytree(staging, args.output)
    print(f"Model exported and parity checked: {args.output}")


if __name__ == "__main__":
    main()
