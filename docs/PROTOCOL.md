# Protocol de achiziție

Versiunea 1, candidat pentru pilot. Fișierul [experiment.json](../config/experiment.json) este sursa parametrilor; [manifestul datelor](../data/manifest.json) identifică octeții exacți. GPIO-urile din README sunt rezervate măsurării și se verifică pe variantele fizice ale plăcilor.

## Alimentare și captură

PPK2 în Source Meter la 3300 mV, VOUT la 3V3 și GND la placă. LOGIC VCC se leagă la 3V3 măsurat și canalele D0–D7 la ieșirile MCU. Conexiunile de instrumentare fac parte din montaj și se păstrează identice între capturi. Placa nu are USB, programator sau alte surse conectate în timpul achiziției. Intrările digitale înlocuiesc marcajele cu LED.

Se pornește captura înaintea alimentării DUT. Aplicația oficială Nordic Power Profiler se setează explicit la 100.000 probe/s, cu toate canalele digitale; se păstrează `.ppk2` și exportul CSV complet. Se salvează seria PPK2, versiunile hardware/firmware/aplicație, setările, placa și hashul binarului efectiv programat. Exportul se verifică pe o secvență de impulsuri cunoscută înainte de campanie. [Manual Nordic](https://docs.nordicsemi.com/r/bundle/nrf-connect-for-desktop/page/app/pc-nrfconnect-ppk/using_ppk_app.html).

## Interpretarea stărilor

Pentru NUCLEO-F446RE, alimentarea externă directă pe 3V3 necesită configurația din UM1724: ST-LINK separat fizic sau punțile **SB2 și SB12 deschise**. Oprirea UART în firmware nu înlocuiește pregătirea electrică. Pentru testele actuale prin USB/ST-LINK nu se cer modificări ale punților; pregătirea de 3V3 aparține pilotului PPK2. Se verifică și rutarea PC0/PC1 înaintea cablării, conform [țintei F446](../firmware/targets/stm32f446/README.md). HSI intern evită dependența de MCO al ST-LINK. [Manual ST, secțiunea 7.5.3](https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf).

- D0 RUN=1 identifică bucla celor N apeluri. ID-ul 1–12 trebuie să fie stabil; un ID schimbat în RUN invalidează captura.
- D5 IDLE_VALID=1 marchează numai repausul activ de control. Configurarea, pregătirea și validarea nu sunt repaus.
- D6 ERROR=1 este persistent; o serie cu ERROR se respinge, chiar dacă unele ferestre anterioare păreau complete.
- D7 DONE=1 apare după toate cele 12 regiuni și după validarea lor. O captură fără DONE este incompletă.
- Înainte ca MCU și LOGIC VCC să fie inițializate, stările digitale pot fi necunoscute. Aceste probe de pornire nu se folosesc pentru baseline sau energie de algoritm.

Pentru repausul inițial se selectează ultimele 2 s din primul interval valid, continuu, de 5 s IDLE_VALID, înainte de prima regiune RUN. Cele 5 s încep după configurarea platformei și pregătirea primei sarcini. Nu etichetăm toate primele 5 s de la alimentarea fizică drept standby; bootul are o durată separată. Așteptările folosesc timere hardware pentru control și mențin procesorul activ. Starea se numește repaus activ/idle operațional; nu reprezintă consumul minim de sleep al MCU.

Între algoritmi se verifică rezultatul, se pregătesc bufferele următorului algoritm, apoi există 1 s IDLE_VALID. Durata totală dintre regiuni poate fi mai mare. ID-ul este stabilit în afara RUN cu o pauză de 1 ms înaintea frontului de început. După verificarea finală se ridică DONE și se păstrează 2 s de repaus activ final. Apoi IDLE_VALID coboară, DONE rămâne ridicat, iar adaptorul poate opri taskul sau intra în WFI; această ultimă stare nu se amestecă cu baseline-ul activ.

## Ce este măsurat

Captura se oprește cel mai devreme la 3 s după apariția DONE, astfel încât să includă și coborârea IDLE_VALID de la sfârșitul celor 2 s finale. Se salvează o singură suită completă per fișier; repetările independente folosesc fișiere separate.

Regiunea RUN cuprinde N apeluri independente ale nucleului și costul minim al buclei/verificării statusului. Stările interne sunt resetate conform definiției fiecărui apel; pregătirea externă, hashul rezultatelor, comparația cu referința și întârzierile sunt în afara RUN. Nu se citesc timere MCU pentru raportarea performanței.

PPK2 furnizează probele de curent și eșantionarea digitală. Pentru intervalul [start, stop), durata de grup este numărul de probe/frecvența de eșantionare, sarcina electrică este suma curenților înmulțită cu pasul temporal, iar energia este aproximativ V_DUT înmulțit cu sarcina. Durata și energia pe apel se împart la N din manifest. Limitele și metoda de integrare sunt raportate explicit de parser. Durata unei bucle nu este confundată cu durata unui singur apel.

Fluxul aplicației PPK2 nu furnizează tensiune eșantionată simultan. Setpointul de 3,3 V nu este o măsurare a tensiunii reale: se verifică la bornele DUT sub sarcină și se documentează incertitudinea. Parserul distinge tensiunea nominală de o constantă furnizată explicit de operator, etichetată ca neverificată de software; verificarea fizică se documentează separat. Incertitudinea declarată este consemnată, fără propagare automată în energia calculată. Nu se scade automat baseline-ul din energia activă totală a plăcii.

100 kS/s înseamnă pas nominal de 10 µs. Trebuie verificate separat cuantizarea fronturilor, latențele analog/digital, comutarea domeniilor și costul GPIO/buclei. O probă cu buclă goală este un control al instrumentării, nu o corecție automată a tuturor energiilor. O coloană temporală uniformă construită din index nu demonstrează singură lipsa pierderilor de date. [Rezoluția digitală Nordic](https://docs.nordicsemi.com/r/bundle/ug_ppk2/page/ug/ppk/digital_input_resolution.html).

Specificația de curent indică tipic ±10% în 5–50 mA și ±15% în 50–1000 mA, cu specificațiile de offset aferente. Verificăm sarcini cunoscute înaintea campaniei și raportăm precizia instrumentului separat de dispersia statistică. Diferențele mici nu sunt automat clasamente demonstrate. [Specificații Nordic](https://docs.nordicsemi.com/r/bundle/ug_ppk2/page/ug/ppk/ppk_measure_accuracy.html).

## Campanie și criterii de acceptare

O singură programare a firmware-ului înghețat per placă; apoi programatorul se deconectează. Propunem minimum 10 capturi complete din porniri separate per placă, cu temperatură și timp de repaus între porniri documentate. N apeluri în aceeași buclă oferă o observație agregată, nu N încercări independente. O placă fizică per model nu caracterizează variația între exemplare.

Pilotul trebuie să confirme configurația ceasurilor, FPU, radioul oprit, integritatea ieșirilor, memoria disponibilă, 12 regiuni în ordine, DONE, schema exportului, tensiunea reală și absența resetărilor sau a pierderilor semnalate. Ordinea fixă poate influența încălzirea/cache-ul; se păstrează condiții și pauze fixe și se verifică deriva. Măsurătorile finale încep numai după rezolvarea problemelor observate în pilot.
