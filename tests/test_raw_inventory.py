import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.build_raw_inventory import build_inventory, main


class RawInventoryTests(unittest.TestCase):
    def test_cli_defaults_use_completed_selections_and_ignore_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for profile, manifest in (
                ("max_clock", "ROW_Data/source_campaign.json"),
                ("common160", "ROW_Data/common160/source_campaign.json"),
            ):
                relative = f"captures_{profile}/rp2040/accepted"
                capture = root / relative
                capture.mkdir(parents=True)
                (capture / "transport.raw4").write_bytes(b"\0\0\0\0")
                selection = root / manifest
                selection.parent.mkdir(parents=True, exist_ok=True)
                selection.write_text(json.dumps({
                    "campaign_id": profile,
                    "boards": {"rp2040": {"capture_directories": [relative]}},
                }), encoding="utf-8")
            templates = root / "campaigns"
            templates.mkdir()
            (templates / "pending.json").write_text(json.dumps({
                "campaign_id": "pending_template",
                "boards": {"rp2040": {"capture_directories": []}},
            }), encoding="utf-8")
            self.assertEqual(main(["--project-root", str(root)]), 0)
            report = json.loads((root / "dataset/raw_inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(report["role_counts"], {"selected_final": 2})
            self.assertEqual(report["campaign_manifests"], [
                "ROW_Data/source_campaign.json", "ROW_Data/common160/source_campaign.json",
            ])
            self.assertEqual({row["selected_campaigns"] for row in report["rows"]}, {"max_clock", "common160"})
            self.assertEqual(main([
                "--project-root", str(root), "--campaign", "ROW_Data/common160/source_campaign.json",
                "--output-dir", "common_only",
            ]), 0)
            explicit = json.loads((root / "common_only/raw_inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(explicit["role_counts"], {"selected_final": 1, "pilot": 1})

    def test_cli_missing_default_selection_does_not_fall_back_to_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "campaigns").mkdir()
            (root / "campaigns/template.json").write_text(json.dumps({
                "campaign_id": "pending", "boards": {},
            }), encoding="utf-8")
            self.assertEqual(main(["--project-root", str(root)]), 2)
            self.assertFalse((root / "dataset").exists())

    def test_separate_clock_profile_roots_are_included_without_merging_campaigns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common_dir = "captures_common160/rp2040/synthetic_common"
            max_dir = "captures_max_clock/rp2040/synthetic_max"
            for relative in (common_dir, max_dir):
                capture = root / relative
                capture.mkdir(parents=True)
                (capture / "transport.raw4").write_bytes(b"\0\0\0\0")
            campaign = root / "common.json"
            campaign.write_text(json.dumps({
                "campaign_id": "synthetic_common160",
                "boards": {"rp2040": {"capture_directories": [common_dir]}},
            }), encoding="utf-8")
            report = build_inventory(root, [campaign])
            rows = {row["capture_directory"]: row for row in report["rows"]}
            self.assertEqual(report["raw_file_count"], 2)
            self.assertEqual(rows[common_dir]["selected_campaigns"], "synthetic_common160")
            self.assertEqual(rows[common_dir]["role"], "selected_final")
            self.assertEqual(rows[max_dir]["selected_campaigns"], "")
            self.assertEqual(rows[max_dir]["role"], "pilot")

    def test_selected_pilot_rejected_and_incomplete_are_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_dir = root / "campaigns"
            campaign_dir.mkdir()
            capture_root = root / "captures" / "esp32"
            selected = capture_root / "selected"
            pilot = capture_root / "pilot"
            rejected = capture_root / "rejected"
            incomplete = capture_root / "incomplete"
            for path in (selected, pilot, rejected, incomplete):
                path.mkdir(parents=True)
            selected_raw = selected / "transport.raw4"
            selected_raw.write_bytes(b"\0\0\0\0")
            digest = hashlib.sha256(selected_raw.read_bytes()).hexdigest()
            (selected / "capture_metadata.json").write_text(json.dumps({
                "board": "esp32",
                "physical_board_id": "board-1",
                "capture": {"transport_sha256": digest},
            }), encoding="utf-8")
            (pilot / "transport.raw4").write_bytes(b"\0\0\0\0")
            (rejected / "transport.raw4").write_bytes(b"\0\0\0\0")
            (rejected / "failure.json").write_text(json.dumps({"error_type": "ExampleError"}), encoding="utf-8")
            (incomplete / "transport.partial.raw4").write_bytes(b"\0\0\0\0")
            campaign = campaign_dir / "campaign.json"
            campaign.write_text(json.dumps({
                "campaign_id": "example",
                "boards": {"esp32": {"capture_directories": ["captures/esp32/selected"]}},
            }), encoding="utf-8")
            report = build_inventory(root, [campaign])
            roles = {row["capture_directory"]: row["role"] for row in report["rows"]}
            self.assertEqual(roles["captures/esp32/selected"], "selected_final")
            self.assertEqual(roles["captures/esp32/pilot"], "pilot")
            self.assertEqual(roles["captures/esp32/rejected"], "rejected_complete")
            self.assertEqual(roles["captures/esp32/incomplete"], "incomplete_transport")
            self.assertEqual(report["raw_file_count"], 4)


if __name__ == "__main__":
    unittest.main()
