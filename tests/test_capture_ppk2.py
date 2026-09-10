"""Host-only checks for the PPK2 stream/protocol monitor."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOL = Path(__file__).resolve().parents[1] / "tools" / "capture_ppk2.py"
spec = importlib.util.spec_from_file_location("capture_ppk2", TOOL)
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


def raw_frame(d0, adc=1234, other_logic=0):
    value = (adc & 0xFFFFFF) | (((other_logic << 1) | d0) << 24)
    return struct.pack("<I", value)


def counted_frame(d0, counter, adc=1234):
    return struct.pack("<I", (adc & 0x3FFF) | ((counter & 0x3F) << 18) | (d0 << 24))


class ProtocolMonitorTests(unittest.TestCase):
    def test_split_frames_preserve_every_byte_and_decode_only_d0(self):
        payload = raw_frame(0, other_logic=0x7F) + raw_frame(1) + raw_frame(0)
        pending = b""
        recovered = b""
        states = []
        for chunk in (payload[:1], payload[1:7], payload[7:11], payload[11:]):
            frames, pending = p.complete_frames(pending, chunk)
            recovered += frames
            states.extend(p.d0_states_from_frames(frames))
        self.assertEqual(pending, b"")
        self.assertEqual(recovered, payload)
        self.assertEqual(states, [0, 1, 0])

    def test_exact_twelve_windows_and_tail_complete(self):
        monitor = p.ProtocolMonitor(required_tail_samples=3)
        states = [0] * 5
        for _ in range(12):
            states += [1, 1, 0, 0]
        states.append(0)
        monitor.consume(states)
        self.assertEqual(len(monitor.rising_edges), 12)
        self.assertEqual(len(monitor.falling_edges), 12)
        self.assertGreaterEqual(monitor.trailing_low_samples, 3)
        self.assertTrue(monitor.complete)
        monitor.validate_complete()

    def test_hardware_sample_counter_wrap_and_discontinuity(self):
        monitor = p.ProtocolMonitor(required_tail_samples=1)
        monitor.consume_frames(b"".join(counted_frame(0, value) for value in (62, 63, 0, 1)))
        self.assertEqual(monitor.first_counter, 62)
        self.assertEqual(monitor.previous_counter, 1)
        with self.assertRaisesRegex(p.AcquisitionError, "sample-counter discontinuity"):
            monitor.consume_frames(counted_frame(0, 3))

    def test_first_high_extra_pulse_incomplete_and_short_tail_are_rejected(self):
        with self.assertRaisesRegex(p.AcquisitionError, "First streamed"):
            p.ProtocolMonitor(1).consume([1])

        extra = p.ProtocolMonitor(1)
        states = [0]
        for _ in range(13):
            states += [1, 0]
        with self.assertRaisesRegex(p.AcquisitionError, "13th"):
            extra.consume(states)

        incomplete = p.ProtocolMonitor(1)
        incomplete.consume([0, 1])
        with self.assertRaisesRegex(p.AcquisitionError, "ended while RUN was HIGH"):
            incomplete.validate_complete()

        short = p.ProtocolMonitor(3)
        states = [0]
        for _ in range(12):
            states += [1, 0]
        short.consume(states)
        self.assertFalse(short.complete)
        with self.assertRaisesRegex(p.AcquisitionError, "trailing LOW"):
            short.validate_complete()

    def test_device_descriptors_and_selection(self):
        devices = p.normalize_devices(["COM4", ("COM8", "ABC123")])
        self.assertEqual(devices, [("COM4", ""), ("COM8", "ABC123")])
        self.assertEqual(p.select_device(devices, "com8"), ("COM8", "ABC123"))
        with self.assertRaisesRegex(p.AcquisitionError, "exactly one"):
            p.select_device(devices, None)

    def test_released_api_port_string_is_enriched_with_usb_serial(self):
        class Api:
            @staticmethod
            def list_devices():
                return ["COM7"]

        class Port:
            device = "COM7"
            serial_number = "F7839E12B2AE"

        with (
            patch.object(p, "import_ppk2_api", return_value=Api),
            patch("serial.tools.list_ports.comports", return_value=[Port()]),
        ):
            self.assertEqual(p.list_ppk2_devices(), [("COM7", "F7839E12B2AE")])

    def test_export_csv_keeps_index_time_current_and_d0(self):
        class FakeApi:
            def __init__(self):
                self.remainder = {}
                self.rolling_avg = self.rolling_avg4 = self.prev_range = None
                self.consecutive_range_samples = self.after_spike = 0

            def get_samples(self, block):
                frames = [block[i:i + 4] for i in range(0, len(block), 4)]
                return [1000.25 + i for i in range(len(frames))], [frame[3] for frame in frames]

        session = object.__new__(p.Ppk2SourceSession)
        session.api = FakeApi()
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "x.raw4"
            output = Path(tmp) / "x.csv"
            raw.write_bytes(raw_frame(0) + raw_frame(1))
            self.assertEqual(session.export_csv(raw, output), 2)
            self.assertEqual(
                output.read_text(encoding="utf-8").splitlines(),
                [
                    "Sample,Timestamp(us),Current(uA),D0",
                    "0,0,1000.25,0",
                    "1,10,1001.25,1",
                ],
            )

    def test_no_first_edge_timeout_powers_dut_off_and_retains_raw(self):
        class Serial:
            in_waiting = 0
            is_open = True

            def flush(self):
                pass

        class Api:
            def __init__(self):
                self.ser = Serial()
                self.measuring = False
                self.toggles = []
                self.remainder = {}
                self.rolling_avg = self.rolling_avg4 = self.prev_range = None
                self.consecutive_range_samples = self.after_spike = 0
                self.counter = 0

            def get_data(self):
                if not self.measuring:
                    return b""
                block = b"".join(counted_frame(0, (self.counter + offset) & 63) for offset in range(100))
                self.counter = (self.counter + 100) & 63
                return block

            def start_measuring(self):
                self.measuring = True

            def stop_measuring(self):
                self.measuring = False

            def toggle_DUT_power(self, state):
                self.toggles.append(state)

        session = object.__new__(p.Ppk2SourceSession)
        session.api = Api()
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "partial.raw4"
            with self.assertRaisesRegex(p.AcquisitionError, "No D0 rising edge"):
                session.capture_raw(
                    raw,
                    pre_power_s=0.00001,
                    tail_s=3.0,
                    max_first_edge_s=0.002,
                    max_capture_s=1.0,
                    max_samples=1_000_000,
                    max_sample_time_error_percent=100.0,
                )
            self.assertGreater(raw.stat().st_size, 0)
            self.assertEqual(session.api.toggles, ["ON", "OFF"])


if __name__ == "__main__":
    unittest.main()
