"""Download the published face-pretrained MobileNet and preserve provenance."""
from __future__ import annotations
import argparse
import json
import urllib.request
from pathlib import Path
from .common import read_spec, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("training/artifacts/pretrained"))
    parser.add_argument("--sha256", help="Optional independently recorded checkpoint SHA-256")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    spec = read_spec()
    destination = args.output / "mobilenet_7.h5"
    if not destination.exists():
        temporary = destination.with_suffix(".download")
        try:
            with urllib.request.urlopen(spec["source"]["url"], timeout=60) as response, temporary.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            # Fail clearly for an HTML error page or an unresolved Git LFS pointer.
            with temporary.open("rb") as source:
                if source.read(8) != b"\x89HDF\r\n\x1a\n":
                    raise ValueError("Downloaded file is not an HDF5 checkpoint")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    digest = sha256(destination)
    if args.sha256 and digest.lower() != args.sha256.lower():
        raise ValueError("Checkpoint hash does not match --sha256; do not use this file")
    metadata = {**spec["source"], "sha256": digest}
    (args.output / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # Keep the upstream licence alongside the downloaded checkpoint.
    licence = args.output / "UPSTREAM-LICENSE.txt"
    if not licence.exists():
        url = spec["source"]["reference"].replace("https://github.com/", "https://raw.githubusercontent.com/") + "/main/LICENSE"
        with urllib.request.urlopen(url, timeout=30) as response:
            licence.write_bytes(response.read())
    print(f"Pretrained checkpoint ready: {destination}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
