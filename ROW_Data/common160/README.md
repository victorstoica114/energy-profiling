# Accepted common 160 MHz CSV dataset

Thirty new captures: ten each for ESP32, RP2040 and STM32F446, all at nominal 160 MHz. Each board folder contains run_01 through run_10 with exact CSVs and unchanged acquisition sidecars. source_campaign.json, capture_index.csv and dataset_manifest.json retain original v5 profile and firmware identities.

This campaign is independent of the maximum-clock dataset in the parent directory. Use each capture's own baseline; do not pair capture run numbers across campaigns or rescale maximum-clock measurements. The full CSV copies remain local; original RAW/CSV and acquisition sidecars are published under captures_common160/.

PPK2 supplies the target at 3.3 V. ESP32/Pico external LDOs are removed; STM32 LDO is fitted with JP6 open and PPK2 feeding MCU VDD. Capture-level SD describes repeatability, not total measurement uncertainty.
