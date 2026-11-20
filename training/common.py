"""Dataset contracts shared by preparation, training and evaluation.

This module intentionally has no machine-learning dependency, so leakage and
label checks can run before installing TensorFlow or downloading weights.
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

SPEC_PATH = Path(__file__).with_name("model_spec.json")
SPLITS = ("train", "validation", "test")
HEADS = ("engagement", "boredom", "confusion")


def read_spec():
    return json.loads(SPEC_PATH.read_text())


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Clip:
    split: str
    clip_id: str
    subject_id: str
    video: Path
    engagement: int
    boredom: int
    confusion: int


def read_labels(path):
    """Read the official CSV header, including its historical trailing spaces."""
    labels = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        for raw in reader:
            row = {str(key).strip().lower(): str(value).strip() for key, value in raw.items()}
            identifier = row.get("clipid", row.get("clip_id", ""))
            key = Path(identifier).stem
            if not key or key in labels:
                raise ValueError(f"Missing or duplicate ClipID in {path}: {identifier}")
            values = {}
            for head in HEADS:
                try:
                    value = int(row[head])
                except (KeyError, ValueError) as error:
                    raise ValueError(f"Invalid {head} label for {identifier}") from error
                if value not in range(4):
                    raise ValueError(f"{head} label must be 0..3: {identifier}")
                values[head] = value
            labels[key] = values
    return labels


def discover_clips(dataset):
    root = Path(dataset).resolve()
    # Support an extracted DAiSEE/ wrapper without changing the official layout.
    if not (root / "Labels").is_dir() and (root / "DAiSEE" / "Labels").is_dir():
        root /= "DAiSEE"
    layout = (("train", "Train", "TrainLabels.csv"),
              ("validation", "Validation", "ValidationLabels.csv"),
              ("test", "Test", "TestLabels.csv"))
    clips, seen_clips, subjects = [], set(), {}
    for split, directory, filename in layout:
        folder = root / "DataSet" / directory
        if not folder.is_dir():
            raise ValueError(f"Official partition not found: {folder}")
        labels = read_labels(root / "Labels" / filename)
        matched = set()
        for video in sorted(folder.rglob("*")):
            if video.suffix.lower() not in (".avi", ".mp4", ".mov"):
                continue
            identifier = video.stem
            if identifier not in labels:
                raise ValueError(f"Video has no label: {video}")
            if identifier in seen_clips:
                raise ValueError(f"Clip appears more than once: {identifier}")
            relative = video.relative_to(folder)
            if len(relative.parts) < 2:
                raise ValueError(f"Missing subject directory: {video}")
            subject = relative.parts[0]
            if subject in subjects and subjects[subject] != split:
                raise ValueError(f"Subject leakage across official partitions: {subject}")
            subjects[subject] = split
            seen_clips.add(identifier)
            matched.add(identifier)
            clips.append(Clip(split, identifier, subject, video, **labels[identifier]))
        if set(labels) != matched:
            missing = sorted(set(labels) - matched)
            raise ValueError(f"Incomplete {split} dataset: {len(missing)} labelled videos missing; first: {missing[:3]}")
        if not matched:
            raise ValueError(f"Empty partition: {split}")
    return clips


def load_manifest(path, verify_images=False):
    path = Path(path).resolve()
    with path.open() as source:
        rows = [json.loads(line) for line in source if line.strip()]
    seen, subjects, clips, targets = set(), {}, {}, {}
    for row in rows:
        if row["split"] not in SPLITS:
            raise ValueError("Invalid split in prepared manifest")
        key = (row["clip_id"], row["frame_index"])
        if key in seen:
            raise ValueError("Duplicate frame in prepared manifest")
        seen.add(key)
        for head in HEADS:
            if type(row[head]) is not int or row[head] not in range(4):
                raise ValueError("Invalid target in prepared manifest")
        for registry, identifier in ((subjects, row["subject_id"]), (clips, row["clip_id"])):
            if identifier in registry and registry[identifier] != row["split"]:
                raise ValueError("Partition leakage in prepared manifest")
            registry[identifier] = row["split"]
        signature = (row["subject_id"], *(row[head] for head in HEADS))
        if row["clip_id"] in targets and targets[row["clip_id"]] != signature:
            raise ValueError("Inconsistent clip labels or subject in prepared manifest")
        targets[row["clip_id"]] = signature
        image = (path.parent / row["image"]).resolve()
        if path.parent not in image.parents or not image.is_file():
            raise ValueError(f"Missing or unsafe prepared image path: {row['image']}")
        if verify_images and (not row.get("image_sha256") or sha256(image) != row["image_sha256"]):
            raise ValueError(f"Prepared image hash missing or changed: {row['image']}")
    return rows


def parse_split(value):
    if value not in SPLITS:
        raise ValueError(f"Split must be one of {SPLITS}")
    return value


@lru_cache(maxsize=1)
def tensorflow_runtime():
    """Choose the validated execution backend before TensorFlow creates devices."""
    import tensorflow as tf
    device = os.environ.get('DAISEE_TF_DEVICE', 'auto')
    if device not in ('auto', 'cpu'):
        raise ValueError('DAISEE_TF_DEVICE must be auto or cpu')
    if device == 'cpu':
        tf.config.set_visible_devices([], 'GPU')
    return tf
