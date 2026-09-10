import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.export_ppk2_raw import ExportError, export_raw


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RawExportTests(unittest.TestCase):
    def metadata(self, raw_path: Path, sample_count: int) -> dict:
        ranges = {str(index): 1.0 for index in range(5)}
        zeros = {str(index): 0.0 for index in range(5)}
        return {
            "ppk2": {
                "source_voltage_setpoint_mV": 3300,
                "calibration_metadata": {
                    "R": ranges,
                    "GS": zeros,
                    "GI": ranges,
                    "O": zeros,
                    "S": zeros,
                    "I": zeros,
                    "UG": ranges,
                },
            },
            "capture": {
                "transport_sha256": file_sha256(raw_path),
                "sample_count": sample_count,
            },
        }

    def test_export_columns_values_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "transport.raw4"
            values = [100 | (0 << 24), 200 | (1 << 24), 300 | (0 << 24)]
            raw.write_bytes(b"".join(value.to_bytes(4, "little") for value in values))
            output = root / "capture.csv"
            metadata = self.metadata(raw, 3)
            result = export_raw(raw, metadata, output)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[0], ["Sample", "Timestamp(us)", "Current(uA)", "D0"])
            self.assertEqual([row[0] for row in rows[1:]], ["0", "1", "2"])
            self.assertEqual([row[1] for row in rows[1:]], ["0", "10", "20"])
            self.assertEqual([row[3] for row in rows[1:]], ["0", "1", "0"])
            self.assertEqual(result["sample_count"], 3)
            self.assertEqual(result["output_sha256"], file_sha256(output))
            with self.assertRaises(FileExistsError):
                export_raw(raw, metadata, output)

    def test_bad_hash_and_partial_frame_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "transport.raw4"
            raw.write_bytes((100).to_bytes(4, "little"))
            metadata = self.metadata(raw, 1)
            metadata["capture"]["transport_sha256"] = "0" * 64
            with self.assertRaisesRegex(ExportError, "SHA-256"):
                export_raw(raw, metadata, root / "bad.csv")
            raw.write_bytes(b"abc")
            with self.assertRaisesRegex(ExportError, "four-byte"):
                export_raw(raw, metadata, root / "partial.csv", verify_hash=False)


if __name__ == "__main__":
    unittest.main()
