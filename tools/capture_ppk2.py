#!/usr/bin/env python3
"""Acquire cold-boot single-GPIO benchmark captures from a Nordic PPK2.

The tool controls Source Meter power, retains the exact four-byte PPK2
transport frames, exports a generic CSV, and invokes analyze_capture.py.  It
does not claim that the transport stream has independent per-sample timestamps
or packet-loss markers; those limitations are recorded in every capture.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


SAMPLE_RATE_HZ = 100_000
ALGORITHM_COUNT = 12
DEFAULT_TAIL_S = 3.0
ACTIVE_EXPERIMENT_ID = "energy-profiling-v4-max-clock"
BOARD_PINS = {"esp32": "GPIO18", "rp2040": "GP2", "stm32": "PC0 (CN7 pin 38)"}


class AcquisitionError(RuntimeError):
    """The physical or streamed capture did not satisfy the acquisition contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AcquisitionError(f"Expected a JSON object in {path}")
    return value


def normalize_devices(items: Iterable[object]) -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            devices.append((item, ""))
        else:
            try:
                port, serial_number = item  # type: ignore[misc]
            except (TypeError, ValueError) as exc:
                raise AcquisitionError(f"Unexpected PPK2 device descriptor: {item!r}") from exc
            devices.append((str(port), str(serial_number or "")))
    return devices


def import_ppk2_api():
    try:
        from ppk2_api.ppk2_api import PPK2_API
    except ImportError as exc:
        raise AcquisitionError(
            "ppk2-api is not installed; create the project venv and install "
            "requirements-ppk2.txt"
        ) from exc
    return PPK2_API


def list_ppk2_devices() -> list[tuple[str, str]]:
    devices = normalize_devices(import_ppk2_api().list_devices())
    # Released ppk2-api 0.9.2 returns only port strings on Windows even though
    # pyserial exposes the USB serial number. Preserve it for provenance.
    try:
        from serial.tools import list_ports

        serials = {item.device.casefold(): str(item.serial_number or "") for item in list_ports.comports()}
    except (ImportError, OSError):
        serials = {}
    return [(port, serial_number or serials.get(port.casefold(), "")) for port, serial_number in devices]


def select_device(devices: list[tuple[str, str]], requested_port: str | None) -> tuple[str, str]:
    if requested_port:
        matches = [item for item in devices if item[0].casefold() == requested_port.casefold()]
        if len(matches) != 1:
            shown = ", ".join(port for port, _ in devices) or "none"
            raise AcquisitionError(f"PPK2 port {requested_port!r} was not found (detected: {shown})")
        return matches[0]
    if len(devices) != 1:
        shown = ", ".join(f"{port} ({serial or 'serial unavailable'})" for port, serial in devices) or "none"
        raise AcquisitionError(f"Expected exactly one PPK2; detected: {shown}. Use --port when needed.")
    return devices[0]


@dataclass
class ProtocolMonitor:
    required_tail_samples: int
    sample_count: int = 0
    rising_edges: list[int] = field(default_factory=list)
    falling_edges: list[int] = field(default_factory=list)
    previous_d0: int | None = None
    first_counter: int | None = None
    previous_counter: int | None = None
    trailing_low_start: int | None = None

    def consume(self, states: Iterable[int], on_edge: Callable[[str, int, int], None] | None = None) -> None:
        for state in states:
            self._consume_state(state, None, on_edge)

    def consume_frames(self, frames: bytes, on_edge: Callable[[str, int, int], None] | None = None) -> None:
        if len(frames) % 4:
            raise AcquisitionError("PPK2 transport frame block is not four-byte aligned")
        for offset in range(0, len(frames), 4):
            value = int.from_bytes(frames[offset:offset + 4], byteorder="little", signed=False)
            self._consume_state((value >> 24) & 1, (value >> 18) & 0x3F, on_edge)

    def _consume_state(
        self,
        state: int,
        counter: int | None,
        on_edge: Callable[[str, int, int], None] | None,
    ) -> None:
        if state not in (0, 1) or isinstance(state, bool):
            raise AcquisitionError(f"Invalid streamed D0 state {state!r}")
        if counter is not None:
            if self.first_counter is None:
                self.first_counter = counter
            elif counter != ((self.previous_counter + 1) & 0x3F):
                raise AcquisitionError(
                    f"PPK2 sample-counter discontinuity at retained sample {self.sample_count}: "
                    f"expected {((self.previous_counter + 1) & 0x3F)}, received {counter}"
                )
            self.previous_counter = counter
        index = self.sample_count
        if self.previous_d0 is None:
            if state != 0:
                raise AcquisitionError("First streamed D0 sample is HIGH; startup is ambiguous")
        elif state != self.previous_d0:
            if state == 1:
                self.rising_edges.append(index)
                if len(self.rising_edges) > ALGORITHM_COUNT:
                    raise AcquisitionError("Observed an extra (13th) RUN rising edge")
                if on_edge:
                    on_edge("rise", len(self.rising_edges), index)
            else:
                self.falling_edges.append(index)
                if len(self.falling_edges) > len(self.rising_edges):
                    raise AcquisitionError("Observed a RUN falling edge without a matching rise")
                if on_edge:
                    on_edge("fall", len(self.falling_edges), index)
                if len(self.falling_edges) == ALGORITHM_COUNT:
                    self.trailing_low_start = index
        self.previous_d0 = state
        self.sample_count += 1

    @property
    def trailing_low_samples(self) -> int:
        if self.trailing_low_start is None:
            return 0
        return self.sample_count - self.trailing_low_start

    @property
    def complete(self) -> bool:
        return (
            len(self.rising_edges) == ALGORITHM_COUNT
            and len(self.falling_edges) == ALGORITHM_COUNT
            and self.previous_d0 == 0
            and self.trailing_low_samples >= self.required_tail_samples
        )

    def validate_complete(self) -> None:
        if self.previous_d0 == 1:
            raise AcquisitionError("Capture ended while RUN was HIGH (incomplete batch or latched fault)")
        if len(self.rising_edges) != ALGORITHM_COUNT or len(self.falling_edges) != ALGORITHM_COUNT:
            raise AcquisitionError(
                f"Observed {len(self.rising_edges)} rises and {len(self.falling_edges)} falls; expected 12/12"
            )
        if self.trailing_low_samples < self.required_tail_samples:
            raise AcquisitionError(
                f"Only {self.trailing_low_samples} trailing LOW samples; expected at least "
                f"{self.required_tail_samples}"
            )


def complete_frames(pending: bytes, chunk: bytes) -> tuple[bytes, bytes]:
    combined = pending + chunk
    end = len(combined) - (len(combined) % 4)
    return combined[:end], combined[end:]


def d0_states_from_frames(frames: bytes) -> Iterable[int]:
    if len(frames) % 4:
        raise AcquisitionError("PPK2 transport frame block is not four-byte aligned")
    # ppk2-api decodes an LE uint32 and extracts MEAS_LOGIC from bits 24..31.
    return ((frames[offset + 3] & 1) for offset in range(0, len(frames), 4))


def reset_ppk_decoder(api) -> None:
    api.remainder = {"sequence": b"", "len": 0}
    api.rolling_avg = None
    api.rolling_avg4 = None
    api.prev_range = None
    if hasattr(api, "consecutive_range_samples"):
        api.consecutive_range_samples = 0
    api.after_spike = 0


@dataclass(frozen=True)
class StreamCapture:
    started_utc: str
    ended_utc: str
    sample_count: int
    raw_bytes: int
    power_on_sample_approx: int
    rising_edges: list[int]
    falling_edges: list[int]
    trailing_low_samples: int
    first_sample_counter: int | None
    last_sample_counter: int | None
    sample_counter_continuity_passed: bool
    measurement_wall_s: float
    represented_sample_s: float
    sample_time_error_percent: float


class Ppk2SourceSession:
    def __init__(self, port: str, *, voltage_mv: int):
        if not 800 <= voltage_mv <= 5000:
            raise AcquisitionError("PPK2 Source Meter voltage must be in [800, 5000] mV")
        api_type = import_ppk2_api()
        self.port = port
        self.voltage_mv = voltage_mv
        self.api = api_type(port, timeout=0)
        try:
            self._stop_and_drain()
            self._read_modifiers_with_retry()
            self.api.use_source_meter()
            self.api.set_source_voltage(voltage_mv)
            self.power_off()
        except BaseException:
            self.close()
            raise

    def _stop_and_drain(self) -> None:
        self.api.stop_measuring()
        time.sleep(0.05)
        quiet_deadline = time.monotonic() + 0.10
        while time.monotonic() < quiet_deadline:
            data = self.api.get_data()
            if data:
                quiet_deadline = time.monotonic() + 0.05
            else:
                time.sleep(0.005)

    def _read_modifiers_with_retry(self) -> None:
        last_error: Exception | None = None
        for _attempt in range(3):
            try:
                self.api.get_modifiers()
                return
            except (UnicodeDecodeError, TypeError, AttributeError, ValueError) as exc:
                last_error = exc
                self._stop_and_drain()
        raise AcquisitionError("Could not read PPK2 calibration metadata cleanly") from last_error

    def power_on(self) -> None:
        self.api.toggle_DUT_power("ON")
        self.api.ser.flush()

    def power_off(self) -> None:
        self.api.toggle_DUT_power("OFF")
        self.api.ser.flush()
        time.sleep(0.02)

    def close(self) -> None:
        api = getattr(self, "api", None)
        if api is None:
            return
        try:
            api.stop_measuring()
        except Exception:
            pass
        try:
            self.power_off()
        except Exception:
            pass
        serial_port = getattr(api, "ser", None)
        if serial_port is not None and getattr(serial_port, "is_open", False):
            serial_port.close()

    def capture_raw(
        self,
        path: Path,
        *,
        pre_power_s: float,
        tail_s: float,
        max_first_edge_s: float,
        max_capture_s: float,
        max_samples: int,
        max_sample_time_error_percent: float,
        on_edge: Callable[[str, int, int], None] | None = None,
    ) -> StreamCapture:
        monitor = ProtocolMonitor(required_tail_samples=math.ceil(tail_s * SAMPLE_RATE_HZ))
        pending = b""
        pre_power_samples = math.ceil(pre_power_s * SAMPLE_RATE_HZ)
        started_utc = utc_now()
        measurement_start = time.perf_counter()
        power_on_sample_approx = -1
        power_on_time = measurement_start
        stop_requested = measurement_start
        measuring = False
        powered = False

        def pump(stream) -> bool:
            nonlocal pending
            chunk = self.api.get_data()
            if not chunk:
                return False
            stream.write(chunk)
            frames, pending = complete_frames(pending, chunk)
            monitor.consume_frames(frames, on_edge=on_edge)
            if monitor.sample_count > max_samples:
                raise AcquisitionError(f"Capture exceeded the {max_samples}-sample safety cap")
            return True

        with path.open("xb", buffering=1024 * 1024) as raw:
            try:
                while self.api.get_data():
                    pass
                reset_ppk_decoder(self.api)
                self.api.start_measuring()
                measuring = True
                measurement_start = time.perf_counter()
                deadline = measurement_start + max_capture_s

                while monitor.sample_count < pre_power_samples:
                    if time.perf_counter() >= deadline:
                        raise AcquisitionError("Timed out before the pre-power prefix was acquired")
                    if not pump(raw):
                        time.sleep(0.0005)

                queued = int(getattr(self.api.ser, "in_waiting", 0))
                power_on_sample_approx = monitor.sample_count + queued // 4
                powered = True
                self.power_on()
                power_on_time = time.perf_counter()

                while not monitor.complete:
                    if not monitor.rising_edges and time.perf_counter() - power_on_time >= max_first_edge_s:
                        raise AcquisitionError(
                            f"No D0 rising edge within {max_first_edge_s:g} s after DUT power-on"
                        )
                    if time.perf_counter() >= deadline:
                        raise AcquisitionError(
                            f"Timed out after {max_capture_s:g} s with "
                            f"{len(monitor.rising_edges)} rises/{len(monitor.falling_edges)} falls"
                        )
                    if not pump(raw):
                        time.sleep(0.0005)

                stop_requested = time.perf_counter()
                self.api.stop_measuring()
                measuring = False
                time.sleep(0.02)
                quiet_deadline = time.monotonic() + 0.08
                while time.monotonic() < quiet_deadline:
                    if pump(raw):
                        quiet_deadline = time.monotonic() + 0.03
                    else:
                        time.sleep(0.002)
            finally:
                if measuring:
                    stop_requested = time.perf_counter()
                    try:
                        self.api.stop_measuring()
                    except Exception:
                        pass
                if powered:
                    self.power_off()

        if pending:
            raise AcquisitionError(f"PPK2 stream ended with {len(pending)} byte(s) of a partial frame")
        monitor.validate_complete()
        wall_s = stop_requested - measurement_start
        represented_s = monitor.sample_count / SAMPLE_RATE_HZ
        time_error = 100.0 * (represented_s - wall_s) / wall_s if wall_s > 0 else math.inf
        if not math.isfinite(time_error) or abs(time_error) > max_sample_time_error_percent:
            raise AcquisitionError(
                f"Sample-count time differs from host measurement time by {time_error:.3f}% "
                f"(limit {max_sample_time_error_percent:g}%)"
            )
        return StreamCapture(
            started_utc=started_utc,
            ended_utc=utc_now(),
            sample_count=monitor.sample_count,
            raw_bytes=path.stat().st_size,
            power_on_sample_approx=power_on_sample_approx,
            rising_edges=list(monitor.rising_edges),
            falling_edges=list(monitor.falling_edges),
            trailing_low_samples=monitor.trailing_low_samples,
            first_sample_counter=monitor.first_counter,
            last_sample_counter=monitor.previous_counter,
            sample_counter_continuity_passed=True,
            measurement_wall_s=wall_s,
            represented_sample_s=represented_s,
            sample_time_error_percent=time_error,
        )

    def export_csv(self, raw_path: Path, csv_path: Path) -> int:
        if raw_path.stat().st_size % 4:
            raise AcquisitionError("Cannot export a partial PPK2 transport frame")
        reset_ppk_decoder(self.api)
        written = 0
        with (
            raw_path.open("rb") as raw,
            csv_path.open("x", encoding="utf-8", newline="", buffering=1024 * 1024) as output,
        ):
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(("Sample", "Timestamp(us)", "Current(uA)", "D0"))
            while True:
                block = raw.read(4 * 16_384)
                if not block:
                    break
                expected = len(block) // 4
                samples, logic = self.api.get_samples(block)
                if len(samples) != expected or len(logic) != expected:
                    raise AcquisitionError(
                        f"PPK2 decoder returned {len(samples)} current/{len(logic)} logic values "
                        f"for {expected} frames"
                    )
                rows = (
                    (written + offset, (written + offset) * 10, repr(float(current)), bits & 1)
                    for offset, (current, bits) in enumerate(zip(samples, logic))
                )
                writer.writerows(rows)
                written += expected
        return written


def resolve_firmware(project_root: Path, current: dict, board: str, requested: Path | None) -> tuple[Path, str]:
    if requested is not None:
        path = requested.resolve()
        basis = "caller_supplied_expected_image_not_attested_by_capture"
    else:
        try:
            relative = current["boards"][board]["profiles"]["single_gpio_measurement"]["primary_image"]
        except (KeyError, TypeError) as exc:
            raise AcquisitionError("CURRENT_FIRMWARE.json has no default single-GPIO image") from exc
        path = (project_root / relative).resolve()
        basis = "CURRENT_FIRMWARE_candidate_default_not_attested_by_capture"
    if not path.is_file():
        raise AcquisitionError(f"Expected firmware image does not exist: {path}")
    return path, basis


def validate_firmware_identity(current: dict, manifest: dict, manifest_path: Path,
                               board: str, firmware_path: Path) -> None:
    """Bind an expected silent image to the exact experiment file before power-on.

    This verifies the archived identity, not the contents of the DUT's flash.
    An explicit --firmware path still has to match the selected profile's bytes.
    """
    if manifest.get("experiment_id") != ACTIVE_EXPERIMENT_ID:
        raise AcquisitionError(f"Acquisition requires experiment {ACTIVE_EXPERIMENT_ID}")
    if current.get("experiment_id") != manifest["experiment_id"]:
        raise AcquisitionError("CURRENT_FIRMWARE experiment does not match the acquisition manifest")
    if current.get("experiment_sha256") != sha256_file(manifest_path):
        raise AcquisitionError("CURRENT_FIRMWARE experiment SHA-256 does not match the manifest file")
    try:
        profile = current["boards"][board]["profiles"]["single_gpio_measurement"]
    except (KeyError, TypeError) as exc:
        raise AcquisitionError("CURRENT_FIRMWARE has no selected single-GPIO profile") from exc
    if profile.get("diagnostics_enabled") is not False:
        raise AcquisitionError("The acquisition image must have diagnostics disabled")
    if profile.get("native_compile_and_link_passed") is not True:
        raise AcquisitionError("The acquisition image has no successful native build record")
    if profile.get("experiment_manifest_sha256") != current["experiment_sha256"]:
        raise AcquisitionError("The image archive experiment SHA-256 differs from the acquisition manifest")
    if profile.get("sha256") != sha256_file(firmware_path):
        raise AcquisitionError("Expected firmware SHA-256 does not match the selected measurement profile")


def make_capture_dir(output_root: Path, board: str, ordinal: int) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = output_root / board / f"{stamp}_{board}_{ordinal:03d}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def ppk_package_version() -> str:
    try:
        return importlib.metadata.version("ppk2-api")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def run_analyzer(
    project_root: Path,
    csv_path: Path,
    board: str,
    manifest: Path,
    output_dir: Path,
    measured_voltage_v: float | None,
    voltage_uncertainty_v: float | None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(project_root / "tools" / "analyze_capture.py"),
        str(csv_path),
        "--csv-profile", "generic",
        "--current-column", "Current(uA)",
        "--current-unit", "uA",
        "--time-column", "Timestamp(us)",
        "--time-unit", "us",
        "--digital-column", "D0",
        "--index-column", "Sample",
        "--sample-rate-hz", str(SAMPLE_RATE_HZ),
        "--board", board,
        "--manifest", str(manifest),
        "--output-dir", str(output_dir),
    ]
    if measured_voltage_v is not None:
        command.extend(("--voltage", str(measured_voltage_v)))
    if voltage_uncertainty_v is not None:
        command.extend(("--voltage-uncertainty-v", str(voltage_uncertainty_v)))
    return subprocess.run(command, text=True, capture_output=True, check=False)


def positive_finite(value: float, label: str, *, allow_zero: bool = False) -> float:
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        comparator = "nonnegative" if allow_zero else "positive"
        raise AcquisitionError(f"{label} must be finite and {comparator}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="List PPK2 control ports and exit")
    parser.add_argument("--power-off", action="store_true", help="Stop acquisition, request DUT power OFF, and exit")
    parser.add_argument("--board", choices=tuple(BOARD_PINS))
    parser.add_argument("--port", help="PPK2 control COM port; auto-selects when exactly one is present")
    parser.add_argument("--manifest", type=Path, default=Path("config/experiment.json"))
    parser.add_argument("--current-firmware", type=Path, default=Path("CURRENT_FIRMWARE.json"))
    parser.add_argument("--firmware", type=Path, help="Expected programmed image; its hash is recorded, not attested")
    parser.add_argument("--output-root", type=Path, default=Path("captures_max_clock"))
    parser.add_argument("--captures", type=int, default=1, help="Independent cold-boot captures (campaign minimum: 10)")
    parser.add_argument("--voltage-mv", type=int, default=3300, help="PPK2 Source Meter setpoint")
    parser.add_argument("--measured-voltage-v", type=float, help="Externally measured DUT voltage under load")
    parser.add_argument("--voltage-uncertainty-v", type=float, help="Absolute uncertainty of that external voltage")
    parser.add_argument("--ambient-temperature-c", type=float, help="Ambient temperature recorded as provenance")
    parser.add_argument("--physical-board-id", help="Label/serial identifying the physical DUT")
    parser.add_argument("--pre-power-seconds", type=float, default=0.25)
    parser.add_argument("--tail-seconds", type=float, default=DEFAULT_TAIL_S)
    parser.add_argument("--rest-seconds", type=float, default=10.0)
    parser.add_argument("--max-capture-seconds", type=float, default=600.0)
    parser.add_argument("--max-first-edge-seconds", type=float, default=30.0)
    parser.add_argument("--max-samples", type=int, default=60_000_000)
    parser.add_argument("--max-sample-time-error-percent", type=float, default=2.0)
    parser.add_argument(
        "--confirm-wiring",
        action="store_true",
        help="Acknowledge isolated DUT power, common ground/logic VCC, and board RUN-to-D0 wiring",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        devices = list_ppk2_devices()
        if args.list_devices:
            print(json.dumps({"devices": [{"port": p, "serial": s or None} for p, s in devices]}))
            return 0
        if args.power_off:
            port, serial_number = select_device(devices, args.port)
            session = Ppk2SourceSession(port, voltage_mv=args.voltage_mv)
            session.close()
            print(f"PPK2 {serial_number or '(serial unavailable)'} on {port}: acquisition stopped, DUT power OFF")
            return 0
        if not args.board:
            raise AcquisitionError("--board is required for acquisition")
        if not args.confirm_wiring:
            raise AcquisitionError(
                f"Refusing to enable PPK2 VOUT without --confirm-wiring. Verify {BOARD_PINS[args.board]} -> D0, "
                "LOGIC VCC -> measured 3V3, common GND, and no other DUT power/programmer connection."
            )
        if not 1 <= args.captures <= 1000:
            raise AcquisitionError("--captures must be between 1 and 1000")
        if not 800 <= args.voltage_mv <= 5000:
            raise AcquisitionError("--voltage-mv must be between 800 and 5000")
        positive_finite(args.pre_power_seconds, "--pre-power-seconds")
        if args.tail_seconds < DEFAULT_TAIL_S:
            raise AcquisitionError("--tail-seconds cannot be below the protocol minimum of 3 s")
        positive_finite(args.tail_seconds, "--tail-seconds")
        positive_finite(args.rest_seconds, "--rest-seconds", allow_zero=True)
        positive_finite(args.max_capture_seconds, "--max-capture-seconds")
        positive_finite(args.max_first_edge_seconds, "--max-first-edge-seconds")
        positive_finite(args.max_sample_time_error_percent, "--max-sample-time-error-percent")
        if not 1 <= args.max_samples <= 1_000_000_000:
            raise AcquisitionError("--max-samples must be between 1 and 1000000000")
        if args.measured_voltage_v is not None:
            positive_finite(args.measured_voltage_v, "--measured-voltage-v")
        if args.voltage_uncertainty_v is not None:
            positive_finite(args.voltage_uncertainty_v, "--voltage-uncertainty-v", allow_zero=True)
            if args.measured_voltage_v is None:
                raise AcquisitionError("--voltage-uncertainty-v requires --measured-voltage-v")
        if args.ambient_temperature_c is not None and not math.isfinite(args.ambient_temperature_c):
            raise AcquisitionError("--ambient-temperature-c must be finite")

        project_root = Path(__file__).resolve().parents[1]
        manifest_path = args.manifest.resolve()
        manifest = load_json(manifest_path)
        if manifest.get("experiment_id") != ACTIVE_EXPERIMENT_ID:
            raise AcquisitionError(f"Manifest is not the active experiment {ACTIVE_EXPERIMENT_ID}")
        if manifest.get("sample_rate_Hz") != SAMPLE_RATE_HZ:
            raise AcquisitionError("Manifest sample rate must be exactly 100000 Hz")
        nominal_mv = round(float(manifest.get("nominal_voltage_V", 0)) * 1000)
        if nominal_mv != 3300 or args.voltage_mv != nominal_mv:
            raise AcquisitionError(
                f"This experiment requires the manifest Source Meter setpoint of {nominal_mv} mV; "
                f"received {args.voltage_mv} mV"
            )
        if args.captures > 1:
            missing = []
            if not args.physical_board_id:
                missing.append("--physical-board-id")
            if args.ambient_temperature_c is None:
                missing.append("--ambient-temperature-c")
            if args.measured_voltage_v is None:
                missing.append("--measured-voltage-v")
            if missing:
                raise AcquisitionError(
                    "Multi-capture campaigns require provenance fields: " + ", ".join(missing)
                )
        current_path = args.current_firmware.resolve()
        current = load_json(current_path)
        firmware_path, firmware_basis = resolve_firmware(project_root, current, args.board, args.firmware)
        validate_firmware_identity(current, manifest, manifest_path, args.board, firmware_path)
        port, serial_number = select_device(devices, args.port)
        output_root = args.output_root.resolve()

        print(f"PPK2 {serial_number or '(serial unavailable)'} on {port}; Source Meter {args.voltage_mv} mV")
        print(f"DUT {args.board}: {BOARD_PINS[args.board]} -> D0; {args.captures} cold-boot capture(s)")
        if args.measured_voltage_v is None:
            print("WARNING: no external DUT voltage supplied; energy will use the unverified manifest nominal voltage")
        if not args.physical_board_id:
            print("WARNING: no --physical-board-id supplied")

        session = Ppk2SourceSession(port, voltage_mv=args.voltage_mv)
        try:
            for ordinal in range(1, args.captures + 1):
                capture_dir = make_capture_dir(output_root, args.board, ordinal)
                raw_partial = capture_dir / "transport.partial.raw4"
                raw_path = capture_dir / "transport.raw4"
                csv_partial = capture_dir / "capture.partial.csv"
                csv_path = capture_dir / "capture.csv"
                print(f"[{ordinal}/{args.captures}] acquiring {capture_dir.name}")

                def report_edge(kind: str, number: int, index: int) -> None:
                    print(f"  D0 {kind} {number:02d} at sample {index}")

                base_metadata = {
                    "schema_version": 1,
                    "experiment_id": manifest["experiment_id"],
                    "board": args.board,
                    "physical_board_id": args.physical_board_id,
                    "run_pin_to_ppk2_d0": BOARD_PINS[args.board],
                    "ppk2": {
                        "port": port,
                        "serial_number": serial_number or None,
                        "mode": "source_meter",
                        "source_voltage_setpoint_mV": args.voltage_mv,
                        "calibration_metadata": getattr(session.api, "modifiers", None),
                    },
                    "acquisition": {
                        "tool": str(Path(__file__).resolve()),
                        "tool_sha256": sha256_file(Path(__file__).resolve()),
                        "ppk2_api_version": ppk_package_version(),
                        "sample_rate_Hz": SAMPLE_RATE_HZ,
                        "pre_power_seconds_requested": args.pre_power_seconds,
                        "minimum_trailing_low_seconds": args.tail_seconds,
                        "rest_seconds_requested_after_capture": args.rest_seconds,
                        "host": platform.node(),
                        "platform": platform.platform(),
                        "python": sys.version,
                    },
                    "provenance": {
                        "manifest_path": str(manifest_path),
                        "manifest_sha256": sha256_file(manifest_path),
                        "current_firmware_manifest_path": str(current_path),
                        "current_firmware_manifest_sha256": sha256_file(current_path),
                        "expected_firmware_path": str(firmware_path),
                        "expected_firmware_sha256": sha256_file(firmware_path),
                        "expected_firmware_basis": firmware_basis,
                        "capture_does_not_attest_programmed_image": True,
                    },
                    "environment": {
                        "externally_measured_dut_voltage_V": args.measured_voltage_v,
                        "voltage_absolute_uncertainty_V": args.voltage_uncertainty_v,
                        "ambient_temperature_C": args.ambient_temperature_c,
                    },
                    "limitations": [
                        "Raw ppk2-api transport has no independent per-sample timestamps.",
                        "The rolling 6-bit hardware sample counter is checked, but a loss of an exact multiple of 64 samples could evade that check.",
                        "Uniform CSV timestamps are reconstructed from sample index at 100000 Hz.",
                        "Host elapsed time is only a coarse stream-integrity cross-check.",
                        "The expected firmware hash is operator provenance, not an attestation of DUT flash contents.",
                        "Twelve pulses plus a LOW tail cannot prove final firmware validation completed.",
                    ],
                }
                try:
                    capture = session.capture_raw(
                        raw_partial,
                        pre_power_s=args.pre_power_seconds,
                        tail_s=args.tail_seconds,
                        max_first_edge_s=args.max_first_edge_seconds,
                        max_capture_s=args.max_capture_seconds,
                        max_samples=args.max_samples,
                        max_sample_time_error_percent=args.max_sample_time_error_percent,
                        on_edge=report_edge,
                    )
                    os.replace(raw_partial, raw_path)
                    exported = session.export_csv(raw_path, csv_partial)
                    if exported != capture.sample_count:
                        raise AcquisitionError(
                            f"CSV exported {exported} samples but the stream monitor counted {capture.sample_count}"
                        )
                    os.replace(csv_partial, csv_path)
                    analysis_dir = capture_dir / "analysis"
                    analyzed = run_analyzer(
                        project_root,
                        csv_path,
                        args.board,
                        manifest_path,
                        analysis_dir,
                        args.measured_voltage_v,
                        args.voltage_uncertainty_v,
                    )
                    metadata = dict(base_metadata)
                    metadata["capture"] = {
                        **asdict(capture),
                        "transport_path": str(raw_path),
                        "transport_sha256": sha256_file(raw_path),
                        "csv_path": str(csv_path),
                        "csv_sha256": sha256_file(csv_path),
                    }
                    metadata["analysis"] = {
                        "return_code": analyzed.returncode,
                        "stdout": analyzed.stdout.strip(),
                        "stderr": analyzed.stderr.strip(),
                        "output_directory": str(analysis_dir),
                    }
                    write_json_new(capture_dir / "capture_metadata.json", metadata)
                    if analyzed.returncode != 0:
                        raise AcquisitionError(f"Offline structural analysis rejected capture: {analyzed.stderr.strip()}")
                    print(f"  accepted: {analyzed.stdout.strip()}")
                except BaseException as exc:
                    failure = dict(base_metadata)
                    failure["failed_utc"] = utc_now()
                    failure["error_type"] = type(exc).__name__
                    failure["error"] = str(exc)
                    failure["partial_files"] = [str(path) for path in capture_dir.iterdir()]
                    failure_path = capture_dir / "failure.json"
                    if not failure_path.exists():
                        write_json_new(failure_path, failure)
                    raise

                if ordinal < args.captures and args.rest_seconds:
                    print(f"  DUT off; resting for at least {args.rest_seconds:g} s")
                    time.sleep(args.rest_seconds)
        finally:
            session.close()
        return 0
    except KeyboardInterrupt:
        print("Acquisition interrupted; DUT power was requested OFF and partial files were retained", file=sys.stderr)
        return 130
    except (AcquisitionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Acquisition failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
