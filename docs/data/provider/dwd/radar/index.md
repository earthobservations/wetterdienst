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
| `SWEEP_PCP_VELOCITY_H`, `SWEEP_PCP_REFLECTIVITY_H`, `SWEEP_VOL_VELOCITY_H`, `SWEEP_VOL_REFLECTIVITY_H` (site) | ODIM HDF5 files, in the folder of the filter (`subset`: `SIMPLE` or `POLARIMETRIC`); the reflectivity has a third folder, `unfiltered` (`subset=DwdRadarDataSubset.UNFILTERED`), with two files for each sweep, `..._th_00-2026102213105700-boo-10132-hd5` and `..._tv_00-...`: the total (uncorrected) reflectivity factor ODIM `TH` and `TV`, the horizontally and the vertically polarized one. A request answers both (there is no choosing one): tell them apart by `result.url` or the `quantity` of the file |
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
listed 15:51 to 15:53 and 5 to 9 at 15:48 to 15:49; the scan time inside the files of 0, 3 and 4 is 15:50, inside that of 9 15:45): ask for a time instead (`MOST_RECENT` can lack the last sweeps of a volume, GH-3302). The folders of a filter hold none and KONRAD3D has none.
`start=DwdRadarDate.MOST_RECENT` of an HDF5 or XML product (not RADOLAN's, unless `fmt` is named) is the 5 minute slot
before now; for RS, DMAX, VII, KONRAD3D and the mesocyclones, which DWD publishes more than 5 minutes after the run in
more than one run of a hundred (up to 9 minutes), the slot 10 minutes before now, and so for the site products PE, PZ, PR
and LMAX, which are as late as RS in 18 of 577 runs (up to 8 minutes, read 2026-10-22).

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
| `SWEEP_VOL_ZDR`, `SWEEP_PCP_ZDR` | the sheets of the sweeps ("Standort-Reflektivitäts- und Radialgeschwindigkeitsprodukte") name no polarimetric moment; DWD's [ODIM-DWD-E_1-0 description](https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/hdf/ODIM-Beschreibung.pdf?__blob=publicationFile) lists the moment `uzdr` as ODIM `UZDR` | `UZDR`, which ODIM 2.3 defines as "Logged differential reflectivity that has not been subject to a Doppler filter", ZDR in dB |
| `SWEEP_VOL_RHOHV`, `SWEEP_PCP_RHOHV` | as above, `urhohv` is ODIM `URHOHV` | `URHOHV`: "Correlation between Zh and Zv that has not been subject to any filter or correction", ρhv from 0 to 1 |
| `SWEEP_VOL_PHIDP`, `SWEEP_PCP_PHIDP` | as above, `uphidp` is ODIM `UPHIDP` | `UPHIDP`: "Differential phase that has not been subject to any filter or correction", φdp in degrees |
| `KONRAD3D_CONVECTIVE_CELLS` | "Erkennung, Verfolgung und Nowcasting konvektiver Zellen" ([Kurzdokumentation KONRAD3D](https://www.dwd.de/DE/leistungen/radarprodukte/konrad3d_kurzbeschreibung.pdf?__blob=publicationFile)); "Ausgabeformat: xml", one file every five minutes, `KONRAD3D_YYYYMMDDThhmmss.xml`, the run's reference time being the start of the radar scan cycle | an XML document, root `konrad3d` (`data_model_name`, `data_model_version`), a `head` (reference time, the run, the grid, the sweeps used) and `cells`, with a `feature` for each cell: its geometry, intensity and further groups; no cell is an empty `cells`. The [format description](https://www.dwd.de/DE/leistungen/radarprodukte/formatbeschreibung_konrad3d.pdf?__blob=publicationFile) is DWD's |
| `MESOCYCLONE_DETECTION` | "xml-Dateien mit sämtlichen Mesozyklonenerkennungen eines Referenzzeitpunktes" ([Dokumentation Mesozyklonenerkennung](https://www.dwd.de/DE/leistungen/radarprodukte/dokumentation_mcd.pdf?__blob=publicationFile), 07.2022), the volume scans of the 17 sites, a run every 5 minutes | an XML document, root `nowcast-data`, with the `radar-stations` and an `event` for each detected mesocyclone (its time, a `location` ellipse and `nowcast-parameters` such as `mesocyclone_shear_max` and `mesocyclone_diameter`, each with its `units`); a run without a mesocyclone is the station list alone (173 bytes) |

The sweeps are the polar data of one site (`site=DwdRadarSite.BOO`): 360 rays of 250 m bins, as many bins as the
elevation has. The volume scan has ten elevations, which are ten files a run (`elevation=0` to `9` picks one of them,
for the polarimetric moments as for the velocity and the reflectivity), the precipitation scan one file. The unfiltered
reflectivity has two files for each sweep, TH and TV, and `elevation` picks the pair. The unfiltered
polarimetric moments have no folder of a filter, as the velocity and the reflectivity sweeps do (`hdf5/filter_simple`
and `hdf5/filter_polarimetric`).
