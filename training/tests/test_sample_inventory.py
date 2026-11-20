import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from training.sample_inventory import prepare


class SampleIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'Labels').mkdir()
        clips = []
        for split, identifier in [('Train', 'a'), ('Validation', 'b'), ('Test', 'c')]:
            path = self.root / (identifier + '.avi')
            path.write_bytes(b'fixture video')
            with (self.root / 'Labels' / (split + 'Labels.csv')).open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ClipID', 'Boredom', 'Engagement', 'Confusion'])
                writer.writerow([identifier + '.avi', 0, 0, 0])
            clips.append({'file': path.name, 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'split': split, 'clip_id': identifier,
                          'source_member': f'DAiSEE/DataSet/{split}/subject-{identifier}/{identifier}/{identifier}.avi',
                          'labels': {'engagement': '0', 'boredom': '0', 'confusion': '0'}})
        self.manifest = {'clips': clips}
        self.save()

    def save(self):
        (self.root / 'sample_manifest.json').write_text(json.dumps(self.manifest))

    def tearDown(self):
        self.temp.cleanup()

    def test_modified_clip_is_rejected_before_decoding(self):
        (self.root / 'a.avi').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'differs from retrieval'):
            prepare(self.root, self.root / 'prepared', '/nonexistent/ffmpeg')

    def test_annotation_disagreement_is_rejected_before_decoding(self):
        self.manifest['clips'][0]['labels']['engagement'] = '3'
        self.save()
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            prepare(self.root, self.root / 'prepared', '/nonexistent/ffmpeg')

    def test_participant_leakage_is_rejected_before_decoding(self):
        self.manifest['clips'][1]['source_member'] = 'DAiSEE/DataSet/Validation/subject-a/b/b.avi'
        self.save()
        with self.assertRaisesRegex(ValueError, 'Participant leakage'):
            prepare(self.root, self.root / 'prepared', '/nonexistent/ffmpeg')


if __name__ == '__main__':
    unittest.main()
