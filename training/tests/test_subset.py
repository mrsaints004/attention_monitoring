import io
import unittest
import zipfile
from training.download_subset import RangeFile, DriveRanges, choose


class MemoryRanges:
    def __init__(self, data):
        self.data = data
        self.size = len(data)

    def fetch(self, start, length):
        return self.data[start:start + length]


class Response:
    status = 200
    headers = {"Content-Type": "application/zip"}
    read_called = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        self.read_called = True
        raise AssertionError("A full-archive response must not be read")


class SubsetTests(unittest.TestCase):
    def test_random_access_can_read_zip_directory_and_selected_member(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("Labels/TrainLabels.csv", "ClipID,Engagement\na.avi,2\n")
            archive.writestr("DataSet/Train/subject/a.avi", b"test video bytes")
        with zipfile.ZipFile(RangeFile(MemoryRanges(data.getvalue()))) as archive:
            self.assertEqual(archive.read("DataSet/Train/subject/a.avi"), b"test video bytes")

    def test_ignored_range_is_rejected_without_reading_full_body(self):
        response = Response()
        source = DriveRanges.__new__(DriveRanges)
        source.url = "https://drive.usercontent.google.com/download?id=fixture"
        source.budget = 1000
        source.received = 0
        source.size = None
        class Opener:
            def open(self, request, timeout):
                return response
        source.opener = Opener()
        with self.assertRaisesRegex(ValueError, "did not honour"):
            source.fetch(0, 1)
        self.assertFalse(response.read_called)

    def test_transfer_budget_stops_before_network_request(self):
        source = DriveRanges.__new__(DriveRanges)
        source.received = 50
        source.budget = 100
        with self.assertRaisesRegex(ValueError, "budget"):
            source.fetch(0, 51)

    def test_selection_uses_labels_and_partition_and_skips_missing_files(self):
        rows = [{"clipid": "b.avi", "engagement": "2"},
                {"clipid": "a.avi", "engagement": "2"},
                {"clipid": "missing.avi", "engagement": "0"}]
        videos = {("train", "a"): "a", ("train", "b"): "b", ("test", "missing"): "m"}
        selected = choose(rows, videos, "Train", 1)
        self.assertEqual([x[0] for x in selected], ["a"])


if __name__ == "__main__":
    unittest.main()
