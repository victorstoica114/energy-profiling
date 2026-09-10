# Comportamentul firmware-ului și al prelucrării PPK2

Specificație verificată față de cod la **10 septembrie 2026**, pentru campania **`energy-profiling-v2-f446`**. Acest document este baza tehnică pentru descrierea metodei în articol. Descrie implementarea existentă, inclusiv limitele ei.

**Firmware-ul de măsurare nu transmite mesaje de diagnostic și nu necesită USB sau UART conectate la placă.** Stările sunt comunicate prin opt ieșiri GPIO către intrările digitale PPK2. Ultimele imagini programate pe cele trei plăci, la 9 septembrie 2026, au fost variantele `measurement`, cu `BENCH_DIAGNOSTICS=OFF`.

Documentul descrie exclusiv firmware-ul utilizat la benchmark. Evidențele testelor sunt păstrate în [raportul de validare](../docs/HARDWARE_VALIDATION.md).

## 1. Identitatea experimentului și sursele de adevăr

| Element | Fișierul care îl definește |
|---|---|
| Ordine, repetări, plăci, frecvențe, pini, pauze | [experiment.json](../config/experiment.json) |
| Imagini programate, profile și SHA-256 | [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json) |
| Intrările binare și definițiile lor | [manifestul datelor](../data/manifest.json), [generator](../tools/generate_inputs.py) |
| Secvența autonomă | [bench_runner.c](common/bench_runner.c), funcția `bench_main` |
| Adaptorul algoritmilor, memoria și verificările | [bench_kernels.c](common/kernels/bench_kernels.c) |
| Implementările efective | [bench_algorithms.c](common/kernels/bench_algorithms.c), [antet privat](common/kernels/bench_original_private.h) |
| Contractul de platformă și motivele de eroare | [bench_platform.h](common/include/bench_platform.h) |
| Integrarea capturilor | [analyze_capture.py](../tools/analyze_capture.py) |

Cheia logică `stm32` din manifest înseamnă acum **NUCLEO-F446RE / STM32F446RET6**, nu F411. Directorul [targets/stm32](targets/stm32/README.md) și primele artefacte păstrate direct în directoarele `build_verified` sunt istorice. CMake blochează explicit recompilarea țintei F411 în configurația curentă.

SHA-256 al manifestului experimentului descris aici:

```text
618da7f1177a7e51427990ca6a4ed2693af8c41940297596813aa12e75387b7b
```

Notație: **L = 2048** este lungimea intrării unui apel; **R** este numărul de apeluri pentru un algoritm pe o placă; **M** este numărul de probe PPK2 dintr-o fereastră. Normalizarea FFT la L nu este împărțirea energiei la R.

## 2. Limbaj, biblioteci și compilare

Implementările comune sunt scrise în **C**. Adaptoarele de platformă configurează hardware-ul prin SDK-urile native sau CMSIS. CMake și Ninja organizează compilarea; nu sunt compilatoarele propriu-zise. Python generează intrările/referințele și prelucrează capturile; PowerShell automatizează unele comenzi de build pe Windows.

| Țintă actuală | SDK / suport | Compilator verificat | Dialect efectiv pentru unitățile C comune |
|---|---|---|---|
| ESP32-D0WD-V3, rev. 3.1 | ESP-IDF 5.5.4 | Espressif GCC 14.2.0, `esp-14.2.0_20260121`, Xtensa | `-std=gnu17` |
| Raspberry Pi Pico, RP2040 | Pico SDK 2.2.0 | GNU Arm Embedded GCC 9.2.1, `20191025` | `-std=gnu11` |
| NUCLEO-F446RE | cmsis-device-f4 v2.6.11, CMSIS_5 5.9.0 | Același GNU Arm Embedded GCC 9.2.1 | `-std=gnu11` |

Prin urmare, formularea exactă este **„implementare comună în C, compilată ca GNU C17 pe ESP32 și GNU C11 pe ARM”**, nu „toate imaginile sunt compilate în C11”. Startup-ul, runtime-ul și bibliotecile SDK pot include și C++, assembler sau cod ROM.

Nucleele provin din biblioteca scalară recuperată din proiectul original realizat de Noela Pirleci, cu modificările documentate mai jos. AES, SHA, ChaCha20, CRC și DSP nu sunt înlocuite cu apeluri către acceleratoare criptografice sau biblioteci DSP ale producătorilor. Funcțiile matematice și runtime-ul rămân însă dependente de platformă; acest experiment compară implementările pe plăcile și stivele software configurate, fără a izola efectul exclusiv al setului de instrucțiuni.

### Opțiunile care influențează rezultatul

Pentru codul comun, comenzile arhivate au efectiv:

```text
-O2 -fno-lto -fno-fast-math -ffp-contract=off
```

| Opțiune | Semnificație în acest experiment |
|---|---|
| `-O2` | Optimizarea obișnuită a codului este activă. Nu este o compilare „fără optimizare”. |
| `-fno-lto` | Nu se aplică optimizarea LTO între unități în etapa de legare. Transformările și inlining-ul permise în fiecare unitate rămân posibile. |
| `-fno-fast-math` | Nu se activează pachetul de relaxări numerice `fast-math`. Acesta ar permite ipoteze și transformări care pot schimba rezultatele floating point. |
| `-ffp-contract=off` | Nu se contractă expresiile floating point, de exemplu în operații multiply-add fuzionate. |

Explicația opțiunilor: [manualul GCC 14.2](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Optimize-Options.html). Pentru ABI-ul FPU ARM: [opțiunile ARM GCC 9.2](https://gcc.gnu.org/onlinedocs/gcc-9.2.0/gcc/ARM-Options.html).

Aceste opțiuni nu garantează rezultate floating point identice la nivel de biți pe toate platformele și nu împiedică singure eliminarea muncii neobservabile. Wrapperul `bench_kernel_run` este `noinline`, unitățile sunt separate, runnerul are bariere de compilator, rezultatele sunt consumate și există evidențe de inspecție a binarelor. Nu se presupune că toate bibliotecile precompilate/SDK folosesc aceleași opțiuni ca nucleele comune.

Pe Pico, comenzile includ `-O3` introdus de configurația SDK și apoi **`-O2`**, care este nivelul efectiv. Comenzile comune ESP32 arhivate folosesc `-O2`; nu li se atribuie aceeași secvență. Sunt păstrate `compile_commands.json`, opțiunile specifice țintei și manifestele surselor în arhivele fiecărui profil. ARM folosește Thumb pentru Cortex-M0+ / Cortex-M4; F446 adaugă `-mfpu=fpv4-sp-d16 -mfloat-abi=hard`.

Comenzile complete și pregătirea dependențelor sunt în [BUILD_AND_TEST.md](../docs/BUILD_AND_TEST.md) și README-urile țintelor. Versiunile/hashurile SDK sunt fixate în `sdk.lock.json`; arhivele verificate identifică și compilatoarele efectiv folosite.

## 3. Intrările: octeți exacți și interpretare

Firmware-ul include tablouri C constante. Nu generează date aleatoare la pornire, nu citește ADC și nu primește date prin UART. Fișierele `.hex` reprezintă lizibil aceiași octeți ca `.bin`; algoritmii nu procesează textul ASCII al reprezentării hex.

### Compresie — ID 1–4

Se construiește un bloc de 256 de octeți:

```text
00 repetat de 32 ori
FF repetat de 32 ori
rampa 00 01 02 ... 3F                 (64 octeți)
00 00 01 01 02 02 03 03 10 20 30 40 AA 55 AA 55
    ultimul motiv de 16 octeți repetat de 8 ori
```

Întreg blocul este repetat de **8 ori**, rezultând 2048 de octeți. Nu este un corpus de texte sau un model universal al datelor IoT.

### Criptografie și CRC — ID 5–8

Intrare deterministă xorshift32. Starea inițială este `0x1A2B3C4D`. Pentru fiecare dintre cei 2048 de octeți:

```c
/* Operații unsigned pe 32 de biți, modulo 2^32. */
s ^= s << 13;
s ^= s >> 17;
s ^= s << 5;
data[i] = s & 0xFF;
```

Se emite octetul inferior după actualizarea completă. Acesta este un set de test fix; nu sunt generate mesaje, chei sau nonce-uri noi între apeluri.

### DSP — ID 9–12

O perioadă de 128 de valori este definită prin:

```text
u[n] = floor(128 + 100 * sin(2*pi*n/128) + 0.5), n = 0..127
```

Perioada se repetă de **16 ori**. Intrarea are **2048 eșantioane numerice `uint8_t`**, minimum 28, maximum 228 și media 128. Nu este memorie `float` reinterpretată ca octeți. Nu se scade componenta continuă și nu se aplică o fereastră spectrală. Nu este definită aici o frecvență fizică de eșantionare a semnalului; cei 100 kS/s ai PPK2 descriu instrumentul de curent, nu această intrare DSP.

Fișierele înghețate sunt autoritatea pentru octeții exacți. Regenerarea cu o bibliotecă matematică diferită nu este acceptată automat doar fiindcă folosește aceeași formulă.

| Fișier, 2048 B fiecare | SHA-256 |
|---|---|
| [compression.bin](../data/compression.bin) | `44a2a279b86d1e7d98c24c5bd341a66adec17470de9e7b0ffa4ffc7092b7dab2` |
| [crypto.bin](../data/crypto.bin) | `b81c57d8f1f5c17f190e279e86f781dee155b05a779fe741a12a6bfacde47b23` |
| [dsp.bin](../data/dsp.bin) | `f7ed02ed3c339a9290b4d5a9981e472ae967a86d8d3e2735948c819650a28cb7` |

`bench_kernel_prepare` copiază intrarea în RAM **o singură dată înaintea lotului**. Toate R apeluri folosesc aceeași intrare neschimbată; ieșirea este suprascrisă și nu devine intrarea următorului apel.

## 4. Ordinea și numărul de apeluri

R este preluat din manifest și devine o constantă a configurației compilate. Numerele provin din notele RAW originale, nu din presupunerea că toate sursele recuperate executau aceleași bucle.

| ID | Algoritm | ESP32 R | Pico R | F446 R |
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

Nu există durată țintă care să determine când se oprește un algoritm. O fereastră RUN conține întregul lot R; nu există marcaj GPIO pentru fiecare apel. Nu se introduc pauze între apelurile aceluiași lot. La primul eșec, bucla este întreruptă și seria devine nevalidă.

## 5. Contractul fiecărui algoritm

Toate dimensiunile de mai jos privesc **un apel**, cu L=2048. Sunt dimensiuni ale ieșirilor în RAM, nu transmisii efectuate. Crearea headerelor, inițializarea algoritmică și conversiile descrise aici intră în RUN.

### 1 — RLE

Scrie perechi `(număr, valoare)`, fiecare componentă de un octet. Numărul este 1..255; un șir mai lung se împarte în mai multe perechi. Nu există header de lungime. Parcurgerea reîncepe la fiecare apel.

Pentru intrarea curentă rezultă **2592 B**, față de 2048 B la intrare. Această variantă RLE extinde datele cu 26,5625%; nu se afirmă că economisește transmisia pe acest pattern. Limita generală este 2L=4096 B.

### 2 — Delta

`d[0]=x[0]`; pentru restul, `d[i]=(x[i]-x[i-1]) mod 256`. Conversia la `uint8_t` definește diferențele modulo 256. Ieșirea are **2048 B**. Este o transformare diferențială reversibilă, fără reducere proprie a numărului de octeți.

### 3 — LZ77

Formatul implementat este propriu: header de 4 B cu L little-endian, apoi tokenuri `(distanță:uint8, lungime:uint8, [literal:uint8])`. Literalul lipsește numai dacă potrivirea ajunge exact la sfârșitul intrării. Istoricul și lookahead-ul sunt limitate la 255 B; potrivirile suprapuse sunt permise.

Căutarea este exhaustivă, de la poziția cea mai veche la cea mai recentă. Egalitățile păstrează prima potrivire, deci distanța cea mai mare. Nu există prag minim de potrivire; lungimea 1 este acceptată. Un literal fără potrivire are distanță și lungime zero. Nu persistă un dicționar între apeluri.

Intrarea curentă produce **1530 B**, header inclus, cu 509 tokenuri. Limita de stocare a variantei este `4+3L`.

### 4 — Huffman

Codare canonică pentru alfabetul de 256 de octeți. Fiecare apel reconstruiește frecvențele, lungimile codurilor și codurile canonice. Mediul de lucru este static, dar este reinițializat în apel.

Construirea lungimilor este „treeless”, prin reunirea ramurilor. Structura numită intern `heap` este o listă cu extragere liniară a minimului, nu un binary heap. Egalitățile de frecvență sunt rezolvate prin `branch_id` mai mic. Codurile finale sunt ordonate după lungime și apoi după valoarea simbolului; lungimile peste 32 sunt respinse. Un singur simbol primește un cod de un bit.

Frame-ul complet, creat în RUN:

```text
4 B: lungimea originală, uint32 little-endian
4 B: numărul de biți valizi din payload, uint32 little-endian
256 B: lungimea codului pentru fiecare simbol 0..255; zero = absent
payload: biți MSB-first; ultimul octet completat cu zerouri
```

Headerul are 264 B. Intrarea curentă are 68 de simboluri distincte și produce 9400 biți de payload, adică 1175 B; **total 1439 B**. Nu este măsurată doar codarea pe o tabelă pregătită anterior.

### 5 — AES-128

AES-128 scalar software, în **ECB cu padding PKCS#7**. Cheia este formată din cei 16 octeți ASCII `0123456789abcdef`, fără terminator NUL. Nu există IV, autentificare sau decriptare în workload.

Expansiunea cheii la 176 B se execută din nou la fiecare apel. Cei 2048 B produc 128 de blocuri de date și încă un bloc de padding, format din 16 octeți `0x10`: **2064 B la ieșire**. Sunt incluse expansiunea, copierea blocurilor, paddingul și toate rundele de criptare.

### 6 — SHA-256

SHA-256 scalar, cu stare și operații pe `uint32_t`. Reinițializează cele opt cuvinte ale stării la fiecare apel. Include message schedule, transformările, paddingul, lungimea în biți și serializarea digestului.

Pentru 2048 B se procesează 32 de blocuri de date și un bloc final de padding. Ieșire: **32 B**, cu cuvintele digestului serializate big-endian. Nu este HMAC.

### 7 — ChaCha20

Variantă cu cheie de 256 biți, nonce de 96 biți și contor de bloc de 32 biți, 20 de runde. Cheia este formată din cei 32 de octeți ASCII `0123456789abcdef0123456789abcdef`, fără NUL. Nonce-ul are 12 octeți zero.

Contorul pornește de la **1 la fiecare apel**. Se generează 32 de blocuri de 64 B, serializate explicit little-endian și combinate XOR cu intrarea. Ieșire: **2048 B**, fără padding sau tag Poly1305. Nu se continuă fluxul de cheie între apeluri. Cheia/nonce-ul fixe definesc acest experiment repetabil, nu un protocol de comunicație implementat aici.

### 8 — CRC32

CRC reflectat, calculat bit cu bit, cu polinomul `0xEDB88320`, stare inițială `0xFFFFFFFF` și complement final. Sunt opt pași de bit pentru fiecare octet. Adaptorul scrie rezultatul în **4 B little-endian**.

Nu se folosesc perifericul CRC sau o tabelă de lookup. CRC32 ca workload este distinct de CRC-ul rezultatului calculat după fiecare lot pentru evidență.

### 9 — FFT

FFT radix-2 iterativă, cu bit reversal și semn negativ în exponent. Intrarea numerică `uint8_t` este convertită la float; partea imaginară pornește de la zero. Pentru L=2048 există 11 etape.

Tablourile real/imag sunt `float`. Twiddle-urile `cos`/`sin` și intermediarii butterfly sunt `double`, apoi valorile stocate revin în float. Magnitudinea folosește calculul cu `sqrt` în double înainte de conversia rezultatului.

Ieșire: **2048 valori float, 8192 B**, definite prin `abs(DFT(x)[k])/L`, pentru întreg spectrul k=0..L−1. Nu se exportă faza, perechi complexe, PSD sau un spectru unilateral cu amplitudinile dublate. Inițializarea scratch-urilor, conversiile, twiddle-urile și magnitudinile fac parte din apel; memoria scratch nu se alocă din heap.

### 10 — FIR

Filtru cu coeficienți întregi `[1,2,3,2,1]`:

```text
y[n] = floor((x[n]+2*x[n-1]+3*x[n-2]+2*x[n-3]+x[n-4])/9)
x[n] = 0 pentru indicii negativi
```

Acumulatorul este `uint32_t`, ieșirea **2048 B `uint8_t`**. Divizorul rămâne 9 la începutul vectorului, chiar când lipsesc termeni. Sursa recalculează suma coeficienților în bucla fiecărui eșantion. Istoricul nu continuă între apeluri. Acesta este un workload întreg, nu un filtru floating point.

### 11 — IIR

Recurența efectivă este:

```text
y[n] = Q((x[n]+2*x[n-1]+x[n-2]+y[n-1]+y[n-2])/4)
Q(v) = trunchiere către întreg și limitare la [0,255]
x[n] = y[n] = 0 pentru indicii negativi
```

Calculele implementării păstrate folosesc `double`, dar feedbackul citește **ieșirile uint8 deja cuantizate și saturate**. Bufferul este rescris în ordine, astfel încât fiecare apel pornește fără istoric din apelul anterior. Ieșire: **2048 B**.

Tabloul intern de feedback `[1,1,1]` nu reprezintă numitorul standard `[1,1,1]`; elementul `a[0]` nu este folosit de acea buclă. Nucleul liniar necuantizat are numărător `[0.25,0.5,0.25]`, numitor `[1,-0.25,-0.25]` și câștig DC **2**. Sistemul implementat include cuantizare și saturare și nu este descris ca filtru liniar cu câștig unitar.

Pe intrarea curentă, **1006/2048 ieșiri, adică 49,12109375%, sunt limitate la 255**. Acesta este comportamentul care va fi măsurat. Corpul filtrului IIR a fost păstrat față de sursa originală; recurența și verificarea lui au fost explicitate.

### 12 — DCT

DCT-II directă, ortonormală:

```text
X[k] = alpha[k] * sum(x[n] * cos(pi*k*(2*n+1)/(2*L)), n=0..L-1)
alpha[0] = sqrt(1/L)
alpha[k>0] = sqrt(2/L)
```

Suma, produsele, normalizarea cu `sqrtf`, apelurile `cosf` și rezultatul folosesc float; literalul PI și unele expresii de inițializare trec prin conversia documentată în sursă. Nu este o implementare integral în double.

Pentru fiecare contribuție se calculează mai întâi faza întreagă `k*(2*n+1) mod (4*L)`, apoi unghiul float. Reducerea păstrează formula matematică, limitează argumentul pentru `cosf` și are cost în RUN. Algoritmul rămâne **O(L²)**, fără factorizare rapidă sau tabelă de cosinus precalculată. Ieșire: **2048 coeficienți float semnați, 8192 B**, fără clipping la 0..255.

## 6. Memorie, stare și verificarea rezultatelor

Există un singur workspace comun, **non-reentrant**; nu se execută algoritmi în paralel. Sunt folosite workspace-uri persistente statice și tablouri locale cu limite fixe pe stivă. Nu există apeluri `malloc`/`calloc`/`free` în nucleele măsurate. SDK-ul poate folosi alocări la inițializare; absența heap-ului din nucleu nu înseamnă absența sa din întregul firmware.

Workspace-urile explicite includ: copie de intrare 2048 B, ieșire byte 6408 B, ieșire float 8192 B, buffer de decodare 2048 B, două scratch-uri FFT a câte 8192 B și mediul Huffman. AES/SHA/ChaCha/Huffman folosesc și tablouri locale fixe. Hărțile de memorie ale binarelor sunt în arhivele profilelor.

Înaintea lotului, `prepare` validează ID/lungime, copiază intrarea, inițializează gardurile de memorie și recunoaște fixture-urile în afara RUN. API-ul permite lungimi până la 2048; FFT cere lungime nenulă putere a lui 2, DCT lungime nenulă. Campania folosește exclusiv 2048. Ieșirile criptografice și transformatele nu sunt acceptate de verificatorul firmware pentru o intrare nerecunoscută, chiar dacă `prepare/run` acceptă acea lungime.

Fiecare `run` verifică ID-ul activ, gardurile înainte și după nucleu, codul de retur și limitele aplicabile ieșirii. Gardurile sunt cuvinte de control în jurul bufferelor; nu demonstrează absența oricărui tip posibil de acces greșit în memorie.

**Verificarea algoritmică completă are loc o singură dată după lot, pe ultima ieșire.** Nu există R comparații complete cu referința în fereastra RUN.

| Rezultat | Verificare după lot |
|---|---|
| RLE, Delta, LZ77, Huffman | Decodare/inversare independentă și comparație cu toată intrarea; validarea formatului |
| AES, SHA, ChaCha20, CRC32 | Compararea integrală cu rezultate de referință înregistrate |
| FIR, IIR | Recalculare independentă cu formule întregi și compararea tuturor octeților |
| FFT | Finit și `abs(actual-ref) <= 0.0001 + 0.00002*abs(ref)` pentru fiecare valoare |
| DCT | Finit și `abs(actual-ref) <= 0.01 + 0.00002*abs(ref)` pentru fiecare valoare |

Referințele sunt generate independent de funcțiile C măsurate. Valorile transformărilor sunt calculate în double pe gazdă și stocate în antetul MCU ca **constante float**, nu ca tablouri double. Valorile incluse și verificatorul utilizat în firmware: [bench_golden.h](common/kernels/bench_golden.h), [bench_kernels.c](common/kernels/bench_kernels.c).

După verificare, un CRC32 al întregii ultime ieșiri este păstrat în `volatile bench_result_digests[]`; numerele de apeluri sunt în `bench_completed_calls[]`. Digesturile FFT/DCT sunt calculate pe reprezentarea byte a float-urilor și nu sunt criterii de egalitate numerică între arhitecturi.

## 7. Secvența autonomă a profilului de măsurare

Firmware-ul rulează autonom, fără mesaje seriale. Stările din diagramă sunt niveluri GPIO.

```text
alimentare/reset
  -> boot și inițializarea platformei
  -> verificare platformă + pregătire RLE
  -> ID=0, IDLE_VALID=1: repaus activ nominal 5 s
  -> IDLE_VALID=0, ID=1, așteptare 1 ms + verificare platformă
  -> RUN=1: R apeluri RLE
  -> RUN=0: verificare lot/rezultat + digest
  -> pregătire Delta, ID=0, IDLE_VALID=1: repaus activ nominal 1 s
  -> aceeași secvență pentru ID=2 ... ID=12
  -> după validarea DCT: ID=0, DONE=1 și IDLE_VALID=1 simultan
  -> repaus activ nominal 2 s
  -> IDLE_VALID=0, DONE rămâne 1
  -> starea finală a platformei; fără reluarea suitei
```

Cele 5 s inițiale încep **după boot, inițializare și pregătirea primei sarcini**. Nu sunt exact primele 5 s de la aplicarea tensiunii. Baseline-ul este repaus activ cu CPU treaz, nu deep sleep și nu modul hardware Standby.

Cele 11 pauze dintre algoritmi sunt de 1 s IDLE_VALID, după verificarea rezultatului anterior și pregătirea celui următor. Distanța totală dintre ferestre poate fi mai mare. ID-ul este stabilit înaintea unei așteptări de 1 ms; între sfârșitul așteptării și frontul RUN se mai verifică platforma. Intervalul ID→RUN nu este promis ca exact 1 ms.

Nu există apeluri suplimentare de încălzire, dar nu se golește cache-ul și nu se resetează procesorul între repetări. Starea algoritmică este reinițializată; starea fizică a procesorului și a memoriei poate fi influențată de apelurile anterioare. R apeluri într-un lot nu sunt R replici statistice independente.

### Ce intră efectiv în RUN

Sunt incluse dispatch-ul wrapperului, gardurile/statusul fiecărui apel, inițializările algoritmice, conversiile/header-ele, calculul și scrierea ieșirii, testul de retur și incrementarea contorului. Expansiunea cheii AES, construirea codului Huffman și inițializarea scratch-urilor FFT sunt muncă măsurată.

Sunt în afara RUN copierea inițială a intrării în RAM, recunoașterea fixture-ului, pauzele, verificările configurației platformei, verificarea algoritmică completă a ultimei ieșiri și calculul digestului de evidență. Nu se folosește `micros()`/`millis()` pentru performanță, iar firmware-ul nu raportează durata sau energia algoritmilor.

Fereastra fizică include și revenirea din funcția care ridică RUN, respectiv apelul/prologul până la scrierea care îl coboară. Nu este o izolare perfectă a instrucțiunilor matematice. Barierele de compilator și barierele MMIO păstrează ordinea relevantă; costul buclei/GPIO și întreruperile platformei nu sunt scăzute automat.

### Erori

Runnerul memorează algoritmul și motivul, coboară RUN/IDLE/DONE, ridică ERROR și oprește secvența. Nu trece la algoritmul următor și nu reia singur testul.

| Motiv în `bench_failure_reason` | Semnificație |
|---:|---|
| 1 | Inițializare platformă eșuată |
| 2 | Configurație nevalidă înainte de pregătire |
| 3 | Pregătire nucleu eșuată |
| 4 | Configurație nevalidă înainte de RUN |
| 5 | Apel de nucleu eșuat |
| 6 | Număr de apeluri diferit de R |
| 7 | Configurație nevalidă după RUN |
| 8 | Verificare algoritmică eșuată |

Un fault sau o eroare internă a platformei poate opri execuția fără completarea acestor variabile. La un eșec foarte timpuriu, GPIO-urile pot să nu fie încă inițializate. Lipsa secvenței complete și a DONE invalidează captura, chiar fără un ERROR lizibil.

## 8. Configurația platformelor

| Parametru | ESP32 | Pico RP2040 | NUCLEO-F446RE |
|---|---|---|---|
| CPU nominal | 240 MHz | 133 MHz | 100 MHz |
| Sursa configurată | Cristal 40 MHz, PLL 480 MHz /2 | Cristal Pico 12 MHz, PLL_SYS | HSI intern nominal 16 MHz, PLL M=16/N=200/P=2 |
| Nucleu de aplicație | CPU0; CPU1 oprit de startup-ul unicore IDF | Core0; core1 rămas în așteptarea Boot ROM, fără aplicație lansată | Un singur Cortex-M4 |
| Floating point | Hardware single; double nu este presupus hardware | Fără FPU; implementări software Pico SDK/ROM | FPU single activă, hard-float ABI; double software |
| Runtime | ESP-IDF / FreeRTOS | Pico SDK, bare metal | CMSIS, bare metal |
| Timer folosit numai pentru pauze | GPTimer, 1 MHz | Timer hardware liber | TIM2, 10 kHz |
| Repaus după cele 2 s finale | Task suspendat, idle/scheduler RTOS | Buclă WFI | Buclă WFI |
| Stivă rezervată relevantă | Task principal 16 KiB | Core0 4 KiB, SCRATCH_Y | 16 KiB în linker |

**ESP32.** Wi-Fi și Bluetooth rămân neinițializate. Verificarea cere `esp_wifi_get_mode(...) == ESP_ERR_WIFI_NOT_INIT`, CPU raportat la 240 MHz și core0; simpla deconectare de la rețea nu ar satisface contractul. PM și tickless idle sunt dezactivate. Tick-ul FreeRTOS de 100 Hz și întreruperile de sistem rămân; task watchdog este dezactivat, interrupt watchdog rămâne activ, configurat la 300 ms. Benchmarkul nu maschează global întreruperile. APB este configurat la 80 MHz. GPTimer este pornit/citit/oprit pentru pauze, fără cronometrarea loturilor. UART0/1/2 sunt resetate și au ceasurile oprite; GPIO1/3 sunt dezactivate, fără pull.

**Pico.** `clock_get_hz` și contorul hardware de frecvență verifică ceasul sistemului. Acesta din urmă este raportat la `clk_ref`, cu acceptare 132867..133133 kHz; nu este calibrare față de un standard extern. UART0/1, USBCTRL și ADC sunt ținute în reset; `clk_usb` și `clk_adc` sunt oprite. GPIO0/1 nu au funcție activă sau pull. **PLL_USB nu este oprit**: configurația SDK folosește PLL_USB la 48 MHz pentru `clk_peri`. `clk_rtc` rămâne la valoarea nominală SDK de 46875 Hz. Oprirea USB nu înseamnă oprirea tuturor PLL-urilor. Operațiile float/double și funcțiile matematice pot folosi wrapper-ele software Pico SDK și Boot ROM.

**F446.** HSI elimină dependența de MCO-ul ST-LINK alimentat. Sunt verificate identitatea de dispozitiv `0x421`, flash 512 KiB, PLL-ul, trim-ul HSI implicit, divizoarele magistralelor, accesul FPU și stările perifericelor urmărite. AHB=100 MHz, APB1=25 MHz (`/4`), APB2=50 MHz (`/2`); TIM2 primește 50 MHz și prescaler 4999. FLASH are 3 wait states; prefetch și cache-urile de instrucțiuni/date Flash sunt activate. Regulatorul este în VOS scale1, fără overdrive. SysTick este oprit; TIM2 este folosit fără IRQ. Ceasurile USB FS/HS, DMA1/2 și CRC trebuie să fie oprite. USART2 are ceasul oprit, iar PA2/PA3 sunt în mod analog, fără pull. Un mic calcul cu operanzi float `volatile` verifică și funcționarea FPU.

ESP32 folosește flash de 4 MiB în mod DIO, la 40 MHz, cu PSRAM dezactivat. Pe Pico, SDK păstrează infrastructura implicită de alarm pool și handler-ul aferent; aplicația nu programează callback-uri periodice și nu maschează global întreruperile. Bare metal nu înseamnă automat absența tuturor întreruperilor.

Citirea registrelor și API-urile de ceas verifică **configurația**, nu frecvența fizică exactă a cristalului/HSI. Deriva HSI, tensiunea reală și integrarea cu PPK2 rămân verificări ale montajului. Nu se declară toate perifericele imaginabile oprite doar pentru că cele enumerate sunt dezactivate.

Pe ESP32, ROM-ul imutabil poate emite text la boot înaintea inițializării aplicației. Aplicația de benchmark nu transmite mesaje, iar UART-ul plăcii rămâne neconectat în timpul achiziției. Nu s-au modificat eFuse-uri pentru suprimarea textului ROM.

Surse: [adaptor ESP32](targets/esp32/main/platform_esp32.c), [configurație ESP32](targets/esp32/sdkconfig), [adaptor Pico](targets/rp2040/platform_rp2040.c), [adaptor F446](targets/stm32f446/platform_stm32f446.c), plus arhivele de compilare indicate în manifest.

## 9. GPIO, alimentare și LED-uri

| PPK2 | Funcție | ESP32 GPIO | Pico GPIO | F446 pin |
|---|---|---:|---:|---|
| D0 | RUN | 18 | 2 | PC0 |
| D1 | ID bit 0 | 19 | 3 | PC1 |
| D2 | ID bit 1 | 21 | 4 | PC2 |
| D3 | ID bit 2 | 22 | 5 | PC3 |
| D4 | ID bit 3 | 23 | 6 | PC4 |
| D5 | IDLE_VALID | 25 | 7 | PC5 |
| D6 | ERROR | 26 | 8 | PC6 |
| D7 | DONE | 27 | 9 | PC7 |

ID = D1 + 2×D2 + 4×D3 + 8×D4. În IDLE, ID este zero. În RUN, ID este 1..12 și rămâne constant. DONE și IDLE final sunt ridicate în aceeași scriere de stare; coborârea ulterioară a IDLE nu produce un impuls LOW pe DONE.

PPK2 în Source Meter alimentează DUT la setpoint 3300 mV prin VOUT→3V3, cu GND comun. LOGIC VCC se leagă la 3V3 măsurat. USB-ul și UART-ul DUT, programatoarele și alte căi de alimentare rămân deconectate în capturile de energie. USB-ul PPK2 către PC rămâne necesar achiziției și este distinct de USB-ul plăcii testate.

Nu există LED extern de marcare în noul protocol. LED-ul controlabil Pico GPIO25 și LED-ul Nucleo PA5 sunt puse LOW/off. Nu se afirmă că software-ul poate stinge orice LED de alimentare ori toate circuitele auxiliare ale oricărei variante de placă. Energia măsurată aparține domeniului de alimentare și montajului ales.

Nucleo cere pregătirea electrică pentru intrarea directă 3V3: ST-LINK separat fizic sau SB2 și SB12 deschise, conform manualului. De asemenea, rutarea PC0/PC1 depinde de punți. Detaliile conectorilor și configurația de alimentare sunt în [README F446](targets/stm32f446/README.md) și [protocol](../docs/PROTOCOL.md), pe baza [UM1724, secțiunea 7.5.3 și tabelul conectorilor](https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf). Oprirea UART în cod nu modifică fizic aceste legături.

## 10. Calculul offline din PPK2

Firmware-ul nu calculează energie și nu exportă timpi de execuție. `analyze_capture.py` folosește baza de eșantionare PPK2 la **100000 probe/s**, adică pas nominal **10 µs**, împreună cu GPIO-urile.

Pentru intervalul `[a,b)`, prima probă RUN=1 este inclusă, prima probă RUN=0 este exclusă:

```text
M = b - a
T_lot = M / fs
Q_lot = sum(I[a:b]) / fs
E_lot = V_const * Q_lot
T_apel = T_lot / R; Q_apel = Q_lot / R; E_apel = E_lot / R
```

Curentul este convertit în amperi. Implementarea folosește media incrementală a probelor înmulțită cu durata, echivalentă sumei dreptunghiulare până la rotunjirea floating point. Nu folosește integrarea trapezoidală. Suportul M/fs este distinct de distanța prima→ultima probă, `(M-1)/fs`.

Baseline-ul selectează **ultimele 200000 de probe**, adică 2 s, din primul repaus valid de 5 s. Se raportează separat repausurile marcate. **Baseline-ul nu se scade automat** din energia activă. Bootul, pregătirea și validarea din afara RUN nu sunt incluse în energia raportată pentru algoritm.

Fișierul citit nu furnizează tensiune eșantionată simultan. Implicit, energia folosește 3,3 V nominal din manifest. `--voltage` introduce o constantă declarată de operator, etichetată ca neverificată de software. `--voltage-uncertainty-v` o consemnează, dar **nu propagă automat incertitudinea în E** și nu construiește un buget complet de incertitudine.

Minimul, maximul și deviația standard populațională a curentului descriu probele din fereastră. Nu sunt intervale de încredere între experimente independente și nu înlocuiesc precizia instrumentului. Parserul nu agregă încă serii de porniri pentru statistici între capturi.

### Acceptarea unei capturi

Se cere o singură suită completă: exact 12 regiuni RUN în ordinea ID 1..12, ID stabil în fiecare, fără ERROR sau suprapuneri de stări incompatibile. Pauzele 5/1/2 s sunt verificate cu toleranță **±1%**, ca regulă de protocol, nu ca incertitudine calibrată.

DONE trebuie să coincidă cu începutul IDLE final în aceeași probă și să rămână HIGH. Parserul cere minimum 2 s de DONE și frontul de coborâre IDLE final; instrucțiunea operatorului este să înregistreze minimum **3 s după DONE**.

Parserul **nu numără independent apelurile R**, nu verifică cei 1 ms ID→RUN și nu autentifică placa sau firmware-ul prin GPIO. Operatorul asociază captura cu manifestul și binarul corecte. Resetările sau pierderile de date care lasă urme în protocol sunt respinse; lipsa oricărei pierderi nu este demonstrată doar de o bază temporală reconstruită uniform.

Valorile digitale necunoscute sunt tolerate numai în prefixul de pornire, înainte de sincronizarea validă, fără RUN/ERROR/DONE cunoscute HIGH. Stările mixte sunt respinse. Curentul finit negativ este permis numai înaintea primei probe IDLE_VALID complet definite; pentru probe complet definite, niciun marker de control nu poate fi activ. O probă parțial necunoscută poate avea IDLE_VALID cunoscut HIGH, însă interdicția RUN/ERROR/DONE HIGH rămâne. Valorile negative acceptate sunt numărate fără clipping sau reindexare. După sincronizare, curentul negativ respinge captura. NaN/Inf sunt respinse peste tot.

### Fișiere și unități

Formatul nativ acceptat este `.ppk2` formatVersion 2: ZIP cu `metadata.json`, `session.raw`, `minimap.raw`. O probă din session are float32 little-endian în µA și uint16 big-endian cu doi biți per canal: `01` LOW, `10` HIGH, `00` unknown, `11` mixed; D0 ocupă perechea cea mai puțin semnificativă. Minimap nu este folosit pentru metrici. Limita implicită este 60 milioane de probe, adică 10 minute; formatul și dimensiunile sunt validate, fără extracție pe disc.

CSV Nordic folosește explicit `Timestamp(ms)`, `Current(uA)` și D0..D7 sau șirul `D0-D7`, cu D0 primul. Pentru CSV generic se declară unitățile și coloanele; nu sunt ghicite după magnitudinea numerelor. Timestamp-urile și indicii opționali sunt verificate pentru discontinuități detectabile. Datele originale nu sunt modificate și rezultatele existente nu sunt suprascrise.

Schema și limitele complete, cu referințe la implementarea oficială Nordic verificată, sunt în [capture_format.md](../docs/capture_format.md). Compatibilitatea cu primul export real din laborator trebuie confirmată în pilot.

## 11. Imaginile de benchmark și starea măsurătorilor

Cele trei imagini `measurement`, cu `BENCH_DIAGNOSTICS=OFF`, sunt identificate prin SHA-256 în [CURRENT_FIRMWARE.json](../CURRENT_FIRMWARE.json). Pentru fiecare țintă, directorul `build_verified/measurement` păstrează binarul, comenzile native de compilare și evidențele verificării. Imaginile au fost programate pe plăci la 9 septembrie 2026.

Verificările funcționale și logurile sunt consemnate în [VALIDATION.md](../docs/VALIDATION.md) și [HARDWARE_VALIDATION.md](../docs/HARDWARE_VALIDATION.md). **Nu există încă o captură PPK2 care să valideze secvența GPIO și energia acestor imagini.** Compilarea, verificarea algoritmilor și programarea plăcilor nu înlocuiesc această probă.

Mai sunt necesare montajul exclusiv la 3V3, verificarea fizică a ceasurilor/tensiunii, a fronturilor și exportului, plus capturile independente. Numărul propus este minimum 10 porniri per placă; ordinea fixă și încălzirea/cache-ul trebuie luate în considerare. O singură placă fizică per model nu caracterizează variația între exemplare.

## 12. Diferențe față de codul și experimentul inițial

Acesta este un benchmark reparat și versionat. Păstrarea volumului de intrare și a repetărilor nu permite reutilizarea energiilor vechi ca rezultate ale noului cod.

| Aspect | Comportament curent care trebuie descris în articol |
|---|---|
| Platformă STM32 | F446RE, 100 MHz explicit, FPU activă și HSI; F411 și configurația recuperată de 96 MHz nu reprezintă această campanie |
| Măsurarea timpului | GPIO și baza PPK2; oprire după R apeluri, fără durate MCU folosite la performanță |
| Marcaj | Intrări digitale PPK2, fără LED extern de marcare |
| Date | Trei seturi deterministe definite byte cu byte; DSP numeric uint8, nu reinterpretare de memorie float |
| Memorie | Workspace-uri reutilizabile și tablouri locale cu limite fixe; costurile istorice malloc/free din FFT au fost eliminate |
| AES | Capacitate de ieșire suficientă pentru 2064 B, inclusiv blocul suplimentar PKCS#7 |
| Huffman | Sortare/caz un simbol/tie-break definite și reparate; header complet în RUN și scriere limitată la payload |
| LZ77 | Fără literal terminal suplimentar când match-ul ajunge la sfârșit; format complet definit |
| SHA/ChaCha/CRC | Deplasări unsigned unde sunt necesare și serializare explicită a rezultatelor; fără dependență tacită de byte order |
| FFT | Intrare numerică, ieșire float normalizată, număr de etape calculat întreg și scratch static |
| FIR/IIR | Variantele scalare originale păstrate; FIR întreg, IIR cuantizat/saturat cu recurența explicită |
| DCT | Unghi DCT-II corect, reducere de fază și coeficienți float semnați; fără clipping byte |

Sursele și capturile istorice nu sunt alterate de această documentare. Numele algoritmului singur nu identifică suficient workload-ul: variantele, datele, inițializarea inclusă, compilatorul și limita RUN fac parte din definiția lui.

## 13. Menținerea concordanței dintre cod, README și articol

Comenzile de mai jos se rulează din rădăcina proiectului:

```powershell
python tools/generate_inputs.py --check
```

Această verificare compară cele 10 fișiere generate fără să le modifice. Schimbarea datelor, cheilor, coeficienților, tipurilor numerice, algoritmilor, repetărilor, limitei RUN, compilatorului sau configurației platformei trebuie înregistrată ca o schimbare a experimentului. Se regenerează deliberat fișierele/referințele necesare, se rulează verificările potrivite și se păstrează noile binare/hashuri și loguri.

Antetele generate și rezultatele golden nu se editează manual ca să se potrivească unei ieșiri neașteptate. `CURRENT_FIRMWARE.json` și raportul hardware trebuie actualizate după o nouă programare verificată. Instrucțiuni de reproducere: [BUILD_AND_TEST.md](../docs/BUILD_AND_TEST.md).

La redactarea articolului se preiau comportamentele confirmate aici și rezultatele PPK2 efectiv obținute, păstrând distincte configurația declarată, verificarea software și verificarea fizică. Acest README nu transformă verificările funcționale sau valorile nominale în măsurători de energie.
