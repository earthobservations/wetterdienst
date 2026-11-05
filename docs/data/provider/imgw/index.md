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
  IMGW-PIB told us in November 2026 that the data it classes as high-value are free for any use under CC BY 4.0, at
  [danepubliczne.imgw.pl/pl/apiinfo](https://danepubliczne.imgw.pl/pl/apiinfo), and that all its other data are
  public-sector information under CC BY-NC-ND 4.0, free only for uses other than business (private or teaching, for
  example) and for the bodies the Polish Water Law names.
- **Which group the data read here are in is not settled.** IMGW-PIB was asked and did not say. That page also links
  the directory read here (`danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/`), but the Polish open data portal
  dane.gov.pl catalogues that directory as CC BY-NC-ND 4.0 and not as high-value (dataset 926, last changed
  2023-05-05), and hydrology is not in the meteorological annex of the regulation, so **a commercial use is not
  cleared** unless IMGW-PIB confirms it.
- **Business use** of data of the state network needs a signed agreement with IMGW-PIB (§ 3 ust. 2, § 5 ust. 1), and
  § 5 ust. 6 calls the use of freely provided data for such purposes fraud under art. 286 of the Polish criminal
  code. "Business" includes publishing the data on a site with advertisements (§ 2 pkt 3). Ask IMGW-PIB
  (biznes@imgw.pl) before you rely on the data for it.
- The terms say nothing on caching, redistribution or serving the data through an API; the credit line is what
  they ask of whoever passes it on. IMGW-PIB was asked about these, and about whether the NoDerivatives condition of
  CC BY-NC-ND allows converted units and a uniform table, which § 5 ust. 4 of the terms provides for as processed
  data. It has not answered.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when IMGW
last wrote the archive or archives the values were read from (their `Last-Modified`), the newest of those that gave a
reading.

```{toctree}
:hidden:

hydrology/index.md
meteorology/index.md
```