# Energy Profiling

Firmware și analiză pentru refacerea măsurătorilor ESP32 / RP2040 / **NUCLEO-F446RE** cu Nordic PPK2. Campania curentă este `energy-profiling-v2-f446`; STM32F446 înlocuiește F411. Rezultatele testării pe plăci se găsesc în [raportul hardware](docs/HARDWARE_VALIDATION.md). Măsurătorile de energie cu PPK2 rămân de efectuat.

Un singur nucleu C execută 12 algoritmi, pe intrări identice între plăci, cu numerele de apeluri din notele experimentului original. Adaptoarele folosesc ESP-IDF, Pico SDK și CMSIS pentru STM32. Intrările digitale PPK2 delimitează ferestrele și transmit identificatorul algoritmului. Firmware-ul nu calculează durata sau energia algoritmilor.

## Punctele de intrare

- [firmware/README.md](firmware/README.md): specificația completă a firmware-ului de benchmark — compilare, date, algoritmi, memorie, configurația plăcilor și limitele ferestrelor măsurate.
- [config/experiment.json](config/experiment.json): ordinea, repetările, volumul intrării, frecvențele țintă, pinii și pauzele.
- [firmware/common/bench_runner.c](firmware/common/bench_runner.c): secvența autonomă și oprirea la eroare.
- [firmware/common/kernels](firmware/common/kernels): implementările comune și verificările rezultatelor.
- [firmware/targets](firmware/targets): adaptoarele și build-urile pentru cele trei plăci.
- [data/manifest.json](data/manifest.json): definiția exactă și SHA-256 pentru cele trei intrări binare/hex.
- [docs/PROTOCOL.md](docs/PROTOCOL.md): montaj, stări, delimitarea energiei și pașii de măsurare.
- [tools/analyze_capture.py](tools/analyze_capture.py): prelucrarea offline a capturilor PPK2/CSV.
- [docs/BUILD_AND_TEST.md](docs/BUILD_AND_TEST.md): compilare și verificări.
- [docs/VALIDATION.md](docs/VALIDATION.md): verificările efectuate și ce rămâne pentru pilot.

Firmware-ul de benchmark este compilat cu **`BENCH_DIAGNOSTICS=OFF`**. Aplicația nu transmite mesaje seriale, iar UART/USB de diagnostic sunt dezactivate. Placa rulează autonom, cu USB, UART și programator deconectate în timpul achiziției; PPK2 citește stările GPIO. Imaginile curente și hashurile lor sunt în [CURRENT_FIRMWARE.json](CURRENT_FIRMWARE.json). Fișierele vechi F411 și primele build-uri rămân evidență istorică, nu imagini pentru campania curentă.

## Semnalele PPK2

| Canal | Semnal | ESP32 GPIO | Pico GPIO | STM32 |
|---|---|---:|---:|---|
| D0 | RUN | 18 | 2 | PC0 |
| D1 | ALG_ID bit 0 | 19 | 3 | PC1 |
| D2 | ALG_ID bit 1 | 21 | 4 | PC2 |
| D3 | ALG_ID bit 2 | 22 | 5 | PC3 |
| D4 | ALG_ID bit 3 | 23 | 6 | PC4 |
| D5 | IDLE_VALID | 25 | 7 | PC5 |
| D6 | ERROR | 26 | 8 | PC6 |
| D7 | DONE | 27 | 9 | PC7 |

Fiecare pin este ieșire MCU către intrare PPK2. LOGIC VCC se leagă la 3V3 de pe partea DUT măsurată, iar masele se conectează conform manualului. În Source Meter, PPK2 alimentează placa prin VOUT → 3V3; USB/programatorul plăcii se deconectează pentru achiziție. Pinii și oscilatorul plăcii fizice trebuie verificați înaintea campaniei.

## Secvența

```text
boot + configurare + pregătire
→ 5 s repaus activ marcat IDLE_VALID
→ RLE → Delta → LZ77 → Huffman → AES → SHA → ChaCha → CRC → FFT → FIR → IIR → DCT
→ DONE + repaus final
```

Între algoritmi: RUN coboară, se verifică rezultatul și configurația, se pregătește următoarea sarcină, apoi există 1 s de repaus activ. ID-ul se stabilizează încă 1 ms înainte de RUN. Cele 5 s inițiale încep după inițializare; timpul fizic de la aplicarea alimentării include și bootul, pe care îl observăm separat în PPK2. Repausul este CPU treaz cu așteptare de control, **nu deep sleep sau modul hardware Standby**.

ERROR oprește seria și o face nevalidă; DONE apare numai după toate cele 12 verificări reușite. Nu există apeluri de încălzire suplimentare sau cronometrare `micros()`/`millis()` în runner. Bufferele reutilizabile elimină alocările heap din RUN; această schimbare față de biblioteca istorică este deliberată.

## Verificări rapide pe PC

```powershell
python tools/generate_inputs.py --check
cmake -S . -B build/host -G Ninja
cmake --build build/host
ctest --test-dir build/host --output-on-failure
```

Testele runnerului folosesc hardware și algoritmi simulați pentru a verifica exact controlul suitei și căile de eroare. Testele funcționale separate verifică algoritmii reali față de referințe. Compilarea pentru MCU și testele pe PC nu înlocuiesc pilotul fizic și verificarea frecvenței, a tensiunii și a semnalelor PPK2.
