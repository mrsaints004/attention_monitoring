import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from training.common import read_spec, sha256
from training.prepared_bundle import pack, unpack, validate_prepared
from training.install_release import install


class BundleTests(unittest.TestCase):
    def make_prepared(self, root):
        rows = []
        coverage = []
        for index, split in enumerate(('train', 'validation', 'test')):
            image = root / split / 'frame.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'lossless crop integrity fixture ' + bytes([index]))
            rows.append(dict(split=split, clip_id=str(index), subject_id=split,
                             frame_index=0, engagement=0, boredom=1, confusion=2,
                             image=image.relative_to(root).as_posix(), image_sha256=sha256(image)))
            coverage.append(dict(split=split, clip_id=str(index), subject_id=split, valid_frames=1))
        (root / 'manifest.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        (root / 'clips.json').write_text(json.dumps(coverage))
        (root / 'preparation_config.json').write_text('{}')
        (root / 'preparation.json').write_text(json.dumps(dict(spec=read_spec(), clip_count=3,
            manifest_sha256=sha256(root / 'manifest.jsonl'))))

    def test_preparation_survives_runtime_handoff_with_identical_crop_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'; root.mkdir()
            self.make_prepared(root)
            archive = Path(temp) / 'prepared.zip'
            pack(root, archive)
            destination = Path(temp) / 'restored'
            unpack(archive, destination)
            self.assertEqual(validate_prepared(root), validate_prepared(destination))

    def test_corrupt_crop_bundle_is_rejected_without_installing_partial_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'; root.mkdir()
            self.make_prepared(root)
            good, bad = Path(temp) / 'good.zip', Path(temp) / 'bad.zip'
            pack(root, good)
            with zipfile.ZipFile(good) as source, zipfile.ZipFile(bad, 'w') as target:
                for name in source.namelist():
                    target.writestr(name, b'changed' if name.endswith('.png') else source.read(name))
            destination = Path(temp) / 'restored'
            with self.assertRaisesRegex(ValueError, 'integrity'):
                unpack(bad, destination)
            self.assertFalse(destination.exists())

    def test_unsafe_release_paths_are_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('../escaped.txt', b'unsafe')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                install(archive, Path(temp) / 'model')
            self.assertFalse((Path(temp) / 'escaped.txt').exists())

    def test_release_integrity_failure_preserves_empty_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('affect.h5', b'changed')
                bundle.writestr('release_inventory.json', json.dumps({'affect.h5': '0' * 64}))
            destination = Path(temp) / 'model'
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                install(archive, destination)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
