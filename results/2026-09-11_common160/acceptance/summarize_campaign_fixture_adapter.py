#!/usr/bin/env python3
"""Validate and summarize an explicit multi-board PPK2 campaign manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ALGORITHMS = (
    "RLE", "Delta", "LZ77", "Huffman", "AES-128", "SHA-256",
    "ChaCha20", "CRC32", "FFT", "FIR", "IIR", "DCT",
)
BOARDS = ("esp32", "rp2040", "stm32")
COMMON160_EXPERIMENT_ID = "energy-profiling-v5-common160"


class CampaignError(ValueError):
    pass


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CampaignError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CampaignError(f"Expected a JSON object in {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise CampaignError(f"{label}: expected {expected!r}, received {actual!r}")


def project_file(project_root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise CampaignError(f"{label}: expected a nonempty project-relative path")
    path = (project_root / relative).resolve()
    try:
        path.relative_to(project_root.resolve())
    except ValueError as exc:
        raise CampaignError(f"{label}: path escapes project root") from exc
    return path


def require_sha256(value, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise CampaignError(f"{label}: missing or invalid pinned SHA-256")
    return value


def board_environment(campaign: dict, board_spec: dict) -> dict:
    environment = board_spec.get("environment", campaign.get("environment"))
    if not isinstance(environment, dict):
        raise CampaignError("Missing recorded board environment")
    for key in ("externally_measured_dut_voltage_V", "voltage_absolute_uncertainty_V", "ambient_temperature_C"):
        value = environment.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise CampaignError(f"Missing or nonfinite recorded environment {key}")
    if environment["externally_measured_dut_voltage_V"] <= 0 or environment["voltage_absolute_uncertainty_V"] < 0:
        raise CampaignError("Invalid recorded voltage or voltage uncertainty")
    return environment


def validate_profile(project_root: Path, board: str, board_spec: dict, campaign: dict) -> dict | None:
    """Schema 2 explicitly pins each board's original experiment and image.

    Schema 1 remains readable for historical campaigns but cannot opt into
    cross-experiment reuse without the stricter schema and its required pins.
    """
    campaign_common160 = campaign.get("experiment_id") == COMMON160_EXPERIMENT_ID
    board_common160 = board_spec.get("experiment_id") == COMMON160_EXPERIMENT_ID
    if campaign_common160 and campaign["schema_version"] != 2:
        raise CampaignError("common160 campaigns require schema 2 with pinned new captures")
    if campaign_common160 != board_common160:
        raise CampaignError(f"{board}: common160 captures cannot be mixed with other experiment profiles")
    if campaign["schema_version"] == 1:
        if "experiment_id" in board_spec:
            raise CampaignError("Per-board experiment overrides require campaign schema 2")
        return None
    experiment_id = board_spec.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise CampaignError(f"{board}: missing explicit board experiment_id")
    justification = board_spec.get("reuse_justification")
    if experiment_id != campaign["experiment_id"] and (not isinstance(justification, str) or not justification.strip()):
        raise CampaignError(f"{board}: cross-profile reuse requires an explicit justification")
    manifest_path = project_file(project_root, board_spec.get("experiment_manifest"), f"{board} experiment manifest")
    require_equal(sha256(manifest_path), require_sha256(board_spec.get("experiment_manifest_sha256"), f"{board} manifest hash"), f"{board} manifest file hash")
    manifest = read_json(manifest_path)
    require_equal(manifest.get("schema_version"), 2, f"{board} experiment schema")
    require_equal(manifest.get("experiment_id"), experiment_id, f"{board} pinned experiment")
    require_equal(manifest.get("gpio_protocol"), "single_run_v1", f"{board} GPIO protocol")
    require_equal(manifest.get("digital_channels"), {"RUN": 0}, f"{board} digital channels")
    require_equal(manifest.get("sample_rate_Hz"), campaign["instrument"]["sample_rate_Hz"], f"{board} profile sample rate")
    target_cpu_hz = board_spec.get("target_cpu_hz")
    if type(target_cpu_hz) is not int or target_cpu_hz <= 0:
        raise CampaignError(f"{board}: missing or invalid target CPU clock")
    require_equal(manifest.get("boards", {}).get(board, {}).get("target_cpu_hz"), target_cpu_hz, f"{board} target CPU clock")
    if campaign_common160:
        require_equal(target_cpu_hz, 160_000_000, f"{board} common160 target CPU clock")
        for name in BOARDS:
            spec = manifest.get("boards", {}).get(name)
            clock = spec.get("target_cpu_hz") if isinstance(spec, dict) else None
            if type(clock) is not int or clock != 160_000_000:
                raise CampaignError(f"common160 experiment must set {name} target CPU clock to 160000000")
        if justification:
            raise CampaignError(f"{board}: common160 requires new captures without historical reuse")
    require_sha256(board_spec.get("expected_firmware_sha256"), f"{board} expected image hash")
    # Local fixture-only adapter: preserve the physical LDO distinction.
    if board_spec.get("onboard_regulator_removed") is not True:
        isolated_stm32 = (
            board == "stm32"
            and board_spec.get("onboard_regulator_removed") is False
            and board_spec.get("onboard_regulator_isolated") is True
            and board_spec.get("regulator_isolation_mechanism") == "JP6_IDD_shunt_open"
            and board_spec.get("supply_injection_domain") == "MCU_VDD_side_of_JP6"
            and isinstance(board_spec.get("fixture_operator_correction"), dict)
            and bool(board_spec["fixture_operator_correction"].get("statement"))
            and board_spec["fixture_operator_correction"].get("original_metadata_preserved") is True
        )
        if not isolated_stm32:
            raise CampaignError(f"{board}: require regulator removal or explicitly documented STM32 JP6 isolation")
    if not isinstance(board_spec.get("capture_file_sha256"), dict):
        raise CampaignError(f"{board}: missing per-capture metadata/analysis hash pins")
    return manifest


def describe(values: list[float]) -> dict:
    if not values or any(not math.isfinite(value) for value in values):
        raise CampaignError("Cannot summarize empty or nonfinite values")
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "sample_standard_deviation": statistics.stdev(values) if len(values) > 1 else None,
        "minimum": min(values),
        "maximum": max(values),
    }


def validate_capture(project_root: Path, relative_dir: str, board: str,
                     board_spec: dict, campaign: dict) -> tuple[dict, dict, dict]:
    capture_dir = (project_root / relative_dir).resolve()
    try:
        capture_dir.relative_to(project_root)
    except ValueError as exc:
        raise CampaignError(f"Capture path escapes project root: {relative_dir}") from exc
    metadata_path = capture_dir / "capture_metadata.json"
    analysis_path = capture_dir / "analysis" / "capture.analysis.json"
    metadata = read_json(metadata_path)
    analysis = read_json(analysis_path)
    expected_environment = board_environment(campaign, board_spec)
    expected_instrument = campaign["instrument"]
    profile = validate_profile(project_root, board, board_spec, campaign)
    expected_experiment = board_spec["experiment_id"] if profile is not None else campaign["experiment_id"]

    require_equal(metadata.get("experiment_id"), expected_experiment, f"{relative_dir} experiment")
    require_equal(metadata.get("board"), board, f"{relative_dir} board")
    require_equal(metadata.get("physical_board_id"), board_spec["physical_board_id"], f"{relative_dir} physical board")
    require_equal(metadata.get("ppk2", {}).get("serial_number"), expected_instrument["serial_number"], f"{relative_dir} PPK2 serial")
    require_equal(metadata.get("ppk2", {}).get("mode"), expected_instrument["mode"], f"{relative_dir} PPK2 mode")
    require_equal(metadata.get("ppk2", {}).get("source_voltage_setpoint_mV"), expected_instrument["setpoint_mV"], f"{relative_dir} voltage setpoint")
    require_equal(metadata.get("acquisition", {}).get("sample_rate_Hz"), expected_instrument["sample_rate_Hz"], f"{relative_dir} sample rate")
    for key in ("externally_measured_dut_voltage_V", "voltage_absolute_uncertainty_V", "ambient_temperature_C"):
        require_equal(metadata.get("environment", {}).get(key), expected_environment[key], f"{relative_dir} {key}")
    require_equal(metadata.get("capture", {}).get("sample_counter_continuity_passed"), True, f"{relative_dir} sample counter")
    require_equal(metadata.get("analysis", {}).get("return_code"), 0, f"{relative_dir} analyzer return code")
    require_equal(analysis.get("status"), "structural_protocol_pass", f"{relative_dir} structural status")
    require_equal(analysis.get("sample_rate_Hz"), expected_instrument["sample_rate_Hz"], f"{relative_dir} analyzed sample rate")
    require_equal(
        analysis.get("startup_and_gap_short_tolerance_fraction"),
        campaign["analysis_policy"]["pause_short_tolerance_fraction"][board],
        f"{relative_dir} pause tolerance",
    )
    runs = analysis.get("runs")
    if not isinstance(runs, list) or len(runs) != len(ALGORITHMS):
        raise CampaignError(f"{relative_dir}: expected twelve analyzed RUN windows")
    if [row.get("algorithm_assumed_from_order") for row in runs] != list(ALGORITHMS):
        raise CampaignError(f"{relative_dir}: unexpected algorithm order")
    require_equal(analysis.get("sample_count"), metadata.get("capture", {}).get("sample_count"), f"{relative_dir} sample count")
    require_equal(
        analysis.get("provenance", {}).get("input_sha256"),
        metadata.get("capture", {}).get("csv_sha256"),
        f"{relative_dir} CSV hash linkage",
    )
    if profile is not None:
        pins = board_spec["capture_file_sha256"].get(relative_dir)
        if not isinstance(pins, dict):
            raise CampaignError(f"{relative_dir}: missing explicit capture-file hash pins")
        for path, key in ((metadata_path, "metadata"), (analysis_path, "analysis")):
            require_equal(sha256(path), require_sha256(pins.get(key), f"{relative_dir} {key} pin"), f"{relative_dir} {key} file hash")
        manifest_hash = board_spec["experiment_manifest_sha256"]
        require_equal(metadata.get("provenance", {}).get("manifest_sha256"), manifest_hash, f"{relative_dir} acquisition manifest hash")
        require_equal(analysis.get("provenance", {}).get("manifest_sha256"), manifest_hash, f"{relative_dir} analysis manifest hash")
        require_equal(analysis.get("provenance", {}).get("experiment_manifest"), profile, f"{relative_dir} embedded experiment manifest")
        require_equal(analysis.get("provenance", {}).get("board"), board, f"{relative_dir} analyzed board")
        require_equal(metadata.get("provenance", {}).get("expected_firmware_sha256"), board_spec["expected_firmware_sha256"], f"{relative_dir} expected firmware hash")
        require_equal(analysis.get("integration", {}).get("assumed_constant_voltage_V"), expected_environment["externally_measured_dut_voltage_V"], f"{relative_dir} integrated voltage")
        require_equal(analysis.get("integration", {}).get("baseline_subtracted"), False, f"{relative_dir} energy boundary")
        for row in runs:
            name = row["algorithm_assumed_from_order"]
            require_equal(row.get("iterations_from_manifest"), profile["boards"][board]["iterations"][name], f"{relative_dir}/{name} iterations")
        raw_path = capture_dir / "transport.raw4"
        require_equal(sha256(raw_path), require_sha256(metadata["capture"].get("transport_sha256"), f"{relative_dir} transport hash"), f"{relative_dir} raw transport hash")
        require_equal(raw_path.stat().st_size, 4 * metadata["capture"]["sample_count"], f"{relative_dir} transport byte count")
    index = {
        "board": board,
        "experiment_id": metadata["experiment_id"],
        "experiment_manifest_sha256": metadata["provenance"]["manifest_sha256"],
        "physical_board_id": metadata["physical_board_id"],
        "capture_directory": relative_dir,
        "started_utc": metadata["capture"]["started_utc"],
        "ended_utc": metadata["capture"]["ended_utc"],
        "sample_count": metadata["capture"]["sample_count"],
        "sample_time_error_percent": metadata["capture"]["sample_time_error_percent"],
        "transport_sha256": metadata["capture"]["transport_sha256"],
        "csv_sha256": metadata["capture"]["csv_sha256"],
        "expected_firmware_sha256": metadata["provenance"]["expected_firmware_sha256"],
        "capture_tool_sha256": metadata["acquisition"]["tool_sha256"],
        "analyzer_sha256": analysis["provenance"]["analyzer_sha256"],
    }
    return metadata, analysis, index


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        project_root = args.project_root.resolve()
        campaign_path = args.campaign.resolve()
        campaign = read_json(campaign_path)
        if type(campaign.get("schema_version")) is not int or campaign["schema_version"] not in (1, 2):
            raise CampaignError("Supported campaign schemas are 1 and 2")
        if campaign.get("experiment_id") == COMMON160_EXPERIMENT_ID and campaign["schema_version"] != 2:
            raise CampaignError("common160 campaigns require schema 2 with pinned new captures")
        if campaign["schema_version"] == 2:
            require_equal(campaign.get("status"), "ready_for_analysis", "campaign acquisition status")
        require_equal(tuple(campaign.get("boards", {})), BOARDS, "campaign board order")
        required = campaign.get("analysis_policy", {}).get("required_cold_boot_captures_per_board")
        require_equal(required, 10, "required captures per board")

        analyses: dict[str, list[dict]] = {board: [] for board in BOARDS}
        index_rows: list[dict] = []
        for board in BOARDS:
            board_spec = campaign["boards"][board]
            directories = board_spec.get("capture_directories")
            if not isinstance(directories, list) or len(directories) != required or len(set(directories)) != required:
                raise CampaignError(f"{board}: expected {required} unique capture directories")
            for relative_dir in directories:
                _metadata, analysis, index = validate_capture(
                    project_root, relative_dir, board, board_spec, campaign
                )
                analyses[board].append(analysis)
                index_rows.append(index)

        summary_rows: list[dict] = []
        baseline_rows: list[dict] = []
        for board in BOARDS:
            environment = board_environment(campaign, campaign["boards"][board])
            voltage = environment["externally_measured_dut_voltage_V"]
            voltage_uncertainty = environment["voltage_absolute_uncertainty_V"]
            board_analyses = analyses[board]
            baseline = describe([item["startup_baseline"]["mean_current_A"] for item in board_analyses])
            baseline_rows.append({"board": board, "mean_current_A": baseline})
            for position, algorithm in enumerate(ALGORITHMS):
                runs = [item["runs"][position] for item in board_analyses]
                iterations = {row["iterations_from_manifest"] for row in runs}
                if len(iterations) != 1:
                    raise CampaignError(f"{board}/{algorithm}: inconsistent iteration counts")
                duration = describe([row["mean_duration_per_call_s"] for row in runs])
                current = describe([row["mean_current_A"] for row in runs])
                charge = describe([row["charge_per_call_C"] for row in runs])
                energy = describe([row["energy_per_call_at_assumed_constant_voltage_J"] for row in runs])
                summary_rows.append({
                    "board": board,
                    "sequence_position": position + 1,
                    "algorithm": algorithm,
                    "captures": len(runs),
                    "iterations_per_capture": iterations.pop(),
                    "duration_per_call_s": duration,
                    "mean_current_A": current,
                    "charge_per_call_C": charge,
                    "energy_per_call_J": energy,
                    "energy_voltage_component_absolute_J": energy["mean"] * voltage_uncertainty / voltage,
                })

        report = {
            "summary_schema_version": 1,
            "status": "complete_30_capture_campaign",
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "campaign": campaign,
            "capture_count": len(index_rows),
            "capture_count_per_board": {board: len(analyses[board]) for board in BOARDS},
            "total_sample_count": sum(int(row["sample_count"]) for row in index_rows),
            "baseline": baseline_rows,
            "workloads": summary_rows,
            "interpretation": {
                "dispersion": "Sample standard deviation across ten independent cold-boot captures.",
                "voltage_component": "Absolute component from the assigned voltage uncertainty only; it excludes PPK2 accuracy, timebase, GPIO aperture and other systematic terms.",
                "per_call": "Batch charge, energy and duration divided by the manifest iteration count; calls within a batch are not independent replicates.",
                "baseline": "Last two seconds of LOW before the first RUN; active control idle, not subtracted from workload energy.",
            },
            "provenance": {
                "campaign_manifest_path": str(campaign_path),
                "campaign_manifest_sha256": sha256(campaign_path),
                "summarizer_path": str(Path(__file__).resolve()),
                "summarizer_sha256": sha256(Path(__file__).resolve()),
                "analysis_hashes": sorted({row["analyzer_sha256"] for row in index_rows}),
                "capture_tool_hashes": sorted({row["capture_tool_sha256"] for row in index_rows}),
            },
        }

        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "campaign_summary.json"
        csv_path = output_dir / "campaign_summary.csv"
        index_path = output_dir / "capture_index.csv"
        for path in (json_path, csv_path, index_path):
            if path.exists():
                raise CampaignError(f"Refusing to overwrite existing output: {path}")
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        with csv_path.open("x", encoding="utf-8", newline="") as stream:
            fields = (
                "board", "sequence_position", "algorithm", "captures", "iterations_per_capture",
                "duration_per_call_us_mean", "duration_per_call_us_sd",
                "mean_current_mA_mean", "mean_current_mA_sd",
                "charge_per_call_uC_mean", "charge_per_call_uC_sd",
                "energy_per_call_mJ_mean", "energy_per_call_mJ_sd",
                "energy_voltage_component_mJ",
            )
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in summary_rows:
                writer.writerow({
                    "board": row["board"],
                    "sequence_position": row["sequence_position"],
                    "algorithm": row["algorithm"],
                    "captures": row["captures"],
                    "iterations_per_capture": row["iterations_per_capture"],
                    "duration_per_call_us_mean": row["duration_per_call_s"]["mean"] * 1e6,
                    "duration_per_call_us_sd": row["duration_per_call_s"]["sample_standard_deviation"] * 1e6,
                    "mean_current_mA_mean": row["mean_current_A"]["mean"] * 1e3,
                    "mean_current_mA_sd": row["mean_current_A"]["sample_standard_deviation"] * 1e3,
                    "charge_per_call_uC_mean": row["charge_per_call_C"]["mean"] * 1e6,
                    "charge_per_call_uC_sd": row["charge_per_call_C"]["sample_standard_deviation"] * 1e6,
                    "energy_per_call_mJ_mean": row["energy_per_call_J"]["mean"] * 1e3,
                    "energy_per_call_mJ_sd": row["energy_per_call_J"]["sample_standard_deviation"] * 1e3,
                    "energy_voltage_component_mJ": row["energy_voltage_component_absolute_J"] * 1e3,
                })
        with index_path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(index_rows[0]))
            writer.writeheader()
            writer.writerows(index_rows)
        print(json.dumps({
            "status": report["status"],
            "captures": report["capture_count"],
            "samples": report["total_sample_count"],
            "outputs": [str(json_path), str(csv_path), str(index_path)],
        }))
        return 0
    except (CampaignError, OSError, KeyError, TypeError, statistics.StatisticsError) as exc:
        print(f"Campaign rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
