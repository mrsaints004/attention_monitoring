import csv
import json
from pathlib import Path
import tempfile
import unittest
from training.common import discover_clips, load_manifest, read_labels
from training.train import frame_weights


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "Labels").mkdir()
        for split, label_file, subject in (("Train", "TrainLabels.csv", "100"), ("Validation", "ValidationLabels.csv", "200"), ("Test", "TestLabels.csv", "300")):
            folder = self.root / "DataSet" / split / subject / (subject + "001")
            folder.mkdir(parents=True)
            (folder / (subject + "001.avi")).write_bytes(b"fixture")
            with (self.root / "Labels" / label_file).open("w", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(["ClipID", "Boredom ", "Engagement", "Confusion", "Frustration"])
                writer.writerow([subject + "001.avi", 1, 2, 0, 1])

    def tearDown(self):
        self.temp.cleanup()

    def test_official_layout_and_whitespace_headers(self):
        clips = discover_clips(self.root)
        self.assertEqual([clip.split for clip in clips], ["train", "validation", "test"])
        self.assertEqual(clips[0].engagement, 2)
        self.assertEqual(clips[0].boredom, 1)

    def test_missing_video_is_not_silently_ignored(self):
        next((self.root / "DataSet" / "Train").rglob("*.avi")).unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            discover_clips(self.root)

    def test_subject_leakage_is_rejected(self):
        folder = self.root / "DataSet" / "Validation" / "200"
        folder.rename(folder.parent / "100")
        with self.assertRaisesRegex(ValueError, "Subject leakage"):
            discover_clips(self.root)

    def test_labels_outside_four_levels_are_rejected(self):
        label_file = self.root / "Labels" / "TrainLabels.csv"
        label_file.write_text("ClipID,Boredom,Engagement,Confusion\na.avi,0,4,1\n")
        with self.assertRaisesRegex(ValueError, "0..3"):
            read_labels(label_file)

    def test_manifest_rejects_frame_path_escape(self):
        manifest = self.root / "manifest.jsonl"
        row = dict(split="train", clip_id="a", frame_index=0, subject_id="1",
                   engagement=0, boredom=0, confusion=0, image="../outside.png")
        manifest.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "unsafe"):
            load_manifest(manifest)

    def test_frame_weighting_gives_each_clip_equal_mass(self):
        rows = []
        for label, frames in enumerate([1, 3, 2, 5]):
            rows.extend(dict(clip_id=str(label), engagement=label, boredom=label, confusion=label) for _ in range(frames))
        weights = frame_weights(rows)
        masses = [sum(w["engagement"] for row, w in zip(rows, weights) if row["clip_id"] == str(label)) for label in range(4)]
        for mass in masses:
            self.assertAlmostEqual(mass, masses[0])


if __name__ == "__main__":
    unittest.main()
