# ECCC (Environment and Climate Change Canada)

## Overview

- Historical Weather Observations
    - Historical (last ~180 years)
    - Hourly, daily, monthly resolution
    - Time series of stations in Canada

## License

Wetterdienst reports the
[Environment and Climate Change Canada Data Server End-use Licence](https://eccc-msc.github.io/open-data/licence/readme_en/)
(version 2.1.1, August 2026) as `license` for ECCC, with the credit line "Data Source: Environment and Climate Change
Canada. Contains information licenced under the Data Server End-use Licence of Environment and Climate Change Canada."
as `attribution`.

**How we know.** The OpenAPI document of the API the library reads, MSC GeoMet (`https://api.weather.gc.ca/openapi?f=json`,
read 2026-11-05), names that licence in its `info.license` and lists the collections `climate-stations`,
`climate-hourly`, `climate-daily` and `climate-monthly`, which are the ones the library reads. The collections state no
licence of their own.

**What the licence allows.** In our words, from the text read on 2026-11-05: a worldwide, royalty-free, perpetual,
non-exclusive licence to use the information, commercial use included, to copy, modify, publish, translate, adapt and
distribute it in any medium or format for any lawful purpose. Weather alerts must be reproduced without altering their
content or intent. The conditions are in section 3:

> Acknowledge the source of the Information by including any attribution statement specified by the Information
> Provider and/or Third Party Information Contributor and as indicated when you access the Information from
> Environment and Climate Change Canada (ECCC) data servers and, where possible, provide a link to this licence.
> Attribute data to the originator, including sources outside Environment and Climate Change Canada. For example;
> "Data Source: Environment and Climate Change Canada" or, in the case where data comes from multiple originators:
> "Data Source: Environment and Climate Change Canada and (''if possible indicate the Third Party Information
> Contributor'')" If the Information Provider or the Third Party Information Contributor does not provide a specific
> attribution statement, or if you are using Information from several information providers and multiple
> attributions are not practical for your product or application, you must use the following attribution statement:
> Contains information licenced under the Data Server End-use Licence of Environment and Climate Change Canada.

Two duties follow, and the credit line has a sentence for each. The licence's example, "Data Source: Environment and
Climate Change Canada", is for attributing the originator, which for the readings is ECCC. The collections specify no
attribution statement of their own, so the licence says to "use" the second text, which is the second sentence of the
credit line. The licence's URL goes with every answer (the `license.url` of the block, the `Link` header), for the
link to the licence the first paragraph asks for where possible. The licence grants no right to
personal information, to rights of third parties, to ECCC's names and logos, or to use the information in a way that
suggests ECCC endorses you (sections 4 and 5), and it comes with no warranty (section 6). Wetterdienst changes the data
it hands over (it is reshaped into one table, parameters are renamed and units converted, see
[licences and credit lines](../licenses.md#what-wetterdienst-does-to-the-data)), which the licence allows and which
every answer says in its `processing_note`. Section 9 says that the use of the information is governed by the licence in
force on the date you accessed it, so a newer version of the licence than the one read here applies to a later access.
The MSC Open Data pages also publish a Services Usage Policy that
complements the licence; it has not been reviewed here.

**What points the other way.** The climate collections' canonical link goes to Climate Data Online
(`https://climate.weather.gc.ca`), and the
[Licence Agreement for Use of Environment and Climate Change Canada Data](https://climate.weather.gc.ca/prods_servs/attachment1_e.html)
of that site restricts redistribution:

> You are authorized to further distribute the data or software, including any portion
> of it, contained in this product under the following conditions only. No fee will be
> charged explicitly for this Environment and Climate Change Canada product to any party
> to whom it is distributed. (Charges for value-added services are permitted.). In
> consideration of the licence you are herein granted, you have the obligation to
> acknowledge the source of the Environment and Climate Change Canada Data with the
> following layout or something similar: based on Environment and Climate Change Canada
> data. Redistribution must occur so that any other party must agree to the same
> redistribution restrictions before use of the redistributed product is allowed.

Our reading is that this agreement belongs to Climate Data Online's bulk download product, which the library does not
read, and that the licence of the data server is the one that covers what it reads. That is our reading and not a
statement from ECCC. If your use depends on the difference, for instance because you pass the data on, ask ECCC.

```{toctree}
:hidden:

observation/index.md
```