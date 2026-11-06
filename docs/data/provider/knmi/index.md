# KNMI

Royal Netherlands Meteorological Institute (Koninklijk Nederlands Meteorologisch
Instituut)

## Overview

KNMI publishes observations from the Dutch weather station network through its Data
Platform, covering 10-minute, hourly and daily resolution. Access requires a free API key,
which you can request at
[developer.dataplatform.knmi.nl](https://developer.dataplatform.knmi.nl/) and provide via
the `WD_AUTH__KNMI` environment variable (or `Settings(auth={"knmi": "<api_key>"})`).

## License

KNMI data is published as open data through the
[KNMI Data Platform](https://dataplatform.knmi.nl/), where each of the three datasets read here
(10-minute, hourly and daily in-situ observations) lists its licence as
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The platform's [fair use policy](https://developer.dataplatform.knmi.nl/fair-use) (read 2026-11-06) asks of a caller:

- "Accounts and keys are personal. They are meant to be used by you or by your organisation for your own applications,
  and should not be shared with, resold to, or distributed to third parties." "Do not create multiple accounts to obtain
  more quota or a higher rate limit."
- "If you want to serve KDP data to your own users, proxy the requests through your own backend, keep the key there, and
  add caching in your backend." "Never embed an API key in a public web client".
- "Every API key has a rate limit and an hourly quota"; on a 429, wait and back off, and "Never retry immediately in a
  tight loop". The [Open Data API](https://developer.dataplatform.knmi.nl/open-data-api) page gives a registered key 200
  requests a second and 1000 an hour. A shared anonymous key exists for unauthenticated clients, whose limits "are shared
  with all other anonymous users" and which "expires yearly"; the library does not use it.
- "Do not poll excessively" (use the Notification Service), "Do not download files you already have", and "To download a
  complete dataset, request a dataset bulk key": "Re-downloading a complete dataset because it is easier than archiving
  it locally is not fair use".

The same policy asks you to "Credit KNMI as the source, for example with 'Source: KNMI' and a link to the dataset", to
"Make clear when you show data that you derived or modified yourself", and to "Send a descriptive User-Agent header that
identifies your application, and, if possible, how to reach you"; the library's User-Agent names the application and
carries no contact. It also names "Distributed downloading of the same data from many clients" and rotating "accounts,
keys, or IP addresses" as abuse. The `attribution` of an answer is "© KNMI".

What this means for wetterdienst (our reading, not KNMI's): the library sends your key from your machine and keeps what
it downloads for five minutes, so a repeated query is not a repeated download. A server that holds a key and answers
other people's queries is the proxy with a cache that KNMI describes for "your own users"; whether an open server that
anyone can reach, with no account of its own, is within "your own applications" the policy does not say. Reading a long
window of the 10-minute data takes one file per time step, which is no bulk download of a dataset and counts against
the hourly quota. Whoever runs a shared instance should ask KNMI first, see
[what it does with the data](../data-use.md#keys-and-credentials).

```{toctree}
:hidden:

observation/index.md
```
