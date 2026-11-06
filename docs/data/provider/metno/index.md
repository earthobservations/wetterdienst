# MET Norway

Norwegian Meteorological Institute (Meteorologisk institutt)

## Overview

MET Norway publishes historical and recent observations from the Norwegian station network
(~2200 stations) through its Frost API, covering 10-minute, hourly, 6-hourly (historical
only), daily, monthly and annual resolution. Access requires free client credentials, which
you can request at [frost.met.no](https://frost.met.no/auth/requestCredentials.html) and
provide via the `WD_AUTH__METNO_FROST` environment variable.

## License

MET Norway states that its data are licensed under the
[Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/en/2.0) and
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (the sentence on its
[licensing page](https://api.met.no/doc/License) says "and", so answers report `CC-BY-4.0 AND NLOD-2.0`:
the conditions of both apply. Both ask for credit to MET Norway and a reference to the licence; NLOD 2.0
also asks for a link to the licence and the source where practical and forbids misleading use or implying
endorsement, CC BY 4.0 a link to the licence and a note of changes), and asks to be credited as the source ("Data from
MET Norway"); see its [licensing and data policy](https://api.met.no/doc/License) and the
[free meteorological data](https://www.met.no/en/free-meteorological-data) page. See the
[Frost API](https://frost.met.no/) documentation for details.

**What the Frost terms ask of a caller** (the [terms of use](https://frost.met.no/termsofuse2.html), read 2026-11-06;
the page carries no date, and Frost's [changelog](https://frost.met.no/changelog2.html) lists 2025-09-25 as its newest
change):

- Identification: "The API requires a unique client ID for identification. Each client ID must be associated with a
  valid email address."
- Caching: "Use the information found in any cache headers." "You should save the information on your own server if you
  have heavy traffic. Heavy traffic means on average more than 1 requests to the API per second. Please contact us if
  you find that your service generates more traffic than this and you have not been able to reduced the amount of
  requests by taking into account our guidelines."
- Proxy: "Use a proxy if possible."
- Blocking: "If we see that there are situations that threaten the operation of our environment, we would consider
  blocking out the users / services that have high load / bad traffic patterns."
- Licence: "Data from frost.met.no are licensed and the license is found in every response." Frost's data answers
  carry that `license` member and it names `https://creativecommons.org/licenses/by/3.0/no/`, which is CC BY 3.0 Norway,
  while MET Norway's licensing page names NLOD 2.0 and CC BY 4.0. (The unauthenticated error answers of Frost carry the
  same member, such as the 404 of `https://frost.met.no/api/v0/`, read 2026-11-06 without a key.) Wetterdienst follows
  the licensing page and reports `CC-BY-4.0 AND NLOD-2.0`; the difference is unexplained.

MET Norway's separate [terms of service](https://api.met.no/doc/TermsOfService) are for its weather API at `api.met.no`
(not read by the library), but state what it expects of every caller: "You must identify yourself" with a User-Agent
naming the application and a contact, and "fake or random strings as identification in the User-Agent header" count as
abuse that "will result in a permanent ban". The library's User-Agent is `wetterdienst/<version> (<system>)`: it names
the application and carries no contact. Frost itself identifies the caller by the client ID, so the Frost terms ask for
no User-Agent; an operator who wants to give a contact sets `fsspec_client_kwargs` (see
[settings](../../../usage/settings.md)). Wetterdienst keeps what it downloads from Frost for five minutes (the
availability listing for an hour) and the station list for twelve hours; it does not read Frost's cache headers, so
these limits are its own.

```{toctree}
:hidden:

frost/index.md
```
