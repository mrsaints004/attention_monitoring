"""Retrieve a small labelled DAiSEE subset using HTTP ZIP ranges, never the full archive."""
from __future__ import annotations
import argparse
import csv
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import io
import json
from pathlib import Path, PurePosixPath
import re
import urllib.parse
import urllib.request
import zipfile

FILE_ID = "1yrk_wyhZ-c7q0Mcyyi888ylFkl_JDELi"


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
        self.active = False

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "form" and values.get("id") == "download-form":
            self.action = values.get("action")
            self.active = True
        if self.active and tag == "input" and values.get("name"):
            self.fields[values["name"]] = values.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = False


class DriveRanges:
    def __init__(self, file_id, budget):
        self.url = "https://drive.usercontent.google.com/download?" + urllib.parse.urlencode(
            {"id": file_id, "export": "download", "confirm": "t"})
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.budget = budget
        self.received = 0
        self.size = None
        self.fetch(0, 1)

    def fetch(self, start, length):
        if length == 0:
            return b""
        if self.received + length > self.budget:
            raise ValueError("Subset transfer budget reached; no full archive will be downloaded")
        for _ in range(3):
            request = urllib.request.Request(self.url, headers={
                "Range": f"bytes={start}-{start + length - 1}",
                "Accept-Encoding": "identity", "User-Agent": "DAiSEE-research-subset/1.0"})
            with self.opener.open(request, timeout=90) as response:
                if "text/html" in response.headers.get("Content-Type", ""):
                    body = response.read(512 * 1024)
                    self.received += len(body)
                    form = DownloadForm()
                    form.feed(body.decode("utf-8", errors="replace"))
                    if not form.action:
                        raise ValueError("Drive returned an access/quota page. Verify file sharing or try again later")
                    action = urllib.parse.urljoin(self.url, form.action)
                    address = urllib.parse.urlparse(action)
                    if address.scheme != "https" or address.hostname not in ("drive.google.com", "drive.usercontent.google.com"):
                        raise ValueError("Unexpected download confirmation destination")
                    self.url = action + ("&" if address.query else "?") + urllib.parse.urlencode(form.fields)
                    continue
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
                if response.status != 206 or not match:
                    raise ValueError("Drive did not honour partial ZIP requests. Stopped before reading the archive; this link cannot be sampled by this method")
                first, last, total = map(int, match.groups())
                if first != start or last != start + length - 1 or (self.size is not None and self.size != total):
                    raise ValueError("Inconsistent remote byte range; archive may have changed")
                self.size = total
                data = response.read(length + 1)
                self.received += len(data)
                if len(data) != length:
                    raise ValueError("Incomplete remote ZIP byte range")
                return data
        raise ValueError("Drive confirmation did not produce a range-enabled archive")


class RangeFile(io.RawIOBase):
    def __init__(self, source):
        self.source = source
        self.position = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.source.size + offset
        if position < 0:
            raise ValueError("Negative ZIP seek")
        self.position = position
        return position

    def read(self, size=-1):
        remaining = max(0, self.source.size - self.position)
        size = remaining if size < 0 else min(size, remaining)
        data = self.source.fetch(self.position, size)
        self.position += len(data)
        return data


def choose(rows, videos, split, per_class):
    result = []
    for label in range(4):
        candidates = []
        for row in rows:
            key = Path(row.get("clipid", "")).stem
            video = videos.get((split.lower(), key))
            if row.get("engagement") == str(label) and video:
                candidates.append((key, video, row))
        result.extend(sorted(candidates)[:per_class])
    return result


def download(file_id, output, per_class=1, max_mib=96):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty output folder so different subsets cannot be mixed")
    source = DriveRanges(file_id, max_mib * 1024**2)
    with zipfile.ZipFile(RangeFile(source)) as archive:
        infos = archive.infolist()
        videos = {}
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.suffix.lower() not in (".avi", ".mp4", ".mov"):
                continue
            lowered = [p.lower() for p in path.parts]
            for split in ("train", "validation", "test"):
                if "dataset" in lowered and split in lowered:
                    key = (split, path.stem)
                    if key in videos:
                        raise ValueError("Duplicate clip in remote archive")
                    videos[key] = info
        if not videos:
            raise ValueError("No DAiSEE videos found; the archive may contain nested ZIPs or use another layout")
        inventory = []
        labels = []
        for split, name in (("Train", "TrainLabels.csv"), ("Validation", "ValidationLabels.csv"), ("Test", "TestLabels.csv")):
            matches = [i for i in infos if PurePosixPath(i.filename).name.lower() == name.lower()]
            if len(matches) != 1 or matches[0].file_size > 8 * 1024**2:
                raise ValueError(f"Missing, ambiguous or unexpectedly large {name}")
            data = archive.read(matches[0])
            rows = [{str(k).strip().lower(): str(v).strip() for k, v in row.items()}
                    for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig")))]
            labels.append((name, data))
            inventory.extend((split, *item) for item in choose(rows, videos, split, per_class))
        if not inventory:
            raise ValueError("No clips matched the labels")
        compressed = sum(info.compress_size for _, _, info, _ in inventory)
        if source.received + compressed + 2 * 1024**2 > source.budget:
            raise ValueError("Selected clips exceed the transfer budget; reduce --per-class")
        if any(info.file_size > 64 * 1024**2 for _, _, info, _ in inventory):
            raise ValueError("A selected clip exceeds the 64 MiB extraction limit")
        output.mkdir(parents=True, exist_ok=True)
        (output / "Labels").mkdir()
        for name, data in labels:
            (output / "Labels" / name).write_bytes(data)
        records = []
        for split, clip_id, info, row in inventory:
            # Original archive paths are recorded, but not used as local extraction paths.
            extension = PurePosixPath(info.filename).suffix.lower()
            if not re.fullmatch(r"[A-Za-z0-9_-]+", clip_id):
                raise ValueError("Unsafe ClipID")
            path = output / "sample_clips" / split / (clip_id + extension)
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(info) as clip, path.open("wb") as destination:
                while block := clip.read(256 * 1024):
                    destination.write(block)
                    digest.update(block)
            records.append({"split": split, "clip_id": clip_id, "source_member": info.filename,
                            "file": str(path.relative_to(output)), "labels": row,
                            "sha256": digest.hexdigest(), "bytes": path.stat().st_size})
            print(f"Retrieved {split}/{clip_id}: engagement {row['engagement']}", flush=True)
        report = {"dataset": "DAiSEE", "scope": "Small selected sample, not the complete dataset or a trained model",
                  "file_id": file_id, "archive_bytes": source.size, "transferred_bytes": source.received,
                  "selection": "First matching ClipID per engagement class in each official partition",
                  "clips": records}
        (output / "sample_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        (output / "SAMPLE_NOTES.txt").write_text(
            "Real archive samples selected by engagement label. This is not a complete training/evaluation set.\n"
            "Labels contains the original full label CSVs; sample_clips contains only selected clips.\n"
            "The full-data training pipeline intentionally rejects this incomplete layout.\n"
            "Keep videos private and follow DAiSEE's image reproduction restrictions.\n")
        print(f"Retrieved {len(records)} clips; network transfer {source.received / 1024**2:.1f} MiB")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file-id", default=FILE_ID)
    parser.add_argument("--output", type=Path, default=Path("data/daisee_sample"))
    parser.add_argument("--per-class", type=int, default=1)
    parser.add_argument("--max-mib", type=int, default=96)
    args = parser.parse_args()
    if not 1 <= args.per_class <= 5 or not 8 <= args.max_mib <= 512:
        parser.error("Use 1..5 clips per class and an 8..512 MiB transfer budget")
    download(args.file_id, args.output, args.per_class, args.max_mib)


if __name__ == "__main__":
    main()
