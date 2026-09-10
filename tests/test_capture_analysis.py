"""Synthetic single-GPIO contract tests; these are not laboratory measurements."""
import copy
import csv
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
import zipfile

TOOL = Path(__file__).resolve().parents[1] / "tools" / "analyze_capture.py"
spec = importlib.util.spec_from_file_location("capture_analysis_single_gpio", TOOL)
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)
COUNTS = {name: i + 10 for i, name in enumerate(a.ALGORITHMS, 1)}


def sequence(startup=500_000, gap=100_000, tail=300_000):
    segments = [(startup, 0.01, 0)]
    for position in range(1, 13):
        segments.append((100 + position, 0.02 * position, 1))
        if position < 12:
            segments.append((gap, 0.008, 0))
    segments.append((tail, 0.004, 0))
    return segments


def capture(segments):
    rows = itertools.chain.from_iterable(itertools.repeat((current, run), n) for n, current, run in segments)
    return a.Capture(rows, 100_000, {"format": "synthetic"})


def native_bytes(segments, other_pairs=0):
    output = io.BytesIO()
    for n, current, run in segments:
        pair = 0 if run is None else (2 if run else 1)
        # D1..D7 are deliberately unconnected by default (native pair 00).
        frame = struct.pack("<f", current * 1e6) + struct.pack(">H", (other_pairs << 2) | pair)
        output.write(frame * n)
    return output.getvalue()


def manifest():
    return {
        "schema_version": 2, "experiment_id": "energy-profiling-v3-single-gpio",
        "digital_channels": {"RUN": 0}, "sample_rate_Hz": 100_000,
        "stable_baseline_seconds": 2.0, "startup_idle_ms": 5000,
        "inter_algorithm_idle_ms": 1000, "post_suite_idle_ms": 2000,
        "minimum_capture_tail_ms": 3000, "nominal_voltage_V": 3.3,
        "algorithms": [{"id": i, "name": name} for i, name in enumerate(a.ALGORITHMS, 1)],
        "boards": {board: {"marker_pin": pin, "iterations": dict(COUNTS)}
                   for board, pin in (("esp32", 18), ("rp2040", 2), ("stm32", "PC0"))},
    }


def write_native(path, payload, meta=None, extra=None, compression=zipfile.ZIP_DEFLATED):
    if meta is None:
        meta = {"formatVersion": 2, "metadata": {"samplesPerSecond": 100_000}}
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        archive.writestr("metadata.json", meta if isinstance(meta, str) else json.dumps(meta))
        archive.writestr("session.raw", payload)
        archive.writestr("minimap.raw", b"")
        if extra:
            archive.writestr(extra, b"unused")


class CaptureAnalysisTests(unittest.TestCase):
    def test_complete_gates_rectangular_integrals_and_inferred_baseline(self):
        result = a.analyze(capture(sequence()), COUNTS, voltage=3.3)
        self.assertEqual(result["status"], "structural_protocol_pass")
        self.assertFalse(result["final_validation_completion_proven"])
        self.assertFalse(result["integration"]["baseline_subtracted"])
        self.assertEqual(result["startup_baseline"]["start_sample_inclusive"], 300_000)
        self.assertEqual(result["startup_baseline"]["sample_count"], 200_000)
        self.assertAlmostEqual(result["startup_baseline"]["charge_C"], 0.02)
        self.assertEqual(len(result["runs"]), 12)
        for position, row in enumerate(result["runs"], 1):
            self.assertEqual(row["sequence_position"], position)
            self.assertEqual(row["algorithm_assumed_from_order"], a.ALGORITHMS[position - 1])
            self.assertEqual(row["sample_count"], 100 + position)
            self.assertEqual(row["end_sample_exclusive"] - row["start_sample_inclusive"], 100 + position)
            self.assertAlmostEqual(row["duration_s"], (100 + position) / 100_000)
            self.assertAlmostEqual(row["charge_C"], 0.02 * position * (100 + position) / 100_000)
            self.assertAlmostEqual(row["energy_per_call_at_assumed_constant_voltage_J"], 3.3 * row["charge_C"] / (10 + position))
        self.assertEqual([w["kind"] for w in result["low_intervals"]], ["startup_low"] + ["inter_workload_low"] * 11 + ["trailing_low"])
        self.assertNotIn("charge_C", result["low_intervals"][0])
        self.assertEqual(result["trailing_low_duration_s"], 3.0)
        self.assertTrue(any("hang while LOW" in text for text in result["limitations"]))
        self.assertNotIn("done_first_sample", result)
        self.assertNotIn("marked_idle_windows", result)

    def test_exact_lower_tolerance_boundaries_are_accepted(self):
        result = a.analyze(capture(sequence(startup=495_000, gap=99_000)), COUNTS, voltage=3.3)
        self.assertEqual(result["low_intervals"][0]["duration_s"], 4.95)
        self.assertEqual(result["low_intervals"][1]["duration_s"], 0.99)

    def test_explicit_two_percent_pause_tolerance_is_reported_and_bounded(self):
        result = a.analyze(
            capture(sequence(startup=490_000, gap=98_000)), COUNTS, voltage=3.3,
            pause_short_tolerance_fraction=0.02,
        )
        self.assertEqual(result["startup_and_gap_short_tolerance_fraction"], 0.02)
        self.assertEqual(result["low_intervals"][0]["minimum_accepted_duration_s"], 4.9)
        self.assertEqual(result["low_intervals"][1]["minimum_accepted_duration_s"], 0.98)
        with self.assertRaisesRegex(a.CaptureError, "inter_workload_low LOW"):
            a.analyze(
                capture(sequence(gap=97_999)), COUNTS, voltage=3.3,
                pause_short_tolerance_fraction=0.02,
            )

    def test_boot_preparation_and_trailing_low_have_no_upper_bound(self):
        result = a.analyze(capture(sequence(startup=620_000, gap=120_000, tail=410_000)), COUNTS, voltage=3.3)
        self.assertEqual(result["startup_baseline"]["start_sample_inclusive"], 420_000)
        self.assertEqual(result["trailing_low_duration_s"], 4.1)

    def test_short_startup_gap_and_tail_rejected(self):
        for segments, reason in (
            (sequence(startup=494_999), "Startup LOW"),
            (sequence(gap=98_999), "inter_workload_low LOW"),
            (sequence(tail=299_999), "trailing_low LOW"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(a.CaptureError, reason):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_initial_high_or_unknown_then_high_is_truncated_or_fault(self):
        for segments in ([(1, 0.02, 1)], [(9, 0, None), (1, 0.02, 1)]):
            with self.assertRaisesRegex(a.CaptureError, "First defined D0 must be LOW"):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_end_high_including_latched_fault_rejected(self):
        for segments in ([(500_000, 0.01, 0), (1000, 0.02, 1)], sequence()[:-1]):
            with self.assertRaisesRegex(a.CaptureError, "ended while RUN was HIGH"):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_missing_window_and_thirteenth_rise_rejected(self):
        with self.assertRaisesRegex(a.CaptureError, "11 of 12 RUN windows"):
            a.analyze(capture(sequence()[:-3] + [(300_000, 0.01, 0)]), COUNTS, voltage=3.3)
        with self.assertRaisesRegex(a.CaptureError, "extra RUN rise"):
            a.analyze(capture(sequence() + [(1, 0.02, 1)]), COUNTS, voltage=3.3)

    def test_split_glitch_or_restart_gap_cannot_be_repaired(self):
        segments = [(500_000, 0.01, 0), (50, 0.02, 1), (1, 0.01, 0), (51, 0.02, 1)]
        with self.assertRaisesRegex(a.CaptureError, "inter_workload_low LOW"):
            a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_unknown_prefix_and_signed_boot_noise_keep_original_indices(self):
        prefix = [(7, -1e-6, None), (3, -2e-6, 0)]
        result = a.analyze(capture(prefix + sequence()), COUNTS, voltage=3.3)
        self.assertEqual(result["unresolved_D0_samples_in_startup_prefix"], 7)
        self.assertEqual(result["negative_current_samples_in_unmeasured_startup"], 10)
        self.assertEqual(result["startup_baseline"]["start_sample_inclusive"], 300_010)
        self.assertAlmostEqual(result["startup_baseline"]["charge_C"], 0.02)

    def test_unknown_d0_after_first_defined_low_is_always_rejected(self):
        for segments in ([(1, 0, 0), (1, 0, None)], [(500_000, 0.01, 0), (1, 0.02, 1), (1, 0.02, None)]):
            with self.assertRaisesRegex(a.CaptureError, "unknown D0 after"):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_negative_baseline_run_intergap_and_tail_rejected(self):
        cases = [
            ([(499_999, 0.01, 0), (1, -1e-6, 0), (1, 0.02, 1)], "selected startup baseline"),
            ([(500_000, 0.01, 0), (1, -1e-6, 1)], "negative current in RUN"),
            ([(500_000, 0.01, 0), (1, 0.02, 1), (1, -1e-6, 0)], "negative current in RUN"),
            (sequence()[:-1] + [(300_000, -1e-6, 0)], "negative current in RUN"),
        ]
        for segments, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(a.CaptureError, reason):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_nonfinite_current_empty_and_invalid_d0_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            for run in (None, 0, 1):
                with self.subTest(value=value, run=run), self.assertRaises(a.CaptureError):
                    a.analyze(capture([(1, value, run)]), COUNTS, voltage=3.3)
        for segments in ([], [(1, 0.01, 32)], [(1, 0.01, True)]):
            with self.assertRaises(a.CaptureError):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_native_d0_endianness_ignores_every_possible_other_channel_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "all_states.ppk2"
            payload = b"".join(struct.pack("<f", 12345.0) + struct.pack(">H", (others << 2) | d0)
                               for d0 in (0, 1, 2) for others in range(1 << 14))
            write_native(path, payload)
            with a.open_native(path) as cap:
                rows = list(cap.samples)
            self.assertEqual([run for _, run in rows], [None] * 16384 + [0] * 16384 + [1] * 16384)
            self.assertTrue(all(abs(current - 0.012345) < 1e-12 for current, _ in rows))

    def test_native_d0_mixed_and_nonfinite_current_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.ppk2"
            for current, pair in ((1.0, 3), (math.nan, 1), (math.inf, 0)):
                write_native(path, struct.pack("<f", current) + struct.pack(">H", pair))
                with self.assertRaises(a.CaptureError):
                    with a.open_native(path) as cap:
                        list(cap.samples)

    def test_native_bad_versions_rates_frames_paths_and_compression_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.ppk2"
            frame = native_bytes([(1, 0.01, 0)])
            cases = [
                (b"12345", None, None, zipfile.ZIP_DEFLATED),
                (b"", None, None, zipfile.ZIP_DEFLATED),
                (frame, {"formatVersion": 3, "metadata": {"samplesPerSecond": 100_000}}, None, zipfile.ZIP_DEFLATED),
                (frame, {"formatVersion": 2, "metadata": {"samplesPerSecond": 10_000}}, None, zipfile.ZIP_DEFLATED),
                (frame, {"formatVersion": True, "metadata": {"samplesPerSecond": 100_000}}, None, zipfile.ZIP_DEFLATED),
                (frame, '{"formatVersion":2,"formatVersion":2,"metadata":{"samplesPerSecond":100000}}', None, zipfile.ZIP_DEFLATED),
                (frame, None, "../escape.txt", zipfile.ZIP_DEFLATED),
                (frame, None, None, zipfile.ZIP_LZMA),
            ]
            for payload, meta, extra, compression in cases:
                write_native(path, payload, meta, extra, compression)
                with self.subTest(meta=meta, extra=extra, compression=compression), self.assertRaises(a.CaptureError):
                    with a.open_native(path) as cap:
                        list(cap.samples)
            self.assertFalse((Path(tmp).parent / "escape.txt").exists())

    def test_native_symlink_and_explicit_sample_limit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.ppk2"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("metadata.json", '{"formatVersion":2,"metadata":{"samplesPerSecond":100000}}')
                entry = zipfile.ZipInfo("session.raw")
                entry.create_system = 3
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, "target")
                archive.writestr("minimap.raw", b"")
            with self.assertRaisesRegex(a.CaptureError, "symlink"):
                with a.open_native(path):
                    pass
            write_native(path, native_bytes([(3, 0.01, 0)]))
            with self.assertRaises(a.CaptureError):
                with a.open_native(path, max_samples=2):
                    pass

    def test_nordic_d0_column_ignores_unselected_noisy_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.csv"
            path.write_text("Timestamp(ms),Current(uA),D0,D1,D2,D0-D7\n0,50000,0,X,nonsense,1XXXXXXX\n0.01,60000,1,-,noisy,garbage\n", encoding="utf-8")
            with a.open_csv(path, sample_rate_hz=100_000, profile="nordic") as cap:
                rows = list(cap.samples)
                self.assertEqual([run for _, run in rows], [0, 1])
                self.assertAlmostEqual(rows[0][0], 0.05)
                self.assertAlmostEqual(rows[1][0], 0.06)

    def test_nordic_bitstring_uses_d0_first_ignoring_remaining_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.csv"
            path.write_text("Timestamp(ms),Current(uA),D0-D7\n0,1000,0XXXXXXX\n0.01,2000,1-?noise\n", encoding="utf-8")
            with a.open_csv(path, sample_rate_hz=100_000, profile="nordic") as cap:
                self.assertEqual(list(cap.samples), [(0.001, 0), (0.002, 1)])

    def test_generic_csv_explicit_columns_units_and_absolute_timebase(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.csv"
            path.write_text("t;I;marker;index\n1000000000000;50;0;4\n1000000000010;60;1;5\n", encoding="utf-8")
            opts = dict(sample_rate_hz=100_000, profile="generic", current_column="I", current_unit="mA", time_column="t", time_unit="us", digital_column="marker", index_column="index", delimiter=";")
            with a.open_csv(path, **opts) as cap:
                self.assertEqual(list(cap.samples), [(0.05, 0), (0.06, 1)])
            del opts["current_unit"]
            with self.assertRaisesRegex(a.CaptureError, "explicit current/time"):
                with a.open_csv(path, **opts):
                    pass

    def test_csv_time_and_index_gaps_duplicates_and_backwards_time_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            for ending in ("0.02,2,1,5", "0,2,1,5", "-0.01,2,1,5", "0.01,2,1,6", "0.010002,2,1,5"):
                path.write_text("Timestamp(ms),Current(uA),D0,index\n0,1,0,4\n" + ending + "\n", encoding="utf-8")
                with self.subTest(ending=ending), self.assertRaises(a.CaptureError):
                    with a.open_csv(path, sample_rate_hz=100_000, profile="nordic", index_column="index") as cap:
                        list(cap.samples)

    def test_csv_headers_fields_nonfinite_current_and_d0_encoding_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            for text in (
                "Timestamp(ms),Current(uA),Current(uA)\n0,1,1\n",
                "Timestamp(ms),Current(uA),D0\n0,nan,0\n",
                "Timestamp(ms),Current(uA)\n0,1\n",
                "Timestamp(ms),Current(uA),D0\n0,1,X\n",
                "Timestamp(ms),Current(uA),D0\n0,1,true\n",
                "Timestamp(ms),Current(uA),D0\n0,1\n",
                "Timestamp(ms),Current(uA),D0-D7\n0,1,1000\n",
            ):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(a.CaptureError):
                    with a.open_csv(path, sample_rate_hz=100_000, profile="nordic") as cap:
                        list(cap.samples)

    def test_manifest_requires_new_single_gpio_identity_pins_and_positive_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiment.json"
            good = manifest()
            path.write_text(json.dumps(good), encoding="utf-8")
            for board in good["boards"]:
                self.assertEqual(a.load_manifest(path, board)["boards"][board]["iterations"], COUNTS)
            bads = []
            for key, value in (("schema_version", 1), ("experiment_id", "energy-profiling-v2-f446"),
                               ("digital_channels", {"RUN": 0, "DONE": 7}), ("digital_channels", {"RUN": False}),
                               ("minimum_capture_tail_ms", 2000), ("sample_rate_Hz", 1000)):
                bad = copy.deepcopy(good); bad[key] = value; bads.append(bad)
            for field, value in (("marker_pin", [18]), ("marker_pin", 19), ("iterations", dict(COUNTS, RLE=True))):
                bad = copy.deepcopy(good); bad["boards"]["esp32"][field] = value; bads.append(bad)
            for bad in bads:
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.subTest(bad=bad), self.assertRaises(a.CaptureError):
                    a.load_manifest(path, "esp32")

    def test_complete_native_cli_outputs_hashes_assumed_voltage_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / "capture.ppk2"; manifest_path = root / "experiment.json"
            write_native(path, native_bytes(sequence(), other_pairs=(1 << 14) - 1))
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            args = [str(path), "--board", "esp32", "--manifest", str(manifest_path), "--output-dir", str(root / "results"), "--voltage", "3.25", "--voltage-uncertainty-v", "0.02"]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(a.main(args), 0)
            report_path = root / "results/capture.analysis.json"
            report = json.loads(report_path.read_text())
            self.assertEqual(report["status"], "structural_protocol_pass")
            self.assertEqual(report["provenance"]["input_sha256"], original_hash)
            self.assertFalse(report["capture"]["packet_loss_absence_proven"])
            self.assertEqual(report["integration"]["voltage_basis"], "caller_supplied_unverified_constant")
            self.assertEqual(report["integration"]["voltage_absolute_uncertainty_V"], 0.02)
            self.assertAlmostEqual(report["runs"][0]["energy_at_assumed_constant_voltage_J"], 3.25 * 0.02 * 101 / 100_000)
            with (root / "results/capture.workloads.csv").open(newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 12)
            # Exercise the overwrite guard directly without re-integrating 2M samples.
            with self.assertRaisesRegex(a.CaptureError, "Refusing to overwrite"):
                a.write_results(report, path, manifest_path, root / "results")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), original_hash)

    def test_cli_rejection_writes_no_derived_files_and_legacy_flags_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / "bad.ppk2"; manifest_path = root / "experiment.json"
            write_native(path, native_bytes([(1, 0.01, 0)]))
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            args = [str(path), "--board", "esp32", "--manifest", str(manifest_path), "--output-dir", str(root / "results")]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(a.main(args), 2)
                with self.assertRaises(SystemExit):
                    a.main(args + ["--digital-columns", "D0,D1,D2,D3,D4,D5,D6,D7"])
            self.assertFalse((root / "results").exists())


if __name__ == "__main__":
    unittest.main()
