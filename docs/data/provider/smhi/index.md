# SMHI

Swedish Meteorological and Hydrological Institute (Sveriges meteorologiska och hydrologiska institut)

## Overview

SMHI publishes observations from the Swedish weather station network through its open data
API, covering 1-minute, hourly, daily and monthly resolution. No authentication is required.

## License

SMHI open data is published under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); SMHI asks to be named as the source and
for a note if you changed the data. SMHI's
[terms of use](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) (in Swedish) also ask
that only documented APIs are used, that downloads are not repeated needlessly and that the
time-limited caching its metadata allows is used. In its words (translated by us, read 2026-11-06): "Do not download
SMHI's services needlessly. Avoid, for example, mass downloads that fetch forecast data for a large number of places
at one time", "If possible, do not hand out outdated data", and SMHI "reserves the right to block individual IP
addresses or shut down services entirely in case of obvious abuse".

What wetterdienst does: it reads the observation API only, keeps a series for five minutes and the station list for
twelve hours (its own limits, not read from SMHI's metadata), and fetches the files of the next four stations while
it parses one (`fetch_ahead`, see [what it does with the data](../data-use.md#how-it-asks-the-provider)).

```{toctree}
:hidden:

observation/index.md
```
