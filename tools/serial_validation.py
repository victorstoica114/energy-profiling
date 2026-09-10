#!/usr/bin/env python3
"""Collect functional diagnostic evidence. Host timestamps are NOT benchmark timing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]
EVENT = re.compile(r"^BENCH event=(BOOT|START|PASS|DONE|ERROR) id=(\d+) calls=(\d+) digest=([0-9a-f]{8})$")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', choices=('esp32', 'rp2040', 'stm32'), required=True)
    parser.add_argument('--port', required=True, help='COMn, or auto for Pico USB diagnostics')
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New output file prefix')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--reset', choices=('none', 'esp32'), default='none')
    args = parser.parse_args()
    if args.reset == 'esp32' and args.board != 'esp32':
        parser.error('ESP32 reset sequence is only valid for the ESP32 target')
    if args.port == 'auto' and args.board != 'rp2040':
        parser.error('Automatic selection is limited to the Pico diagnostic USB identity')
    config_path = ROOT / 'config/experiment.json'
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    firmware_sha = hashlib.sha256(args.firmware.read_bytes()).hexdigest()
    expected = [config['boards'][args.board]['iterations'][a['name']] for a in config['algorithms']]
    log_path = args.output.with_suffix('.log')
    result_path = args.output.with_suffix('.json')
    if log_path.exists() or result_path.exists():
        parser.error('Output already exists; choose a fresh prefix')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    evidence = {
        'board': args.board, 'status': 'incomplete',
        'scope': 'diagnostic functional execution; no time, current or energy measurement',
        'firmware_path': str(args.firmware), 'firmware_sha256': firmware_sha,
        'experiment_sha256': hashlib.sha256(config_bytes).hexdigest(),
        'events': [], 'configuration_lines': [], 'error': None,
    }
    connection = None
    state, next_id = 'boot', 1
    completion_deadline = None
    pending = b''
    try:
        with log_path.open('x', encoding='utf-8', newline='\n') as log:
            while time.monotonic() - start < args.timeout:
                if completion_deadline is not None and time.monotonic() >= completion_deadline:
                    if pending.strip():
                        log.write('UNTERMINATED\t' + pending.decode('utf-8', errors='replace') + '\n')
                        raise RuntimeError('Unterminated trailing serial data after DONE')
                    evidence['status'] = 'passed'
                    evidence['validated_algorithms'] = 12
                    return 0
                if connection is None:
                    port = args.port
                    if port == 'auto':
                        candidates = [p for p in list_ports.comports() if p.vid == 0x2e8a and p.pid == 0x000a]
                        if len(candidates) > 1:
                            raise RuntimeError('Multiple Pico diagnostic ports; specify the exact COM port')
                        if not candidates:
                            time.sleep(0.2)
                            continue
                        port = candidates[0].device
                    try:
                        connection = serial.Serial(port, 115200, timeout=0.2)
                    except serial.SerialException:
                        time.sleep(0.2)
                        continue
                    evidence['port'] = port
                    print('Connected ' + port, flush=True)
                    if args.reset == 'esp32':
                        connection.reset_input_buffer()
                        connection.dtr = False
                        connection.rts = True
                        time.sleep(0.1)
                        connection.rts = False
                pending += connection.read(max(1, connection.in_waiting))
                if len(pending) > 65536:
                    raise RuntimeError('Unterminated serial line exceeds limit')
                while b'\n' in pending:
                    raw_line, pending = pending.split(b'\n', 1)
                    line = raw_line.decode('utf-8', errors='replace').rstrip('\r')
                    log.write(f'{time.monotonic()-start:.6f}\t{line}\n')
                    log.flush()
                    print(line, flush=True)
                    if line.startswith('CONFIG') or line.startswith('BENCH CONFIG'):
                        evidence['configuration_lines'].append(line)
                    match = EVENT.fullmatch(line)
                    if not match:
                        if line.startswith('BENCH event='):
                            raise RuntimeError('Malformed diagnostic event: ' + line)
                        continue
                    event, identifier, count, digest = match.groups()
                    identifier, count = int(identifier), int(count)
                    evidence['events'].append(dict(event=event, id=identifier, calls=count, digest=digest))
                    if event == 'ERROR':
                        raise RuntimeError(f'Firmware ERROR at algorithm {identifier}, reason={int(digest,16)}')
                    if state == 'boot' and event == 'BOOT' and identifier == 0 and count == 0 and digest == '00000000':
                        state = 'start'
                    elif state == 'start' and event == 'START' and identifier == next_id and count == expected[next_id-1] and digest == '00000000':
                        state = 'pass'
                    elif state == 'pass' and event == 'PASS' and identifier == next_id and count == expected[next_id-1]:
                        next_id += 1
                        state = 'done' if next_id == 13 else 'start'
                    elif state == 'done' and event == 'DONE' and identifier == 0 and count == 0 and digest == '00000000':
                        # Process the rest of this read, then drain briefly: a trailing
                        # ERROR/reset/repeated event must not become a false pass.
                        state = 'complete'
                        completion_deadline = time.monotonic() + 0.5
                    else:
                        raise RuntimeError(f'Unexpected event {event}/{identifier}/{count} in state {state}/{next_id}')
            raise RuntimeError('Timeout before a complete BOOT + 12 START/PASS + DONE sequence')
    except (RuntimeError, serial.SerialException, OSError) as exc:
        evidence['status'] = 'failed'
        evidence['error'] = str(exc)
        print('Validation failed: ' + str(exc), flush=True)
        return 1
    finally:
        if connection:
            connection.close()
        if log_path.exists():
            evidence['log_sha256'] = hashlib.sha256(log_path.read_bytes()).hexdigest()
        with result_path.open('x', encoding='utf-8') as result:
            json.dump(evidence, result, indent=2)
            result.write('\n')


if __name__ == '__main__':
    raise SystemExit(main())
