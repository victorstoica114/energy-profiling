"""Synthetic protocol/format checks. They are not experimental measurements."""
import csv
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

TOOL = Path(__file__).resolve().parents[1] / "tools" / "analyze_capture.py"
spec = importlib.util.spec_from_file_location("capture_analysis", TOOL)
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)

COUNTS = {name: i + 10 for i, name in enumerate(a.ALGORITHMS, 1)}


def sequence():
    segments = [(3, 0.002, 0), (500_005, 0.01, 32)]
    for algorithm_id in range(1, 13):
        segments.extend([(4, 0.5, algorithm_id << 1),
                         (100 + algorithm_id, 0.02 * algorithm_id, (algorithm_id << 1) | 1)])
        if algorithm_id < 12:
            segments.extend([(2, 0.5, algorithm_id << 1), (100_000, 0.01, 32)])
    segments.append((200_000, 0.008, 128 | 32))
    segments.append((100_000, 0.001, 128))
    return segments


def flatten(segments):
    return itertools.chain.from_iterable(itertools.repeat((current, bits), n) for n, current, bits in segments)


def capture(segments):
    return a.Capture(flatten(segments), 100_000, {"format": "synthetic"})


def native_bytes(segments):
    out = io.BytesIO()
    for n, current, bits in segments:
        if bits is None:
            pairs = 0
        else:
            pairs = sum((2 if (bits >> b) & 1 else 1) << (2 * b) for b in range(8))
        out.write((struct.pack("<f", current * 1e6) + struct.pack(">H", pairs)) * n)
    return out.getvalue()


class CaptureAnalysisTests(unittest.TestCase):
    def test_complete_gates_integrate_only_run_samples_and_last_two_idle_seconds(self):
        result = a.analyze(capture(sequence()), COUNTS, voltage=3.3)
        self.assertEqual(len(result["runs"]), 12)
        self.assertFalse(result["integration"]["baseline_subtracted"])
        self.assertEqual(result["startup_baseline"]["sample_count"], 200_000)
        self.assertEqual(result["startup_baseline"]["start_sample_inclusive"], 300_008)
        self.assertAlmostEqual(result["startup_baseline"]["charge_C"], 0.02)
        for i, row in enumerate(result["runs"], 1):
            self.assertEqual(row["sample_count"], 100 + i)
            self.assertAlmostEqual(row["duration_s"], (100 + i) / 100_000)
            self.assertAlmostEqual(row["charge_C"], 0.02 * i * (100 + i) / 100_000)
            self.assertAlmostEqual(row["energy_per_call_at_assumed_constant_voltage_J"], 3.3 * row["charge_C"] / (10 + i))
        self.assertEqual(sum(x["kind"] == "pause" for x in result["marked_idle_windows"]), 11)
        self.assertEqual(result["done_hold_s"], 3)

    def test_unknown_powerup_inputs_allowed_only_before_first_valid_idle(self):
        segments = [(7, 0, None)] + sequence()
        result = a.analyze(capture(segments), COUNTS, voltage=3.3)
        self.assertEqual(result["unresolved_digital_samples_before_idle_sync"], 7)
        with self.assertRaisesRegex(a.CaptureError, "unresolved digital channel after"):
            a.analyze(capture([(1, 0, 0), (5, 0.01, 32), (1, 0.01, None)]), COUNTS, voltage=3.3)

    def test_invalid_sequences_fail_closed(self):
        baseline = [(1, 0, 0), (500_000, 0.01, 32)]
        cases = [
            ([(1, 0.02, 3)], "truncated start"),
            (baseline + [(1, 0.02, 5)], "expected algorithm ID 1"),
            (baseline + [(1, 0.02, 3), (1, 0.02, 5)], "ID changed"),
            (baseline + [(1, 0.02, 3 | 32)], "overlaps"),
            ([(1, 0.02, 64)], "ERROR marker"),
            ([(1, 0.02, 128)], "premature DONE"),
            (baseline + [(1, 0.02, 3)], "ended while RUN"),
            (baseline + [(1, 0.02, 3), (1, 0.01, 0)], "Incomplete capture"),
            (baseline + [(1, 0.02, 3), (1, 0.01, 0), (1, 0.02, 3)], "expected algorithm ID 2"),
            ([(1, 0, 0), (199_999, 0.01, 32), (1, 0.02, 3)], "startup IDLE_VALID duration"),
            ([(1, 0.01, 34)], "IDLE_VALID requires"),
        ]
        for segments, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(a.CaptureError, message):
                a.analyze(capture(segments), COUNTS, voltage=3.3)

    def test_missing_workloads_done_and_restart_rejected(self):
        segments = sequence()
        with self.assertRaisesRegex(a.CaptureError, "Incomplete capture"):
            a.analyze(capture(segments[:-2] + [(1, 0.01, 0)]), COUNTS, voltage=3.3)
        with self.assertRaisesRegex(a.CaptureError, "persistent DONE"):
            a.analyze(capture(segments[:-2] + [(1, 0.01, 128 | 32)]), COUNTS, voltage=3.3)
        with self.assertRaisesRegex(a.CaptureError, "DONE deasserted"):
            a.analyze(capture(segments + [(1, 0.01, 0)]), COUNTS, voltage=3.3)

    def test_nonfinite_values_never_clipped(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(a.CaptureError):
                a.analyze(capture([(1, value, 0)]), COUNTS, voltage=3.3)

    def test_finite_negative_startup_noise_retained_but_negative_run_rejected(self):
        result = a.analyze(capture([(2, -1e-6, None), (3, -2e-6, 0)] + sequence()), COUNTS, voltage=3.3)
        self.assertEqual(result["negative_current_samples_in_unmeasured_startup"], 5)
        self.assertEqual(result["unresolved_digital_samples_before_idle_sync"], 2)
        self.assertEqual(result["startup_baseline"]["start_sample_inclusive"], 300_013)
        self.assertAlmostEqual(result["startup_baseline"]["charge_C"], 0.02)
        negative_run = sequence()
        negative_run[3] = (101, -1e-6, 3)
        with self.assertRaisesRegex(a.CaptureError, "negative current outside"):
            a.analyze(capture(negative_run), COUNTS, voltage=3.3)
        with self.assertRaisesRegex(a.CaptureError, "negative current outside"):
            a.analyze(capture([(1, 0, 0), (1, -1e-6, 32)]), COUNTS, voltage=3.3)

    def test_short_missing_and_partial_idle_regions_rejected(self):
        short = sequence()
        short[5] = (50_000, 0.01, 32)
        with self.assertRaisesRegex(a.CaptureError, "pause IDLE_VALID duration"):
            a.analyze(capture(short), COUNTS, voltage=3.3)
        missing = sequence()
        missing[5] = (100_000, 0.01, 0)
        with self.assertRaisesRegex(a.CaptureError, "missing 1 s IDLE_VALID"):
            a.analyze(capture(missing), COUNTS, voltage=3.3)
        with self.assertRaisesRegex(a.CaptureError, "ended inside IDLE_VALID"):
            a.analyze(capture(sequence()[:-1]), COUNTS, voltage=3.3)

    def test_done_must_cover_the_entire_final_idle_window(self):
        # Regression: idle with DONE=0 followed by DONE after idle used to pass.
        with self.assertRaisesRegex(a.CaptureError, "requires DONE throughout"):
            a.analyze(capture(sequence()[:-2] + [(200_000, 0.008, 32), (200_000, 0.001, 128)]), COUNTS, voltage=3.3)
        # Even a one-sample stagger is invalid: firmware must update D5/D7
        # atomically, without a capture-dependent inferred grace window.
        with self.assertRaisesRegex(a.CaptureError, "requires DONE throughout"):
            a.analyze(capture(sequence()[:-2] + [(1, 0.008, 32)] + sequence()[-2:]), COUNTS, voltage=3.3)
        with self.assertRaisesRegex(a.CaptureError, "first DONE must coincide"):
            a.analyze(capture(sequence()[:-2] + [(1, 0.001, 128)] + sequence()[-2:]), COUNTS, voltage=3.3)

    def test_native_endianness_and_all_eight_digital_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.ppk2"
            payload = native_bytes([(1, 0.001, i) for i in range(256)])
            self.write_native(p, payload)
            with a.open_native(p) as cap:
                rows = list(cap.samples)
                self.assertEqual([bits for _, bits in rows], list(range(256)))
                self.assertTrue(all(abs(current - 0.001) < 1e-12 for current, _ in rows))

    def test_native_full_capture_agrees_with_gpio_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.ppk2"
            self.write_native(p, native_bytes(sequence()))
            with a.open_native(p) as cap:
                result = a.analyze(cap, COUNTS, voltage=3.3)
            self.assertEqual(len(result["runs"]), 12)
            self.assertAlmostEqual(result["runs"][0]["mean_current_A"], 0.02)

    @staticmethod
    def write_native(path, payload, meta=None, extra=None):
        if meta is None:
            meta = {"formatVersion": 2, "metadata": {"samplesPerSecond": 100_000}}
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("metadata.json", json.dumps(meta))
            z.writestr("session.raw", payload)
            z.writestr("minimap.raw", b"")
            if extra:
                z.writestr(extra, b"untrusted")

    def test_native_unsupported_version_rate_truncation_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.ppk2"
            cases = [
                (b"12345", None, None),
                (native_bytes([(1, 0.01, 0)]), {"formatVersion": 3, "metadata": {"samplesPerSecond": 100_000}}, None),
                (native_bytes([(1, 0.01, 0)]), {"formatVersion": 2, "metadata": {"samplesPerSecond": 10_000}}, None),
                (native_bytes([(1, 0.01, 0)]), None, "../escape.txt"),
            ]
            for payload, meta, extra in cases:
                self.write_native(p, payload, meta, extra)
                with self.subTest(meta=meta, extra=extra), self.assertRaises(a.CaptureError):
                    with a.open_native(p) as cap:
                        list(cap.samples)
            self.assertFalse((Path(tmp).parent / "escape.txt").exists())

    def test_native_mixed_bits_and_known_run_with_unknown_other_bits_rejected(self):
        for states in ([3] + [1] * 7, [2, 0] + [1] * 6):
            with self.assertRaises(a.CaptureError):
                a.decode_states(states, "fixture")

    def test_csv_explicit_units_bit_order_and_timebase(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.csv"
            p.write_text("time,current,bits,index\n0,50,10000000,4\n10,60,01000000,5\n", encoding="utf-8")
            with a.open_csv(p, sample_rate_hz=100_000, profile="generic", time_column="time", time_unit="us", current_column="current", current_unit="mA", digital_bitstring_column="bits", index_column="index") as cap:
                self.assertEqual(list(cap.samples), [(0.05, 1), (0.06, 2)])
            with self.assertRaisesRegex(a.CaptureError, "explicit current/time"):
                with a.open_csv(p, sample_rate_hz=100_000, profile="generic", time_column="time", current_column="current", digital_bitstring_column="bits"):
                    pass

    def test_nordic_csv_and_detectable_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.csv"
            p.write_text("Timestamp(ms),Current(uA),D0,D1,D2,D3,D4,D5,D6,D7\n0,50000,0,0,0,0,0,1,0,0\n0.01,60000,1,1,0,0,0,0,0,0\n", encoding="utf-8")
            with a.open_csv(p, sample_rate_hz=100_000, profile="nordic") as cap:
                rows = list(cap.samples)
                self.assertEqual([x[1] for x in rows], [32, 3])
                self.assertAlmostEqual(rows[0][0], 0.05)
            for ending in ("0.02,2,00000000", "0,2,00000000", "-0.01,2,00000000"):
                p.write_text("Timestamp(ms),Current(uA),D0-D7\n0,1,00000000\n" + ending + "\n", encoding="utf-8")
                with self.subTest(ending=ending), self.assertRaises(a.CaptureError):
                    with a.open_csv(p, sample_rate_hz=100_000, profile="nordic") as cap:
                        list(cap.samples)

    def test_csv_duplicate_header_nonfinite_and_missing_digital(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.csv"
            for text in ("Timestamp(ms),Current(uA),Current(uA)\n0,1,1\n",
                         "Timestamp(ms),Current(uA),D0-D7\n0,nan,00000000\n",
                         "Timestamp(ms),Current(uA)\n0,1\n"):
                p.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(a.CaptureError):
                    with a.open_csv(p, sample_rate_hz=100_000, profile="nordic") as cap:
                        list(cap.samples)

    def test_csv_index_gap_detected_independent_of_contiguous_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.csv"
            p.write_text("t,i,b,n\n0,1,00000000,0\n0.00001,1,00000000,2\n", encoding="utf-8")
            with self.assertRaisesRegex(a.CaptureError, "index gap"):
                with a.open_csv(p, sample_rate_hz=100_000, profile="generic", time_column="t", time_unit="s", current_column="i", current_unit="A", digital_bitstring_column="b", index_column="n") as cap:
                    list(cap.samples)

    def test_manifest_duplicate_json_keys_and_wrong_counts_rejected(self):
        with self.assertRaisesRegex(a.CaptureError, "Duplicate JSON"):
            a.strict_json('{"sample_rate_Hz":100000,"sample_rate_Hz":10000}')
        with self.assertRaises(a.CaptureError):
            a.analyze(capture(sequence()), {**COUNTS, "RLE": 0}, voltage=3.3)

    def test_numeric_overflow_and_contradictory_csv_digital_columns_rejected(self):
        with self.assertRaises(a.CaptureError):
            a.strict_json('{"unsupported_value": 1e999}')
        with self.assertRaisesRegex(a.CaptureError, "overflow"):
            a.analyze(capture([(1, 0, 0), (1, 1e308, 32), (1, 0, 32)]), COUNTS, voltage=3.3)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.csv"
            p.write_text("Timestamp(ms),Current(uA),D0-D7,D0,D1,D2,D3,D4,D5,D6,D7\n0,1,10000000,0,0,0,0,0,0,0,0\n", encoding="utf-8")
            with self.assertRaisesRegex(a.CaptureError, "contradict"):
                with a.open_csv(p, sample_rate_hz=100_000, profile="nordic") as cap:
                    list(cap.samples)

    def test_cli_writes_complete_outputs_and_leaves_input_unchanged(self):
        manifest = {
            "schema_version": 1, "nominal_voltage_V": 3.3, "sample_rate_Hz": 100_000,
            "stable_baseline_seconds": 2.0, "startup_idle_ms": 5000,
            "inter_algorithm_idle_ms": 1000, "post_suite_idle_ms": 2000,
            "digital_channels": {"RUN": 0, "ALG_ID": [1, 2, 3, 4], "IDLE_VALID": 5, "ERROR": 6, "DONE": 7},
            "algorithms": [{"id": i, "name": name} for i, name in enumerate(a.ALGORITHMS, 1)],
            "boards": {"esp32": {"iterations": COUNTS}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, config, results = folder / "fixture.ppk2", folder / "manifest.json", folder / "results"
            self.write_native(source, native_bytes(sequence()))
            config.write_text(json.dumps(manifest), encoding="utf-8")
            before = a.file_hash(source)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                status = a.main([str(source), "--board", "esp32", "--manifest", str(config), "--output-dir", str(results)])
            self.assertEqual(status, 0)
            self.assertEqual(a.file_hash(source), before)
            report = json.loads((results / "fixture.analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(report["integration"]["voltage_basis"], "manifest_nominal_not_measured")
            with (results / "fixture.workloads.csv").open(newline="", encoding="utf-8") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 12)
            with self.assertRaisesRegex(a.CaptureError, "Refusing to overwrite"):
                a.write_results(report, source, config, results)
            bad = folder / "invalid.csv"
            bad.write_text("Timestamp(ms),Current(uA)\n0,1\n", encoding="utf-8")
            rejected_output = folder / "rejected"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                status = a.main([str(bad), "--csv-profile", "nordic", "--board", "esp32", "--manifest", str(config), "--output-dir", str(rejected_output)])
            self.assertEqual(status, 2)
            self.assertFalse(rejected_output.exists())


if __name__ == "__main__":
    unittest.main()
