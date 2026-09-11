# Measurement firmware and PPK2 analysis

Specification checked against the source on **11 September 2026**, for **`energy-profiling-v4-max-clock`**, release **v1.1.0**, experiment schema 2 and GPIO protocol `single_run_v1`. This document describes the measurement firmware. Existing PPK2 datasets belong to the preceding campaign; new RP2040 and STM32 captures are required before this configuration can supply replacement results for the article.

**The measurement application emits no diagnostic messages and requires no DUT USB or UART connection.** It uses one GPIO output connected to PPK2 D0. HIGH normally marks a fixed-count batch; LOW is outside that batch. No separate algorithm-ID, ERROR, DONE or IDLE_VALID output exists. A detected fault latches the same output HIGH until reset.

## 1. Experiment identity and authoritative files

| Item | Defining file |
|---|---|
| Order, repetitions, boards, clocks, output pin and pauses | [experiment.json](../config/experiment.json) |
| Current image hashes, compilation and recorded programming status | [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) |
| Exact inputs and their definitions | [data manifest](../data/manifest.json), [generator](../tools/generate_inputs.py) |
| Autonomous sequence | [bench_runner.c](common/bench_runner.c), `bench_main` |
| Kernel adapter, memory and result verification | [bench_kernels.c](common/kernels/bench_kernels.c) |
| Algorithm implementations | [bench_algorithms.c](common/kernels/bench_algorithms.c), [private header](common/kernels/bench_original_private.h) |
| Platform contract and error reasons | [bench_platform.h](common/include/bench_platform.h) |
| Capture integration | [analyze_capture.py](../tools/analyze_capture.py) |

The logical `stm32` key means **NUCLEO-F446RE / STM32F446RET6** and selects [targets/stm32f446](targets/stm32f446/README.md). Current images belong in `build_verified/max_clock_measurement`; their existence does not establish that they were programmed or physically measured. The `single_gpio_measurement` profile key in CURRENT_FIRMWARE.json is retained for collector compatibility and points to this archive. Earlier firmware is available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0).

The experiment manifest SHA-256 is recorded in CURRENT_FIRMWARE.json, the build provenance and each new capture. Always use the manifest matching the capture's recorded experiment; do not replace an older dataset's manifest with the current one.

Notation: **L = 2048** is the input length of one kernel call; **R** is the board-specific call count in one batch; **M** is the number of PPK2 samples in a window. FFT normalization by L is distinct from dividing batch energy by R.

## 2. Language, libraries and compilation

The common implementations are written in **C**. Platform adapters configure hardware through native SDKs or CMSIS. CMake and Ninja organize compilation; they are not compilers. Python generates inputs/references and processes captures. PowerShell automates some Windows build commands.

| Current target | SDK / support | Compiler identity used for the campaign | Common C translation units |
|---|---|---|---|
| ESP32-D0WD-V3, revision 3.1 | ESP-IDF 5.5.4 | Espressif GCC 14.2.0, `esp-14.2.0_20260121`, Xtensa | `-std=gnu17` |
| Marble Pico, RP2040 | Pico SDK 2.2.0, Pico-compatible board profile | GNU Arm Embedded GCC 9.2.1, `20191025` | `-std=gnu11` |
| NUCLEO-F446RE | cmsis-device-f4 v2.6.11, CMSIS_5 5.9.0 | GNU Arm Embedded GCC 9.2.1, `20191025` | `-std=gnu11` |

Thus the precise description is **common C implementation compiled as GNU C17 on ESP32 and GNU C11 on ARM**. SDK startup, runtime and libraries may also contain C++, assembly or ROM code. Exact commands and artifact identities are retained with each build; historical build records do not substitute for a new source-version build record.

The kernels derive from the recovered scalar library in Noela Pirleci's original project, with the repairs documented below. AES, SHA, ChaCha20, CRC and DSP are not replaced by vendor cryptographic accelerators or DSP-library calls. Mathematical functions and runtime support still depend on the platform. The experiment compares the configured boards and software stacks; it does not isolate the instruction set alone.

### Options affecting the workload

The common benchmark compilation uses:

```text
-O2 -fno-lto -fno-fast-math -ffp-contract=off
```

| Option | Meaning in this experiment |
|---|---|
| `-O2` | Normal compiler optimization is enabled. |
| `-fno-lto` | Link-time optimization across translation units is disabled. Inlining and transformations within a translation unit remain possible. |
| `-fno-fast-math` | The fast-math package of numerical relaxations is disabled. |
| `-ffp-contract=off` | Floating-point expressions are not contracted into fused multiply-add operations. |

See the [GCC 14.2 optimization manual](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Optimize-Options.html) and [GCC 9.2 ARM options](https://gcc.gnu.org/onlinedocs/gcc-9.2.0/gcc/ARM-Options.html).

These flags do not guarantee identical floating-point bits on every platform and do not alone preserve otherwise unobservable work. `bench_kernel_run` is noinline; kernels and runner are separate units; the runner contains compiler barriers and consumes results. The generated binary must retain the calls and boundaries. Precompiled SDK/runtime libraries are not assumed to use the same options as the common kernels.

Pico SDK commands can contain `-O3` followed by **`-O2`**, making the latter effective. ESP32 commands must be read from their own archive rather than assigned that same sequence. ARM uses Thumb for Cortex-M0+ / Cortex-M4; F446 also uses `-mfpu=fpv4-sp-d16 -mfloat-abi=hard`. `compile_commands.json`, target options, toolchain identities and source manifests are retained with the images.

Pico and STM32 dependencies are pinned in target `sdk.lock.json` files. ESP-IDF 5.5.4 is required by ESP32 CMake; the packaged framework is framework-espidf 3.50504, with package and observed SDK-source identities retained in the archive. Reproduction instructions are in [BUILD_AND_TEST.md](../docs/BUILD_AND_TEST.md) and the target READMEs.

## 3. Exact input bytes and interpretation

The firmware contains constant C arrays. It does not generate random input at boot, read an ADC or receive workload data over UART. The `.hex` files are readable representations of the same bytes as `.bin`; algorithms do not process ASCII hexadecimal text.

### Compression - internal IDs 1-4

A 256-byte block is constructed as follows:

```text
00 repeated 32 times
FF repeated 32 times
ramp 00 01 02 ... 3F                  (64 bytes)
00 00 01 01 02 02 03 03 10 20 30 40 AA 55 AA 55
    this final 16-byte motif repeated 8 times
```

The whole block is repeated **8 times**, producing 2048 bytes. This is one fixed synthetic input, not a text corpus or a universal distribution of IoT data.

### Cryptography and CRC - internal IDs 5-8

The deterministic xorshift32 state starts at `0x1A2B3C4D`. For each of the 2048 emitted bytes:

```c
/* Unsigned 32-bit operations, modulo 2^32. */
s ^= s << 13;
s ^= s >> 17;
s ^= s << 5;
data[i] = s & 0xFF;
```

The low byte is emitted after the full update. This fixed input does not introduce new messages, keys or nonces between calls.

### DSP - internal IDs 9-12

A 128-value period is defined by:

```text
u[n] = floor(128 + 100 * sin(2*pi*n/128) + 0.5), n = 0..127
```

The period is repeated **16 times**. The input consists of **2048 numerical uint8_t samples**, minimum 28, maximum 228 and mean 128. It is not float storage reinterpreted as bytes. No DC subtraction or spectral window is applied. No physical signal sample rate is assigned here; PPK2's 100 kS/s describes current acquisition, not the synthetic DSP input.

The frozen files define the exact bytes. A regeneration using another mathematical library is not automatically equivalent merely because the formula is unchanged.

| File, 2048 B each | SHA-256 |
|---|---|
| [compression.bin](../data/compression.bin) | `44a2a279b86d1e7d98c24c5bd341a66adec17470de9e7b0ffa4ffc7092b7dab2` |
| [crypto.bin](../data/crypto.bin) | `b81c57d8f1f5c17f190e279e86f781dee155b05a779fe741a12a6bfacde47b23` |
| [dsp.bin](../data/dsp.bin) | `f7ed02ed3c339a9290b4d5a9981e472ae967a86d8d3e2735948c819650a28cb7` |

`bench_kernel_prepare` copies the input to RAM **once before the batch**. All R calls use that unchanged copy. Each result overwrites the previous result and is not fed into the next call.

## 4. Fixed order and call counts

R comes from the manifest and is compiled into the board configuration. Counts originate in the original RAW experiment notes, not an assumption that all recovered source files used identical loops. Internal IDs below select kernels in software; they are **not transmitted on GPIO**. The analyzer assigns algorithms from the first through twelfth HIGH pulse.

| Position / internal ID | Algorithm | ESP32 R | Pico R | F446 R |
|---:|---|---:|---:|---:|
| 1 | RLE | 3000 | 3000 | 3000 |
| 2 | Delta | 3000 | 3000 | 3000 |
| 3 | LZ77 | 200 | 200 | 200 |
| 4 | Huffman | 200 | 500 | 100 |
| 5 | AES-128 | 1000 | 100 | 100 |
| 6 | SHA-256 | 1000 | 500 | 500 |
| 7 | ChaCha20 | 3000 | 3000 | 3000 |
| 8 | CRC32 | 3000 | 3000 | 3000 |
| 9 | FFT | 50 | 20 | 20 |
| 10 | FIR | 300 | 300 | 300 |
| 11 | IIR | 50 | 50 | 50 |
| 12 | DCT | 1 | 1 | 1 |

No target duration determines when a kernel stops. One HIGH window contains the full R-call batch; no per-call GPIO pulse or inter-call pause is inserted. On a detected failure, the sequence stops with RUN latched HIGH.

## 5. Algorithm contracts

All sizes below describe **one call with L=2048**. They are output sizes in RAM, not transmitted data. Header construction, algorithmic initialization and the stated conversions belong inside RUN.

### 1 - RLE

Writes `(count,value)` pairs, one byte per component. Count is 1..255; longer runs are split. There is no original-length header. Scanning restarts for each call.

The current input produces **2592 B**, expanding 2048 B by **26.5625%**. This pattern therefore does not yield a transmission saving with this RLE format. The general bound is 2L=4096 B.

### 2 - Delta

`d[0]=x[0]`; otherwise `d[i]=(x[i]-x[i-1]) mod 256`. Conversion to uint8_t defines the modulo-256 differences. Output is **2048 B**. This is a reversible difference transform without a reduction in byte count by itself.

### 3 - LZ77

The format is custom: a 4-byte little-endian original length L, followed by `(distance:uint8, length:uint8, [literal:uint8])` tokens. The literal is omitted only when a match reaches the exact end of the input. History and lookahead are limited to 255 bytes. Overlapping matches are allowed.

Search is exhaustive, oldest to most recent position. Equal match lengths retain the first match, hence the greatest distance. There is no minimum match threshold; a length-one match is accepted. A literal without a match has zero distance and length. No dictionary survives between calls.

The current input produces **1530 B**, including the header, with **509 tokens**. The storage bound is `4+3L`.

### 4 - Huffman

Canonical Huffman coding over a 256-byte alphabet. Every call rebuilds frequencies, code lengths and canonical codes. The static working environment is reset in the call.

Code lengths are constructed without a pointer tree by merging branch memberships. The internally named heap is a list with a linear minimum search, not a binary heap. Frequency ties select the smaller branch_id. Leaf IDs are byte values; internal branch IDs increase from 256. Canonical ordering is by length and then symbol value. Lengths above 32 are rejected; a sole symbol gets a one-bit code.

The complete frame is created inside RUN:

```text
4 B: original length, uint32 little-endian
4 B: valid payload bit count, uint32 little-endian
256 B: code length for symbols 0..255; zero means absent
payload: MSB-first bits, unused final bits set to zero
```

The header is 264 B. The current input has 68 distinct symbols and produces **9400 payload bits =1175 B**, or **1439 B including the header**. This measures code construction as well as encoding, not encoding with a precomputed table.

### 5 - AES-128

Scalar software AES-128 in **ECB with PKCS#7 padding**. The key is exactly the 16 ASCII bytes `0123456789abcdef`, without a NUL terminator. No IV, authentication or decryption is part of this workload.

Expansion to a 176-byte key schedule repeats in every call. The 2048-byte input produces 128 data blocks plus one padding block of sixteen `0x10` bytes: **2064 B output**. Key expansion, block copies, padding and all encryption rounds are included.

### 6 - SHA-256

Scalar SHA-256 with uint32_t state and operations. The eight initial state words are restored for each call. Work includes the message schedule, transforms, padding, input bit length and digest serialization.

For 2048 B, 32 data blocks and one final padding block are processed. Output is **32 B**, with digest words serialized big-endian. This is not HMAC.

### 7 - ChaCha20

The 20-round variant uses a 256-bit key, 96-bit nonce and 32-bit block counter. The key is exactly the 32 ASCII bytes `0123456789abcdef0123456789abcdef`, without NUL. The nonce is twelve zero bytes.

The counter starts at **1 for every call**. Thirty-two 64-byte blocks are generated, explicitly serialized little-endian and XORed with the input. Output is **2048 B**, with no padding or Poly1305 tag. The keystream state does not continue across calls. Fixed key/nonce values define this repeatable workload, not a communication protocol implemented here.

### 8 - CRC32

Reflected, bit-at-a-time CRC with polynomial `0xEDB88320`, initial state `0xFFFFFFFF` and final complement. There are eight bit steps per input byte. The adapter writes **4 little-endian bytes**.

No CRC peripheral or lookup table is used. The CRC32 workload is distinct from the result digest calculated outside RUN after each batch.

### 9 - FFT

Iterative radix-2 FFT with bit reversal and a negative exponent. Numerical uint8_t input is converted to float and the imaginary part starts at zero. L=2048 requires eleven stages.

Real/imaginary arrays are float. The cos/sin twiddles and butterfly intermediates use double; stored butterfly outputs return to float. Magnitude uses double sqrt arithmetic before the final float conversion.

Output is **2048 float values, 8192 B**, defined as `abs(DFT(x)[k])/L` over the full spectrum k=0..L-1. No phase, complex pairs, PSD or doubled one-sided spectrum is exported. Scratch initialization, conversions, twiddles and magnitude calculation belong to the call. Scratch memory is static rather than allocated from the heap.

### 10 - FIR

Integer taps `[1,2,3,2,1]` implement:

```text
y[n] = floor((x[n]+2*x[n-1]+3*x[n-2]+2*x[n-3]+x[n-4])/9)
x[n] = 0 for negative indices
```

The accumulator is uint32_t and output is **2048 uint8_t bytes**. The divisor remains 9 at the beginning even when history terms are absent. The source recalculates the coefficient sum inside each sample's loop. History does not continue across calls. This is an integer workload, not a floating-point filter.

### 11 - IIR

The actual recurrence is:

```text
y[n] = Q((x[n]+2*x[n-1]+x[n-2]+y[n-1]+y[n-2])/4)
Q(v) = truncation to integer and saturation to [0,255]
x[n] = y[n] = 0 for negative indices
```

The retained implementation uses double arithmetic, but feedback reads **already quantized and saturated uint8 outputs**. The output buffer is overwritten in causal order, so each call starts without history from the previous call. Output is **2048 B**.

The internal feedback array `[1,1,1]` does not mean a conventional denominator `[1,1,1]`; its a[0] is unused by that loop. The unquantized linear core has numerator `[0.25,0.5,0.25]`, denominator `[1,-0.25,-0.25]` and **DC gain 2**. Quantization and saturation mean the implemented system is not a unit-gain linear filter.

For the current input, **1006/2048 outputs, or 49.12109375%, saturate to 255**. This is the workload being measured. The IIR function body is retained from the recovered source; its recurrence and verification are now explicit.

### 12 - DCT

Direct orthonormal DCT-II:

```text
X[k] = alpha[k] * sum(x[n] * cos(pi*k*(2*n+1)/(2*L)), n=0..L-1)
alpha[0] = sqrt(1/L)
alpha[k>0] = sqrt(2/L)
```

Accumulation, products, sqrtf normalization, cosf calls and output use float. PI is a double literal in the initial factor expression, which is assigned to float. This is not an all-double implementation.

Each contribution first computes integer phase `k*(2*n+1) mod (4*L)`, then the float angle. Reduction preserves the mathematical formula, limits the cosf argument and has a cost inside RUN. Complexity remains **O(L^2)**, without a fast factorization or precomputed cosine table. Output is **2048 signed float coefficients, 8192 B**, without clipping to 0..255.

## 6. Memory, state and result verification

There is one **non-reentrant** common workspace, and kernels do not run in parallel. Persistent workspaces are static and local arrays have fixed bounds. Measured kernels contain no malloc/calloc/free calls. SDK initialization may allocate memory, so the absence of heap allocation in a kernel does not imply its absence from the entire firmware.

Explicit workspaces include a 2048-byte input copy, 6408-byte output buffer, 8192-byte float output, 2048-byte decode buffer, two 8192-byte FFT scratch arrays and the Huffman environment. AES/SHA/ChaCha/Huffman also use fixed local arrays. Binary maps describe the actual memory layout; individual stack frames are not a measurement of total stack high-water usage.

Before a batch, prepare validates the internal ID and length, copies the input, initializes memory guards and recognizes registered inputs outside RUN. The API accepts lengths up to 2048; FFT requires a nonzero power of two and DCT requires nonzero length. The campaign always uses 2048. Cryptographic/CRC outputs and FFT/DCT transforms are not accepted by the firmware verifier for unregistered inputs, even if prepare/run can process that length. Compression and FIR/IIR verifiers work for arbitrary supported inputs.

Each run checks the active ID, guards before and after the kernel, the return code and applicable output limits. Guards are control words around buffers; they do not prove that every possible invalid memory access is absent.

**Full algorithmic verification runs once after the batch, on the last output.** It is outside RUN; the R intermediate results are not each fully compared with a reference.

| Result | Verification after the batch |
|---|---|
| RLE, Delta, LZ77, Huffman | Independent decoding/inversion and comparison with the full input, including format checks |
| AES, SHA, ChaCha20, CRC32 | Full comparison with registered independent reference bytes |
| FIR, IIR | Independent integer formulas and comparison of every output byte |
| FFT | Each value is finite and `abs(actual-ref) <= 0.0001 + 0.00002*abs(ref)` |
| DCT | Each value is finite and `abs(actual-ref) <= 0.01 + 0.00002*abs(ref)` |

References are generated independently of the measured C functions. Transform values are calculated in double on the host and stored in the MCU header as **float constants**, not double arrays. The frozen periodic FFT reference uses 128 period bins placed at multiples of 16, with zero in the remaining positions; all 2048 outputs are still checked. Firmware values and verifier: [bench_golden.h](common/kernels/bench_golden.h), [bench_kernels.c](common/kernels/bench_kernels.c).

After verification, a CRC32 over the complete last output is stored in volatile `bench_result_digests[]`; completed call counts are stored in `bench_completed_calls[]`. FFT/DCT digests cover the byte representation of float values and are not cross-platform numerical-equivalence criteria.

## 7. Autonomous measurement sequence

The application runs without serial messages. The diagram shows the single GPIO level:

```text
power/reset
  -> boot and platform initialization
  -> RUN LOW: platform checks and RLE preparation
  -> nominal 5 s active control idle, RUN LOW
  -> RUN HIGH: R independent RLE calls
  -> successful batch/count checks while HIGH
  -> RUN LOW: platform check, result verification and digest
  -> Delta preparation and platform checks
  -> nominal 1 s active control idle, RUN LOW
  -> repeat for positions 2 ... 12
  -> after DCT falls LOW: final platform/result checks and digest
  -> nominal 2 s active control idle, RUN remains LOW
  -> platform final state; no automatic restart
```

The initial five seconds begin **after boot, initialization, checks and first preparation**. They are not exactly the first five seconds after power-on. The final two seconds before the first rising edge form the operational baseline, apart from timer-return and GPIO-boundary overhead. Platform checks are performed before the idle interval, not between that interval and the first gate. Active idle keeps the CPU awake; it is not deep sleep or hardware Standby.

Each of the eleven inter-workload idle pauses is nominally one second, after previous-result verification and next-workload preparation/checks. Total LOW gaps can be longer. There is no ID bus, ID setup time or extra 1 ms delay. LOW intervals cannot independently distinguish those different kinds of work.

There are no extra kernel warm-up calls, cache flushes or processor resets between repetitions. Algorithmic state is reinitialized, but CPU/memory state can be influenced by earlier calls. R calls within one batch are not R statistically independent replicates.

After final verification, two seconds of active idle precede the platform final state. There is no completion edge. Record at least **three seconds LOW after the twelfth falling edge**. This tail is a recording requirement and does not mark exactly two seconds of idle or independently prove final verification completed.

### Work included in RUN

Included work comprises wrapper dispatch, per-call guards/status, algorithmic initialization, conversions/headers, computation/output writes, return checking, counter increments and successful batch/count checks just before the falling edge. AES key expansion, Huffman code construction and FFT scratch initialization are measured work.

Initial copying to RAM, registered-input recognition, pauses, platform configuration checks, full verification of the final output and the result digest are outside RUN. The firmware does not use micros()/millis() for performance and does not report algorithm duration or energy.

The physical gate also includes return from the function that raises RUN and the call/prologue preceding the write that lowers it. It is not a perfect isolation of mathematical instructions. Compiler and MMIO barriers preserve the relevant ordering. GPIO/loop overhead and platform interrupts are not automatically subtracted.

### Detected errors

The runner records the internal algorithm ID and reason, requests **RUN HIGH**, and stops. It does not continue to the next kernel or restart the suite. A failure inside an active batch keeps the original gate HIGH without first producing a normal falling edge. A failure in post-RUN verification reasserts HIGH. Successful-call/count tests occur before lowering the gate so a failed batch does not look completed.

| bench_failure_reason | Meaning |
|---:|---|
| 1 | Platform initialization failed |
| 2 | Invalid platform state before preparation |
| 3 | Kernel preparation failed |
| 4 | Invalid platform state before RUN |
| 5 | Kernel invocation failed |
| 6 | Completed call count differs from R |
| 7 | Invalid platform state after RUN |
| 8 | Algorithmic verification failed |

A CPU fault or platform-internal failure may stop execution before these variables are populated. Very early failures can precede usable GPIO initialization. A permanently HIGH signal, incomplete or extra pulse sequence, or absent final LOW tail is structurally invalid. One wire cannot identify every reset/hang, and a hang LOW during final verification may leave a structurally valid trace. A parser pass therefore does not certify all runtime checks completed.

## 8. Platform configuration

| Parameter | ESP32 | Pico RP2040 | NUCLEO-F446RE |
|---|---|---|---|
| Nominal CPU | 240 MHz | 200 MHz | 180 MHz |
| Configured source | 40 MHz crystal, 480 MHz PLL /2 | 12 MHz crystal, PLL VCO 1200 MHz /6 /1 | Nominal 16 MHz HSI, PLL M=16/N=360/P=2 |
| Core regulator policy | SDK configuration for fixed CPU clock | Internal 1.15 V selection, checked before RUN | Scale 1 with OverDrive enabled and ready |
| Flash access configuration | DIO, 40 MHz | QSPI, divider 4, 50 MHz | Five wait states; prefetch and instruction/data caches |
| Application core | CPU0; CPU1 stopped by unicore IDF startup | Core0; core1 remains in Boot ROM waiting state, no application launched | One Cortex-M4 |
| Floating point | Hardware single; double is not assumed hardware | Software, no FPU | Single-precision FPU enabled, hard-float ABI; software double |
| Runtime | ESP-IDF / FreeRTOS | Pico SDK, bare metal | CMSIS, bare metal |
| Timer used only for pauses | GPTimer, 1 MHz | Free-running hardware timer | TIM2, 10 kHz |
| Final state after the 2 s pause | Main task suspended; RTOS idle/scheduler | WFI loop | WFI loop |
| Relevant reserved stack | Main task 16 KiB | Core0 4 KiB, SCRATCH_Y | 16 KiB linker reservation |

**ESP32.** Wi-Fi and Bluetooth are never initialized. Platform checks require `esp_wifi_get_mode(...) == ESP_ERR_WIFI_NOT_INIT`, reported CPU clock 240 MHz and core0; disconnecting an initialized Wi-Fi driver would not satisfy the contract. PM and tickless idle are disabled. The 100 Hz FreeRTOS tick and system interrupts remain. Task watchdog is disabled; interrupt watchdog remains enabled with a 300 ms setting. The benchmark does not globally mask interrupts. APB is 80 MHz. Flash is configured as 4 MiB, DIO at 40 MHz, with PSRAM disabled. GPTimer starts, is read and stops for pauses, without timing kernel batches.

UART0/1/2 are reset and their clocks disabled; GPIO1/3 are disabled without pulls. The measurement application has no serial console. Immutable ESP32 ROM may emit boot text before application initialization and the baseline; ROM output is not an application measurement report. No eFuse change is made to suppress it.

**Pico.** Before the first preparation or measurement window, the firmware selects an internal core voltage of 1.15 V, allows at least 1 ms settling and checks regulation before switching to 200 MHz. clock_get_hz and a hardware frequency counter check the system clock. The counter is relative to clk_ref, accepting 199800..200200 kHz; this is not calibration against an external standard. Runtime checks also require the 1.15 V selection, regulation-ready status, clk_peri at 48 MHz and the SSI Flash divider at 4. The boot stage and application use the same divider, giving 50 MHz QSPI access during RUN. The Pico-compatible profile configures 2 MiB of Flash address space; this is a build setting, not a claim that the physical board has only that capacity. The internal core regulator is distinct from the removed board regulator; PPK2 supplies 3.3 V to the board rail. [RP2040 datasheet, Sections 2.15.3 and 5.6](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf).

UART0/1, USBCTRL and ADC are held in reset, clk_usb and clk_adc are stopped, and GPIO0/1 have no function/pull. **PLL_USB remains enabled** because the SDK uses its 48 MHz output for clk_peri. Stopping USB does not mean every PLL is stopped. Float/double and mathematical operations may use Pico SDK/Boot ROM software wrappers. clk_rtc remains at 46875 Hz. The SDK default alarm pool/handler is compiled in, but the application registers no periodic alarm callbacks and does not globally mask interrupts.

**F446.** Internal HSI avoids dependence on a powered ST-LINK MCO. Checks cover device ID 0x421, 512 KiB Flash, PLL configuration, default HSI trim, bus dividers, FPU access, Flash settings, voltage scaling, OverDrive readiness and the explicitly tracked peripherals. AHB=180 MHz, APB1=45 MHz (/4), APB2=90 MHz (/2); TIM2 receives 90 MHz with prescaler 8999 and TIMPRE cleared. Flash has five wait states, with prefetch and instruction/data caches enabled. Regulator VOS is Scale 1; OverDrive and its switching/readiness flags must be set. Clock initialization performs the regulator transition while SYSCLK still uses HSI and selects the PLL only after Flash and bus settings are ready. SysTick is stopped; TIM2 has no IRQ. USB FS/HS, DMA1/2 and CRC clocks must be off. USART2 is disabled; PA2/PA3 are analog inputs without pulls. A small calculation with volatile float operands checks an executable FPU path.

Register reads and clock APIs validate **configuration**, not the exact physical oscillator frequency. HSI drift, actual voltage and PPK2 integration remain fixture checks. The list does not imply every conceivable peripheral is off.

Sources: [ESP32 adapter](targets/esp32/main/platform_esp32.c), [ESP32 configuration](targets/esp32/sdkconfig.defaults), [Pico adapter](targets/rp2040/platform_rp2040.c), [F446 adapter](targets/stm32f446/platform_stm32f446.c), and the current build archives.

## 9. GPIO, power and LEDs

| PPK2 | Signal | ESP32 GPIO | Pico GPIO | F446 pin |
|---|---|---:|---:|---|
| D0 | RUN | 18 | 2 | PC0 |

RUN is the only measurement output. D1-D7 are unused; there is no separate ID/status encoding. Normal execution yields twelve complete HIGH pulses in the fixed order. Internal software IDs continue to select kernels but are not transmitted on additional pins.

PPK2 Source Meter supplies the DUT at a nominal 3300 mV through VOUT to 3V3, with common ground. Connect LOGIC VCC to measured DUT 3V3. DUT USB/UART, programmers and other power paths are disconnected during energy capture. The PPK2 USB connection to the PC remains necessary and is distinct from DUT USB.

There is no external marker LED. The controllable Pico GPIO25 LED and Nucleo PA5 LED are held LOW/off. Software does not turn off every power LED or auxiliary circuit on every possible board variant. Measured energy belongs to the selected supply domain and fixture.

For direct Nucleo 3V3 power, physically separate ST-LINK or open SB2 and SB12 according to the manual. Confirm PC0 routing on the physical board. Connector and power details are in the [F446 target README](targets/stm32f446/README.md) and [protocol](../docs/PROTOCOL.md), based on [UM1724, section 7.5.3 and connector tables](https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf). Disabling UART in firmware does not modify electrical bridges.

## 10. Offline PPK2 calculation

The firmware does not calculate energy or export execution times. analyze_capture.py uses nominal PPK2 sampling at **100000 samples/s**, or **10 microseconds per sample**, and only the RUN input.

For interval `[a,b)`, the first HIGH sample is included and the first LOW sample excluded:

```text
M = b - a
T_batch = M / fs
Q_batch = sum(I[a:b]) / fs
E_batch = V_constant * Q_batch
T_call = T_batch / R; Q_call = Q_batch / R; E_call = E_batch / R
```

Current is converted to amperes. Incremental mean multiplied by duration is equivalent to rectangular summation up to floating-point rounding; integration is not trapezoidal. Support M/fs is distinct from the first-to-last sample span `(M-1)/fs`.

The baseline selects the **last 200000 LOW samples**, two seconds, immediately before the first HIGH pulse. This positional baseline corresponds to the end of the firmware's five-second active pause, with timer/gate boundary overhead. Entire LOW gaps include mixed activity and are not labeled controlled idle. **Baseline is not automatically subtracted** from active energy. Boot, preparation and verification outside RUN are excluded from reported kernel-batch energy.

The stream contains no simultaneously sampled voltage. Default energy uses nominal 3.3 V from the manifest. `--voltage` supplies an operator-declared constant, labeled unverified by software. `--voltage-uncertainty-v` records a value but **does not automatically propagate uncertainty into E** or construct a complete uncertainty budget.

Current minimum, maximum and population standard deviation describe samples within a window. They are not confidence intervals across independent experiments or a replacement for instrument accuracy. Between-capture aggregation is a separate analysis step.

### Structural capture acceptance

The analyzer requires exactly twelve complete HIGH regions and assigns algorithms by ordinal position. ESP32 and RP2040 require at least 495000 defined LOW samples before the first HIGH and at least 99000 between successive pulses. STM32 uses 490000 and 98000 respectively, reflecting a 2% allowance for its HSI-derived control timer instead of 1%. Every board requires at least 300000 LOW samples after the twelfth falling edge. These are nominal five/one-second MCU pause lower bounds and an exact three-second recording-tail minimum. There are no upper bounds because other work can lengthen LOW gaps. The tolerance is a protocol threshold, not calibrated timing uncertainty; verify it in the new physical pilot.

The selected RUN input may be unknown only in a contiguous prefix before its first defined LOW. Later unknown or mixed states reject the capture. Unused digital channels are ignored. Finite negative current is allowed before the first RUN except in the selected baseline; the baseline and every sample from the first RUN onward must be nonnegative. NaN/Inf current is always rejected, without clipping or reindexing.

A structural pass cannot count R independently, authenticate the board/image, prove no reset occurred or prove final verification completed. In particular, a hang LOW after the last fall may satisfy the recording shape. The operator associates the capture with the programmed binary and manifest. The parser reports `structural_protocol_pass`, not firmware-completion certification.

### Files and units

Native support is `.ppk2` formatVersion 2: a ZIP containing metadata.json, session.raw and minimap.raw. Each session sample contains little-endian float32 current in microamperes followed by a big-endian uint16 digital word, two bits per channel. D0 occupies the lowest pair: 01 LOW, 10 HIGH, 00 unknown, 11 mixed. Only D0 is used for the protocol; minimap is not used for metrics. The default limit is sixty million samples, ten minutes, with validated sizes/format and no extraction to disk.

Nordic CSV uses explicit Timestamp(ms), Current(uA), and D0 or the D0-first D0-D7 bitstring. A generic CSV declares units and `--digital-column` or a D0-first `--digital-bitstring-column`; units are not guessed from numeric magnitude. Optional sample indices and timestamps are checked for detectable discontinuities. Native captures are unchanged and existing outputs are not overwritten.

The complete schema, CLI and official Nordic format references are in [capture_format.md](../docs/capture_format.md). Each new acquisition setup requires a physical compatibility check.

## 11. Measurement images and acquisition status

[CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) records build hashes and observed programming status separately. New build evidence belongs in each target's `build_verified/max_clock_measurement`; a successful compile is not a programming or PPK2 record. See [validation status](../docs/VALIDATION.md) and the [hardware report](../docs/HARDWARE_VALIDATION.md) for the evidence currently available.

The maximum-clock campaign requires new RP2040 and STM32 PPK2 pilots and ten accepted independent cold-boot captures per board. No replacement energy datasets for those configurations are available yet. The existing captured files and their original manifests remain unchanged; they do not become current results after a firmware update. ESP32 measurements can be retained only with original provenance and verified equivalence of the measured settings. Required checks include isolated 3V3 wiring, physical clock/voltage measurements, pulse boundaries, exported file format and independent captures. Fixed order, heating and cache state matter; one physical unit per model does not characterize unit-to-unit variation.

## 12. Changes from the original code and earlier protocol

This is a repaired, versioned benchmark. Preserving input volume and repetitions does not make historical energy values valid results of the new code.

| Aspect | Current behavior to describe in the article |
|---|---|
| CPU operating profiles | ESP32 240 MHz; RP2040 200 MHz with internal 1.15 V; F446RE 180 MHz with Scale 1/OverDrive and HSI |
| Timing | External PPK2 timebase, fixed R calls, no MCU performance timestamps |
| Marker | One GPIO pulse per batch, no external marker LED or ID/status bus; errors latch RUN HIGH |
| Input | Three byte-defined deterministic sets; numerical uint8 DSP, not reinterpreted float storage |
| Memory | Reusable workspaces and fixed-bound local arrays; historical FFT malloc/free cost removed |
| AES | Output capacity covers 2064 B including the extra PKCS#7 block; original padding behavior retained |
| Huffman | Correct full sort, defined singleton/tie behavior, complete header inside RUN and bounded payload writes |
| LZ77 | No extra terminal literal when a match reaches the end; complete custom format defined |
| SHA/ChaCha/CRC | Unsigned shifts where required and explicit byte serialization |
| FFT | Numerical input, normalized float output, integer stage count and static scratch |
| FIR/IIR | Original scalar variants retained; integer FIR and quantized/saturated IIR with explicit recurrence |
| DCT | Correct DCT-II angle, phase reduction and signed float coefficients without byte clipping |
| One-wire validation | Algorithm assignment from order, lower-bound LOW checks and structural acceptance; no independent completion/error bus |

Historical firmware remains available in the [v1.0.0 release archive](https://github.com/victorstoica114/energy-profiling/releases/tag/v1.0.0). Input data and captured logs retain their own versioned provenance. An algorithm name alone does not define a workload: variant, input, included initialization, compiler and RUN boundary are part of its identity.

## 13. Keeping source, documentation and article consistent

Run from the project root:

```powershell
python tools/generate_inputs.py --check
```

This compares the ten generated files without modifying them. Changes to inputs, keys, coefficients, numeric types, algorithms, repetitions, boundaries, compiler or platform configuration define a changed experiment. Deliberately regenerate the necessary inputs/references, perform the relevant checks and retain new binaries, hashes and evidence.

Do not manually alter golden values to accept unexpected output. CURRENT_FIRMWARE.json must reflect verified programming separately from compilation. Reproduction instructions are in [BUILD_AND_TEST.md](../docs/BUILD_AND_TEST.md).

When writing the article, use the behavior established here and the PPK2 measurements actually acquired. Keep declared configuration, software checks and physical validation distinct. Nominal values or functional checks are not energy measurements.
