"""The inputs of the benchmarks, read through the library from DWD's open data (key-less)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from research.altair_vl_convert.prototype import Stripes
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.core import StripesImageRequest, _get_stripes_data

if TYPE_CHECKING:
    from wetterdienst.model.result import StationsResult, ValuesResult


def stripes(kind: str = "temperature", station: str = "02290") -> Stripes:
    """Return the climate stripes of a station: Hohenpeissenberg's 245 years of annual means by default."""
    data = _get_stripes_data(StripesImageRequest(kind=kind, station=station))  # ty: ignore[invalid-argument-type]
    return Stripes(kind=kind, data=data)  # ty: ignore[invalid-argument-type]


def stations(distance: float = 60, latlon: tuple[float, float] = (48.14, 11.58)) -> StationsResult:
    """Return the DWD stations within `distance` km of a point (Munich) of hourly air temperature and hourly solar radiation."""
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air"), ("hourly", "solar")],
        periods="recent",
    )
    return request.filter_by_distance(latlon=latlon, distance=distance)


def values(*, start: str, end: str, station_ids: tuple[str, ...] = ("00433",), parameters: int = 1) -> ValuesResult:
    """Return the hourly values of stations in `[start, end]`: air temperature, and with `parameters=2` humidity too."""
    selection = [("hourly", "temperature_air", "temperature_air_2m")]
    if parameters == 2:
        selection.append(("hourly", "temperature_air", "humidity_relative"))
    request = DwdObservationRequest(parameters=selection, periods="historical", start=start, end=end)
    return request.filter_by_station_id(station_ids).values().all()
