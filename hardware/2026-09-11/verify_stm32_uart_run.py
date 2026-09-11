"""Verify a complete STM32 diagnostic sequence from the raw UART monitor."""
import argparse
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--raw', type=Path, required=True)
parser.add_argument('--firmware', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
config_path = root.parents[1] / 'config/experiment.json'
config = json.loads(config_path.read_text())
expected = [('BOOT', 0, 0)]
for item in config['algorithms']:
    count = config['boards']['stm32']['iterations'][item['name']]
    expected.extend([('START', item['id'], count), ('PASS', item['id'], count)])
expected.append(('DONE', 0, 0))
event_pattern = re.compile(r'^BENCH event=(BOOT|START|PASS|DONE|ERROR) id=(\d+) calls=(\d+) digest=([0-9a-f]{8})$')
raw = args.raw.read_bytes()
observed_config = None
events = []
complete = None
for raw_line in raw.splitlines():
    line = raw_line.decode('ascii', errors='replace')
    if line.startswith('CONFIG '):
        observed_config = dict(re.findall(r'(\w+)=([^ ]+)', line))
        events = []
        complete = None
    if not line.startswith('BENCH event='):
        continue
    match = event_pattern.fullmatch(line)
    if match is None:
        raise SystemExit('Malformed BENCH diagnostic event')
    event, identifier, count, digest = match.groups()
    found = (event, int(identifier), int(count))
    if len(events) >= len(expected) or found != expected[len(events)]:
        raise SystemExit(f'Unexpected event {found} at position {len(events)}')
    if event in ('BOOT', 'START', 'DONE') and digest != '00000000':
        raise SystemExit('Nonzero control-event digest')
    events.append({'event': event, 'id': int(identifier), 'calls': int(count), 'digest': digest})
    if event == 'DONE':
        complete = list(events)
if complete is None or observed_config is None:
    raise SystemExit(f'Incomplete diagnostic run: {len(events)}/{len(expected)} expected events')
for key, value in {'board': 'NUCLEO-F446RE', 'diagnostics': '1', 'cpu_hz': '180000000',
                   'pclk1_hz': '45000000', 'pclk2_hz': '90000000', 'flash_kib': '512',
                   'tim2_psc': '8999', 'transport': 'USART3_PC10'}.items():
    if observed_config.get(key) != value:
        raise SystemExit(f'Configuration mismatch for {key}: {observed_config.get(key)}')
for key, mask, value in [('idcode', 0xfff, 0x421), ('cpacr', 0xf00000, 0xf00000),
                         ('flash_acr', 0x70f, 0x705), ('pwr_cr', 0x3c000, 0x3c000),
                         ('pwr_csr', 0x34000, 0x34000), ('pllcfgr', 0xffffffff, 0x25005a10)]:
    if int(observed_config[key], 16) & mask != value:
        raise SystemExit('Register configuration mismatch: ' + key)
if args.output.exists():
    raise SystemExit('Output already exists; use a fresh evidence filename')
sha = lambda data: hashlib.sha256(data).hexdigest()
result = {'board': 'stm32', 'status': 'passed', 'validated_algorithms': 12,
          'scope': 'separate USART3/PC10 diagnostic image; no energy or external clock calibration',
          'configuration': observed_config, 'events': complete,
          'raw_uart_sha256': sha(raw), 'firmware_sha256': sha(args.firmware.read_bytes()),
          'experiment_sha256': sha(config_path.read_bytes()),
          'flash_readback_attestation': False, 'ppk2_capture_validated': False}
args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print('PASS: configuration, all twelve workload counts/PASS events, and final DONE verified.')
