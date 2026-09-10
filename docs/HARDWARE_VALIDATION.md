# Testare funcțională pe plăci — 9 septembrie 2026

Toate cele trei plăci au executat cu succes **12/12 algoritmi**, cu numerele de apeluri din configurație și verificarea rezultatelor pe microcontroler. Fiecare log conține BOOT, 12 perechi START/PASS și DONE. După validare, pe fiecare placă a fost încărcat profilul `measurement`, fără diagnosticul serial.

| Placă identificată | Configurație raportată la pornire | Transport de test | Rezultat |
|---|---|---|---|
| ESP32-D0WD-V3, revizia 3.1, flash 4 MB | CPU 240 MHz, core 0, FPU single, radio neinițializat | UART0 prin CH340, COM4, 115200 | 12 PASS + DONE |
| Raspberry Pi Pico, RP2040 | CPU 133 MHz, core 0, calcul floating point software | USB CDC, COM7 după programare | 12 PASS + DONE |
| NUCLEO-F446RE, IDCODE `10006421`, flash 512 KiB | HSI + PLL, CPU 100 MHz, APB1 25 MHz, APB2 50 MHz, CPACR `00f00000` | USART2 prin ST-LINK VCP, COM6, 115200 | 12 PASS + DONE |

Frecvențele din tabel sunt cele deduse de firmware din configurația hardware, nu calibrări externe. Numerele de port COM pot varia între conectări. Testele au folosit alimentarea și instrumentarea de la PC, fără achiziție PPK2.

## Dovezi păstrate

- ESP32: [log serial](../hardware/2026-09-09/esp32_diagnostic_01.log), [rezultat și hashuri](../hardware/2026-09-09/esp32_diagnostic_01.json), [programarea fără UART](../hardware/2026-09-09/esp32_measurement_programming.json).
- Pico: [log serial](../hardware/2026-09-09/rp2040_diagnostic_01.log), [rezultat și hashuri](../hardware/2026-09-09/rp2040_diagnostic_01.json), [programarea fără USB/UART](../hardware/2026-09-09/rp2040_measurement_programming.json).
- Nucleo: [log serial](../hardware/2026-09-09/stm32_diagnostic_01.log), [rezultat și hashuri](../hardware/2026-09-09/stm32_diagnostic_01.json), [programarea fără UART](../hardware/2026-09-09/stm32_measurement_programming.json).

Manifestul [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) identifică imaginile curente de diagnostic și măsurare. Cele șase build-uri sunt separate în `firmware/targets/<target>/build_verified/{diagnostic,measurement}`; ținta Nucleo este `stm32f446`. Manifestele vechi aflate direct în directoarele `build_verified` sunt istorice.

ESP32 a fost programat prin esptool, cu verificarea hashurilor scrise pentru bootloader, partiții și aplicație. Nucleo a fost programat prin volumul ST-LINK `NODE_F446RE`, fără `FAIL.TXT`, iar Pico prin UF2 pe volumul ROM `RPI-RP2`. Interfețele USB de debug ST-LINK și picoboot aveau drivere indisponibile; programarea prin volumele respective și feedbackul serial au funcționat. Nu s-au instalat drivere globale.

Nucleo fără UART nu a transmis date în observația de 8 s. ESP32 fără UART de aplicație a emis numai mesajele ROM de boot. Pico fără USB a dispărut din lista porturilor seriale, conform configurației. Aceste observații și inspecția binarelor confirmă oprirea diagnosticului; nu demonstrează singure terminarea secvenței GPIO din profilul fără diagnostic.

## Repetarea testului cu diagnostic

Se programează explicit imaginea `diagnostic` corespunzătoare. Pentru ESP32, din proiect:

```powershell
python tools/serial_validation.py --board esp32 --port COM4 --reset esp32 --firmware firmware/targets/esp32/build_verified/diagnostic/energy_bench_esp32.bin --output hardware/new_esp32_run
```

Pentru Nucleo, se pornește colectorul pe portul VCP, apoi se resetează/programază placa. Pentru Pico, `--board rp2040 --port auto` așteaptă USB CDC `2E8A:000A`; colectorul trebuie pornit înainte de încărcarea UF2. După instalarea profilului fără USB, Pico se readuce în BOOTSEL ținând butonul apăsat în timpul conectării USB.

Colectorul refuză să suprascrie fișiere existente. Timpul din log este timpul PC-ului și nu se folosește pentru performanță sau energie. Digesturile rezultatelor floating point pot diferi între arhitecturi; acceptarea FFT/DCT folosește referințe numerice și toleranțe explicite, nu egalitatea digesturilor.

## Ce rămâne pentru măsurare

Confirmarea celor 12 ferestre și a stărilor ERROR/DONE cu intrările digitale PPK2, alimentarea autonomă exclusiv la 3V3, verificarea tensiunii și frecvențelor reale, plus pregătirea punților Nucleo conform [protocolului](PROTOCOL.md). Aceste verificări nu au fost substituite cu timpii UART sau cu testele pe PC.
