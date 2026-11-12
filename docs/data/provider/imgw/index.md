# IMGW (Instytut Meteorologii i Gospodarki Wodnej)

## Overview

## License

Wetterdienst reports [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) for all IMGW data, in the
response metadata of both networks. IMGW-PIB told us in November 2026 that the data it classes as high-value are free
for any use under CC BY 4.0, and that all its other data are public-sector information under CC BY-NC-ND 4.0. It did
not say which of the two the directory read here (`danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/`) is. The
Polish open data portal dane.gov.pl catalogues that directory as CC BY-NC-ND 4.0 and not as high-value (dataset 926,
last changed 2023-05-05), so wetterdienst applies that licence to all of it, meteorology and hydrology alike.

IMGW-PIB's own terms apply beside the licence, the "Regulamin udostępniania danych"
([PDF](https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf), in Polish, offered on the
[open data portal](https://danepubliczne.imgw.pl/)), on the legal basis of the Polish act of 11 August 2021 on
open data and the re-use of public sector information and the implementing regulation (EU) 2023/138 on
high-value datasets.

- **Credit**: the terms make the use conditional on naming the source on every work or product made with the data,
  with „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"
  (§ 5 ust. 3), and, where the data were processed, also „Dane Instytutu Meteorologii i Gospodarki Wodnej –
  Państwowego Instytutu Badawczego zostały przetworzone" (§ 5 ust. 4). Wetterdienst always hands the data over
  processed (tidy rows, its own timestamps and quality flags, a filled-in zero for a day the daily precipitation
  files leave out, converted units where you ask for other units), so the `attribution` of IMGW carries both
  sentences, one after the other. Leaving them out can bring liability under the copyright act (§ 5 ust. 5).
- **Private use** is free (§ 5 ust. 1; „cel prywatny", § 2 pkt 2, is non-commercial use, theses included). So is use
  by the bodies the Polish Water Law names.
- **Business use** of data of the state network needs a signed agreement with IMGW-PIB (§ 3 ust. 2, § 5 ust. 1), and
  § 5 ust. 6 calls the use of freely provided data for such purposes fraud under art. 286 of the Polish criminal
  code. "Business" includes publishing the data on a site with advertisements (§ 2 pkt 3). Ask IMGW-PIB
  (biznes@imgw.pl) before you rely on the data for it.
- **Processing and passing on**: the terms provide for processed data (§ 5 ust. 4) and say nothing on caching,
  redistribution or serving the data through an API; the credit line is what they ask of whoever passes it on.
  IMGW-PIB was asked how this relates to the NoDerivatives condition of the licence and did not say, so ask it if your
  use depends on that.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when IMGW
last wrote the archive or archives the values were read from (their `Last-Modified`), the newest of those that gave a
reading.

```{toctree}
:hidden:

hydrology/index.md
meteorology/index.md
```