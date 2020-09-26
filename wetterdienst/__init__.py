from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.time_resolution import TimeResolution
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst.dwd.observations.api import (
    DWDStationRequest,
    discover_climate_observations,
)
from wetterdienst.dwd.observations.stations import (
    metadata_for_climate_observations,
    get_nearby_stations_by_number,
    get_nearby_stations_by_distance,
)
from wetterdienst.dwd.radolan.api import DWDRadolanRequest

# Load Pandas extensions.
import wetterdienst.pandas

"""Wetterdienst - Open weather data for humans"""
__appname__ = "wetterdienst"

# Single-sourcing the package version
# https://cjolowicz.github.io/posts/hypermodern-python-06-ci-cd/
try:
    from importlib.metadata import version, PackageNotFoundError  # noqa
except ImportError:  # pragma: no cover
    from importlib_metadata import version, PackageNotFoundError  # noqa

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
