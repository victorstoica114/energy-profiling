"""Synthetic evidence-binding tests; these fixtures are not measurements."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("campaign_profiles", ROOT / "tools/summarize_campaign.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class CampaignProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.relative = "captures_noreg/esp32/synthetic_001"
        self.capture = self.root / self.relative
        (self.capture / "analysis").mkdir(parents=True)
        self.profile = json.loads((ROOT / "campaigns/profiles/energy-profiling-v3-single-gpio.json").read_text(encoding="utf-8"))
        self.profile_path = self.root / "old_experiment.json"
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")
        self.profile_hash = s.sha256(self.profile_path)
        self.image_hash = "a" * 64
        (self.capture / "transport.raw4").write_bytes(b"\x00\x00\x00\x00" * 4)
        self.environment = {
            "externally_measured_dut_voltage_V": 3.3,
            "voltage_absolute_uncertainty_V": 0.01, "ambient_temperature_C": 25.0,
        }
        self.metadata = {
            "experiment_id": self.profile["experiment_id"], "board": "esp32",
            "physical_board_id": "test-unit",
            "ppk2": {"serial_number": "test-ppk", "mode": "source_meter", "source_voltage_setpoint_mV": 3300},
            "acquisition": {"sample_rate_Hz": 100000, "tool_sha256": "b" * 64},
            "environment": dict(self.environment),
            "capture": {"sample_counter_continuity_passed": True, "sample_count": 4,
                        "csv_sha256": "c" * 64, "transport_sha256": s.sha256(self.capture / "transport.raw4"),
                        "started_utc": "synthetic", "ended_utc": "synthetic", "sample_time_error_percent": 0.0},
            "analysis": {"return_code": 0},
            "provenance": {"manifest_sha256": self.profile_hash, "expected_firmware_sha256": self.image_hash},
        }
        self.analysis = {
            "status": "structural_protocol_pass", "sample_rate_Hz": 100000,
            "startup_and_gap_short_tolerance_fraction": 0.01, "sample_count": 4,
            "integration": {"assumed_constant_voltage_V": 3.3, "baseline_subtracted": False},
            "provenance": {"input_sha256": "c" * 64, "manifest_sha256": self.profile_hash,
                           "experiment_manifest": copy.deepcopy(self.profile), "board": "esp32", "analyzer_sha256": "d" * 64},
            "runs": [{"algorithm_assumed_from_order": name,
                      "iterations_from_manifest": self.profile["boards"]["esp32"]["iterations"][name]}
                     for name in s.ALGORITHMS],
        }
        self.board = {
            "physical_board_id": "test-unit", "onboard_regulator_removed": True,
            "experiment_id": self.profile["experiment_id"],
            "experiment_manifest": "old_experiment.json", "experiment_manifest_sha256": self.profile_hash,
            "expected_firmware_sha256": self.image_hash, "target_cpu_hz": 240000000,
            "reuse_justification": "Explicit reuse of an unchanged ESP32 operating point.",
            "environment": self.environment, "capture_file_sha256": {},
        }
        self.campaign = {
            "schema_version": 2, "status": "ready_for_analysis",
            "experiment_id": "energy-profiling-v4-max-clock",
            "instrument": {"serial_number": "test-ppk", "mode": "source_meter",
                           "setpoint_mV": 3300, "sample_rate_Hz": 100000},
            "analysis_policy": {"pause_short_tolerance_fraction": {"esp32": 0.01}},
        }
        self.save_and_pin()

    def save_and_pin(self):
        metadata_path = self.capture / "capture_metadata.json"
        analysis_path = self.capture / "analysis/capture.analysis.json"
        metadata_path.write_text(json.dumps(self.metadata), encoding="utf-8")
        analysis_path.write_text(json.dumps(self.analysis), encoding="utf-8")
        self.board["capture_file_sha256"][self.relative] = {
            "metadata": s.sha256(metadata_path), "analysis": s.sha256(analysis_path),
        }

    def validate(self):
        return s.validate_capture(self.root, self.relative, "esp32", self.board, self.campaign)

    def test_explicit_old_esp32_reuse_preserves_original_identity(self):
        _, _, index = self.validate()
        self.assertEqual(index["experiment_id"], "energy-profiling-v3-single-gpio")
        self.assertEqual(index["experiment_manifest_sha256"], self.profile_hash)
        self.assertEqual(index["expected_firmware_sha256"], self.image_hash)

    def test_current_profile_capture_also_passes(self):
        self.profile = json.loads((ROOT / "config/experiment.json").read_text(encoding="utf-8"))
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")
        digest = s.sha256(self.profile_path)
        self.metadata["experiment_id"] = self.profile["experiment_id"]
        self.metadata["provenance"]["manifest_sha256"] = digest
        self.analysis["provenance"]["manifest_sha256"] = digest
        self.analysis["provenance"]["experiment_manifest"] = self.profile
        self.board["experiment_id"] = self.profile["experiment_id"]
        self.board["experiment_manifest_sha256"] = digest
        self.board.pop("reuse_justification")
        self.save_and_pin()
        self.validate()

    def test_missing_explicit_override_or_justification_is_rejected(self):
        saved = copy.deepcopy(self.board)
        for key in ("experiment_id", "reuse_justification"):
            self.board = copy.deepcopy(saved)
            del self.board[key]
            with self.subTest(key=key), self.assertRaises(s.CampaignError):
                self.validate()

    def test_schema_one_cannot_enable_cross_profile_overrides(self):
        self.campaign["schema_version"] = 1
        with self.assertRaisesRegex(s.CampaignError, "require campaign schema 2"):
            self.validate()

    def test_old_capture_cannot_be_relabelled_as_current_profile(self):
        self.metadata["experiment_id"] = self.campaign["experiment_id"]
        self.save_and_pin()
        with self.assertRaisesRegex(s.CampaignError, "experiment"):
            self.validate()

    def test_repinning_metadata_cannot_hide_wrong_manifest_or_image(self):
        saved = copy.deepcopy(self.metadata)
        for key in ("manifest_sha256", "expected_firmware_sha256"):
            self.metadata = copy.deepcopy(saved)
            self.metadata["provenance"][key] = "0" * 64
            self.save_and_pin()
            with self.subTest(key=key), self.assertRaises(s.CampaignError):
                self.validate()

    def test_repinning_analysis_cannot_hide_wrong_embedded_profile(self):
        self.analysis["provenance"]["experiment_manifest"]["boards"]["esp32"]["target_cpu_hz"] = 200000000
        self.save_and_pin()
        with self.assertRaisesRegex(s.CampaignError, "embedded experiment"):
            self.validate()

    def test_wrong_iteration_normalization_is_rejected(self):
        self.analysis["runs"][0]["iterations_from_manifest"] += 1
        self.save_and_pin()
        with self.assertRaisesRegex(s.CampaignError, "iterations"):
            self.validate()

    def test_wrong_recorded_clock_is_rejected(self):
        self.board["target_cpu_hz"] = 200000000
        with self.assertRaisesRegex(s.CampaignError, "target CPU clock"):
            self.validate()

    def test_unpinned_capture_and_tampered_analysis_are_rejected(self):
        self.board["capture_file_sha256"] = {}
        with self.assertRaisesRegex(s.CampaignError, "capture-file hash pins"):
            self.validate()
        self.save_and_pin()
        path = self.capture / "analysis/capture.analysis.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(s.CampaignError, "analysis file hash"):
            self.validate()

    def test_raw_transport_tampering_is_rejected(self):
        (self.capture / "transport.raw4").write_bytes(b"changed raw data!")
        with self.assertRaisesRegex(s.CampaignError, "raw transport hash"):
            self.validate()

    def test_missing_new_session_environment_is_rejected(self):
        self.board["environment"]["ambient_temperature_C"] = None
        with self.assertRaisesRegex(s.CampaignError, "environment"):
            self.validate()

    def test_pending_campaign_template_produces_no_summary(self):
        output = self.root / "must_not_exist"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = s.main([str(ROOT / "campaigns/2026-09-11_ppk2_max_clock.template.json"),
                           "--project-root", str(self.root), "--output-dir", str(output)])
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
