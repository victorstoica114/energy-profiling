#!/usr/bin/env python3
"""Rebuild a capture CSV from the exact four-byte ppk2-api transport stream."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


class ExportError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_metadata(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"Cannot read metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExportError(f"Expected a JSON object in {path}")
    return value


def make_decoder(metadata: dict):
    try:
        from ppk2_api.ppk2_api import PPK2_API
    except ImportError as exc:
        raise ExportError("ppk2-api is required; install requirements-ppk2.txt") from exc
    try:
        modifiers = metadata["ppk2"]["calibration_metadata"]
        source_voltage_mv = metadata["ppk2"]["source_voltage_setpoint_mV"]
    except (KeyError, TypeError) as exc:
        raise ExportError("Metadata lacks PPK2 calibration or source-voltage data") from exc
    if not isinstance(modifiers, dict) or not isinstance(source_voltage_mv, int):
        raise ExportError("Invalid PPK2 calibration or source-voltage data")

    # PPK2_API.__init__ opens a serial port.  Construct only its documented
    # decoder state so archived streams can be decoded without hardware.
    decoder = PPK2_API.__new__(PPK2_API)
    decoder.ser = None
    decoder.modifiers = modifiers
    decoder.current_vdd = source_voltage_mv
    decoder.adc_mult = 1.8 / 163840
    decoder.MEAS_ADC = {"mask": (2**14 - 1), "pos": 0}
    decoder.MEAS_RANGE = {"mask": (2**3 - 1) << 14, "pos": 14}
    decoder.MEAS_LOGIC = {"mask": (2**8 - 1) << 24, "pos": 24}
    decoder.spike_filter_alpha = 0.18
    decoder.spike_filter_alpha5 = 0.06
    decoder.spike_filter_samples = 3
    decoder.remainder = {"sequence": b"", "len": 0}
    decoder.rolling_avg = None
    decoder.rolling_avg4 = None
    decoder.prev_range = None
    decoder.consecutive_range_samples = 0
    decoder.after_spike = 0
    return decoder


def export_raw(raw_path: Path, metadata: dict, output_path: Path, *, verify_hash: bool = True) -> dict:
    if not raw_path.is_file():
        raise ExportError(f"Raw transport does not exist: {raw_path}")
    byte_count = raw_path.stat().st_size
    if byte_count == 0 or byte_count % 4:
        raise ExportError("Raw transport must contain a nonempty whole number of four-byte frames")
    actual_raw_sha256 = sha256_file(raw_path)
    recorded_sha256 = metadata.get("capture", {}).get("transport_sha256")
    if verify_hash:
        if not isinstance(recorded_sha256, str):
            raise ExportError("Metadata does not contain capture.transport_sha256")
        if actual_raw_sha256 != recorded_sha256:
            raise ExportError("Raw transport SHA-256 does not match capture metadata")
    if output_path.resolve() == raw_path.resolve():
        raise ExportError("Output path cannot replace the raw transport")

    decoder = make_decoder(metadata)
    written = 0
    digest = hashlib.sha256()
    try:
        with (
            raw_path.open("rb") as raw,
            output_path.open("x", encoding="utf-8", newline="", buffering=1024 * 1024) as output,
        ):
            class HashingWriter:
                def write(self, value: str) -> int:
                    digest.update(value.encode("utf-8"))
                    return output.write(value)

            writer = csv.writer(HashingWriter(), lineterminator="\n")
            writer.writerow(("Sample", "Timestamp(us)", "Current(uA)", "D0"))
            while True:
                block = raw.read(4 * 16_384)
                if not block:
                    break
                expected = len(block) // 4
                samples, logic = decoder.get_samples(block)
                if len(samples) != expected or len(logic) != expected:
                    raise ExportError(
                        f"Decoder returned {len(samples)} current/{len(logic)} logic values "
                        f"for {expected} frames"
                    )
                writer.writerows(
                    (written + offset, (written + offset) * 10, repr(float(current)), bits & 1)
                    for offset, (current, bits) in enumerate(zip(samples, logic))
                )
                written += expected
    except BaseException:
        if output_path.exists():
            output_path.unlink()
        raise

    expected_samples = metadata.get("capture", {}).get("sample_count")
    if isinstance(expected_samples, int) and written != expected_samples:
        output_path.unlink()
        raise ExportError(f"Expected {expected_samples} samples from metadata, exported {written}")
    result = {
        "status": "export_complete",
        "raw_path": str(raw_path.resolve()),
        "raw_sha256": actual_raw_sha256,
        "output_path": str(output_path.resolve()),
        "output_sha256": digest.hexdigest(),
        "sample_count": written,
    }
    recorded_csv_sha256 = metadata.get("capture", {}).get("csv_sha256")
    if isinstance(recorded_csv_sha256, str):
        result["recorded_csv_sha256"] = recorded_csv_sha256
        result["csv_hash_matches_recorded"] = digest.hexdigest() == recorded_csv_sha256
        if not result["csv_hash_matches_recorded"]:
            output_path.unlink()
            raise ExportError("Reconstructed CSV SHA-256 does not match capture metadata")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_path", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--allow-unverified",
        action="store_true",
        help="allow a partial/diagnostic stream without its own recorded SHA-256",
    )
    args = parser.parse_args(argv)
    raw_path = args.raw_path.resolve()
    metadata_path = (args.metadata or (raw_path.parent / "capture_metadata.json")).resolve()
    output_path = (args.output or (raw_path.parent / "capture.csv")).resolve()
    try:
        metadata = read_metadata(metadata_path)
        result = export_raw(raw_path, metadata, output_path, verify_hash=not args.allow_unverified)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ExportError, OSError, KeyError, TypeError) as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
