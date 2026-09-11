"""Acquisition must not silently relabel an archived or diagnostic image."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_identity_tool", ROOT / "tools/capture_ppk2.py")
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


class CaptureIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = json.loads((ROOT / "config/experiment.json").read_text(encoding="utf-8"))
        self.manifest_path = self.root / "experiment.json"
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.image = self.root / "firmware.bin"
        self.image.write_bytes(b"synthetic silent measurement image")
        digest = p.sha256_file(self.manifest_path)
        self.current = {
            "experiment_id": p.ACTIVE_EXPERIMENT_ID, "experiment_sha256": digest,
            "boards": {"rp2040": {"profiles": {"single_gpio_measurement": {
                "primary_image": "firmware.bin", "sha256": p.sha256_file(self.image),
                "experiment_manifest_sha256": digest,
                "diagnostics_enabled": False, "native_compile_and_link_passed": True,
            }}}},
        }

    def validate(self, current=None, manifest=None):
        p.validate_firmware_identity(current or self.current, manifest or self.manifest,
                                     self.manifest_path, "rp2040", self.image)

    def test_exact_expected_silent_image_is_accepted(self):
        self.validate()

    def test_legacy_acquisition_is_rejected(self):
        with self.assertRaisesRegex(p.AcquisitionError, "Acquisition requires"):
            self.validate(manifest={"experiment_id": "energy-profiling-v3-single-gpio"})

    def test_current_and_archive_identity_mismatches_are_rejected(self):
        for key, value in (("experiment_id", "other"), ("experiment_sha256", "0" * 64)):
            current = copy.deepcopy(self.current)
            current[key] = value
            with self.subTest(key=key), self.assertRaises(p.AcquisitionError):
                self.validate(current=current)
        for key, value in (("experiment_manifest_sha256", "0" * 64),
                           ("sha256", "0" * 64), ("diagnostics_enabled", True),
                           ("native_compile_and_link_passed", False)):
            current = copy.deepcopy(self.current)
            current["boards"]["rp2040"]["profiles"]["single_gpio_measurement"][key] = value
            with self.subTest(key=key), self.assertRaises(p.AcquisitionError):
                self.validate(current=current)

    def test_changed_file_bytes_are_rejected(self):
        self.image.write_bytes(b"different firmware")
        with self.assertRaisesRegex(p.AcquisitionError, "firmware SHA-256"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
