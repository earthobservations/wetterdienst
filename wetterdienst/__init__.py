"""Wetterdienst - Open weather data for humans"""
__appname__ = "wetterdienst"

from wetterdienst.dwd.metadata import Parameter, TimeResolution, PeriodType
from wetterdienst.dwd.observations.api import (
    DWDObservationData,
    DWDObservationSites,
    DWDObservationMetadata,
)
from wetterdienst.dwd.radar.api import DWDRadarRequest
from wetterdienst.dwd.radar.metadata import RadarParameter

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
