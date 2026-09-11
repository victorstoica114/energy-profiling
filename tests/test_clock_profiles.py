"""Clock-profile isolation using synthetic firmware; no PPK2 or DUT is opened."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p = load_tool("capture_clock_profiles", "capture_ppk2.py")
a = load_tool("analyze_clock_profiles", "analyze_capture.py")


class SessionBoundaryReached(Exception):
    """Stop an accepted preflight before any hardware interaction."""


class ClockProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = {}
        for profile, filename in (("max_clock", "experiment.json"), ("common160", "experiment.common160.json")):
            folder = self.root / profile
            folder.mkdir()
            manifest_path = folder / "experiment.json"
            manifest_path.write_bytes((ROOT / "config" / filename).read_bytes())
            image = folder / "firmware.bin"
            image.write_bytes(f"Synthetic {profile} image, not flashable".encode("ascii"))
            digest = p.sha256_file(manifest_path)
            current = {
                "experiment_id": json.loads(manifest_path.read_text())["experiment_id"],
                "experiment_sha256": digest,
                "boards": {"esp32": {"profiles": {"single_gpio_measurement": {
                    "primary_image": str(image), "sha256": p.sha256_file(image),
                    "experiment_manifest_sha256": digest,
                    "diagnostics_enabled": False, "native_compile_and_link_passed": True,
                }}}},
            }
            current_path = folder / "CURRENT_FIRMWARE.json"
            current_path.write_text(json.dumps(current), encoding="utf-8")
            self.paths[profile] = (manifest_path, current_path, image)

    def cli_args(self, profile, *, source=None, firmware=None):
        manifest_path, current_path, _ = self.paths[source or profile]
        args = ["--board", "esp32", "--clock-profile", profile, "--confirm-wiring",
                "--manifest", str(manifest_path), "--current-firmware", str(current_path),
                "--output-root", str(self.root / "must_not_exist")]
        if firmware is not None:
            args += ["--firmware", str(firmware)]
        return args

    def reject_before_session(self, argv, reason):
        stderr = io.StringIO()
        with (patch.object(p, "list_ppk2_devices", return_value=[("SYNTHETIC", "TEST")]),
              patch.object(p, "Ppk2SourceSession") as session,
              redirect_stdout(io.StringIO()), redirect_stderr(stderr)):
            self.assertEqual(p.main(argv), 2)
            session.assert_not_called()
        self.assertIn(reason, stderr.getvalue())
        self.assertFalse((self.root / "must_not_exist").exists())

    def test_max_clock_remains_default_and_common160_selects_separate_paths(self):
        defaults = p.apply_clock_profile_defaults(p.build_parser().parse_args([]))
        self.assertEqual(defaults.clock_profile, "max_clock")
        self.assertEqual(defaults.manifest, Path("config/experiment.json"))
        self.assertEqual(defaults.current_firmware, Path("CURRENT_FIRMWARE.json"))
        self.assertEqual(defaults.output_root, Path("captures_max_clock"))
        common = p.apply_clock_profile_defaults(p.build_parser().parse_args(["--clock-profile", "common160"]))
        self.assertEqual(common.manifest, Path("config/experiment.common160.json"))
        self.assertEqual(common.current_firmware, Path("profiles/common160/CURRENT_FIRMWARE.json"))
        self.assertEqual(common.output_root, Path("captures_common160"))

    def test_explicit_paths_are_preserved_for_both_profiles_in_either_argument_order(self):
        for profile in ("max_clock", "common160"):
            paths = ["--manifest", "custom/manifest.json", "--current-firmware", "custom/images.json",
                     "--output-root", "custom/captures"]
            for argv in (paths + ["--clock-profile", profile], ["--clock-profile", profile] + paths):
                args = p.apply_clock_profile_defaults(p.build_parser().parse_args(argv))
                self.assertEqual(args.manifest, Path("custom/manifest.json"))
                self.assertEqual(args.current_firmware, Path("custom/images.json"))
                self.assertEqual(args.output_root, Path("custom/captures"))

    def test_valid_explicit_image_and_profile_reach_session_boundary(self):
        for profile in ("max_clock", "common160"):
            with (self.subTest(profile=profile),
                  patch.object(p, "list_ppk2_devices", return_value=[("SYNTHETIC", "TEST")]),
                  patch.object(p, "Ppk2SourceSession", side_effect=SessionBoundaryReached) as session,
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                with self.assertRaises(SessionBoundaryReached):
                    p.main(self.cli_args(profile, firmware=self.paths[profile][2]))
                session.assert_called_once_with("SYNTHETIC", voltage_mv=3300)

    def test_wrong_profile_manifest_override_is_rejected_in_both_directions(self):
        for selected, source in (("common160", "max_clock"), ("max_clock", "common160")):
            with self.subTest(selected=selected):
                self.reject_before_session(self.cli_args(selected, source=source), "Acquisition requires experiment")

    def test_common160_rejects_max_current_manifest_override(self):
        args = self.cli_args("common160")
        args[args.index("--current-firmware") + 1] = str(self.paths["max_clock"][1])
        self.reject_before_session(args, "CURRENT_FIRMWARE experiment does not match")

    def test_explicit_firmware_override_cannot_bypass_profile_hash(self):
        for selected, source in (("common160", "max_clock"), ("max_clock", "common160")):
            with self.subTest(selected=selected):
                self.reject_before_session(self.cli_args(selected, firmware=self.paths[source][2]),
                                           "firmware SHA-256 does not match")

    def test_common160_rejects_relabelled_max_clock_even_with_updated_manifest_pins(self):
        manifest_path, current_path, _ = self.paths["common160"]
        original = json.loads(manifest_path.read_text())
        for board, clock in (("esp32", 240000000), ("rp2040", 200000000), ("stm32", 180000000)):
            manifest = copy.deepcopy(original)
            manifest["boards"][board]["target_cpu_hz"] = clock
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            current = json.loads(current_path.read_text())
            current["experiment_sha256"] = p.sha256_file(manifest_path)
            current["boards"]["esp32"]["profiles"]["single_gpio_measurement"]["experiment_manifest_sha256"] = current["experiment_sha256"]
            current_path.write_text(json.dumps(current), encoding="utf-8")
            with self.subTest(board=board):
                self.reject_before_session(self.cli_args("common160"), f"requires {board} target_cpu_hz=160000000")

    def test_common160_requires_schema_two(self):
        path = self.paths["common160"][0]
        manifest = json.loads(path.read_text())
        manifest["schema_version"] = 1
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.reject_before_session(self.cli_args("common160"), "schema_version 2")

    def test_common160_requires_native_silent_image_and_matching_archive_manifest(self):
        path = self.paths["common160"][1]
        original = json.loads(path.read_text())
        for key, value, reason in (
            ("diagnostics_enabled", True, "diagnostics disabled"),
            ("native_compile_and_link_passed", False, "successful native build"),
            ("experiment_manifest_sha256", "0" * 64, "archive experiment SHA-256"),
        ):
            current = copy.deepcopy(original)
            current["boards"]["esp32"]["profiles"]["single_gpio_measurement"][key] = value
            path.write_text(json.dumps(current), encoding="utf-8")
            with self.subTest(key=key):
                self.reject_before_session(self.cli_args("common160"), reason)

    def test_analyzer_supports_all_three_profiles_and_preserves_board_counts(self):
        for relative in ("config/experiment.json", "config/experiment.common160.json",
                         "campaigns/profiles/energy-profiling-v3-single-gpio.json"):
            for board in ("esp32", "rp2040", "stm32"):
                with self.subTest(profile=relative, board=board):
                    manifest = a.load_manifest(ROOT / relative, board)
                    self.assertEqual(len(manifest["boards"][board]["iterations"]), 12)

    def test_analyzer_rejects_common160_manifest_with_a_noncommon_clock(self):
        path = self.paths["common160"][0]
        manifest = json.loads(path.read_text())
        manifest["boards"]["rp2040"]["target_cpu_hz"] = 200000000
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(a.CaptureError, "common160 requires rp2040"):
            a.load_manifest(path, "esp32")


if __name__ == "__main__":
    unittest.main()
