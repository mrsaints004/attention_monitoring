import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib
from training.common import sha256
from training.extract_dataset import extract


class LocalArchiveTests(unittest.TestCase):
    def make_archive(self, archive_path, corrupt=False):
        target = 'DAiSEE/DataSet/Train/TrainSubject/Train001/Train001.avi'
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for split in ('Train', 'Validation', 'Test'):
                archive.writestr(f'DAiSEE/Labels/{split}Labels.csv',
                    f'ClipID,Engagement,Boredom,Confusion\n{split}001.avi,0,1,2\n')
                archive.writestr(f'DAiSEE/DataSet/{split}/{split}Subject/{split}001/{split}001.avi', b'video integrity fixture')
            archive.writestr('../../outside.txt', b'never extracted')
        if corrupt:
            data = bytearray(archive_path.read_bytes())
            position = data.find(b'PK\x01\x02')
            while position >= 0:
                size = struct.unpack_from('<H', data, position + 28)[0]
                if bytes(data[position + 46:position + 46 + size]).decode() == target:
                    crc = struct.unpack_from('<I', data, position + 16)[0]
                    struct.pack_into('<I', data, position + 16, crc ^ 1)
                    break
                position = data.find(b'PK\x01\x02', position + 4)
            archive_path.write_bytes(data)
        return target

    def test_full_local_extraction_preserves_partitions_and_ignores_other_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = root / 'input.zip'
            self.make_archive(archive)
            output = root / 'dataset'
            extract(archive, output)
            report = json.loads((output / 'download_manifest.json').read_text())
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['splits'], {'train':1, 'validation':1, 'test':1})
            self.assertFalse((root.parent / 'outside.txt').exists())
            extract(archive, output, resume=True)
            self.assertEqual(json.loads((output / 'download_manifest.json').read_text())['existing_members_verified'], 6)

    def test_corruption_is_recorded_and_never_silently_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = root / 'input.zip'
            self.make_archive(archive, corrupt=True)
            output = root / 'dataset'
            with self.assertRaisesRegex(ValueError, 'corrupt labelled'):
                extract(archive, output)
            report = json.loads((output / 'download_manifest.json').read_text())
            self.assertEqual(report['status'], 'incomplete')
            self.assertEqual(len(report['failed_members']), 1)

    def test_source_exception_requires_matching_content_hashes_and_stays_in_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = root / 'input.zip'
            member = self.make_archive(archive, corrupt=True)
            with zipfile.ZipFile(archive) as zipped, archive.open('rb') as stream:
                info = zipped.getinfo(member)
                stream.seek(info.header_offset)
                header = struct.unpack('<4s5H3I2H', stream.read(30))
                start = info.header_offset + 30 + header[-2] + header[-1]
                stream.seek(start); compressed = stream.read(info.compress_size)
                data = zlib.decompress(compressed, -15)
            exception = dict(declared_crc32=info.CRC, source_range=[start,start+info.compress_size-1],
                compressed_sha256=hashlib.sha256(compressed).hexdigest(), sha256=hashlib.sha256(data).hexdigest(),
                actual_crc32=zlib.crc32(data)&0xffffffff)
            receipt = root / 'source_receipt.json'
            receipt.write_text(json.dumps(dict(archive_sha256=sha256(archive), members={member:exception})))
            output = root / 'dataset'
            extract(archive, output, source_exceptions=receipt)
            report = json.loads((output / 'download_manifest.json').read_text())
            self.assertEqual(report['status'], 'complete')
            self.assertIn(member, report['source_crc_exceptions'])
            self.assertIn('declared_zip_crc_mismatch', report['clips'][0]['integrity'])
            exception['sha256'] = '0'*64
            receipt.write_text(json.dumps(dict(archive_sha256=sha256(archive), members={member:exception})))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                extract(archive, root / 'other', source_exceptions=receipt)


if __name__ == '__main__':
    unittest.main()
