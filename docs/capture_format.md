# Capture files and offline integration

The analyzer uses Python's standard library. It accepts one complete experiment
sequence per file and produces derived JSON and workload CSV files. It never
changes a capture, repairs marker boundaries, substitutes published algorithm
times, or subtracts an idle current automatically.

## Acquisition contract

Use the official Nordic Power Profiler application at **100,000 samples/s**.
Start recording before powering or releasing reset on the target. Preserve the
native `.ppk2` file and export **All** samples to CSV with timestamps, current,
and all eight digital channels. Record the application/PPK2 firmware versions
and the exact experiment manifest with each measurement campaign.

Lower sampling settings average the data before storage. They cannot recover
native timing when exported later; this analyzer rejects rates other than
100,000 samples/s. Display zoom/minimap data are not used for integration.

The GPIO protocol is fixed:

| Channel | Meaning |
|---|---|
| D0 | RUN: integrate only while HIGH |
| D1, D2, D3, D4 | Algorithm ID, least significant bit first |
| D5 | IDLE_VALID: deliberate controlled idle, algorithm ID must be zero |
| D6 | ERROR: any asserted sample rejects the complete capture |
| D7 | DONE: all 12 kernels and checks completed; stays HIGH |

IDs 1 through 12 are RLE, Delta, LZ77, Huffman, AES-128, SHA-256,
ChaCha20, CRC32, FFT, FIR, IIR, DCT. There must be exactly one contiguous
RUN window for each ID, in that order. The ID must stay constant throughout
RUN. Preparation and validation can take arbitrary time outside RUN and
outside IDLE_VALID; these portions are excluded from both active and idle
metrics.

Require the full **5 s initial IDLE_VALID**, then one **1 s IDLE_VALID pause**
between successive algorithms and a **2 s post-suite IDLE_VALID**. The analyzer
checks each complete marker interval against its nominal duration with a
**1% acceptance tolerance**, independently of algorithm execution times. This
is a protocol consistency threshold, not a calibrated uncertainty estimate.
An initial capture starting inside IDLE_VALID, shortened/split/missing pauses,
or an unfinished final idle region is rejected. Record at least **3 s after
DONE** so the post-suite idle falling edge and its following tail are present;
the analyzer requires at least 2 s of persistent DONE plus the completed
post-suite IDLE_VALID window.

DONE and the final IDLE_VALID rising edge must occur in the same sample;
DONE must remain HIGH throughout that final interval and the remainder of
the recording. Firmware must assert both markers atomically. An idle interval
followed by a delayed DONE, or a stagger of even one retained sample, is
rejected rather than accepted with an inferred timing allowance.

Unresolved digital inputs can occur before valid power/reference levels.
Unknown states are allowed only before the first fully valid IDLE_VALID
sample, are counted, and are excluded from measurement windows. Even there,
a partially unknown sample with a known HIGH RUN, ERROR or DONE is rejected.
Mixed states (`X` / native pair `11`) are always rejected. After the first
valid IDLE_VALID sample, every channel must have a definite LOW/HIGH value.
This rule does not establish the electrical cause of an unknown startup
sample, or prove absence of a completely unobserved reset before synchronization.

Finite signed current values are permitted in the unmeasured startup prefix,
before the first IDLE_VALID synchronization and with no RUN, IDLE_VALID, ERROR
or DONE asserted. Such values can reflect a pre-power-on ADC offset. Negative
startup samples are counted in the JSON, retain their original indices, and
are neither clipped nor included in active/idle integrals. Their sign does
not prove the cause is offset. A negative value in IDLE_VALID, RUN, or anywhere
after synchronization rejects this active-board experiment. Nonfinite current
always rejects the capture, including before power-on.

## Native `.ppk2` support

Supported format: Nordic `.ppk2` **formatVersion 2**. The ZIP must contain
exactly these three root-level files:

* `metadata.json`: JSON object containing `formatVersion: 2` and
  `metadata.samplesPerSecond: 100000`; optional `metadata.startSystemTime`.
* `session.raw`: six bytes per retained sample: a **little-endian float32
  current in microamperes**, followed by a **big-endian uint16** of digital
  states. Each channel uses two bits, D0 at the least-significant pair:
  `01` = LOW, `10` = HIGH, `00` = unknown, `11` = mixed.
* `minimap.raw`: the condensed display representation, never used for metrics.

The unusual mixed byte order is intentional. It was checked against Nordic's
`DataView` reads/writes and tested with all 256 possible digital masks.
Unsupported versions and legacy `.ppk` files are rejected, not guessed.

ZIP members are read without extraction, in bounded chunks. The default limit
is 60 million samples (10 minutes at 100 kS/s), metadata is limited to 1 MiB,
and the minimap to 64 MiB. `--max-samples` changes the explicit recording-size
limit. Unexpected paths/members, encrypted entries, symlinks, unsupported
compression and partial sample frames are rejected. Metadata/session CRC
errors also abort analysis; the unused minimap is not decompressed for a CRC
check.

Nordic implementation examined at commit
`881d596480f60dea045ad6f3643afdc3f9d5a0a6`:
[sample storage and timebase](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/globals.ts),
[digital encoding](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/utils/bitConversion.ts),
[metadata and save format](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/utils/saveFileHandler.ts).

## CSV support: choose the profile explicitly

For the current official Nordic export, pass `--csv-profile nordic`. It selects
these documented columns and units:

* `Timestamp(ms)`, interpreted as milliseconds;
* `Current(uA)`, interpreted as microamperes;
* eight columns `D0` through `D7`, or the official `D0-D7` eight-character
  bitstring if the separate columns are absent. In the bitstring, D0 is the
  **first** character, not the last.

If both digital representations are present, they must agree; the eight
separate columns are used. Nordic CSV output rounds current to 0.001 microampere; the native file
retains its stored float32 values. Nordic's CSV exporter skips NaN current
samples, so such an omission can appear as a timestamp gap and will be
rejected. [Official CSV exporter](https://github.com/NordicSemiconductor/pc-nrfconnect-ppk/blob/881d596480f60dea045ad6f3643afdc3f9d5a0a6/src/actions/exportChartAction.ts).

For any other schema, use `--csv-profile generic` and specify current/time
column names and units. Supported current units: `A`, `mA`, `uA`. Supported
time units: `s`, `ms`, `us`. Supply eight digital column names in D0..D7 order
or one D0-first bitstring column. There is no unit inference from the size or
shape of the values. Digital values use `0`/`1`; `-` denotes unknown and `X`
mixed, subject to the startup policy above. Decimal separator is a dot;
`--delimiter` can change the column separator. Headers must be unique.

Every timestamp interval must match `1/fs` within `max(1 ps, 0.01% of 1/fs)`.
Decimal arithmetic preserves timestamp differences even with large absolute
offsets. `--index-column` optionally checks consecutive integer sample indices.
Missing, repeated, backwards or detectably irregular timestamps/indices reject
the capture. These checks cannot detect data loss if upstream software rebuilt
a uniform index/timebase after losing data. Native `.ppk2` stores an index-based
timebase without a hardware timestamp for every sample; **the analyzer never
claims packet-loss absence is proven**.

## Commands

Run from the project root, using a fresh results directory or unused capture
stem. Existing result files are not overwritten.

```powershell
python tools/analyze_capture.py captures/esp32_001.ppk2 --board esp32 --manifest config/experiment.json --output-dir results/esp32_001

python tools/analyze_capture.py captures/esp32_001.csv --csv-profile nordic --board esp32 --manifest config/experiment.json --output-dir results/esp32_001_csv

python tools/analyze_capture.py captures/custom.csv --csv-profile generic --current-column I --current-unit mA --time-column t --time-unit us --digital-columns D0,D1,D2,D3,D4,D5,D6,D7 --board rp2040 --manifest config/experiment.json --output-dir results/custom
```

Sampling rate comes from the explicit experiment manifest and must agree with
native metadata. Optional `--sample-rate-hz 100000` adds a user cross-check.
`--voltage 3.3` supplies an explicitly assumed constant DUT voltage; without it,
the manifest nominal voltage is used. Neither option certifies that voltage
was measured. Optional `--voltage-uncertainty-v` records an absolute uncertainty
value whose basis must be documented separately; it does not produce a complete
energy uncertainty budget.

## Numerical meaning of the results

For each half-open RUN window `[a,b)` at nominal rate `fs`:

```text
T = (b - a) / fs
Q = sum(I[a:b]) / fs
E = V_assumed_constant * Q
Q_per_call = Q / iterations_from_manifest
E_per_call = E / iterations_from_manifest
```

The falling-edge sample belongs outside RUN. Gate duration includes the
firmware loop and GPIO-boundary overhead; no algorithm execution time from the
MCU or original article is used. Iteration counts come from the board-specific
manifest, not from identifying individual pulses in the current waveform.
The full capture's first-to-last sample span `(N-1)/fs` is reported separately
from its integration support `N/fs`.

The startup baseline is the **last 2 s of the full initial 5 s IDLE_VALID**
region. All completed IDLE_VALID windows are also reported separately; arbitrary
gaps, validation, initialization and post-DONE sleep are not labelled idle by
looking at current levels. Current mean, population standard deviation,
minimum and maximum describe each window, without claiming statistical
independence of adjacent samples or calibrated current stability. Negative
current follows the startup-only policy above; nonfinite values are always
rejected rather than silently clipped.

JSON includes window indices, integral metrics, idle statistics, protocol
checks, voltage basis, limitations, the selected manifest, and SHA-256 hashes
of the input, manifest and analyzer. The workload CSV contains the 12 validated
active-window rows. Rejected captures generate no new analysis files. Multiple
independent cold boots must be recorded and analyzed as separate files; their
between-capture statistics are a separate analysis step.

## Verification

```powershell
python -m unittest discover -s tests -p test_capture_analysis.py -v
```

These synthetic tests cover numerical gate integration, native byte/bit order,
explicit CSV units, missing/partial/malformed markers, errors and restarts,
CSV timestamp/index gaps, unsupported/truncated/unsafe native files, and
nonfinite data. They do not replace an initial physical GPIO/export pilot.
