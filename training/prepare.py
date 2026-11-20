"""Decode official DAiSEE partitions in time order and prepare MobileNet crops."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
from .common import discover_clips, read_spec, sha256


def face_box(landmarks, margin=0.1):
    xs = [p.x for p in landmarks]
    ys = [p.y for p in landmarks]
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    width, height = x2 - x1, y2 - y1
    return [max(0, y1 - margin * height), max(0, x1 - margin * width),
            min(1, y2 + margin * height), min(1, x2 + margin * width)]


def prepare(dataset, output, resume=False):
    clips = discover_clips(dataset)  # Validate all partitions before writing frames.
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()) and not resume:
        raise ValueError("Output must be empty; use a new folder to avoid mixing preparation runs")
    import cv2
    import mediapipe as mp
    import numpy as np
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    spec = read_spec()
    height, width, _ = spec["input"]["shape"]
    output.mkdir(parents=True, exist_ok=True)
    identity = [{'split': c.split, 'subject_id': c.subject_id, 'clip_id': c.clip_id,
                 'video_sha256': sha256(c.video), 'engagement': c.engagement,
                 'boredom': c.boredom, 'confusion': c.confusion} for c in clips]
    configuration = {'spec': spec, 'clips': identity}
    config_path = output / 'preparation_config.json'
    if config_path.exists():
        if json.loads(config_path.read_text()) != configuration:
            raise ValueError('Dataset or preprocessing changed; use a new preparation folder')
    elif resume and any(output.iterdir()):
        raise ValueError('This folder has no resumable preparation record; use a new output')
    config_path.write_text(json.dumps(configuration, indent=2) + '\n')
    receipts = output / 'clip_receipts'
    receipts.mkdir(exist_ok=True)
    inventory = []
    with (output / "manifest.jsonl").open("w") as manifest:
        for number, clip in enumerate(clips, 1):
            receipt = receipts / f'{clip.split}-{clip.clip_id}.json'
            if resume and receipt.exists():
                cached = json.loads(receipt.read_text())
                for row in cached['rows']:
                    image = (output / row['image']).resolve()
                    if output not in image.parents or not image.is_file() or sha256(image) != row['image_sha256']:
                        raise ValueError(f'Changed/missing cached crop: {row["image"]}')
                    manifest.write(json.dumps(row) + '\n')
                inventory.append(cached['inventory'])
                print(f'{number}/{len(clips)} {clip.split}/{clip.clip_id}: verified cached preparation', flush=True)
                continue
            if shutil.disk_usage(output).free < 1024**3:
                raise ValueError('Less than 1 GiB free; stop and resume on a larger persistent workspace')
            clip_rows = []
            capture = cv2.VideoCapture(str(clip.video))
            fps = capture.get(cv2.CAP_PROP_FPS)
            if not capture.isOpened() or not (fps > 0):
                capture.release()
                inventory.append(dict(split=clip.split, clip_id=clip.clip_id, subject_id=clip.subject_id,
                                      engagement=clip.engagement, boredom=clip.boredom, confusion=clip.confusion,
                                      sampled_frames=0, valid_frames=0, failure="decode_failed"))
                receipt.write_text(json.dumps({'rows': [], 'inventory': inventory[-1]}) + '\n')
                print(f"{number}/{len(clips)} {clip.split}/{clip.clip_id}: decode failed; retained in coverage report", flush=True)
                continue
            decoded, valid, sampled, last_bucket = 0, 0, 0, -1
            try:
                with mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False, max_num_faces=2, refine_landmarks=True,
                    min_detection_confidence=0.8, min_tracking_confidence=0.8,
                ) as detector:
                    while True:
                        success, bgr = capture.read()
                        if not success:
                            break
                        timestamp_ms = 1000 * decoded / fps
                        decoded += 1
                        bucket = int(timestamp_ms * spec["sampling_fps"] / 1000 + 1e-6)
                        if bucket == last_bucket:
                            continue
                        last_bucket = bucket
                        sampled += 1
                        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                        faces = detector.process(rgb).multi_face_landmarks
                        if not faces or len(faces) != 1:
                            continue
                        box = face_box(faces[0].landmark, spec["crop_margin"])
                        if box[2] <= box[0] or box[3] <= box[1]:
                            continue
                        # Same RGB cropAndResize operation and 10% margin as the browser.
                        crop = tf.image.crop_and_resize(tf.cast(rgb[None], tf.float32),
                                                        [box], [0], [height, width])[0]
                        if float(tf.reduce_mean(crop)) < 35:
                            continue
                        pixels = np.clip(crop.numpy(), 0, 255).astype(np.uint8)
                        relative = Path(clip.split) / clip.clip_id / f"{bucket:05d}.png"
                        image = output / relative
                        image.parent.mkdir(parents=True, exist_ok=True)
                        tf.io.write_file(str(image), tf.io.encode_png(pixels))
                        row = dict(split=clip.split, subject_id=clip.subject_id,
                                   clip_id=clip.clip_id, frame_index=bucket,
                                   timestamp_ms=timestamp_ms, image=relative.as_posix(),
                                   engagement=clip.engagement, boredom=clip.boredom, confusion=clip.confusion, image_sha256=sha256(image))
                        clip_rows.append(row)
                        manifest.write(json.dumps(row) + "\n")
                        valid += 1
            finally:
                capture.release()
            inventory.append(dict(split=clip.split, clip_id=clip.clip_id,
                                  subject_id=clip.subject_id, engagement=clip.engagement,
                                  boredom=clip.boredom, confusion=clip.confusion,
                                  sampled_frames=sampled, valid_frames=valid,
                                  failure="decode_failed" if decoded == 0 else "no_reliable_face" if valid == 0 else None))
            temporary = receipt.with_suffix('.partial')
            temporary.write_text(json.dumps({'rows': clip_rows, 'inventory': inventory[-1]}) + '\n')
            temporary.replace(receipt)
            print(f"{number}/{len(clips)} {clip.split}/{clip.clip_id}: {valid}/{sampled} usable frames", flush=True)
    (output / "clips.json").write_text(json.dumps(inventory, indent=2) + "\n")
    (output / "preparation.json").write_text(json.dumps({
        "spec": spec, "manifest_sha256": sha256(output / "manifest.jsonl"),
        "clip_count": len(inventory), "sampling": f"ordered sequence, at most {spec['sampling_fps']} FPS",
    }, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument('--resume', action='store_true', help='Verify completed clips and continue interrupted preparation')
    args = parser.parse_args()
    prepare(args.dataset, args.output, args.resume)


if __name__ == "__main__":
    main()
