# NWS (National Weather Service)

## Overview

## License

The NOAA NWS Observations cover recent data (last week) of the US. The
[description](https://www.weather.gov/documentation/services-web-api) page
includes more information on the usage, references, qualities etc. It states that "all of the information
presented via the API is intended to be open data, free to use for any purpose".

What the page asks of a caller (read 2026-11-06): "A User Agent is required to identify your application. This string
can be anything, and the more unique to your application the less likely it will be affected by a security event. If you
include contact information (website or email), we can contact you if your string is associated to a security event."
The rate limit "is not public information, but allows a generous amount for typical use", a request over it "will return
with an error, and may be retried after the limit clears (typically within 5 seconds)", and "Proxies are more likely to
reach the limit, whereas requests directly from clients are not likely." Wetterdienst sends the User-Agent
`wetterdienst/<version> (<system>)` and does not retry a 429, which is a `ProviderRateLimitError` with the wait NWS sent, else a minute. A server that answers many callers may be the kind of proxy the
page means: our reading is that the hosted instance can reach the limit where each of its users alone would not.

```{toctree}
:hidden:

observation/index.md
```