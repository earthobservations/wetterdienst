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
| `RV_REFLECTIVITY`, `WN_REFLECTIVITY`, `RS_PRECIPITATION_SUM` (composite) | one `.tar` a run, `composite_rv_20261022_1130.tar`, holding an ODIM HDF5 file for the analysis and for every forecast lead time (`..._1130_000-hd5` to `..._1130_120-hd5`, every 5 minutes) |
| `HX_REFLECTIVITY`, `DMAX_REFLECTIVITY`, `VII_INTEGRATED_ICE`, `HYMECNG_PRECIPITATION_TYPE` (composite) | one ODIM HDF5 file a run, `composite_hx_20261022_1130-hd5` (`composite_HymecNG_20261022_1130_000-hd5`: the lead time 0 is in its name) |
| `LMAX_VOLUME_SCAN`, `PE_ECHO_TOP`, `PR_VELOCITY`, `PX250_REFLECTIVITY`, `PZ_CAPPI` (site) | ODIM HDF5 files, `rab02-pe_10132-20261022113000-deboo-hd5` |
| `SWEEP_PCP_VELOCITY_H`, `SWEEP_PCP_REFLECTIVITY_H`, `SWEEP_VOL_VELOCITY_H`, `SWEEP_VOL_REFLECTIVITY_H` (site) | ODIM HDF5 files, in the folder of the filter (`subset`: `SIMPLE` or `POLARIMETRIC`); the reflectivity has a third folder, `unfiltered` (`subset=DwdRadarDataSubset.UNFILTERED`), with two files for each sweep, `..._th_00-2026102213105700-boo-10132-hd5` and `..._tv_00-...`: the total (uncorrected) reflectivity factor ODIM `TH` and `TV`, the horizontally and the vertically polarized one. A request answers both, or the one `polarization` names (see below); they are told apart by `result.url` or the `quantity` of the file |
| `SWEEP_PCP_ZDR`, `SWEEP_PCP_RHOHV`, `SWEEP_PCP_PHIDP`, `SWEEP_VOL_ZDR`, `SWEEP_VOL_RHOHV`, `SWEEP_VOL_PHIDP` (site) | ODIM HDF5 files, `ras07-vol5minng01_sweeph5onem_uzdr_00-2026102213105700-boo-10132-hd5`, in the folder `unfiltered`, the only one they have (`subset` need not be named) |
| `DX_REFLECTIVITY` (site) | binary files, `raa00-dx_10132-2610221130-boo---bin` |
| `RW_REFLECTIVITY`, `RY_REFLECTIVITY`, `SF_REFLECTIVITY`, `YW_REFLECTIVITY` (radolan) | HDF5 files named `raa01-rw_10000-2610221130-dwd---bin.hdf5` (the name says bin, the file is HDF5); `fmt` need not be named |
| `KONRAD3D_CONVECTIVE_CELLS`, `MESOCYCLONE_DETECTION` | XML files, `KONRAD3D_20261022T130500.xml` and `meso_20261022_1305.xml`, a run every 5 minutes |
| `RADOLAN_CDC` | as before: `.gz` and `.tar.gz` of RADOLAN binary files |

A request names a format only to say which one it wants, and a format the product is not served in is refused, saying the format it is
served in (RADOLAN's products, which are no choice of format, refuse XML only). Leave `fmt` out: it is the one format the product
has. DWD no longer publishes any radar product as BUFR (`fmt="bufr"` is refused, the reader of it was removed), and the composites HG and PG, the site product PF and the
RADVOR products RE and RQ hold no file, nor does the site product PX but for stale files of one site (they are no `DwdRadarParameter` any more, and a request for one says so). `start=DwdRadarDate.LATEST` reads
the file named latest: `composite_rv_LATEST.tar` (`composite_wn__LATEST.tar` with two underscores) of a composite
that is a `.tar`, whose first file, the analysis, it answers, `composite_hx_LATEST-hd5`, `composite_VII_latest-hd5`,
`composite_HymecNG_LATEST_000-hd5`, `raa01-yw_10000-latest-dwd---bin.hdf5` and `meso_latest.xml`. The folders `unfiltered` hold
one for each sweep (`..._uzdr_00-LATEST-boo-10132-hd5`), which LATEST reads for the precipitation scan, whose one sweep it is
(two files, TH and TV, for the reflectivity). It does not for the volume scan: DWD replaces its ten files one by one as
the scan is published, so for minutes they are of two volumes (on 2026-10-22 at 15:53 UTC the sweeps 0 to 4 were
listed 15:51 to 15:53 and 5 to 9 at 15:48 to 15:49; the scan time inside the files of 0, 3 and 4 is 15:50, inside that of 9 15:45): ask for a time instead (`MOST_RECENT` is the volume of the slot 10 minutes before now, see below). The folders of a filter hold none and KONRAD3D has none.
The name of a latest file has no time (but the `.tar` of a composite, whose first file names its run), so `result.timestamp` is the time the file says it is of: with h5py installed (the `radar` extra) `date` and `time` of the `/what` group of an ODIM HDF5 file, the time of the header of a `DX` file (which needs no h5py), the time of the first event of `meso_latest.xml`. It is the run, as the name of the dated files says it (read 2026-10-22: the two agree to the minute for the composites, RADOLAN, the site products and the sweeps of the precipitation scan, 20:35 for a run of 20:35). A run with no event carries no time (554 of the 576 `meso_` files of 2026-10-20 to 22), and the `timestamp` of `meso_latest.xml` stays `None` then, as it does for any latest HDF5 file read without h5py, which is warned about once.
`start=DwdRadarDate.MOST_RECENT` of an HDF5 or XML product (not RADOLAN's, unless `fmt` is named) is the 5 minute slot
before now; for RS, DMAX, VII, KONRAD3D and the mesocyclones, which DWD publishes more than 5 minutes after the run in
more than one run of a hundred (up to 9 minutes), the slot 10 minutes before now, and so for the site products PE, PZ, PR
and LMAX, which are as late as RS in 18 of 577 runs (up to 8 minutes, read 2026-10-22), and for the sweeps of the volume
scan, whose last sweeps are listed up to 485 s after their slot starts (more than 300 s in 3 % of the volumes of the 17 sites, read
2026-10-20 to 22): a request at a lag of 5 minutes is 5 to 10 minutes after the slot starts, and 0.6 % of them lacked a sweep.

The unfiltered reflectivity sweeps (`SWEEP_PCP_REFLECTIVITY_H`, `SWEEP_VOL_REFLECTIVITY_H` with `subset=DwdRadarDataSubset.UNFILTERED`)
have a file for each polarization, which a request answers both of unless it names one with `polarization`:
`DwdRadarPolarization.HORIZONTAL` is the `..._th_NN-...` files (ODIM `TH`, the horizontally polarized total reflectivity factor) and
`DwdRadarPolarization.VERTICAL` the `..._tv_NN-...` files (`TV`, the vertically polarized one). The enumeration takes its member
name or the file's spelling as a string, `"horizontal"` or `"th"`, `"vertical"` or `"tv"`. It combines with `elevation` and with
`start=DwdRadarDate.LATEST` of the precipitation sweep, and it is refused with a `RequestError` saying why for any product other than
those two and for any folder other than `unfiltered`, as the polarimetric moments (ZDR, RHOHV and PHIDP) and the velocity have one file
for each sweep. The vertical files are those of `..._REFLECTIVITY_H` all the same: the `_H` of the product names is unchanged.

```python
import datetime as dt

from wetterdienst.provider.dwd.radar import (
    DwdRadarDataSubset,
    DwdRadarParameter,
    DwdRadarPolarization,
    DwdRadarSite,
    DwdRadarValues,
)

request = DwdRadarValues(
    parameter=DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
    site=DwdRadarSite.BOO,
    subset=DwdRadarDataSubset.UNFILTERED,
    polarization=DwdRadarPolarization.VERTICAL,  # only the ..._tv_NN-... files; leave it out for TH and TV
    # a time of the last hours: DWD keeps about two days
    start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30),
)
```

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

`result.data` is an ODIM HDF5 file (`ODIM_H5/V2_3`, the sweeps declare `V2_2`), which [h5py](https://www.h5py.org/) or
[wradlib](https://docs.wradlib.org/) read; with h5py installed (the `radar` extra) every file of a window of an HDF5 product (not RADOLAN's, unless `fmt` is named) is opened once to
check it is HDF5 (the one of `LATEST` is not). The XML products are handed over as the bytes DWD wrote, to be parsed
by the caller; nothing is read from any file.

## What the products are

The wording is DWD's, from its [product sheets](https://www.dwd.de/DE/leistungen/radarprodukte/radarprodukte.html)
(the quotes are theirs, in German) and the attributes of the files (`what`, `how`, the ODIM quantity `quantity` of
`dataset1/data1/what` and the `gain`, `offset`, `nodata` and `undetect` that turn a count into the physical value, as
the sheets say). Where the sheet says nothing, the file's attribute is given as it is.

| Product | What DWD says | In the file |
| --- | --- | --- |
| `HX_REFLECTIVITY` | "ein Deutschland-Reflektivitäts-Komposit" of the "Niederschlags-Radarscan", 250 m × 250 m, 4800 × 4400 px, every 5 minutes, 16 bit | `DBZH` (reflectivity factor, dBZ), `prodname` `HX_top_view`, `camethod` `MAXIMUM` |
| `DMAX_REFLECTIVITY` | the same text, of the "Volumen-Radarscan" | `DBZH`, `prodname` `DMax_top_view`, `camethod` `MAXIMUM` |
| `VII_INTEGRATED_ICE` | "ein Deutschland-Komposit des vertikal integrierten Eises (engl. vertically integrated ice), das die vom Radar erfasste Eismasse in einer vertikalen Luftsäule beschreibt", 1 km × 1 km, 1200 × 1100 px, value range 0 mm to 1000 mm | `VIL`, which ODIM 2.3 defines as "Vertical Integrated Liquid water" in kg/m², `prodname` `VII_top_view`; the sheet gives the range in mm |
| `HYMECNG_PRECIPITATION_TYPE` | "ein Deutschland-Komposit der Niederschlagsart in 2 m Höhe über Grund", 1 km × 1 km, 11 classes (large hail, small hail, graupel, freezing rain, freezing drizzle, snow, sleet, rain, drizzle, not classifiable, no precipitation) | `CLASS`, 8 bit, the classes in the dataset `dataset1/data1/legend` (`NO_PRECIPITATION` 0, `NOT_CLASSIFIED` 1, `DRIZZLE` 2, `RAIN` 3, `FREEZING_DRIZZLE` 4, `FREEZING_RAIN` 5, `SNOW_RAIN` 6, `SNOW` 7, `GRAUPEL` 8, `HAIL` 9, `LARGE_HAIL` 10) |
| `RS_PRECIPITATION_SUM` | "ein Deutschland-Komposit der über einen Zeitraum von 1 Stunde akkumulierten Niederschlagsmenge in mm", 1 km × 1 km, value range 0 mm to 4.3 · 10⁶ mm, step 0.001 mm | `ACRR` (accumulated precipitation, mm); each file spans the hour before its lead time (`startdate`/`starttime` to `enddate`/`endtime`), where `RV_REFLECTIVITY` has the same quantity over 5 minutes |
| `YW_REFLECTIVITY` | RADOLAN's "quasi-angeeichte Radardaten auf der Basis der RY-, RH- und RW-Produkte" ([RADOLAN-RADVOR format description](https://www.dwd.de/DE/leistungen/radolan/radolan_info/radolan_radvor_op_komposit_format_pdf.pdf?__blob=publicationFile) 2.6), every 5 minutes | `RATE` (precipitation rate), `gain` 0.01, `camethod` `QUASI-ADJUSTED WITH GAUGES`. DWD publishes it 35 to 40 minutes after its time, two files every 10 minutes |
| `RW_REFLECTIVITY` | RADOLAN's hourly sum of the precipitation (the sheet is not quoted here), a file every 10 minutes | `ACRR` (accumulated precipitation, mm), `gain` 0.1, `camethod` `RGA: STANDARD ADJUSTMENT WITH GAUGES`; each file spans the hour before its time (`startdate`/`starttime` to `enddate`/`endtime`). wradlib's `read_radolan_header` and `read_radolan_composite` read RADOLAN binary and fail on it, `xr.open_dataset(..., engine="radolan")` (wradlib 2.6.0 and later, the floor of the `radarplus` extra) and h5py read it |
| `SWEEP_VOL_ZDR`, `SWEEP_PCP_ZDR` | the sheets of the sweeps ("Standort-Reflektivitäts- und Radialgeschwindigkeitsprodukte") name no polarimetric moment; DWD's [ODIM-DWD-E_1-0 description](https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/hdf/ODIM-Beschreibung.pdf?__blob=publicationFile) lists the moment `uzdr` as ODIM `UZDR` | `UZDR`, which ODIM 2.3 defines as "Logged differential reflectivity that has not been subject to a Doppler filter", ZDR in dB |
| `SWEEP_VOL_RHOHV`, `SWEEP_PCP_RHOHV` | as above, `urhohv` is ODIM `URHOHV` | `URHOHV`: "Correlation between Zh and Zv that has not been subject to any filter or correction", ρhv from 0 to 1 |
| `SWEEP_VOL_PHIDP`, `SWEEP_PCP_PHIDP` | as above, `uphidp` is ODIM `UPHIDP` | `UPHIDP`: "Differential phase that has not been subject to any filter or correction", φdp in degrees |
| `KONRAD3D_CONVECTIVE_CELLS` | "Erkennung, Verfolgung und Nowcasting konvektiver Zellen" ([Kurzdokumentation KONRAD3D](https://www.dwd.de/DE/leistungen/radarprodukte/konrad3d_kurzbeschreibung.pdf?__blob=publicationFile)); "Ausgabeformat: xml", one file every five minutes, `KONRAD3D_YYYYMMDDThhmmss.xml`, the run's reference time being the start of the radar scan cycle | an XML document, root `konrad3d` (`data_model_name`, `data_model_version`), a `head` (reference time, the run, the grid, the sweeps used) and `cells`, with a `feature` for each cell: its geometry, intensity and further groups; no cell is an empty `cells`. The [format description](https://www.dwd.de/DE/leistungen/radarprodukte/formatbeschreibung_konrad3d.pdf?__blob=publicationFile) is DWD's |
| `MESOCYCLONE_DETECTION` | "xml-Dateien mit sämtlichen Mesozyklonenerkennungen eines Referenzzeitpunktes" ([Dokumentation Mesozyklonenerkennung](https://www.dwd.de/DE/leistungen/radarprodukte/dokumentation_mcd.pdf?__blob=publicationFile), 07.2022), the volume scans of the 17 sites, a run every 5 minutes | an XML document, root `nowcast-data`, with the `radar-stations` and an `event` for each detected mesocyclone (its time, a `location` ellipse and `nowcast-parameters` such as `mesocyclone_shear_max` and `mesocyclone_diameter`, each with its `units`); a run without a mesocyclone is the station list alone (173 bytes) |

The sweeps are the polar data of one site (`site=DwdRadarSite.BOO`): 360 rays of 250 m bins, as many bins as the
elevation has (`nbins`, `rscale` and `how/range` of the file say how many and how long). The volume scan has ten
elevations, which are ten files a run (`elevation=0` to `9` picks one of them, for the polarimetric moments as for the
velocity and the reflectivity), the precipitation scan one file. DWD extended the range of the precipitation scan
(`SWEEP_PCP_*`) from 150 km (600 bins) to 180 km (720 bins) on 24 November 2026 (the first file with 720 bins is the
scan of 09:20 UTC; [announcement of 3 November 2026](https://www.dwd.de/DE/leistungen/opendata/neuigkeiten/opendata_november2026_1.html)):
a file of an earlier time has 600 bins, so a request across that time returns both. The volume scan did not change.
The unfiltered reflectivity has two files for each sweep, TH and TV, and `elevation` picks the pair. The unfiltered
polarimetric moments have no folder of a filter, as the velocity and the reflectivity sweeps do (`hdf5/filter_simple`
and `hdf5/filter_polarimetric`).

## Radar frames on the REST API

`GET /api/v1/radar/frames` and `GET /api/v1/radar/frame` (`/api/radar/...` is the same) serve the RV composite as
map images, for a viewer that plays the last hours and DWD's forecast of the next two (GH-3788). The server decodes
the HDF5 files; a browser never gets one. The answers carry DWD's licence and credit line like every answer that holds
provider data (`metadata` of the list, `X-Wetterdienst-License` and `X-Wetterdienst-Attribution` of an image), and a
`processing_note` that says what wetterdienst did: the sums became rates in classes, and the grid was warped. Neither
route is an MCP tool: an overlay is nothing a model can read.

```bash
http localhost:7890/api/radar/frames                      # the loop and its forecast
http localhost:7890/api/radar/frames past==30 forecast==false
# time and run are those of a frame of /radar/frames (DWD keeps about two days)
http localhost:7890/api/radar/frame time==2026-11-19T21:10:00Z run==2026-11-19T21:10:00Z > frame.png
```

**The frames.** `/radar/frames` lists the analysis of every run of the last `past` minutes (120 by default, at most
360: a frame every 5 minutes) and, with `forecast=true` (the default), the 24 frames of DWD's forecast of the newest
run, 5 to 120 minutes after it. Every frame is `{time, run, lead_minutes, kind}`: `time` is the UTC time the 5 minutes
of the frame end at, `run` the run of DWD it is read from, and `kind` is `observation` (the radar analysis) or
`forecast`. The forecast is DWD's extrapolation of the recent movement of the rain (RADVOR),
not a weather model, and a frame of it is the same product as an analysis frame, a lead time later. A run that DWD did
not publish is a frame that is not in the list. The times are UTC with a `Z`, which a query takes as it is. The
answer also says where the images lie (`image`) and what the colours mean (`legend`):

```json
{
  "run": "2026-11-19T21:25:00Z",
  "image": {
    "crs": "EPSG:3857",
    "bounds": {"west": 1.4633, "south": 45.6823, "east": 18.7316, "north": 56.2194},
    "width": 1200, "height": 1169, "media_type": "image/png"
  },
  "legend": {
    "unit": "mm/h", "transparent_below": 0.1,
    "classes": [{"lower": 0.1, "upper": 0.5, "color": "#c7e9b4", "label": "0.1 to under 0.5 mm/h"}, "..."]
  },
  "frames": [{"time": "2026-11-19T20:55:00Z", "run": "2026-11-19T20:55:00Z", "lead_minutes": 0, "kind": "observation"}, "..."]
}
```

The newest run is 3 to 8 minutes old when it appears on DWD's server and the server holds the list of runs for a
minute, so the last frame of the loop is some 5 to 15 minutes in the past. A newest run older than 20 minutes is a
`radar-stale` warning in `metadata` (DWD's feed has stopped: the loop ends at that run and the forecast starts from
it), and that list is sent without a `Cache-Control`; one without a warning has `public, max-age=60` and an `ETag`.

**One image.** `/radar/frame` takes the `time` and the `run` of a frame and answers an indexed PNG, 1200 x 1169 pixels,
some 35 KB, with `X-Wetterdienst-Radar-Time` and `X-Wetterdienst-Radar-Run` saying which frame it is. Where there is no
rain, and where the composite has no data (outside its coverage, or where a radar is missing), it is transparent. A
`time` up to the newest run is the analysis, a later one the forecast of the newest run, so `run` may be left out; the
image is then of whichever run is newest, and may be reused for a minute. With `run` it is the same for as long as DWD
keeps the run (about 48 hours, a run DWD does not list is a 404, and so is the forecast of a run that is not one of the newest three), and may be reused for an hour. A `time` that is no
multiple of 5 minutes, or is not 0 to 120 minutes after the run, is a 400; a file DWD sends that the decoder is not
written for (it changed the grid, the quantity or the projection) is a 502 that says what changed, and a missing `radar`
extra on the server a 501.

**What the colours are.** The RV composite holds the precipitation of the 5 minutes that end at the time of the frame
(ODIM `ACRR`, a `uint32` of 0.001 mm per count). It is turned into a rate in mm/h from the length of time the file
states it is of (300 s, so x 12) and sorted into seven classes: 0.1 to under 0.5, 0.5 to 1, 1 to 2.5, 2.5 to 5, 5 to 10,
10 to 25 and 25 mm/h and more. The colours are ColorBrewer's YlGnBu from its third step on, one ramp whose lightness
falls from each class to the next by more than 6 (CIE L\*, held by a test), so the order reads in grey and for every
kind of colour vision and does not depend on telling hues apart; the legend gives the numbers as well, for a page to
write them out. A pixel is a class and no reading: a rate under 0.1 mm/h is as transparent as no rain, and the class
of a cell is the class of its 5-minute sum, which is no hourly intensity.

**Where the image lies.** The grid of the composite (DE1200: 1100 x 1200 cells of 1 km) is in a polar stereographic
projection, in which a row is not a parallel, so it is not drawn as it is. The image is warped to Web Mercator
(EPSG:3857): its pixels are square there, it is 1200 pixels wide over the longitudes of the grid, and `bounds` are its
outer edges in WGS84, which a Leaflet `ImageOverlay` stretches the image over (linearly in longitude and in Mercator
`y`, which is what makes it right); a map in another projection must warp it again. Each pixel takes the cell that
contains its centre, so classes are never blended. The projection is DWD's `projdef` of every file (`+proj=stere +lat_ts=60
+lat_0=90 +lon_0=10`, on the WGS 84 ellipsoid), written in this package so that no PROJ is needed. It is held to DWD's own
numbers: the four outer corners a file states in degrees (`UL` 55.8621 N 1.4633 E, `UR` 55.8454 N 18.7316 E, `LL`
45.6964 N 3.5670 E, `LR` 45.6846 N 16.5809 E) are where the projection puts the corners of the grid, to within 10⁻⁶ degrees
(10 cm); it agrees with PROJ's to a micrometre over Germany; and the cell a pixel takes is within 1.2 km of the city it
is the pixel of, for seven cities from Kiel to Freiburg. The grid is anchored at the corner a file states: the
corner values are the outer corners and not the cell centres (half a cell, 500 m, which a reader taking them for
centres would be off by). A file of another grid is refused.

**What it costs.** Measured on a developer laptop (Apple silicon, Python 3.13, a home connection to opendata.dwd.de on
2026-11-19), and not on the server, which no one here has access to:

| | one frame | the loop of 2 hours: 25 analysis frames and 24 forecast frames |
| --- | --- | --- |
| transfer | analysis: one range request of 400 KB (the file is about 320 KB); the `.tar` of a run is 7.7 MB (the analysis and 24 forecasts) | 25 x 400 KB = 10 MB for the analysis (the whole `.tar` of each would be 190 MB), and 7.7 MB once for the forecast |
| time on the network | 0.3 to 0.9 s; the 7.7 MB `.tar` 1.5 to 16 s (DWD's server, its speed varies a lot) | 15 s one after the other for the analysis (a page asks 4 to 6 at a time, see below), once per run for the forecast |
| CPU (decode, classify, warp, PNG) | 10 to 60 ms to read the file, 25 to 50 ms to draw it | about 2.5 s for 49 frames; each is drawn once, whoever asks |
| memory | about 32 MB above what is held while a frame is drawn, at most two at a time; 18 MB for the warp, made once | 49 PNGs of 35 KB (1.7 MB) and up to four `.tar` files held (31 MB: the three runs whose forecast is served and the next, so a run's tar is read once however the frames of the runs are asked for); the cap is 400 frames (14 MB) |
| size | PNG 34 KB | 1.7 MB |

Steady state is a new run every 5 minutes: one analysis frame (400 KB, 0.1 s of CPU) and, the first time anyone asks for
the forecast of it, 24 frames of 30 ms each. The frames are held in the process (by run and lead time, which never
change, so there is no expiry: the oldest are dropped), a frame that two readers ask for at the same time is drawn once,
and at most two are drawn at a time. The forecast is served for the newest three runs DWD lists only (a request for the forecast of an older run is a 404, so no request makes the server read the 7.7 MB tar of any of the 576 runs of two days), and no file is asked of DWD for a run it does not list. The tar of a forecast is downloaded before the frame's lock is taken, so a cold analysis frame does not wait behind it. The whole tar of a run is read for its analysis only where the first file of the tar is not the analysis (or the server ignores `Range`), and then for the newest three runs only. A body that DWD answers for a tar and that is none (an outage page, an empty body) is a 502 and is held for no frame. A server holds at most 32 requests at once by default (`WD_RESTAPI_MAX_CONCURRENT`, a 33rd is a 503): a page should load its frames 4 to 6 at a time, not the 49 at once. With several worker processes each holds its own, and a worker whose list of runs is older than a run that has just appeared answers a 404 for it until it lists again (at most 10 seconds). Decoding needs `h5py` and
`numpy`, which the `radar` extra installs and the image of the server (`docker/Dockerfile`) already has; wradlib,
xradar and PROJ are not used. h5py reads the grid by its own filters in a build that leaks about the size of the grid on
every read (h5py 3.16 with HDF5 2.0 on macOS grew by 5.7 MB per read, to 220 MB after 25 frames), so the one chunk of
DWD's grid is inflated from its stored bytes by zlib, which does not, and is faster; any other layout is read by h5py.
