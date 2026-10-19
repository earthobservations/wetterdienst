# IMGW (Instytut Meteorologii i Gospodarki Wodnej)

## Overview

## License

IMGW-PIB publishes its data under terms of its own, the "Regulamin udostępniania danych"
([PDF](https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf), in Polish, offered on the
[open data portal](https://danepubliczne.imgw.pl/)), on the legal basis of the Polish act of 11 August 2021 on
open data and the re-use of public sector information and the implementing regulation (EU) 2023/138 on
high-value datasets. They are no standard licence, so the response metadata of the REST API has
`license.spdx_id: null` with the name and the link of the terms.

- **Credit**: the terms make the use conditional on naming the source on every work or product made with the data,
  with „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"
  (§ 5 ust. 3), and, where the data were processed, also „Dane Instytutu Meteorologii i Gospodarki Wodnej –
  Państwowego Instytutu Badawczego zostały przetworzone" (§ 5 ust. 4). Wetterdienst always hands the data over
  processed (tidy rows, its own timestamps and quality flags, a filled-in zero for a day the daily precipitation
  files leave out, converted units where you ask for other units), so the `attribution` of IMGW carries both
  sentences, one after the other. Leaving them out can bring liability under the copyright act (§ 5 ust. 5).
- **Private use** is free (§ 5 ust. 1; „cel prywatny", § 2 pkt 2, is non-commercial use, theses included).
- **Any other purpose** is free only for "dane o wysokiej wartości" (high-value data, § 3 ust. 1 and § 5 ust. 1).
  IMGW-PIB does not state which of its datasets are high-value. The directory read here
  (`dane.imgw.pl/data/dane_pomiarowo_obserwacyjne/`) is catalogued on the Polish open data portal dane.gov.pl as
  CC BY-NC-ND 4.0 and not as high-value (dataset 926, last changed 2023-05-05), and hydrology is not in the
  meteorological annex of the regulation, so **a commercial use is not cleared** unless IMGW-PIB confirms it.
- **Business use** of data of the state network needs a signed agreement with IMGW-PIB (§ 3 ust. 2, § 5 ust. 1), and
  § 5 ust. 6 calls the use of freely provided data for such purposes fraud under art. 286 of the Polish criminal
  code. "Business" includes publishing the data on a site with advertisements (§ 2 pkt 3). Ask IMGW-PIB
  (biznes@imgw.pl) before you rely on the data for it.
- The terms say nothing on caching, redistribution or serving the data through an API; the credit line is what
  they ask of whoever passes it on.

```{toctree}
:hidden:

hydrology/index.md
meteorology/index.md
```