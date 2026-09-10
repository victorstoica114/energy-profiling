import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.build_raw_inventory import build_inventory


class RawInventoryTests(unittest.TestCase):
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
