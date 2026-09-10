# Compilare și verificări

Comenzile se rulează din rădăcina `Energy Profiling`. SDK-urile externe și directoarele intermediare de build nu sunt codul experimentului. Sursele, intrările, configurația și artefactele livrate au hashuri separate.

## Verificări pe PC

Sunt necesare Python 3.11+, GCC, CMake și Ninja. Nu sunt necesare module Python externe pentru verificarea nucleelor și parserului.

```powershell
python tools/generate_inputs.py --check
python tests/kernel_tests/test_kernels.py
python -m unittest discover -s tests -p test_capture_analysis.py -v
cmake -S . -B build/host -G Ninja
cmake --build build/host
ctest --test-dir build/host --output-on-failure
```

Verificările de kernel compilează C original din acest proiect pe PC și îl compară cu referințe independente, inclusiv la coruperea intenționată a ieșirii. Testele runnerului folosesc hardware și algoritmi simulați și verifică ordinea, N, pauzele și oprirea la eroare. Parserul este testat cu date sintetice pentru care intervalele, curenții și rezultatele sunt cunoscute. Detalii: [testele nucleelor](../tests/kernel_tests/README.md), [formatul capturii](capture_format.md).

`generate_inputs.py --check` nu modifică fișierele. Rularea fără `--check` regenerează deliberat datele și antetele din definiția scriptului și manifestul configurației. Referințele numerice sunt înghețate în `bench_golden.h`; schimbarea datelor necesită regenerarea și reverificarea lor explicită, conform README-ului testelor.

## Pico și STM32

Versiunile SDK și hashurile arhivelor sunt fixate în fișierele `sdk.lock.json` ale țintelor. Scriptul de descărcare verifică integritatea arhivelor și a arborilor extrași. El nu folosește o ramură Git flotantă și nu modifică instalări globale.

```powershell
python scripts/fetch_native_sdks.py --help
Get-Help scripts/build_arms.ps1
```

Argumentele pentru directoarele SDK și toolchain sunt explicite în script și în README-urile țintelor. Acest proiect a fost compilat pentru ARM cu GNU Arm Embedded 9.2.1; bibliotecile de runtime și compilatorul exact se fixează pentru campanie. Pico folosește SDK 2.2.0; STM32 folosește cmsis-device-f4 v2.6.11 și CMSIS_5 5.9.0, cu acces explicit la registre, fără un runtime Arduino/HAL periodic.

Pentru compilare directă STM32, sunt necesare căile `ARM_GCC_BIN`, `STM32_CMSIS_DEVICE_PATH` și `CMSIS_CORE_PATH`. Pentru Pico sunt necesare `PICO_SDK_PATH` și toolchain-ul ARM pe PATH. Folosiți comenzile complete din [ținta STM32](../firmware/targets/stm32f446/README.md) și [ținta Pico](../firmware/targets/rp2040/README.md).

## ESP32

Necesită ESP-IDF **5.5.4**, toolchain-ul Espressif recomandat de această versiune și mediul Python corespunzător. Nu reutilizați automat mediul Python al unei versiuni majore diferite de ESP-IDF. Configurația este verificată la compilare și apoi la pornire.

Din terminalul ESP-IDF pregătit pentru 5.5.4:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32 build
```

Build-ul produce binarul aplicației, bootloaderul și tabela de partiții. Acestea se păstrează împreună, cu argumentele de flash; aplicația `.bin` nu este singură o imagine completă pentru o placă goală. Programările și rezultatele pe plăci sunt în [raportul hardware](HARDWARE_VALIDATION.md). Configurația de măsurare are CPU 240 MHz, un singur nucleu FreeRTOS, radio neinițializat, PM și task watchdog dezactivate, loguri și consolă de aplicație oprite. Întreruperile de sistem rămân parte documentată a platformei ESP-IDF.

## Ce mai trebuie verificat fizic

Înainte de măsurători: tensiunea la DUT, pinii, markerii exportați și frecvența fizică. F446 folosește HSI intern nominal de 16 MHz și PLL pentru 100 MHz; registrele și funcționarea sunt verificate, însă frecvența reală și deriva HSI necesită validare externă. Testele funcționale cu UART/USB și alimentare de la PC nu reprezintă măsurători de energie. Montajul Nucleo pentru alimentare directă 3V3 are cerințe de punți explicate în protocol.

## Profiluri de diagnostic

Opțiunea CMake `-DBENCH_DIAGNOSTICS=ON` activează mesajele de test; `OFF` este implicit și elimină diagnosticul din imaginea de măsurare. Pentru ESP32 se folosesc directoare de build distincte:

```powershell
idf.py -C firmware/targets/esp32 -B build/esp32-diagnostic -DBENCH_DIAGNOSTICS=ON build
idf.py -C firmware/targets/esp32 -B build/esp32-measurement -DBENCH_DIAGNOSTICS=OFF build
```

Pe ARM, `scripts/build_arms.ps1 -Diagnostics` selectează diagnosticul, iar omiterea opțiunii selectează măsurarea. Helperul folosește F446; F411 este arhivă și compilarea lui în campania curentă este blocată. Diagnosticul USB Pico necesită submodulul TinyUSB fixat de Pico SDK și variabila de mediu `PICO_TINYUSB_PATH`; pregătirea este explicată în [ținta Pico](../firmware/targets/rp2040/README.md).

`tools/serial_validation.py` necesită suplimentar modulul Python `pyserial`. Înregistrează BOOT, cele 12 perechi START/PASS, numerele exacte de apeluri și DONE, respingând ERROR și secvențele nevalide. Marcajele temporale ale logului provin de la PC și nu sunt durate de benchmark. Exemplele și starea reală a plăcilor sunt în [raportul hardware](HARDWARE_VALIDATION.md).

```powershell
python -m unittest discover -s tests -p test_serial_validation.py -v
```
