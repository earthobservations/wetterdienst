# ECCC (Environment and Climate Change Canada)

## Overview

- Historical Weather Observations
    - Historical (last ~180 years)
    - Hourly, daily, monthly resolution
    - Time series of stations in Canada

## License

The license for the use of ECCC data is given [here](https://climate.weather.gc.ca/prods_servs/attachment1_e.html).

**Notice.** The redistribution restriction quoted below allows ECCC's data to be passed on only if no fee is charged
for it and every recipient agrees to the same restrictions before use. The hosted instance of wetterdienst (REST API,
MCP server, app) serves ECCC data to whoever asks, as does any server run from the library, and the library hands it
to the programs that use it. Every answer for ECCC therefore carries the restriction, so that whoever passes the data
on knows of it: as `notice` in the `provider` block of the
[response metadata](../../../usage/restapi.md#response-metadata), in the `X-Wetterdienst-Notice` header, in the files
the library writes and in the [`providers`](../../../usage/restapi.md#providers) list. The notice informs and refuses
nothing: ECCC data is still served. Whether the use the hosted instance makes of the data is within the agreement is
not settled. If you run a public instance or build a product on ECCC data, read the agreement and ask ECCC.

**Which terms.** The agreement quoted here is the one of Climate Data Online. The library reads the data from the
MSC GeoMet OGC API (`api.weather.gc.ca`), whose collections state no licence, and the MSC Open Data pages publish a
second text, the
[Data Services End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/) (version 2.1.1, August
2026), which allows copying, modification and distribution, commercial use included, with attribution, and has no
redistribution condition. Which of the two covers the data the library reads is not stated by ECCC. Wetterdienst
reports the agreement and its notice until that is settled.

Specifically we want to quote and therewith highlight two passages from ECCC:

- REDISTRIBUTION RESTRICTIONS

    > You are authorized to further distribute the data or software, including any portion
    > of it, contained in this product under the following conditions only. No fee will be
    > charged explicitly for this Environment and Climate Change Canada product to any party
    > to whom it is distributed. (Charges for value-added services are permitted.). In
    > consideration of the licence you are herein granted, you have the obligation to
    > acknowledge the source of the Environment and Climate Change Canada Data with the
    > following layout or something similar: based on Environment and Climate Change Canada
    > data. Redistribution must occur so that any other party must agree to the same
    > redistribution restrictions before use of the redistributed product is allowed.

- NO WARRANTIES

    > Environment and Climate Change Canada does not warrant the quality,
    > accuracy, or completeness of any information or data. Such information and data is
    > provided "AS IS" without warranty or condition of any nature. Environment and Climate
    > Change Canada disclaims all other warranties, expressed or implied, including but not
    > limited to implied warranties of merchantability and fitness for a particular purpose,
    > with respect to the software, the data retrieved from this product, and any accompanying
    > materials.

```{toctree}
:hidden:

observation/index.md
```