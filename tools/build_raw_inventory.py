#!/usr/bin/env python3
"""Inventory every archived PPK2 raw stream and its campaign-selection role."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class InventoryError(ValueError):
    pass


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InventoryError(f"Expected a JSON object in {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def campaign_selections(project_root: Path, campaign_paths: list[Path]) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    for path in campaign_paths:
        campaign = read_json(path)
        campaign_id = campaign.get("campaign_id")
        boards = campaign.get("boards")
        if not isinstance(campaign_id, str) or not isinstance(boards, dict):
            raise InventoryError(f"Invalid campaign structure: {path}")
        for board in boards.values():
            if not isinstance(board, dict):
                raise InventoryError(f"Invalid board structure: {path}")
            for relative_dir in board.get("capture_directories", []):
                normalized = Path(relative_dir).as_posix()
                selected.setdefault(normalized, []).append(campaign_id)
    return selected


def infer_board(relative_path: Path) -> str:
    for part in relative_path.parts:
        if part in {"esp32", "rp2040", "stm32"}:
            return part
    return "unknown"


def build_inventory(project_root: Path, campaign_paths: list[Path]) -> dict:
    selections = campaign_selections(project_root, campaign_paths)
    raw_paths: list[Path] = []
    for root_name in ("captures", "captures_noreg", "captures_max_clock", "captures_common160", "diagnostics"):
        root = project_root / root_name
        if root.is_dir():
            raw_paths.extend(root.rglob("*.raw4"))
    raw_paths = sorted(set(raw_paths), key=lambda path: path.relative_to(project_root).as_posix())
    if not raw_paths:
        raise InventoryError("No .raw4 streams found")

    rows: list[dict] = []
    for raw_path in raw_paths:
        capture_dir = raw_path.parent
        relative_dir = capture_dir.relative_to(project_root).as_posix()
        relative_path = raw_path.relative_to(project_root).as_posix()
        metadata_path = capture_dir / "capture_metadata.json"
        failure_path = capture_dir / "failure.json"
        analysis_path = capture_dir / "analysis" / "capture.analysis.json"
        metadata = read_json(metadata_path) if metadata_path.is_file() else {}
        failure = read_json(failure_path) if failure_path.is_file() else {}
        analysis = read_json(analysis_path) if analysis_path.is_file() else {}
        campaigns = sorted(set(selections.get(relative_dir, [])))
        if raw_path.name != "transport.raw4":
            role = "incomplete_transport"
        elif campaigns:
            role = "selected_final"
        elif failure:
            role = "rejected_complete"
        else:
            role = "pilot"
        actual_sha256 = sha256_file(raw_path)
        recorded_sha256 = metadata.get("capture", {}).get("transport_sha256")
        rows.append({
            "raw_path": relative_path,
            "capture_directory": relative_dir,
            "board": metadata.get("board") or failure.get("board") or infer_board(Path(relative_path)),
            "physical_board_id": metadata.get("physical_board_id") or failure.get("physical_board_id") or "",
            "role": role,
            "selected_campaigns": ";".join(campaigns),
            "analysis_status": analysis.get("status", ""),
            "failure_type": failure.get("error_type", ""),
            "bytes": raw_path.stat().st_size,
            "frames": raw_path.stat().st_size // 4,
            "sha256": actual_sha256,
            "recorded_sha256": recorded_sha256 or "",
            "recorded_hash_matches": "" if not recorded_sha256 else str(actual_sha256 == recorded_sha256).lower(),
        })

    role_counts: dict[str, int] = {}
    for row in rows:
        role_counts[row["role"]] = role_counts.get(row["role"], 0) + 1
    mismatches = [row["raw_path"] for row in rows if row["recorded_hash_matches"] == "false"]
    if mismatches:
        raise InventoryError(f"Recorded raw hash mismatch: {', '.join(mismatches)}")
    return {
        "inventory_schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "raw_format": "Exact four-byte ppk2-api transport frames; not a Nordic .ppk2 application archive.",
        "raw_file_count": len(rows),
        "raw_total_bytes": sum(row["bytes"] for row in rows),
        "role_counts": role_counts,
        "campaign_manifests": [path.relative_to(project_root).as_posix() for path in campaign_paths],
        "rows": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("dataset"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        project_root = args.project_root.resolve()
        campaigns = sorted((project_root / "campaigns").glob("*.json"))
        if not campaigns:
            raise InventoryError("No campaign manifests found")
        report = build_inventory(project_root, campaigns)
        output_dir = args.output_dir
        if not output_dir.is_absolute():
            output_dir = project_root / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "raw_inventory.json"
        csv_path = output_dir / "raw_inventory.csv"
        if not args.force and (json_path.exists() or csv_path.exists()):
            raise InventoryError("Inventory output exists; use --force to replace it")
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(report["rows"][0]))
            writer.writeheader()
            writer.writerows(report["rows"])
        print(json.dumps({
            "status": "inventory_complete",
            "raw_files": report["raw_file_count"],
            "raw_bytes": report["raw_total_bytes"],
            "roles": report["role_counts"],
            "outputs": [str(json_path.resolve()), str(csv_path.resolve())],
        }))
        return 0
    except (InventoryError, OSError, KeyError, TypeError) as exc:
        print(f"Inventory failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
