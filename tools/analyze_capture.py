#!/usr/bin/env python3
"""Check 12 single-GPIO windows structurally, then integrate their charge.

No MCU execution times or waveform thresholds are used. Original captures are
opened read-only. See docs/capture_format.md for the deliberately strict schema.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
import sys
import zipfile
import zlib
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator

ALGORITHMS = ("RLE", "Delta", "LZ77", "Huffman", "AES-128", "SHA-256",
              "ChaCha20", "CRC32", "FFT", "FIR", "IIR", "DCT")
CURRENT_UNITS = {"A": 1.0, "mA": 1e-3, "uA": 1e-6}
TIME_UNITS = {"s": 1.0, "ms": 1e-3, "us": 1e-6}
REQUIRED_RATE = 100_000
DEFAULT_MAX_SAMPLES = 60_000_000
NORDIC_COMMIT = "881d596480f60dea045ad6f3643afdc3f9d5a0a6"


class CaptureError(ValueError):
    """Input violates the single-GPIO structural acquisition contract."""


def finite_number(value, label: str, *, positive=False) -> float:
    if isinstance(value, bool):
        raise CaptureError(f"{label}: boolean is not a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CaptureError(f"{label}: expected a number") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        raise CaptureError(f"{label}: expected a finite{' positive' if positive else ''} number")
    return number


def require_rate(rate, expected=REQUIRED_RATE) -> float:
    rate = finite_number(rate, "sample rate", positive=True)
    if rate != expected or rate != REQUIRED_RATE:
        raise CaptureError(f"Expected native 100000 samples/s; received {rate:g}")
    return rate


def strict_json(data: bytes | str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CaptureError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise CaptureError(f"Nonfinite JSON constant: {value}")

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=reject_constant,
                          parse_float=lambda value: finite_number(value, "JSON number"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CaptureError(f"Invalid JSON: {exc}") from exc


def load_manifest(path: Path, board: str) -> dict:
    manifest = strict_json(path.read_bytes())
    if not isinstance(manifest, dict):
        raise CaptureError("Experiment manifest must be a JSON object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 2:
        raise CaptureError("Expected single-GPIO experiment manifest schema_version 2; legacy protocols are unsupported")
    if manifest.get("experiment_id") != "energy-profiling-v3-single-gpio":
        raise CaptureError("Expected experiment_id energy-profiling-v3-single-gpio")
    channels = manifest.get("digital_channels")
    if channels != {"RUN": 0} or type(channels["RUN"]) is not int:
        raise CaptureError("Manifest must assign only RUN to D0")
    if manifest.get("stable_baseline_seconds") != 2.0:
        raise CaptureError("Manifest must select a 2-second startup baseline")
    for key, expected_ms in (("startup_idle_ms", 5000), ("inter_algorithm_idle_ms", 1000),
                             ("post_suite_idle_ms", 2000), ("minimum_capture_tail_ms", 3000)):
        if manifest.get(key) != expected_ms:
            raise CaptureError(f"Manifest {key} must be {expected_ms} for this protocol version")
    require_rate(manifest.get("sample_rate_Hz"))
    listed = manifest.get("algorithms")
    expected = [{"id": i, "name": name} for i, name in enumerate(ALGORITHMS, 1)]
    if not isinstance(listed, list) or len(listed) != 12 or any(
        not isinstance(a, dict) or type(a.get("id")) is not int or a.get("id") != e["id"] or a.get("name") != e["name"]
        for a, e in zip(listed, expected)
    ):
        raise CaptureError("Manifest algorithms must list fixed IDs 1..12 in protocol order")
    boards = manifest.get("boards")
    if not isinstance(boards, dict) or not isinstance(boards.get(board), dict):
        raise CaptureError(f"Manifest has no board {board!r}")
    expected_pin = {"esp32": 18, "rp2040": 2, "stm32": "PC0"}.get(board)
    pin = boards[board].get("marker_pin")
    if expected_pin is None or type(pin) is not type(expected_pin) or pin != expected_pin:
        raise CaptureError(f"Manifest marker_pin for {board} must be {expected_pin!r}")
    counts = boards[board].get("iterations")
    if not isinstance(counts, dict) or set(counts) != set(ALGORITHMS):
        raise CaptureError("Board iterations must specify exactly the 12 algorithm names")
    for name, count in counts.items():
        if type(count) is not int or count <= 0:
            raise CaptureError(f"Invalid iteration count for {name}: {count!r}")
    finite_number(manifest.get("nominal_voltage_V"), "nominal voltage", positive=True)
    return manifest


@dataclass
class Capture:
    samples: Iterable[tuple[float, int | None]]  # D0: 0/1; None only in unknown startup prefix
    sample_rate_hz: float
    metadata: dict


def decode_d0(state: int, label: str) -> int | None:
    """Decode only D0. Unconnected D1..D7 never establish or invalidate a gate."""
    if state == 3:
        raise CaptureError(f"{label}: mixed D0 state; native-resolution gates required")
    if type(state) is not int or state not in (0, 1, 2):
        raise CaptureError(f"{label}: invalid D0 state")
    return (None, 0, 1)[state]


@contextmanager
def open_native(path: Path, *, expected_rate=REQUIRED_RATE,
                max_samples=DEFAULT_MAX_SAMPLES) -> Iterator[Capture]:
    """Read version-2 PPK2 ZIP in bounded chunks; never extract to disk."""
    max_bytes = max_samples * 6 + 65 * 1024 * 1024
    if path.stat().st_size > max_bytes:
        raise CaptureError("PPK2 archive exceeds configured size limit")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != 3 or {x.filename for x in entries} != {
            "metadata.json", "session.raw", "minimap.raw"
        }:
            raise CaptureError("Expected exactly metadata.json, session.raw and minimap.raw")
        if len({x.filename for x in entries}) != len(entries):
            raise CaptureError("Duplicate ZIP member")
        for entry in entries:
            if entry.flag_bits & 1 or entry.is_dir() or ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                raise CaptureError("Encrypted, directory or symlink ZIP members are unsupported")
            if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise CaptureError("Unsupported ZIP compression")
        if sum(x.file_size for x in entries) > max_bytes:
            raise CaptureError("Decompressed ZIP exceeds configured limit")
        if archive.getinfo("metadata.json").file_size > 1024 * 1024:
            raise CaptureError("PPK2 metadata exceeds 1 MiB")
        if archive.getinfo("minimap.raw").file_size > 64 * 1024 * 1024:
            raise CaptureError("PPK2 minimap exceeds 64 MiB")
        meta = strict_json(archive.read("metadata.json"))
        if not isinstance(meta, dict) or type(meta.get("formatVersion")) is not int or meta["formatVersion"] != 2:
            raise CaptureError("Only explicitly versioned PPK2 formatVersion 2 is supported")
        payload = meta.get("metadata")
        if not isinstance(payload, dict):
            raise CaptureError("Missing PPK2 metadata object")
        if type(payload.get("samplesPerSecond")) not in (int, float):
            raise CaptureError("PPK2 samplesPerSecond must be a JSON number")
        rate = require_rate(payload.get("samplesPerSecond"), expected_rate)
        if "startSystemTime" in payload:
            finite_number(payload["startSystemTime"], "startSystemTime")
        size = archive.getinfo("session.raw").file_size
        if not size or size % 6 or size // 6 > max_samples:
            raise CaptureError("Empty, truncated or oversized native sample stream")

        def samples():
            count = 0
            with archive.open("session.raw") as stream:
                while True:
                    block = stream.read(6 * 16_384)
                    if not block:
                        break
                    if len(block) % 6:
                        raise CaptureError("Native stream ends inside a six-byte frame")
                    for current_ua, wire_bits in struct.iter_unpack("<fH", block):
                        # Digital word is big endian; <H reads it byte-swapped.
                        # D0's least-significant pair is therefore bits 8..9 here.
                        run = decode_d0((wire_bits >> 8) & 3, f"Sample {count}")
                        current = finite_number(current_ua, f"sample {count} current") * 1e-6
                        yield current, run
                        count += 1
                        if count > max_samples:
                            raise CaptureError("Sample limit exceeded")
            if count * 6 != size:
                raise CaptureError("Native sample count does not match ZIP member length")

        yield Capture(samples(), rate, {
            "format": "nordic_ppk2_v2", "native_metadata": meta,
            "declared_samples": size // 6,
            "time_basis": "index / metadata.samplesPerSecond; no per-sample physical timestamps",
            "digital_encoding": "big-endian uint16; only D0 low pair decoded, 01=LOW, 10=HIGH",
            "selected_digital_channel": "D0", "ignored_digital_channels": ["D1", "D2", "D3", "D4", "D5", "D6", "D7"],
            "voltage_sampled": False,
            "packet_loss_absence_proven": False,
        })


@contextmanager
def open_csv(path: Path, *, sample_rate_hz: float, profile: str,
             current_column=None, current_unit=None, time_column=None, time_unit=None,
             digital_column=None, digital_bitstring_column=None, index_column=None,
             delimiter=",", max_samples=DEFAULT_MAX_SAMPLES) -> Iterator[Capture]:
    rate = require_rate(sample_rate_hz)
    if len(delimiter) != 1:
        raise CaptureError("CSV delimiter must be one character")
    if profile == "nordic":
        if any(x is not None for x in (current_column, current_unit, time_column,
                                      time_unit, digital_column, digital_bitstring_column)):
            raise CaptureError("Use profile generic to override Nordic CSV fields")
        current_column, current_unit = "Current(uA)", "uA"
        time_column, time_unit = "Timestamp(ms)", "ms"
    elif profile != "generic":
        raise CaptureError("CSV requires an explicit nordic or generic profile")
    if not current_column or current_unit not in CURRENT_UNITS or not time_column or time_unit not in TIME_UNITS:
        raise CaptureError("Generic CSV requires explicit current/time columns and supported units")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)):
            raise CaptureError("Empty or duplicate CSV header")
        if profile == "nordic":
            if "D0" in fields:
                digital_column = "D0"
            else:
                digital_bitstring_column = "D0-D7"
        if bool(digital_column) == bool(digital_bitstring_column):
            raise CaptureError("Specify one D0 digital column OR one D0-first bitstring column")
        selected = [current_column, time_column, digital_column or digital_bitstring_column]
        if index_column:
            selected.append(index_column)
        if len(selected) != len(set(selected)) or any(x not in fields for x in selected):
            raise CaptureError("Missing or overlapping required CSV columns")
        information = {
            "format": "csv", "profile": profile, "columns": {
                "current": current_column, "current_unit": current_unit,
                "time": time_column, "time_unit": time_unit,
                "digital_column_D0": digital_column,
                "digital_bitstring_D0_first": digital_bitstring_column,
                "sample_index": index_column,
            },
            "selected_digital_channel": "D0", "ignored_digital_channels": ["D1", "D2", "D3", "D4", "D5", "D6", "D7"],
            "time_basis": "CSV timestamps checked against explicit nominal sampling rate",
            "timestamp_gap_checks": True, "sample_index_gap_checks": bool(index_column),
            "voltage_sampled": False, "packet_loss_absence_proven": False,
        }

        def samples():
            previous_time = previous_index = None
            dt = Decimal(1) / Decimal(str(rate))
            tolerance = max(Decimal("1e-12"), dt * Decimal("1e-4"))
            count = 0
            for row_number, row in enumerate(reader, 2):
                if None in row or any(value is None for value in row.values()):
                    raise CaptureError(f"CSV row {row_number}: wrong number of fields")
                try:
                    timestamp = Decimal(row[time_column]) * Decimal(str(TIME_UNITS[time_unit]))
                except InvalidOperation as exc:
                    raise CaptureError(f"CSV row {row_number}: invalid timestamp") from exc
                if not timestamp.is_finite() or timestamp < 0:
                    raise CaptureError(f"CSV row {row_number}: nonfinite or negative timestamp")
                finite_number(timestamp, f"CSV row {row_number} timestamp")
                if previous_time is None:
                    information["first_csv_timestamp_s"] = float(timestamp)
                elif abs(timestamp - previous_time - dt) > tolerance:
                    raise CaptureError(f"CSV row {row_number}: timestamp gap, duplicate or nonuniform sampling")
                previous_time = timestamp
                if index_column:
                    try:
                        index = int(row[index_column])
                    except (ValueError, TypeError) as exc:
                        raise CaptureError(f"CSV row {row_number}: invalid sample index") from exc
                    if index < 0 or (previous_index is not None and index != previous_index + 1):
                        raise CaptureError(f"CSV row {row_number}: sample index gap/reset")
                    previous_index = index
                if digital_column:
                    digit = row[digital_column].strip()
                else:
                    digits = row[digital_bitstring_column].strip()
                    if len(digits) != 8:
                        raise CaptureError(f"CSV row {row_number}: D0-first bitstring must contain eight characters")
                    digit = digits[0]
                if digit not in ("0", "1", "-", "X"):
                    raise CaptureError(f"CSV row {row_number}: invalid D0 encoding")
                # When standalone D0 is present, all unselected columns are
                # irrelevant, including a redundant full-channel bitstring.
                run = decode_d0({"-": 0, "0": 1, "1": 2, "X": 3}[digit], f"CSV row {row_number}")
                current = finite_number(row[current_column], f"row {row_number} current") * CURRENT_UNITS[current_unit]
                count += 1
                if count > max_samples:
                    raise CaptureError("CSV sample limit exceeded")
                yield current, run
            information["last_csv_timestamp_s"] = float(previous_time) if previous_time is not None else None

        yield Capture(samples(), rate, information)


class Moments:
    def __init__(self, start: int):
        self.start = start
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum = math.inf
        self.maximum = -math.inf

    def add(self, value: float):
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        if not math.isfinite(self.mean) or not math.isfinite(self.m2):
            raise CaptureError("Current statistics overflow; invalid numeric scale")
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    def metrics(self, rate: float, voltage: float) -> dict:
        if not self.n:
            raise CaptureError("Empty integration window")
        duration = self.n / rate
        charge = self.mean * duration
        if not math.isfinite(charge) or not math.isfinite(voltage * charge):
            raise CaptureError("Charge/energy integration overflow; invalid numeric scale")
        return {
            "start_sample_inclusive": self.start,
            "end_sample_exclusive": self.start + self.n,
            "sample_count": self.n,
            "start_time_from_first_sample_s": self.start / rate,
            "end_time_from_first_sample_s": (self.start + self.n) / rate,
            "duration_s": duration, "mean_current_A": self.mean,
            "min_current_A": self.minimum, "max_current_A": self.maximum,
            "current_population_stddev_A": math.sqrt(max(0.0, self.m2 / self.n)),
            "charge_C": charge, "energy_at_assumed_constant_voltage_J": voltage * charge,
        }


def analyze(capture: Capture, iterations: dict, *, voltage: float,
            startup_idle_seconds: float = 2.0) -> dict:
    """Check one sequence of 12 D0 gates; their algorithm identities are assumed."""
    rate = require_rate(capture.sample_rate_hz)
    voltage = finite_number(voltage, "voltage", positive=True)
    if set(iterations) != set(ALGORITHMS) or any(type(x) is not int or x <= 0 for x in iterations.values()):
        raise CaptureError("Exact positive iteration counts for all 12 algorithms are required")
    if startup_idle_seconds != 2.0:
        raise CaptureError("Baseline selection is fixed to the last 2 s LOW before the first RUN")
    baseline_count = int(rate) * 2
    minimum_startup_count = int(rate) * 5 * 99 // 100
    minimum_gap_count = int(rate) * 99 // 100
    minimum_tail_count = int(rate) * 3
    baseline_tail = deque(maxlen=baseline_count)
    startup_baseline = None
    runs, low_intervals = [], []
    active_run = active_low = None
    first_defined_low = None
    sample_count = unresolved_startup_samples = negative_startup_samples = 0

    def low_metrics(window: Moments, kind: str, minimum_count: int) -> dict:
        if window.n < minimum_count:
            raise CaptureError(f"{kind} LOW interval is {window.n / rate:g} s; minimum {minimum_count / rate:g} s")
        return {"kind": kind, "after_sequence_position": len(runs),
                "minimum_accepted_duration_s": minimum_count / rate,
                "state_interpretation": "unmarked LOW; may include validation, preparation, control waits or final state",
                **window.metrics(rate, voltage)}

    for i, (current, run) in enumerate(capture.samples):
        current = finite_number(current, f"sample {i} current")
        sample_count = i + 1
        if run is None:
            if first_defined_low is not None:
                raise CaptureError(f"Sample {i}: unknown D0 after the first defined LOW")
            unresolved_startup_samples += 1
            if current < 0:
                negative_startup_samples += 1
            continue
        if type(run) is not int or run not in (0, 1):
            raise CaptureError(f"Sample {i}: D0 must be LOW=0 or HIGH=1")
        if first_defined_low is None:
            if run:
                raise CaptureError("First defined D0 must be LOW; capture begins inside RUN or a latched fault")
            first_defined_low = i
        if current < 0:
            if run or active_run is not None or runs:
                raise CaptureError(f"Sample {i}: negative current in RUN or post-start LOW; no clipping permitted")
            negative_startup_samples += 1

        if run:
            if active_run is None:
                if len(runs) >= 12:
                    raise CaptureError(f"Sample {i}: extra RUN rise after 12 windows; fault, reset or additional sequence")
                if not runs:
                    startup_count = i - first_defined_low
                    if startup_count < minimum_startup_count:
                        raise CaptureError(f"Startup LOW interval is {startup_count / rate:g} s; minimum 4.95 s")
                    if len(baseline_tail) != baseline_count:
                        raise CaptureError("Missing the complete 2 s LOW startup baseline")
                    if any(value < 0 for value in baseline_tail):
                        raise CaptureError("Negative current in the selected startup baseline; no clipping permitted")
                    baseline = Moments(i - baseline_count)
                    for value in baseline_tail:
                        baseline.add(value)
                    startup_baseline = baseline.metrics(rate, voltage)
                    low_intervals.append({
                        "kind": "startup_low", "after_sequence_position": 0,
                        "start_sample_inclusive": first_defined_low, "end_sample_exclusive": i,
                        "sample_count": startup_count, "duration_s": startup_count / rate,
                        "minimum_accepted_duration_s": minimum_startup_count / rate,
                        "state_interpretation": "unmarked startup LOW; includes possible boot/preparation, not integrated as idle",
                    })
                    baseline_tail.clear()
                else:
                    low_intervals.append(low_metrics(active_low, "inter_workload_low", minimum_gap_count))
                    active_low = None
                active_run = Moments(i)
            active_run.add(current)
        else:
            if active_run is not None:
                position = len(runs) + 1
                name = ALGORITHMS[position - 1]
                count = iterations[name]
                row = {"sequence_position": position, "algorithm_assumed_from_order": name,
                       "iterations_from_manifest": count, **active_run.metrics(rate, voltage)}
                row["mean_duration_per_call_s"] = row["duration_s"] / count
                row["charge_per_call_C"] = row["charge_C"] / count
                row["energy_per_call_at_assumed_constant_voltage_J"] = row["energy_at_assumed_constant_voltage_J"] / count
                runs.append(row)
                active_run = None
                active_low = Moments(i)
            if not runs:
                baseline_tail.append(current)
            else:
                active_low.add(current)

    if not sample_count:
        raise CaptureError("Empty capture")
    if active_run is not None:
        raise CaptureError("Capture ended while RUN was HIGH; incomplete gate or latched fault")
    if len(runs) != 12:
        raise CaptureError(f"Incomplete capture: {len(runs)} of 12 RUN windows")
    low_intervals.append(low_metrics(active_low, "trailing_low", minimum_tail_count))
    return {
        "analysis_schema_version": 2, "status": "structural_protocol_pass",
        "sample_rate_Hz": rate, "sample_count": sample_count,
        "first_to_last_sample_span_s": (sample_count - 1) / rate,
        "sample_count_times_dt_s": sample_count / rate,
        "startup_and_gap_short_tolerance_fraction": 0.01,
        "minimum_capture_tail_s": 3.0,
        "trailing_low_duration_s": active_low.n / rate,
        "unresolved_D0_samples_in_startup_prefix": unresolved_startup_samples,
        "negative_current_samples_in_unmeasured_startup": negative_startup_samples,
        "algorithm_assignment_basis": "assumed fixed order from manifest; no algorithm ID is transmitted",
        "final_validation_completion_proven": False,
        "capture": capture.metadata,
        "integration": {
            "rule": "half-open D0 RUN gates [rise,fall); charge = sum(current_A)/fs",
            "duration_rule": "RUN sample count / fs; includes loop and GPIO gate overhead",
            "energy_rule": "assumed constant DUT voltage * charge; divided by manifest iterations for per-call values",
            "baseline_subtracted": False, "mcu_times_used": False,
            "assumed_constant_voltage_V": voltage,
        },
        "startup_baseline_selection": "last 2 seconds of defined LOW before first RUN; inferred control idle, not separately marked",
        "startup_baseline": startup_baseline,
        "runs": runs, "low_intervals": low_intervals,
        "limitations": [
            "Structural pass only: D0 does not authenticate algorithms, board identity, firmware or iteration counts.",
            "No DONE/ERROR/IDLE channels exist. A sufficiently long trailing LOW cannot prove completion of final validation or distinguish a hang while LOW.",
            "Faults that latch HIGH, incomplete gates, extra rises and visibly short gaps are rejected, but not all resets or corrupted sequences are detectable.",
            "Nominal timebase does not prove absence of device/serial packet loss, especially if upstream software rebuilt uniform indices.",
            "The baseline is inferred from the final 2 s LOW before the first RUN; no separate marker proves idle state, calibration or current stability.",
            "LOW gaps include possible preparation/validation/control waits; trailing LOW may include the platform final state. They are not pure idle measurements.",
            "Voltage is not sampled. Energy assumes constant voltage; nominal or caller-supplied voltage is not independently verified.",
            "GPIO aperture/phase and instrument timing uncertainty are not removed from gate boundaries.",
            "Within-window current samples and repeated calls are not independent cold-boot replicates.",
            "D1 through D7 are intentionally ignored, including unknown, mixed or noisy states.",
        ],
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_results(report: dict, input_path: Path, manifest_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / (input_path.stem + ".analysis.json")
    csv_path = output_dir / (input_path.stem + ".workloads.csv")
    originals = {input_path.resolve(), manifest_path.resolve()}
    for target in (json_path, csv_path):
        if target.resolve() in originals or target.exists():
            raise CaptureError(f"Refusing to overwrite an input or existing result: {target}")
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with json_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report["runs"][0]))
        writer.writeheader()
        writer.writerows(report["runs"])
    return json_path, csv_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--board", choices=("esp32", "rp2040", "stm32"), required=True)
    parser.add_argument("--manifest", type=Path, default=Path("config/experiment.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--voltage", type=float, help="Explicit assumed constant DUT voltage; does not certify a measurement")
    parser.add_argument("--voltage-uncertainty-v", type=float, help="Optional absolute voltage uncertainty; document its basis separately")
    parser.add_argument("--sample-rate-hz", type=float, help="Optional explicit cross-check; must match the 100 kS/s manifest/native metadata")
    parser.add_argument("--csv-profile", choices=("nordic", "generic"))
    parser.add_argument("--current-column")
    parser.add_argument("--current-unit", choices=tuple(CURRENT_UNITS))
    parser.add_argument("--time-column")
    parser.add_argument("--time-unit", choices=tuple(TIME_UNITS))
    parser.add_argument("--digital-column", help="Single column containing the D0 RUN marker")
    parser.add_argument("--digital-bitstring-column", help="Eight-character bitstring, D0 first; other channels ignored")
    parser.add_argument("--index-column", help="Optional integer sample index for additional gap checks")
    parser.add_argument("--delimiter", default=",")
    parser.add_argument("--max-samples", type=int, default=DEFAULT_MAX_SAMPLES)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.max_samples <= 1_000_000_000:
            raise CaptureError("--max-samples must be between 1 and 1000000000")
        manifest = load_manifest(args.manifest, args.board)
        rate = require_rate(manifest["sample_rate_Hz"])
        if args.sample_rate_hz is not None:
            require_rate(args.sample_rate_hz, rate)
        voltage = finite_number(args.voltage if args.voltage is not None else manifest["nominal_voltage_V"], "voltage", positive=True)
        uncertainty = args.voltage_uncertainty_v
        if uncertainty is not None and finite_number(uncertainty, "voltage uncertainty") < 0:
            raise CaptureError("Voltage uncertainty cannot be negative")
        input_before = args.input.stat()
        if args.input.suffix.lower() == ".ppk2":
            if any(x is not None for x in (args.csv_profile, args.current_column, args.current_unit,
                                           args.time_column, args.time_unit, args.digital_column,
                                           args.digital_bitstring_column, args.index_column)) or args.delimiter != ",":
                raise CaptureError("CSV options do not apply to native PPK2 files")
            context = open_native(args.input, expected_rate=rate, max_samples=args.max_samples)
        elif args.input.suffix.lower() == ".csv":
            context = open_csv(
                args.input, sample_rate_hz=rate, profile=args.csv_profile,
                current_column=args.current_column, current_unit=args.current_unit,
                time_column=args.time_column, time_unit=args.time_unit,
                digital_column=args.digital_column,
                digital_bitstring_column=args.digital_bitstring_column,
                index_column=args.index_column, delimiter=args.delimiter, max_samples=args.max_samples)
        else:
            raise CaptureError("Supported input extensions: .ppk2 and .csv")
        with context as capture:
            report = analyze(capture, manifest["boards"][args.board]["iterations"], voltage=voltage)
        report["provenance"] = {
            "board": args.board, "input_path": str(args.input.resolve()),
            "input_sha256": file_hash(args.input),
            "manifest_path": str(args.manifest.resolve()), "manifest_sha256": file_hash(args.manifest),
            "analyzer_sha256": file_hash(Path(__file__)),
            "experiment_manifest": manifest,
            "ppk2_format_reference_commit": NORDIC_COMMIT,
        }
        report["integration"]["voltage_basis"] = "caller_supplied_unverified_constant" if args.voltage is not None else "manifest_nominal_not_measured"
        report["integration"]["voltage_absolute_uncertainty_V"] = uncertainty
        report["integration"]["voltage_uncertainty_basis"] = "caller supplied; interpretation/calibration must be documented separately" if uncertainty is not None else "not supplied; energy uncertainty is not quantified"
        input_after = args.input.stat()
        if (input_before.st_size, input_before.st_mtime_ns) != (input_after.st_size, input_after.st_mtime_ns):
            raise CaptureError("Input changed during analysis")
        paths = write_results(report, args.input, args.manifest, args.output_dir)
        print(json.dumps({"status": report["status"], "workloads": len(report["runs"]), "outputs": [str(p) for p in paths]}))
        return 0
    except (CaptureError, OSError, zipfile.BadZipFile, zlib.error, RuntimeError, csv.Error, UnicodeError) as exc:
        print(f"Capture rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
