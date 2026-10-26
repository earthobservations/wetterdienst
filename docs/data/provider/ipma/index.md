# IPMA

Instituto Português do Mar e da Atmosfera (Portuguese Institute for Sea and Atmosphere)

## Overview

IPMA publishes near-real-time hourly observations from the Portuguese automatic weather station
network as key-less JSON open data. No authentication is required.

## License

IPMA names no licence. Its [news item of 6 February 2020](https://www.ipma.pt/pt/media/noticias/news.detail.jsp?y=2020&f=api-2020.html)
on the [IPMA API](https://api.ipma.pt/) says the data "podem ser usados, reutilizados e redistribuídos livremente -
sendo exigido sempre a indicação da fonte dos mesmos" (may be used, reused and redistributed freely, the source
always to be named), so the response metadata of the REST API has `license.spdx_id: null` and credits IPMA.
The conditions of use at the foot of the API page add that content may be used free of charge "desde que dessa
utilização não decorram finalidades lucrativas ou ofensivas" (as long as no profit-making or offensive purpose
results); whether that binds users of the API is not stated, so ask IPMA before a commercial use.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when IPMA
last wrote the all-stations feed the values were read from (its `Last-Modified`), not when a station reported.

```{toctree}
:hidden:

observation/index.md
```
