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

    # /radolan
    # https://opendata.dwd.de/weather/radar/radolan/
    RW_REFLECTIVITY = "rw"
    RY_REFLECTIVITY = "ry"
    SF_REFLECTIVITY = "sf"

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

    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    RADOLAN_CDC = "radolan_cdc"


RADAR_PARAMETERS_COMPOSITES = [
    DwdRadarParameter.RV_REFLECTIVITY,
    DwdRadarParameter.WN_REFLECTIVITY,
]
RADAR_PARAMETERS_RADOLAN = [
    DwdRadarParameter.RW_REFLECTIVITY,
    DwdRadarParameter.RY_REFLECTIVITY,
    DwdRadarParameter.SF_REFLECTIVITY,
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
]
RADAR_PARAMETERS_SWEEPS = [
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
]


class DwdRadarDate(Enum):
    """Enumeration for pointing to different radar dates."""

    LATEST = "latest"
    CURRENT = "current"
    MOST_RECENT = "most_recent"


class DwdRadarDataFormat(Enum):
    """Radar data formats."""

    BINARY = "binary"
    BUFR = "bufr"
    HDF5 = "hdf5"


class DwdRadarDataSubset(Enum):
    """HDF5 subset types for radar sweep data.

    https://opendata.dwd.de/weather/radar/sites/sweep_pcp_v/boo/hdf5/
    """

    SIMPLE = "simple"
    POLARIMETRIC = "polarimetric"


# What the source serves each product as, read from the directory listings on 2026-10-22, when the composites
# were ODIM HDF5 (files back to 2026-10-20) and no radar product was published as BUFR: a request names the
# format of the product it asks for, or none, and a format the product is not served in is refused
# instead of answering an empty listing. The RADOLAN products and RADOLAN_CDC are not listed: they are
# no choice of format (the RADOLAN files are HDF5 named `---bin.hdf5`).
RADAR_DATA_FORMATS: dict[DwdRadarParameter, tuple[DwdRadarDataFormat, ...]] = {
    # composite/{rv,wn}/composite_rv_YYYYMMDD_HHMM.tar, one ODIM HDF5 file in it for each lead time
    DwdRadarParameter.RV_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.WN_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    # sites/dx/<site>/raa00-dx_10132-2610221130-boo---bin
    DwdRadarParameter.DX_REFLECTIVITY: (DwdRadarDataFormat.BINARY,),
    # sites/<product>/<site>/rab02-pe_10132-20261022113000-deboo-hd5
    DwdRadarParameter.LMAX_VOLUME_SCAN: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PE_ECHO_TOP: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PR_VELOCITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PX250_REFLECTIVITY: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.PZ_CAPPI: (DwdRadarDataFormat.HDF5,),
    # sites/sweep_*/<site>/hdf5/filter_<subset>/
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H: (DwdRadarDataFormat.HDF5,),
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H: (DwdRadarDataFormat.HDF5,),
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
        # no product of the others is published as BUFR either
        if fmt == DwdRadarDataFormat.BUFR:
            msg = f"{parameter.name} is not published as BUFR: DWD publishes no radar product as BUFR"
            raise RequestError(msg)
        return fmt
    if fmt is None:
        return served[0] if len(served) == 1 else None
    if fmt not in served:
        names = ", ".join(f"{f.name} ({f.value})" for f in served)
        msg = f"{parameter.name} is published as {names} only, not as {fmt.name}"
        raise RequestError(msg)
    return fmt
