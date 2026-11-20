import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipInfo
from training.download_dataset import planned_members
from training.run_state import best_snapshot, completed_snapshots


class FullWorkflowTests(unittest.TestCase):
    def test_archive_only_plans_official_partition_members(self):
        members = [ZipInfo('DAiSEE/Labels/' + name) for name in ['TrainLabels.csv', 'ValidationLabels.csv', 'TestLabels.csv']]
        members += [ZipInfo('DAiSEE/DataSet/Train/subject/clip/clip.avi'), ZipInfo('../../surprise.py')]
        labels, videos = planned_members(members)
        self.assertEqual(len(labels), 3)
        self.assertEqual(set(videos), {('Train', 'clip')})

    def test_ambiguous_labels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            planned_members([ZipInfo('a/TrainLabels.csv'), ZipInfo('b/TrainLabels.csv')])

    def test_duplicate_clip_is_rejected(self):
        names = ['Labels/TrainLabels.csv', 'Labels/ValidationLabels.csv', 'Labels/TestLabels.csv',
                 'DataSet/Train/one/x/x.avi', 'DataSet/Train/two/x/x.avi']
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            planned_members([ZipInfo(n) for n in names])

    def test_earliest_checkpoint_wins_ties_even_after_restart(self):
        records = [{'stage': 'fine_tune', 'epoch': 2, 'validation_macro_f1': .4},
                   {'stage': 'head', 'epoch': 3, 'validation_macro_f1': .4},
                   {'stage': 'head', 'epoch': 1, 'validation_macro_f1': .2}]
        self.assertEqual(best_snapshot(records)['stage'], 'head')
        self.assertEqual(best_snapshot(records)['epoch'], 3)

    def test_incomplete_epoch_snapshot_does_not_count_as_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            pending = Path(temp) / 'head-0001'
            pending.mkdir()
            (pending / 'pending.keras').write_bytes(b'incomplete')
            self.assertEqual(completed_snapshots(temp, {'seed': 42}), [])

    def test_resume_with_different_run_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'head-0001'
            path.mkdir()
            (path / 'state.json').write_text(json.dumps({'config': {'seed': 42}}))
            with self.assertRaisesRegex(ValueError, 'configuration'):
                completed_snapshots(temp, {'seed': 43})

    def test_missing_committed_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'head-0001'
            path.mkdir()
            (path / 'state.json').write_text(json.dumps({'config': {}, 'stage': 'head', 'epoch': 1,
                                                       'directory': 'head-0001'}))
            with self.assertRaisesRegex(ValueError, 'missing'):
                completed_snapshots(temp, {})


class ClusterBootstrapTests(unittest.TestCase):
    def test_perfect_accuracy_interval_and_seed_reproducibility(self):
        from training.metrics import subject_bootstrap_metrics
        labels = [0, 1, 2, 3, 0, 1, 2, 3]
        subjects = ['one'] * 4 + ['two'] * 4
        a = subject_bootstrap_metrics(labels, labels, subjects, 50, 42)
        b = subject_bootstrap_metrics(labels, labels, subjects, 50, 42)
        self.assertEqual(a, b)
        self.assertEqual(a['participants'], 2)
        self.assertEqual(a['scorable_accuracy_interval'], [1., 1.])
        self.assertEqual(a['scorable_macro_f1_interval'], [1., 1.])

    def test_abstentions_cannot_be_silently_included_as_classes(self):
        from training.metrics import subject_bootstrap_metrics
        with self.assertRaisesRegex(ValueError, 'scorable'):
            subject_bootstrap_metrics([0], [-1], ['one'], 10)


class PreparedImageIntegrityTests(unittest.TestCase):
    def test_modified_training_crop_is_rejected(self):
        from training.common import load_manifest, sha256
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / 'frame.png'
            image.write_bytes(b'original PNG fixture')
            manifest = root / 'manifest.jsonl'
            manifest.write_text(json.dumps({'split': 'train', 'clip_id': 'a', 'subject_id': 'one',
                'frame_index': 0, 'engagement': 0, 'boredom': 1, 'confusion': 2,
                'image': image.name, 'image_sha256': sha256(image)}) + '\n')
            self.assertEqual(len(load_manifest(manifest, verify_images=True)), 1)
            image.write_bytes(b'changed crop')
            with self.assertRaisesRegex(ValueError, 'hash'):
                load_manifest(manifest, verify_images=True)


class FullDownloadIntegrationTests(unittest.TestCase):
    def test_full_release_resume_repairs_corruption_and_excludes_unlabelled_video(self):
        import io
        import zipfile
        from unittest.mock import patch
        from training.download_dataset import retrieve
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
            for split in ('Train', 'Validation', 'Test'):
                archive.writestr(f'DAiSEE/Labels/{split}Labels.csv',
                    f'ClipID,Engagement,Boredom,Confusion\n{split}001.avi,0,1,2\n')
                archive.writestr(f'DAiSEE/DataSet/{split}/subject{split}/{split}001/{split}001.avi', b'video fixture')
            archive.writestr('DAiSEE/DataSet/Train/other/unlabelled.avi', b'excluded')
        payload = memory.getvalue()
        class MemoryRanges:
            def __init__(self, file_id, budget):
                self.size, self.received = len(payload), 0
            def fetch(self, start, length):
                data = payload[start:start + length]
                self.received += len(data)
                return data
        with tempfile.TemporaryDirectory() as temp, patch('training.download_dataset.DriveRanges', MemoryRanges):
            output = Path(temp) / 'dataset'
            retrieve('fixture', output)
            report = json.loads((output / 'download_manifest.json').read_text())
            self.assertEqual(report['splits'], {'train': 1, 'validation': 1, 'test': 1})
            self.assertEqual(report['archive_unlabelled_videos_excluded'], 1)
            video = output / report['clips'][0]['file']
            video.write_bytes(b'corrupt file!')
            retrieve('fixture', output, resume=True)
            self.assertEqual(video.read_bytes(), b'video fixture')
            report = json.loads((output / 'download_manifest.json').read_text())
            self.assertEqual(report['existing_members_verified'], 5)


if __name__ == '__main__':
    unittest.main()
