"""Audit DAiSEE evidence without loading TensorFlow or changing any artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from .common import HEADS, SPLITS, discover_clips, read_spec, sha256


def audit(dataset=None, run=None, release=Path("frontend/public/models/fer"), prepared=None, download_manifest=None):
    checks = []

    def check(name, operation):
        try:
            details = operation()
            checks.append({"name": name, "passed": True, "details": details})
        except (OSError, ValueError, KeyError, TypeError) as error:
            checks.append({"name": name, "passed": False, "reason": str(error)})

    def inventory():
        if dataset is None:
            if prepared is None or download_manifest is None:
                raise ValueError("Supply raw dataset or verified prepared data plus its download inventory")
            from .prepared_bundle import validate_prepared
            validate_prepared(prepared)
            source = json.loads(Path(download_manifest).read_text())
            config = json.loads((Path(prepared) / 'preparation_config.json').read_text())
            coverage = json.loads((Path(prepared) / 'clips.json').read_text())
            downloaded = {(c['split'], c['clip_id']): (c['subject_id'], c['sha256']) for c in source['clips']}
            prepared_sources = {(c['split'], c['clip_id']): (c['subject_id'], c['video_sha256']) for c in config['clips']}
            if (source.get('status') != 'complete' or downloaded != prepared_sources
                    or len(downloaded) != source['labelled_clips']
                    or {(c['split'], c['clip_id']) for c in coverage} != set(downloaded)):
                raise ValueError('Prepared data does not cover the completed source download inventory')
            counts = dict(Counter(c['split'] for c in coverage))
            if counts != source['splits']:
                raise ValueError('Prepared partition counts differ from the source inventory')
            return {'scope': 'Verified prepared crops and recorded source hashes; raw videos not re-read',
                    'splits': counts, 'clips': len(downloaded)}
        clips = discover_clips(dataset)
        return {split: {
            "clips": sum(c.split == split for c in clips),
            "subjects": len({c.subject_id for c in clips if c.split == split}),
            "labels": {head: dict(sorted(Counter(getattr(c, head) for c in clips if c.split == split).items()))
                       for head in HEADS},
        } for split in SPLITS}

    def training_record():
        if run is None:
            raise ValueError("Training run path not supplied; no completed run verified")
        record = json.loads((Path(run) / "training.json").read_text())
        if record.get("status") != "fine_tuned" or record.get("dataset") != "DAiSEE":
            raise ValueError("No completed DAiSEE training record")
        if record.get("spec") != read_spec():
            raise ValueError("Training specification differs from the application contract")
        if sha256(Path(run) / "affect.h5") != record["model_sha256"]:
            raise ValueError("Checkpoint hash differs from training record")
        return {key: record[key] for key in ("model_sha256", "train_clips", "validation_clips")}

    def evaluation(split):
        if run is None:
            raise ValueError("No training run supplied")
        record = json.loads((Path(run) / "training.json").read_text())
        report = json.loads((Path(run) / f"{split}_report.json").read_text())
        if report["split"] != split or report["model_sha256"] != record["model_sha256"]:
            raise ValueError("Evaluation report does not match the selected checkpoint/partition")
        if not 0 < report["scorable_clips"] <= report["total_clips"]:
            raise ValueError("Evaluation contains no usable clips or inconsistent coverage")
        if set(report["heads"]) != set(HEADS):
            raise ValueError("Evaluation does not cover all three affect heads")
        return {"total_clips": report["total_clips"], "scorable_clips": report["scorable_clips"],
                "scope": report.get("scope", "unspecified")}

    def deployed():
        release_path = Path(release)
        metadata = json.loads((release_path / "metadata.json").read_text())
        if metadata.get("training", {}).get("status") != "fine_tuned" or metadata["training"].get("dataset") != "DAiSEE":
            raise ValueError("Browser model has no completed DAiSEE training metadata")
        if metadata.get("parity", {}).get("status") != "passed":
            raise ValueError("Python/JavaScript conversion parity was not verified")
        model = json.loads((release_path / "model.json").read_text())
        shards = [p for group in model["weightsManifest"] for p in group["paths"]]
        if not shards:
            raise ValueError("Browser model contains no weight shards")
        for shard in shards:
            path = (release_path / shard).resolve()
            if release_path.resolve() not in path.parents or not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Missing, empty or unsafe model shard: {shard}")
        if run is not None:
            record = json.loads((Path(run) / "training.json").read_text())
            if metadata["training"]["model_sha256"] != record["model_sha256"]:
                raise ValueError("Deployed model differs from the selected training run")
        return {"weight_shards": len(shards), "model_sha256": metadata["training"]["model_sha256"]}

    check("official_dataset_inventory", inventory)
    check("trained_checkpoint", training_record)
    check("validation_evaluation", lambda: evaluation("validation"))
    check("held_out_test_evaluation", lambda: evaluation("test"))
    check("browser_model_release", deployed)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "affect_model_evidence_complete": all(c["passed"] for c in checks),
        "checks": checks,
        "research_requirements_not_established_by_this_audit": [
            "Fused-system versus affect-only evaluation with validation-fitted weights and cut-points",
            "Paired held-out predictions and McNemar hypothesis test",
            "Actual webcam/browser inference and instructor broadcast verification",
            "Measured end-to-end latency and resource usage on two devices",
            "Consented volunteer trials and calibration comparison",
        ],
        "dataset_access": "https://people.iith.ac.in/vineethnb/resources/daisee/index.html",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--download-manifest", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--release", type=Path, default=Path("frontend/public/models/fer"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.dataset, args.run, args.release, args.prepared, args.download_manifest)
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content)
    raise SystemExit(0 if report["affect_model_evidence_complete"] else 2)


if __name__ == "__main__":
    main()
