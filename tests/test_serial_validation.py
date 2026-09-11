"""Serial protocol regressions using a fake port and fake time; no hardware.

Run from the project root:
    python -B -m unittest discover -s tests -p test_serial_validation.py -v
"""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "serial_validation_under_test", PROJECT / "tools" / "serial_validation.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

NAMES = ("RLE", "Delta", "LZ77", "Huffman", "AES-128", "SHA-256",
         "ChaCha20", "CRC32", "FFT", "FIR", "IIR", "DCT")
# Original STM32 repeat counts, independent of the parser implementation.
COUNTS = (3000, 3000, 200, 100, 100, 500, 3000, 3000, 20, 300, 50, 1)


def complete_events(counts=COUNTS):
    lines = ["BENCH event=BOOT id=0 calls=0 digest=00000000"]
    for identifier, count in enumerate(counts, 1):
        lines.extend([
            f"BENCH event=START id={identifier} calls={count} digest=00000000",
            f"BENCH event=PASS id={identifier} calls={count} digest={0xabcd0000+identifier:08x}",
        ])
    lines.append("BENCH event=DONE id=0 calls=0 digest=00000000")
    return lines


def wire(lines):
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeSerial:
    def __init__(self, chunks, clock):
        self.chunks = list(chunks)
        self.clock = clock
        self.reads = 0
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, count):
        self.reads += 1
        # A bounded read consumes fake time only. Empty chunks model a timeout
        # between packets, allowing the post-DONE drain to be exercised.
        self.clock.sleep(0.2)
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) > count:
            self.chunks.insert(0, chunk[count:])
        return chunk[:count]

    def close(self):
        self.closed = True


class SerialValidationTests(unittest.TestCase):
    def collect(self, chunks, *, clock_profile='max_clock', board='stm32'):
        clock = FakeClock()
        port = FakeSerial(chunks, clock)
        with tempfile.TemporaryDirectory(prefix="energy-serial-test-") as directory:
            root = Path(directory)
            (root / "config").mkdir()
            config_filename = 'experiment.common160.json' if clock_profile == 'common160' else 'experiment.json'
            config = json.loads((PROJECT / 'config' / config_filename).read_text(encoding='utf-8'))
            config_bytes = json.dumps(config, sort_keys=True).encode("utf-8")
            (root / "config" / config_filename).write_bytes(config_bytes)
            firmware_bytes = b"mock firmware for protocol tests, never flashed"
            firmware = root / "firmware.bin"
            firmware.write_bytes(firmware_bytes)
            prefix = root / "capture"
            argv = [str(PROJECT / "tools" / "serial_validation.py"),
                    "--board", board, "--port", "MOCK_PORT",
                    "--firmware", str(firmware), "--output", str(prefix),
                    "--timeout", "5"]
            if clock_profile != 'max_clock':
                argv += ['--clock-profile', clock_profile]
            with mock.patch.object(VALIDATOR, "ROOT", root), \
                    mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(VALIDATOR.serial, "Serial", return_value=port) as serial_open, \
                    mock.patch.object(VALIDATOR.time, "monotonic", clock.monotonic), \
                    mock.patch.object(VALIDATOR.time, "sleep", clock.sleep), \
                    redirect_stdout(io.StringIO()):
                code = VALIDATOR.main()
            serial_open.assert_called_once_with("MOCK_PORT", 115200, timeout=0.2)
            evidence = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
            log_bytes = prefix.with_suffix(".log").read_bytes()
            self.assertTrue(port.closed)
            self.assertEqual(evidence["firmware_sha256"], hashlib.sha256(firmware_bytes).hexdigest())
            self.assertEqual(evidence["experiment_sha256"], hashlib.sha256(config_bytes).hexdigest())
            self.assertEqual(evidence['experiment_id'], config['experiment_id'])
            self.assertEqual(evidence['clock_profile'], clock_profile)
            self.assertEqual(evidence['target_cpu_hz'], config['boards'][board]['target_cpu_hz'])
            self.assertEqual(evidence["log_sha256"], hashlib.sha256(log_bytes).hexdigest())
            return code, evidence, log_bytes.decode("utf-8"), clock.now, port.reads

    def assert_rejected(self, chunks, message):
        code, evidence, log, _, _ = self.collect(chunks)
        self.assertEqual(code, 1)
        self.assertEqual(evidence["status"], "failed")
        self.assertNotIn("validated_algorithms", evidence)
        self.assertIn(message, evidence["error"])
        return evidence, log

    def test_complete_sequence_records_provenance_and_drains(self):
        config_lines = ["CONFIG board=stm32 cpu_hz=180000000",
                        "BENCH CONFIG uart=115200 diagnostics=1"]
        code, evidence, log, elapsed, reads = self.collect([wire(config_lines + complete_events())])
        self.assertEqual(code, 0)
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["validated_algorithms"], 12)
        self.assertEqual(len(evidence["events"]), 26)
        self.assertEqual(evidence["configuration_lines"], config_lines)
        self.assertEqual(evidence["events"][0]["event"], "BOOT")
        self.assertEqual(evidence["events"][-1], {
            "event": "DONE", "id": 0, "calls": 0, "digest": "00000000"})
        for identifier, count in enumerate(COUNTS, 1):
            start, passed = evidence["events"][2*identifier-1:2*identifier+1]
            self.assertEqual((start["event"], start["id"], start["calls"]), ("START", identifier, count))
            self.assertEqual((passed["event"], passed["id"], passed["calls"]), ("PASS", identifier, count))
        self.assertIn("no time, current or energy measurement", evidence["scope"])
        self.assertIn("BENCH event=DONE", log)
        self.assertGreaterEqual(elapsed, 0.7)  # first read 0.2 + drain at least 0.5
        self.assertGreater(reads, 1)

    def test_max_clock_keeps_legacy_stream_without_config_supported(self):
        code, evidence, _, _, _ = self.collect([wire(complete_events())])
        self.assertEqual(code, 0)
        self.assertEqual(evidence['clock_profile'], 'max_clock')
        self.assertFalse(evidence['configuration_verified'])

    def test_common160_checks_runtime_configuration_and_records_selected_identity(self):
        line = 'CONFIG board=NUCLEO-F446RE diagnostics=1 cpu_hz=160000000 clock_profile=common160'
        code, evidence, _, _, _ = self.collect([wire([line] + complete_events())], clock_profile='common160')
        self.assertEqual(code, 0)
        self.assertEqual(evidence['validated_algorithms'], 12)
        self.assertEqual(evidence['experiment_id'], 'energy-profiling-v5-common160')
        self.assertTrue(evidence['configuration_verified'])
        self.assertEqual(evidence['reported_configuration']['cpu_hz'], '160000000')
        self.assertTrue(evidence['experiment_manifest_path'].endswith('experiment.common160.json'))

    def test_common160_esp32_config_without_profile_field_is_supported(self):
        counts = (3000, 3000, 200, 200, 1000, 1000, 3000, 3000, 50, 300, 50, 1)
        line = 'BENCH CONFIG board=esp32 diagnostics=1 cpu_hz=160000000 apb_hz=80000000 check=1'
        code, evidence, _, _, _ = self.collect([wire([line] + complete_events(counts))],
                                              clock_profile='common160', board='esp32')
        self.assertEqual(code, 0)
        self.assertTrue(evidence['configuration_verified'])
        self.assertEqual(evidence['clock_profile'], 'common160')

    def test_common160_rejects_missing_partial_wrong_or_ambiguous_configuration(self):
        invalid = (
            ([], 'requires CONFIG'),
            (['CONFIG diagnostics=1'], 'requires CONFIG'),
            (['CONFIG cpu_hz=160000000'], 'requires CONFIG'),
            (['CONFIG diagnostics=1 cpu_hz=180000000 clock_profile=common160'], 'cpu_hz must be 160000000'),
            (['CONFIG diagnostics=1 cpu_hz=160000000 clock_profile=max_clock'], 'clock_profile does not match'),
            (['CONFIG diagnostics=0 cpu_hz=160000000'], 'diagnostics=1'),
            (['CONFIG diagnostics=1 cpu_hz=160000000 check=0'], 'failed platform check'),
            (['CONFIG diagnostics=1 cpu_hz=160000000 cpu_hz=180000000'], 'duplicate CONFIG field'),
            (['CONFIG board=esp32 diagnostics=1 cpu_hz=160000000'], 'board does not match'),
        )
        for lines, message in invalid:
            with self.subTest(lines=lines):
                code, evidence, _, _, _ = self.collect([wire(lines + complete_events())], clock_profile='common160')
                self.assertEqual(code, 1)
                self.assertNotIn('validated_algorithms', evidence)
                self.assertIn(message, evidence['error'])

    def test_default_max_clock_rejects_a_common160_runtime_configuration(self):
        line = 'CONFIG diagnostics=1 cpu_hz=160000000 clock_profile=common160'
        self.assert_rejected([wire([line] + complete_events())], 'clock_profile does not match')

    def test_config_restart_after_done_cannot_be_accepted_during_drain(self):
        line = 'CONFIG board=stm32 diagnostics=1 cpu_hz=180000000'
        self.assert_rejected([wire(complete_events()), wire([line])], 'Unexpected CONFIG after DONE')

    def test_wrong_manifest_profile_schema_or_clock_is_rejected_before_serial_open(self):
        max_config = json.loads((PROJECT / 'config/experiment.json').read_text(encoding='utf-8'))
        common_config = json.loads((PROJECT / 'config/experiment.common160.json').read_text(encoding='utf-8'))
        wrong_clock = json.loads(json.dumps(common_config))
        wrong_clock['boards']['stm32']['target_cpu_hz'] = 180000000
        wrong_schema = json.loads(json.dumps(common_config))
        wrong_schema['schema_version'] = 1
        cases = (('common160', max_config), ('max_clock', common_config),
                 ('common160', wrong_clock), ('common160', wrong_schema))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'override.json'
            for profile, config in cases:
                manifest.write_text(json.dumps(config), encoding='utf-8')
                argv = ['--board', 'stm32', '--port', 'MOCK_PORT', '--clock-profile', profile,
                        '--manifest', str(manifest), '--firmware', str(root / 'unread.bin'),
                        '--output', str(root / 'no_evidence')]
                with (self.subTest(profile=profile, experiment=config['experiment_id']),
                      mock.patch.object(VALIDATOR.serial, 'Serial') as serial_open,
                      redirect_stderr(io.StringIO())):
                    with self.assertRaises(SystemExit) as exc:
                        VALIDATOR.main(argv)
                    self.assertEqual(exc.exception.code, 2)
                    serial_open.assert_not_called()
                self.assertFalse((root / 'no_evidence.json').exists())
                self.assertFalse((root / 'no_evidence.log').exists())

    def test_boot_start_done_require_their_fixed_zero_fields(self):
        changes = [
            (0, "calls=0", "calls=1"),
            (0, "digest=00000000", "digest=00000001"),
            (1, "digest=00000000", "digest=00000001"),
            (25, "calls=0", "calls=999"),
            (25, "digest=00000000", "digest=ffffffff"),
        ]
        for index, old, new in changes:
            with self.subTest(index=index, invalid=new):
                lines = complete_events()
                lines[index] = lines[index].replace(old, new)
                self.assert_rejected([wire(lines)], "Unexpected event")

    def test_start_and_pass_require_exact_repeat_counts(self):
        for index in (1, 2):
            with self.subTest(event=complete_events()[index]):
                lines = complete_events()
                lines[index] = lines[index].replace("calls=3000", "calls=2999")
                self.assert_rejected([wire(lines)], "Unexpected event")

    def test_error_after_done_is_logged_and_rejected(self):
        error = "BENCH event=ERROR id=12 calls=1 digest=00000008"
        cases = {
            "same_read": [wire(complete_events() + [error])],
            "during_drain": [wire(complete_events()), b"", wire([error])],
        }
        for name, chunks in cases.items():
            with self.subTest(arrival=name):
                evidence, log = self.assert_rejected(chunks, "Firmware ERROR")
                self.assertEqual(evidence["events"][-1]["event"], "ERROR")
                self.assertIn(error, log)

    def test_unterminated_trailing_event_is_not_a_pass(self):
        partial = b"BENCH event=ERROR id=12 calls=1 digest=00000008"
        _, log = self.assert_rejected([wire(complete_events()) + partial],
                                      "Unterminated trailing serial data after DONE")
        self.assertIn("UNTERMINATED\t" + partial.decode("ascii"), log)


if __name__ == "__main__":
    unittest.main()
