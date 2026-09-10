# Verificări efectuate

Data: 9 septembrie 2026. Campania curentă folosește NUCLEO-F446RE. Toate cele trei plăci au trecut testele funcționale; logurile și imaginile programate sunt în [raportul hardware](HARDWARE_VALIDATION.md). Măsurătorile de energie cu PPK2 rămân de efectuat.

| Verificare | Rezultat |
|---|---|
| Algoritmi reali C, comparați cu referințe independente | 119 verificări trecute pentru toate cele 12 nuclee; ieșirea coruptă este respinsă pentru fiecare nucleu |
| Parser PPK2/CSV | 19 teste trecute, inclusiv integrare pe ferestre cunoscute, capturi incomplete și semnalizare nevalidă |
| Runner pe PC | 6/6 teste trecute: trei plăci, diagnostic OFF/ON; ordinea, N, pauzele, șapte căi de eroare și absența logării în RUN/IDLE sunt verificate |
| Colector serial | 5 teste trecute; respinge câmpuri greșite, N greșit, ERROR după DONE și evenimente incomplete |
| Intrări și antete generate | 10 fișiere conforme cu generatorul și configurația |
| Numere de apeluri | Toate cele 36 de valori algoritm/placă coincid cu tabelul recuperat din experimentul inițial |
| ESP32, RP2040 și STM32F446RE | Profilele diagnostic și measurement compilate; sursele și artefactele au manifestele SHA-256 verificate |

Rezultatele detaliate ale nucleelor se găsesc în [results.json](../tests/kernel_tests/results.json). Celelalte teste pot fi reproduse prin [comenzile de verificare](BUILD_AND_TEST.md). Parserul este verificat pe capturi sintetice; compatibilitatea cu exportul real folosit în laborator trebuie confirmată în pilot.

Fiecare director de artefacte păstrează binarele, simbolurile și proveniența compilării:

- [ESP32: verification.json](../firmware/targets/esp32/build_verified/measurement/verification.json), cu aplicație, bootloader și tabelă de partiții.
- [RP2040: verification.json](../firmware/targets/rp2040/build_verified/measurement/verification.json), cu imagine UF2.
- [STM32: verification.json](../firmware/targets/stm32f446/build_verified/measurement/verification.json).

Inspectarea codului compilat confirmă păstrarea nucleelor și a buclei cu număr fix de apeluri. Pentru ESP32 și STM32, DCT conține instrucțiuni aritmetice FPU. Aritmetica `double` nu este prezentată drept accelerată hardware. Scrierile GPIO păstrează delimitarea RUN și activarea simultană a DONE cu repausul final.

Profilul este explicit: ESP32 240 MHz, un nucleu, Wi-Fi/Bluetooth neinițializate; RP2040 133 MHz, un nucleu; STM32F446RE 100 MHz, FPU activă, HSI intern nominal de 16 MHz și magistrale APB1/APB2 de 25/50 MHz. Firmware-ul verifică configurația la execuție. Frecvența fizică, tensiunea reală și semnalele digitale exportate trebuie confirmate conform [protocolului de pilot](PROTOCOL.md).

Codul comun corectează erorile algoritmice și de memorie identificate în sursele vechi și folosește buffere statice. De aceea păstrarea volumului și a numărului de apeluri nu face noile rezultate echivalente cu măsurătorile istorice.

Fișierele de evidență pot conține căile absolute ale directorului temporar în care au fost compilate. Aceste căi consemnează compilarea efectuată; comenzile pentru o compilare nouă se execută din rădăcina proiectului conform documentației. Manifestul `.delivery_manifest.json` de la rădăcină identifică fișierele copiate în folderul de livrare.

Binarele de diagnostic sunt păstrate separat în subdirectoarele `build_verified/diagnostic`. Fișierele aflate direct în vechile directoare `build_verified` aparțin primei etape F411 și nu corespund configurației curente. Manifestele lor originale au rămas neschimbate ca evidență istorică.
