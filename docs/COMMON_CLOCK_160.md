# Common 160 MHz comparison

Release **v1.2.0** adds `energy-profiling-v5-common160`, a separate experiment in which all three CPUs run at a nominal **160 MHz**. Select it explicitly with `BENCH_CLOCK_PROFILE=common160` for compilation and `--clock-profile common160` for acquisition. The default remains `max_clock`, experiment `energy-profiling-v4-max-clock`; its released images and completed functional validation are retained.

**The common160 acquisition campaign is complete:** thirty accepted v5 captures,
ten per board, acquired on 11 September 2026. The [completed selection](../ROW_Data/common160/source_campaign.json)
and [dataset guide](../ROW_Data/common160/README.md) preserve the original
capture/profile/image hashes from source commit
`f19c3b4c96e85d6348c9966bc012bbdbbeac1112`. Maximum-clock and common160 data
remain separate.

## Why 160 MHz

The classic ESP32 supports the standard CPU settings 80, 160 and 240 MHz in the pinned ESP-IDF 5.5.4. STM32F446 is rated up to 180 MHz. Consequently, **160 MHz is the highest common nominal setting supported by the three devices and their selected SDKs**; 180 MHz is not a standard ESP32 setting. RP2040 can synthesize 160 MHz from the 12 MHz reference using its PLL. Sources: [Espressif clock settings](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32/api-reference/system/power_management.html), [STM32F446 datasheet](https://www.st.com/resource/en/datasheet/stm32f446re.pdf), [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf).

The common frequency controls the nominal CPU rate. It does not equalize instruction sets, cycles per operation, floating-point hardware, buses, memory, software runtimes, internal voltages or oscillator accuracy. The experiment compares the complete documented operating configurations; it cannot isolate frequency as the only cause of a change from the maximum-clock results.

## Exact operating configuration

| Item | ESP32-D0WD-V3 | Marble Pico / RP2040 | NUCLEO-F446RE |
|---|---|---|---|
| CPU | 160 MHz, one application core | 160 MHz, core 1 parked | 160 MHz nominal HSI-derived clock |
| CPU PLL | SDK 320 MHz / 2 | 12 MHz reference, VCO 1440 MHz, postdividers 3 and 3 | HSI16 / 16 x 320 / 2 |
| Core supply policy | SDK normal 160 MHz bias, nominal 1.10 V with Flash at 40 MHz | Internal VREG selection 1.15 V | Scale 1, OverDrive disabled |
| Bus / peripheral clocks | APB 80 MHz | `clk_peri` 48 MHz | APB1 40 MHz; APB2 80 MHz |
| Flash | DIO 40 MHz | QSPI divider 4, resulting in 40 MHz | Five wait states, prefetch and instruction/data caches enabled |
| Floating point | Hardware single precision | Software floating point | CP10/CP11 enabled, hard-float single precision |
| RUN to PPK2 D0 | GPIO18 | GP2 | PC0 |

The voltage entries are configured internal regulator/bias settings, not measured internal voltages. PPK2 supplies the measured domain at nominal 3.3 V. ESP32/Pico board LDOs are removed; the operator confirmed that the Nucleo LDO remains fitted, with JP6 open and PPK2 feeding MCU VDD. This correction is recorded separately from original metadata. The MCU's internal regulator remains present.

ESP-IDF chooses a different CPU PLL and digital bias at 160 MHz than at 240 MHz. The pinned [ESP32 clock implementation](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_hw_support/port/esp32/rtc_clk.c) and [bias definitions](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_hw_support/port/esp32/include/soc/rtc.h) are authoritative. Dynamic frequency scaling and radios remain disabled/uninitialized as specified by the measurement profile.

RP2040 retains VREG 1.15 V and Flash divider four. Its Flash frequency consequently changes from 50 MHz in the 200 MHz experiment to 40 MHz here, and the SDK selects a different system PLL arrangement. The peripheral clock remains 48 MHz. This is not a constant-memory-clock sweep.

STM32F446 Scale 1 supports 160 MHz without OverDrive; OverDrive remains enabled in the separate 180 MHz profile. Five Flash wait states are required above 150 MHz at the selected supply range. TIM2 receives 80 MHz and uses prescaler 7999, preserving the 10 kHz control-pause clock. The unused PLL Q/R outputs do not supply a USB interface. See the [STM32F446 reference manual, Flash latency and RCC/PWR sections](https://www.st.com/st-web-ui/static/active/en/resource/technical/document/reference_manual/DM00135183.pdf).

## Workload and timing policy

The twelve kernels, immutable 2048-byte inputs, board-specific call counts, validation rules, memory policy, compiler versions and flags are unchanged. There is no frequency-based rescaling of the number of calls. Normalize each measured batch by that board/workload's declared call count before comparing or averaging results. All clocks are selected before the first measured batch and remain fixed during RUN.

The single-GPIO sequence is unchanged: initialization and preparation; five seconds of active control idle; twelve ordered HIGH batches separated by validation/preparation and one-second active pauses; final LOW tail. No serial diagnostics or MCU duration/energy reports are present in measurement images. PPK2 samples determine RUN duration and energy. The input patterns and compiler policies are described in the [firmware specification](../firmware/README.md).

## Configuration, images and provenance

| Purpose | Maximum clock | Common 160 MHz |
|---|---|---|
| Experiment | `energy-profiling-v4-max-clock` | `energy-profiling-v5-common160` |
| Configuration | `config/experiment.json` | `config/experiment.common160.json` |
| Image manifest | `CURRENT_FIRMWARE.json` | `profiles/common160/CURRENT_FIRMWARE.json` |
| Measurement archive under each target | `build_verified/max_clock_measurement` | `build_verified/common160_measurement` |
| Build selector | `-DBENCH_CLOCK_PROFILE=max_clock` | `-DBENCH_CLOCK_PROFILE=common160` |
| Acquisition selector | `--clock-profile max_clock` (default) | `--clock-profile common160` |
| Default output | `captures_max_clock/` | `captures_common160/` |

Every native build directory is bound to one clock profile. Reconfiguring it with the other profile fails; use a fresh directory. ESP32 also uses a build-local `sdkconfig`, so the checked-in 240 MHz configuration cannot silently override the 160 MHz defaults. Compile-time and runtime clock checks must agree with the selected profile.

The v1.1.0 maximum-clock binaries remain available with their original hashes and source revision. The source tree now supports both profiles; an old archive's source manifest still identifies the original source used to build it. The new release identifies common160 images separately. Never infer the programmed profile solely from the one-wire trace or a firmware filename.

## Completed acquisition campaign

**All three platforms now have ten accepted independent common160 cold boots:**
30 captures, 153,391,616 sample rows and 360 complete workload batches. All
available common160 captures passed structural and hash validation; none was
excluded by ranking its performance. Every session records 26 C, 3.3 V and an
assigned absolute voltage uncertainty of 0.01 V. The complete RAW/CSV archive
and unchanged sidecars are published under `captures_common160/`; the local
curated copies are in `ROW_Data/common160/`. Selection metadata and experiment
profiles are published without duplicating the full local curated run folders.

This campaign reuses no earlier waveform, active-idle value or energy result.
The original pending template and experiment preparation status are preserved
as historical records; completion is recorded in the separate accepted manifest.

### Repeating acquisition for a new campaign

Use the same physical board and fixture when comparing profiles, record actual
acquisition order/environment, and preserve pilot/rejected traces separately.
The following commands describe acquisition of another independent campaign;
they are not required to analyze the existing accepted captures.

After installing and functionally checking the selected image, install its matching silent measurement image and disconnect DUT USB, UART and the programmer. Use the same [PPK2 wiring and acquisition protocol](PROTOCOL.md). First acquire one pilot, replacing the board ID and measured environment fields with actual session observations:

```powershell
python tools/capture_ppk2.py --clock-profile common160 --board stm32 --physical-board-id NUCLEO-F446RE-01 --captures 1 --confirm-wiring
```

After pilot acceptance, acquire the ten full-suite cold boots with `--captures 10`. Repeat using `--board esp32` and `--board rp2040`. The collector records the selected experiment, expected image hash and acquisition profile; these are expected-image provenance, not device flash readback. The archive, supplied manifest and selected profile must agree before the collector powers the DUT.

For the ten-capture session, supply the actual measured environment; the collector requires measured voltage and ambient temperature. In PowerShell, record these values for the selected board before acquisition:

```powershell
$Common160DutVoltageV = [double](Read-Host 'Measured DUT voltage in V')
$Common160VoltageUncertaintyV = [double](Read-Host 'Absolute voltage uncertainty in V')
$Common160AmbientC = [double](Read-Host 'Measured ambient temperature in C')
python tools/capture_ppk2.py --clock-profile common160 --board stm32 --physical-board-id NUCLEO-F446RE-01 --captures 10 --measured-voltage-v $Common160DutVoltageV --voltage-uncertainty-v $Common160VoltageUncertaintyV --ambient-temperature-c $Common160AmbientC --confirm-wiring
```

The same values may be recorded with the one-capture pilot. Use the actual physical ID and a newly observed session environment when changing boards.

For offline trace analysis, pass `--manifest config/experiment.common160.json`
to `tools/analyze_capture.py`. The existing dataset's
[completed campaign](../ROW_Data/common160/source_campaign.json) already pins
all thirty original capture paths, metadata/analysis hashes and environment
records. The [original template](../campaigns/2026-09-11_ppk2_common160.template.json)
remains unchanged. The [public acceptance and results package](../results/2026-09-11_common160/README.md)
supplies the exact audited fixture adapter, patch, source hashes and results.
The preserved adapter differs from its original source snapshot only by
admitting STM32's explicitly documented JP6 isolation; all other profile,
image, timing, count, environment and integrity checks are preserved. The
current `tools/summarize_campaign.py` also accepts this fixture and requires
a nonempty operator correction statement. The supplied adapter, patch and
audit evidence retain their original bytes. With the Git
LFS RAW objects available, reproduce the summaries from the repository root:

```powershell
python results/2026-09-11_common160/acceptance/summarize_campaign_fixture_adapter.py ROW_Data/common160/source_campaign.json --project-root . --output-dir results/common160_recheck
```

Use an unused output directory. The command needs no private article-workspace
path; the preserved audit reports retain their original historical provenance.

The common160 campaign rejects mixed clock profiles. Retaining older ESP32 data is specific to the separate maximum-clock campaign; it is not allowed here. The two campaigns must have separate summaries. For each workload/board/profile, report the arithmetic mean and sample standard deviation of the ten per-call energies. The current-difference analysis uses each capture's own active-idle baseline; total RUN energy and EDP are not baseline-subtracted. Cross-profile ratios compare the separate means without assigning an SD or pairing run numbers across campaigns.

## Validation state

The 160 MHz images have separate build and hardware records in [the profile manifest](../profiles/common160/CURRENT_FIRMWARE.json). Native build success alone does not establish programming or execution.

On 11 September 2026, the [Pico common160 diagnostic](../hardware/common160/2026-09-11/rp2040_diagnostic_01.json) passed all twelve workloads with exact call counts and final DONE. It reported 160 MHz CPU, 48 MHz peripheral clock, VREG selection 12 (nominal 1.15 V) with regulation ready, Flash divider 4 and derived Flash clock 40 MHz. The [matching silent UF2 was installed afterward](../hardware/common160/2026-09-11/rp2040_measurement_programming_01.json) and is the Pico's latest recorded installation. The transfer and disappearance of the ROM volume/diagnostic CDC do not independently validate silent-image execution or attest flash contents.

The [ESP32 common160 diagnostic](../hardware/common160/2026-09-11/esp32_diagnostic_01.json) also passed all twelve workloads with exact call counts and final DONE, reporting CPU 160 MHz, APB 80 MHz, digital-bias selection 4 (SDK nominal 1.10 V), active core 0, uninitialized radio and platform check 1. The [matching silent release segments were installed afterward](../hardware/common160/2026-09-11/esp32_measurement_programming_01.json); esptool verified the bootloader, partition table and application hashes. Common160 is the ESP32's latest recorded installation. Independent flash readback remains unavailable; the subsequent PPK2 captures are included in the completed common160 selection.

The [STM32F446 common160 diagnostic](../hardware/common160/2026-09-11/stm32f446_diagnostic_01.json) passed all twelve workloads with exact call counts and final DONE through USART3/PC10. It reported nominal CPU 160 MHz, APB1/APB2 40/80 MHz, Scale 1 ready with OverDrive disabled, full FPU access, five Flash wait states and TIM2 prescaler 7999. The [matching silent release BIN was installed afterward](../hardware/common160/2026-09-11/stm32f446_measurement_programming_01.json) through ST-LINK mass storage, with completed host transfer and no `FAIL.TXT` after five seconds. Common160 is the STM32's latest recorded installation. The transfer does not independently attest flash contents or the silent image's execution.

All three common160 functional diagnostics passed and their silent measurement images were installed; all three subsequent PPK2 capture sets have now been accepted. The successful RP2040 200 MHz and STM32 180 MHz diagnostics already recorded for v1.1.0 remain valid for those exact maximum-clock images. The ten accepted regulator-removed ESP32 captures at 240 MHz are retained with their original v3 experiment/image provenance; no repeat 240 MHz acquisition is required. Those records remain separate from the accepted common160 captures.
