"""Serial protocol regressions using a fake port and fake time; no hardware.

Run from the project root:
    python -B -m unittest discover -s tests -p test_serial_validation.py -v
"""
from contextlib import redirect_stdout
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


def complete_events():
    lines = ["BENCH event=BOOT id=0 calls=0 digest=00000000"]
    for identifier, count in enumerate(COUNTS, 1):
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
    def collect(self, chunks):
        clock = FakeClock()
        port = FakeSerial(chunks, clock)
        with tempfile.TemporaryDirectory(prefix="energy-serial-test-") as directory:
            root = Path(directory)
            (root / "config").mkdir()
            config = {
                "schema_version": 1,
                "algorithms": [{"id": i, "name": name}
                               for i, name in enumerate(NAMES, 1)],
                "boards": {"stm32": {"iterations": dict(zip(NAMES, COUNTS))}},
            }
            config_bytes = json.dumps(config, sort_keys=True).encode("utf-8")
            (root / "config" / "experiment.json").write_bytes(config_bytes)
            firmware_bytes = b"mock firmware for protocol tests, never flashed"
            firmware = root / "firmware.bin"
            firmware.write_bytes(firmware_bytes)
            prefix = root / "capture"
            argv = [str(PROJECT / "tools" / "serial_validation.py"),
                    "--board", "stm32", "--port", "MOCK_PORT",
                    "--firmware", str(firmware), "--output", str(prefix),
                    "--timeout", "5"]
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
