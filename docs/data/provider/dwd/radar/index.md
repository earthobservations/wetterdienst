# Radar

## Overview

The DWD provides several data products produced by radar for different 
[radar sites](https://opendata.dwd.de/weather/radar/sites/).
Those are not further explained as of their complexity. The DWD also offers 
[Radolan](https://www.dwd.de/DE/leistungen/radolan/radolan.html),
an advanced radar product with calibrated areal precipitation, and 
[Radvor](https://www.dwd.de/DE/leistungen/radvor/radvor.html), a
precipitation forecast based on radar. Further information on radar products can be
found their 
[radar products overview](https://www.dwd.de/DE/leistungen/radolan/produktuebersicht/radolan_produktuebersicht_pdf.pdf?__blob=publicationFile).

Radolan offers the user radar precipitation measurements that are calibrated with
ground based measurements. The data is offered in hourly and daily versions, both
being frequently updated for the recent version and data for each concluded year is
stored in the historical version. The daily version offers gliding sums of the last 24
hours while the hourly version offers hourly sums of precipitation. The precipitation
amount is given in 1/10 mm.

## Products and their formats

Which formats the products are served in, as read from the
[opendata.dwd.de/weather/radar](https://opendata.dwd.de/weather/radar/) listings on 2026-10-22 (the formats are
`DwdRadarDataFormat`, the table `RADAR_DATA_FORMATS` in `wetterdienst.provider.dwd.radar.metadata`):

| Product (`DwdRadarParameter`) | Served as |
| --- | --- |
| `RV_REFLECTIVITY`, `WN_REFLECTIVITY` (composite) | one `.tar` a run, `composite_rv_20261022_1130.tar`, holding an ODIM HDF5 file for the analysis and for every forecast lead time (`..._1130_000-hd5` to `..._1130_120-hd5`, every 5 minutes) |
| `LMAX_VOLUME_SCAN`, `PE_ECHO_TOP`, `PR_VELOCITY`, `PX250_REFLECTIVITY`, `PZ_CAPPI` (site) | ODIM HDF5 files, `rab02-pe_10132-20261022113000-deboo-hd5` |
| `SWEEP_*` (site) | ODIM HDF5 files, in the folder of the filter (`subset`) |
| `DX_REFLECTIVITY` (site) | binary files, `raa00-dx_10132-2610221130-boo---bin` |
| `RW_REFLECTIVITY`, `RY_REFLECTIVITY`, `SF_REFLECTIVITY` (radolan) | HDF5 files named `raa01-rw_10000-2610221130-dwd---bin.hdf5` (the name says bin, the file is HDF5); `fmt` need not be named |
| `RADOLAN_CDC` | as before: `.gz` and `.tar.gz` of RADOLAN binary files |

A request names a format only to say which one it wants, and a format the product is not served in is refused (for
the products of the first rows, with the format it is served in). Leave `fmt` out: it is the one format the product
has. DWD no longer publishes any radar product as BUFR (`fmt="bufr"` is refused, the reader of it was removed), and the composites HG and PG, the site product PF and the
RADVOR products RE and RQ hold no file, nor does the site product PX but for stale files of one site (they are no `DwdRadarParameter` any more, and a request for one says so). `start=DwdRadarDate.LATEST` reads
`composite_rv_LATEST.tar` (`composite_wn__LATEST.tar` with two underscores) and answers its first file, the analysis;
the sweeps have no latest file.

A request for a window answers a file for every lead time of every run in it, `timestamp` being the run:

```python
import datetime as dt

from wetterdienst.provider.dwd.radar import DwdRadarParameter, DwdRadarValues

request = DwdRadarValues(
    parameter=DwdRadarParameter.RV_REFLECTIVITY,
    start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),  # DWD keeps about two days
    end=dt.timedelta(minutes=5),
)
for result in request.query():
    print(result.timestamp, result.filename)  # composite_rv_20261022_1130_000-hd5, ..._005-hd5, ...
```

`result.data` is an ODIM HDF5 file (`ODIM_H5/V2_3`), which [h5py](https://www.h5py.org/) or
[wradlib](https://docs.wradlib.org/) read; with h5py installed (the `radar` extra) every file of a window is opened once to
check it is HDF5 (the one of `LATEST` is not).
