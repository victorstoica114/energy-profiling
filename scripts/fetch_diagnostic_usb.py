#!/usr/bin/env python3
"""Fetch Pico SDK 2.2.0's pinned TinyUSB dependency without modifying the SDK."""
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

COMMIT = "86ad6e56c1700e85f1c5678607a762cfe3aa2f47"
SDK_COMMIT = "a1438dff1d38bd9c65dbd693f0e5db4b9ae91779"
ARCHIVE_SHA256 = "3011c90c128988012b553e5d2f0a90bc0b64046591c964bc1f9f6659edcd7e4b"
URL = f"https://codeload.github.com/hathach/tinyusb/zip/{COMMIT}"
MARKER = ".energy_diagnostic_usb.json"
MAX_DOWNLOAD = 64 * 1024 * 1024
MAX_EXTRACTED = 256 * 1024 * 1024
DOC_LINKS = {
    "docs/contributing/code_of_conduct.rst": "CODE_OF_CONDUCT.rst",
    "docs/info/contributors.rst": "CONTRIBUTORS.rst",
}


def tree_sha256(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected filesystem symlink: {path}")
        if path.is_file() and path.name != MARKER:
            digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def unpack(archive: bytes, directory: Path) -> None:
    """Validate every ZIP entry before writing; materialize two known doc links."""
    root = directory.resolve()
    prefix = f"tinyusb-{COMMIT}"
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        entries = source.infolist()
        if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_EXTRACTED:
            raise ValueError("Archive exceeds the extraction limits")
        names: set[str] = set()
        links: list[tuple[zipfile.ZipInfo, Path, str]] = []
        ordinary: list[tuple[zipfile.ZipInfo, Path]] = []
        for entry in entries:
            parts = PurePosixPath(entry.filename).parts
            if (not parts or parts[0] != prefix or ".." in parts or
                    PurePosixPath(entry.filename).is_absolute() or
                    any("\\" in p or ":" in p for p in parts)):
                raise ValueError(f"Unsafe archive path: {entry.filename}")
            relative = PurePosixPath(*parts[1:])
            if not relative.parts:
                continue
            name = relative.as_posix()
            if name.casefold() in names:
                raise ValueError(f"Duplicate archive path: {name}")
            names.add(name.casefold())
            target = root.joinpath(*relative.parts).resolve()
            if not target.is_relative_to(root) or entry.file_size > MAX_DOWNLOAD:
                raise ValueError(f"Invalid archive entry: {name}")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                if name not in DOC_LINKS:
                    raise ValueError(f"Unexpected archive symlink: {name}")
                links.append((entry, target, DOC_LINKS[name]))
            elif entry.is_dir() or not stat.S_IFMT(mode) or stat.S_ISREG(mode):
                ordinary.append((entry, target))
            else:
                raise ValueError(f"Unsupported archive file type: {name}")
        for entry, target in ordinary:
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read(entry))
        for entry, target, expected in links:
            link = source.read(entry).decode("utf-8")
            resolved = (target.parent / link).resolve()
            if resolved != root / expected or not resolved.is_file():
                raise ValueError(f"Unexpected documentation link target: {entry.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(resolved.read_bytes())


def fetch(destination: Path, archive_path: Path | None = None) -> Path:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    directory = destination / f"tinyusb-{COMMIT[:12]}"
    if directory.exists():
        if directory.is_symlink():
            raise ValueError("Existing dependency directory is a symlink")
        record = json.loads((directory / MARKER).read_text(encoding="utf-8"))
        if (record.get("commit") != COMMIT or record.get("archive_sha256") != ARCHIVE_SHA256 or
                record.get("extracted_tree_sha256") != tree_sha256(directory)):
            raise ValueError(f"Existing dependency identity or tree changed: {directory}")
        return directory
    if archive_path is None:
        request = urllib.request.Request(URL, headers={"User-Agent": "EnergyProfiling-diagnostic-fetch"})
        with urllib.request.urlopen(request, timeout=60) as response:
            archive = response.read(MAX_DOWNLOAD + 1)
    else:
        with archive_path.open("rb") as source:
            archive = source.read(MAX_DOWNLOAD + 1)
    if len(archive) > MAX_DOWNLOAD or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Archive exceeds the download limit or differs from the pinned SHA256")
    # TemporaryDirectory cleanup is restricted to this newly created child of destination.
    with tempfile.TemporaryDirectory(prefix=".tinyusb-", dir=destination) as temporary:
        temporary_root = Path(temporary).resolve()
        if temporary_root.parent != destination:
            raise ValueError("Temporary directory escaped the selected destination")
        unpacked = temporary_root / "source"
        unpacked.mkdir()
        unpack(archive, unpacked)
        if not (unpacked / "hw/bsp/rp2040").is_dir():
            raise ValueError("Archive lacks the RP2040 TinyUSB board support")
        record = {"commit": COMMIT, "pico_sdk_commit": SDK_COMMIT,
                  "archive_url": URL, "archive_sha256": ARCHIVE_SHA256,
                  "materialized_documentation_symlinks": DOC_LINKS,
                  "extracted_tree_sha256": tree_sha256(unpacked)}
        (unpacked / MARKER).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        unpacked.rename(directory)
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True, help="Separate dependency parent; prefer a short path")
    parser.add_argument("--archive", type=Path, help="Optional previously downloaded ZIP; the pinned hash is still checked")
    args = parser.parse_args()
    print(fetch(args.dest, args.archive).as_posix())


if __name__ == "__main__":
    main()
