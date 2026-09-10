#!/usr/bin/env python3
"""Fetch locked native ARM SDKs; never runs downloaded code or changes global tools."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import urllib.request
import zipfile

PROJECT = Path(__file__).resolve().parents[1]


def tree_sha256(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink in SDK: {path}")
        if not path.is_file() or path.name == ".energy_sdk.json":
            continue
        digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def fetch(item: dict, destination: Path) -> Path:
    directory = destination / f"{item['name']}-{item['commit'][:12]}"
    marker = directory / ".energy_sdk.json"
    if directory.exists():
        if not marker.exists():
            raise ValueError(f"Existing directory has no verification record: {directory}")
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if any(previous.get(k) != item[k] for k in ("commit", "archive_sha256")):
            raise ValueError(f"SDK identity differs from lock: {directory}")
        if tree_sha256(directory) != previous["extracted_tree_sha256"]:
            raise ValueError(f"SDK files changed after extraction: {directory}")
        print(f"Verified existing {directory}")
        return directory
    request = urllib.request.Request(item["archive_url"], headers={"User-Agent": "EnergyProfiling-SDK-fetch"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != item["archive_sha256"]:
        raise ValueError(f"Downloaded archive hash differs from lock: {item['name']}")
    with tempfile.TemporaryDirectory(prefix=".extract-", dir=destination) as temporary:
        unpacked = Path(temporary) / "sdk"
        unpacked.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as files:
            prefix = files.infolist()[0].filename.split("/")[0]
            for entry in files.infolist():
                parts = PurePosixPath(entry.filename).parts
                if not parts or parts[0] != prefix or ".." in parts or PurePosixPath(entry.filename).is_absolute():
                    raise ValueError(f"Unsafe archive path: {entry.filename}")
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError(f"Symlink rejected: {entry.filename}")
                relative = Path(*parts[1:])
                if not relative.parts:
                    continue
                target = (unpacked / relative).resolve()
                if not target.is_relative_to(unpacked.resolve()):
                    raise ValueError(f"Archive escapes destination: {entry.filename}")
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(files.read(entry))
        record = dict(item, extracted_tree_sha256=tree_sha256(unpacked))
        (unpacked / ".energy_sdk.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        unpacked.rename(directory)
    print(f"Fetched and verified {directory}")
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=PROJECT / ".deps", help="Prefer a short Windows path")
    parser.add_argument("--only", choices=("all", "stm32", "stm32f446", "rp2040"), default="all")
    args = parser.parse_args()
    destination = args.dest.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    targets = ("stm32f446", "rp2040") if args.only == "all" else (args.only,)
    for target in targets:
        lock = PROJECT / "firmware" / "targets" / target / "sdk.lock.json"
        for item in json.loads(lock.read_text(encoding="utf-8")):
            fetch(item, destination)


if __name__ == "__main__":
    main()
