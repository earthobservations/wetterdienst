# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for radar parameters."""

from enum import Enum

from wetterdienst.exceptions import RequestError


class DwdRadarParameter(Enum):
    """All available radar moments."""

    # /composites
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-RADOLAN-(quantitative)-composit  # noqa: E501

    # https://opendata.dwd.de/weather/radar/composite/
    # one .tar of ODIM HDF5 files a run, the analysis and the forecasts of the next two hours
    RV_REFLECTIVITY = "rv"
    WN_REFLECTIVITY = "wn"
    # the same, the precipitation accumulated over the hour before each lead time
    RS_PRECIPITATION_SUM = "rs"
    # one ODIM HDF5 file a run: the reflectivity of the precipitation scan (HX) and of the volume scan (DMAX), the
    # vertically integrated ice (VII) and the precipitation type at 2 m (HymecNG)
    HX_REFLECTIVITY = "hx"
    DMAX_REFLECTIVITY = "dmax"
    VII_INTEGRATED_ICE = "vii"
    HYMECNG_PRECIPITATION_TYPE = "hymecng"

    # /radolan
    # https://opendata.dwd.de/weather/radar/radolan/
    RW_REFLECTIVITY = "rw"
    RY_REFLECTIVITY = "ry"
    SF_REFLECTIVITY = "sf"
    YW_REFLECTIVITY = "yw"

    # /konrad3d, /mesocyclones: one XML file every 5 minutes
    # https://opendata.dwd.de/weather/radar/konrad3d/
    # https://opendata.dwd.de/weather/radar/mesocyclones/
    KONRAD3D_CONVECTIVE_CELLS = "konrad3d"
    MESOCYCLONE_DETECTION = "mesocyclones"

    # /sites
    # https://opendata.dwd.de/weather/radar/sites/
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-DX-format
    DX_REFLECTIVITY = "dx"
    LMAX_VOLUME_SCAN = "lmax"
    PE_ECHO_TOP = "pe"
    PR_VELOCITY = "pr"
    PX250_REFLECTIVITY = "px250"
    PZ_CAPPI = "pz"

    # OPERA HDF5 (ODIM_H5)
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#HDF5
    SWEEP_PCP_VELOCITY_H = "sweep_pcp_v"
    SWEEP_PCP_REFLECTIVITY_H = "sweep_pcp_z"
    SWEEP_VOL_VELOCITY_H = "sweep_vol_v"
    SWEEP_VOL_REFLECTIVITY_H = "sweep_vol_z"
    # the polarimetric moments, unfiltered: differential reflectivity, correlation coefficient, differential phase
    SWEEP_PCP_ZDR = "sweep_pcp_zdr"
    SWEEP_PCP_RHOHV = "sweep_pcp_rhohv"
    SWEEP_PCP_PHIDP = "sweep_pcp_phidp"
    SWEEP_VOL_ZDR = "sweep_vol_zdr"
    SWEEP_VOL_RHOHV = "sweep_vol_rhohv"
    SWEEP_VOL_PHIDP = "sweep_vol_phidp"

    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    RADOLAN_CDC = "radolan_cdc"


RADAR_PARAMETERS_COMPOSITES = [
    DwdRadarParameter.RV_REFLECTIVITY,
    DwdRadarParameter.WN_REFLECTIVITY,
    DwdRadarParameter.RS_PRECIPITATION_SUM,
    DwdRadarParameter.HX_REFLECTIVITY,
    DwdRadarParameter.DMAX_REFLECTIVITY,
    DwdRadarParameter.VII_INTEGRATED_ICE,
    DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE,
]
# the composites that are a .tar a run, with a file in it for every lead time; the others are the file itself
RADAR_PARAMETERS_COMPOSITES_TAR = [
    DwdRadarParameter.RV_REFLECTIVITY,
    DwdRadarParameter.WN_REFLECTIVITY,
    DwdRadarParameter.RS_PRECIPITATION_SUM,
]
RADAR_PARAMETERS_RADOLAN = [
    DwdRadarParameter.RW_REFLECTIVITY,
    DwdRadarParameter.RY_REFLECTIVITY,
    DwdRadarParameter.SF_REFLECTIVITY,
    DwdRadarParameter.YW_REFLECTIVITY,
]
# what is detected in the radar data, one XML file a run, in a directory of weather/radar of its own
RADAR_PARAMETERS_DETECTIONS = [
    DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS,
    DwdRadarParameter.MESOCYCLONE_DETECTION,
]
RADAR_PARAMETERS_SITES = [
    DwdRadarParameter.DX_REFLECTIVITY,
    DwdRadarParameter.LMAX_VOLUME_SCAN,
    DwdRadarParameter.PE_ECHO_TOP,
    DwdRadarParameter.PR_VELOCITY,
    DwdRadarParameter.PX250_REFLECTIVITY,
    DwdRadarParameter.PZ_CAPPI,
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_PCP_ZDR,
    DwdRadarParameter.SWEEP_PCP_RHOHV,
    DwdRadarParameter.SWEEP_PCP_PHIDP,
    DwdRadarParameter.SWEEP_VOL_ZDR,
    DwdRadarParameter.SWEEP_VOL_RHOHV,
    DwdRadarParameter.SWEEP_VOL_PHIDP,
]
RADAR_PARAMETERS_SWEEPS = [
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_PCP_ZDR,
    DwdRadarParameter.SWEEP_PCP_RHOHV,
    DwdRadarParameter.SWEEP_PCP_PHIDP,
    DwdRadarParameter.SWEEP_VOL_ZDR,
    DwdRadarParameter.SWEEP_VOL_RHOHV,
    DwdRadarParameter.SWEEP_VOL_PHIDP,
]
# the products that DWD publishes more than 5 minutes after their run in more than one run of a hundred, whose most
# recent file is the slot 10 minutes before now, where that of the others (HX never, HymecNG twice) is the one 5 minutes
# before. The 576 runs of the two days of 2026-10-20 to 22 (the longest delay 523 s): VII all, KONRAD3D 161, the
# mesocyclones 56, DMAX 55, RS 7 (GH-3283); the site products PE, PZ, PR and LMAX at BOO, 18 of 577 runs each, the
# longest 484 s (GH-3288)
RADAR_PARAMETERS_SLOW = [
    DwdRadarParameter.RS_PRECIPITATION_SUM,
    DwdRadarParameter.DMAX_REFLECTIVITY,
    DwdRadarParameter.VII_INTEGRATED_ICE,
    DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS,
    DwdRadarParameter.MESOCYCLONE_DETECTION,
    DwdRadarParameter.LMAX_VOLUME_SCAN,
    DwdRadarParameter.PE_ECHO_TOP,
    DwdRadarParameter.PR_VELOCITY,
    DwdRadarParameter.PZ_CAPPI,
]
# the sweeps of the volume scan, which has ten elevations: the ones `elevation` selects among
RADAR_PARAMETERS_SWEEPS_VOLUME = [
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_VOL_ZDR,
    DwdRadarParameter.SWEEP_VOL_RHOHV,
    DwdRadarParameter.SWEEP_VOL_PHIDP,
]


class DwdRadarDate(Enum):
    """Enumeration for pointing to different radar dates."""

    LATEST = "latest"
    CURRENT = "current"
    MOST_RECENT = "most_recent"


class DwdRadarDataFormat(Enum):
    """Radar data formats."""

    BINARY = "binary"
    HDF5 = "hdf5"
    XML = "xml"


class DwdRadarDataSubset(Enum):
    """HDF5 subset types for radar sweep data.

    https://opendata.dwd.de/weather/radar/sites/sweep_pcp_v/boo/hdf5/
    """

    SIMPLE = "simple"
    POLARIMETRIC = "polarimetric"
    # the folder `unfiltered`: the polarimetric moments ZDR, RHOHV and PHIDP as measured, and the total reflectivity
    # TH and TV of SWEEP_PCP_REFLECTIVITY_H and SWEEP_VOL_REFLECTIVITY_H
    UNFILTERED = "unfiltered"


# What the source serves each product as, read from the directory listings on 2026-10-22, when the composites
# were ODIM HDF5 (files back to 2026-10-20) and no radar product was published as BUFR: a request names the
# format of the product it asks for, or none, and a format the product is not served in is refused
# instead of answering an empty listing. The RADOLAN products and RADOLAN_CDC are not listed: they are
# no choice of format (the RADOLAN files are HDF5 named `---bin.hdf5`).
RADAR_DATA_FORMATS: dict[DwdRadarParameter, tuple[DwdRadarDataFormat, ...]] = {
    # composite/{rv,wn,rs}/composite_rv_YYYYMMDD_HHMM.tar, one ODIM HDF5 file in it for each lead time
    DwdRadarParameter.RV_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.WN_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.RS_PRECIPITATION_SUM: (DwdRadarDataFormat.HDF5,),
    # composite/{hx,dmax,vii,hymecng}/composite_hx_YYYYMMDD_HHMM-hd5, one ODIM HDF5 file a run
    DwdRadarParameter.HX_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.DMAX_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.VII_INTEGRATED_ICE: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE: (DwdRadarDataFormat.HDF5,),
    # konrad3d/KONRAD3D_YYYYMMDDThhmmss.xml, mesocyclones/meso_YYYYMMDD_HHMM.xml
    DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS: (DwdRadarDataFormat.XML,),
    DwdRadarParameter.MESOCYCLONE_DETECTION: (DwdRadarDataFormat.XML,),
    # sites/dx/<site>/raa00-dx_10132-2610221130-boo---bin
    DwdRadarParameter.DX_REFLECTIVITY: (DwdRadarDataFormat.BINARY,),
    # sites/<product>/<site>/rab02-pe_10132-20261022113000-deboo-hd5
    DwdRadarParameter.LMAX_VOLUME_SCAN: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PE_ECHO_TOP: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PR_VELOCITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PX250_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PZ_CAPPI: (DwdRadarDataFormat.HDF5,),
    # sites/sweep_*/<site>/hdf5/filter_<subset>/, sites/sweep_*_{zdr,rhohv,phidp}/<site>/unfiltered/
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_PCP_ZDR: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_PCP_RHOHV: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_PCP_PHIDP: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_ZDR: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_RHOHV: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_PHIDP: (DwdRadarDataFormat.HDF5,),
}

# The folders of a sweep product a request can choose between: the velocity holds a folder for each filter, the
# reflectivity those two and `unfiltered`, which holds the total (uncorrected) reflectivity factor TH and TV, the
# horizontally and the vertically polarized one, as two files for each sweep; the polarimetric moments have only the
# unfiltered folder (their quantities are the ODIM ones of the unfiltered moments, UZDR, URHOHV and UPHIDP). A product
# with one folder need not be asked for it; one with several is asked, as it always was. The two quantities of the
# unfiltered reflectivity cannot be told apart by the request: it answers both (GH-3288).
RADAR_DATA_SUBSETS: dict[DwdRadarParameter, tuple[DwdRadarDataSubset, ...]] = {
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H: (DwdRadarDataSubset.SIMPLE, DwdRadarDataSubset.POLARIMETRIC),
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H: (
        DwdRadarDataSubset.SIMPLE,
        DwdRadarDataSubset.POLARIMETRIC,
        DwdRadarDataSubset.UNFILTERED,
    ),
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H: (DwdRadarDataSubset.SIMPLE, DwdRadarDataSubset.POLARIMETRIC),
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H: (
        DwdRadarDataSubset.SIMPLE,
        DwdRadarDataSubset.POLARIMETRIC,
        DwdRadarDataSubset.UNFILTERED,
    ),
    DwdRadarParameter.SWEEP_PCP_ZDR: (DwdRadarDataSubset.UNFILTERED,),
    DwdRadarParameter.SWEEP_PCP_RHOHV: (DwdRadarDataSubset.UNFILTERED,),
    DwdRadarParameter.SWEEP_PCP_PHIDP: (DwdRadarDataSubset.UNFILTERED,),
    DwdRadarParameter.SWEEP_VOL_ZDR: (DwdRadarDataSubset.UNFILTERED,),
    DwdRadarParameter.SWEEP_VOL_RHOHV: (DwdRadarDataSubset.UNFILTERED,),
    DwdRadarParameter.SWEEP_VOL_PHIDP: (DwdRadarDataSubset.UNFILTERED,),
}

# Products DWD no longer publishes, by the value they were requested by, and what a caller is told. They
# are no members of `DwdRadarParameter` any more, so the request names why instead of the valid values.
_NOT_PUBLISHED_COMPOSITE = (
    "opendata.dwd.de/weather/radar/composite/{value}/ holds no file (found empty on 2026-10-22), and the "
    "composites DWD publishes now are ODIM HDF5: use rv_reflectivity or wn_reflectivity"
)
_NOT_PUBLISHED_RADVOR = (
    "opendata.dwd.de/weather/radar/radvor/{value}/ holds no file ({found}): use rv_reflectivity or wn_reflectivity, "
    "the nowcasts of the composites"
)
_NOT_PUBLISHED_SITE = (
    "opendata.dwd.de/weather/radar/sites/{value}/ holds no current file of any site (found on 2026-10-22: "
    "{found}), and DWD no longer publishes BUFR radar products"
)
# A format DWD no longer publishes any radar product in, by the value it was requested by
RADAR_DATA_FORMATS_NOT_PUBLISHED: dict[str, str] = {
    "bufr": (
        "DWD no longer publishes any radar product as BUFR (found on 2026-10-22: no BUFR file in "
        "opendata.dwd.de/weather/radar/, whose products are ODIM HDF5, binary RADOLAN or XML), and the reader "
        "of it was removed: use the format a product is served in, see RADAR_DATA_FORMATS"
    ),
}
RADAR_PARAMETERS_NOT_PUBLISHED: dict[str, str] = {
    "hg": _NOT_PUBLISHED_COMPOSITE.format(value="hg"),
    "pg": _NOT_PUBLISHED_COMPOSITE.format(value="pg"),
    "px": _NOT_PUBLISHED_SITE.format(value="px", found="no file for any site but mhp, whose newest is from 2026-10-21"),
    "pf": _NOT_PUBLISHED_SITE.format(value="pf", found="no file for any site"),
    "re": _NOT_PUBLISHED_RADVOR.format(value="re", found="found empty on 2026-10-22, its last files of 2026-10-20"),
    "rq": _NOT_PUBLISHED_RADVOR.format(value="rq", found="found empty on 2026-10-22, empty since 2026-05-14"),
}


def radar_data_format(parameter: DwdRadarParameter, fmt: DwdRadarDataFormat | None) -> DwdRadarDataFormat | None:
    """Give the format a request reads a product in: the one asked for, or the only one it is served in.

    Raises:
        RequestError: the product is not served in the format asked for.

    """
    served = RADAR_DATA_FORMATS.get(parameter)
    if served is None:
        # the RADOLAN products are HDF5 or binary as they are asked, and no XML
        if fmt == DwdRadarDataFormat.XML:
            msg = f"{parameter.name} is no XML product: DWD publishes XML for KONRAD3D and the mesocyclones only"
            raise RequestError(msg)
        return fmt
    if fmt is None:
        return served[0] if len(served) == 1 else None
    if fmt not in served:
        names = ", ".join(f"{f.name} ({f.value})" for f in served)
        msg = f"{parameter.name} is published as {names} only, not as {fmt.name}"
        raise RequestError(msg)
    return fmt


def radar_data_subset(parameter: DwdRadarParameter, subset: DwdRadarDataSubset | None) -> DwdRadarDataSubset | None:
    """Give the folder of a sweep product a request reads: the one asked for, or the only one it has.

    A product that is no sweep has no folders and is given the subset back as it is.

    Raises:
        RequestError: the product has no folder of that subset.

    """
    served = RADAR_DATA_SUBSETS.get(parameter)
    if served is None:
        return subset
    if subset is None:
        return served[0] if len(served) == 1 else None
    if subset not in served:
        names = ", ".join(f"{s.name} ({s.value})" for s in served)
        msg = f"{parameter.name} is offered as {names} only, not as {subset.name}"
        raise RequestError(msg)
    return subset
