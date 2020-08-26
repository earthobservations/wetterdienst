from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import (
    TimeResolution,
)
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.parse_metadata import metadata_for_climate_observations
from wetterdienst.file_path_handling.file_list_creation import (
    create_file_list_for_climate_observations,
)
from wetterdienst.indexing.file_index_creation import (
    reset_file_index_cache,
)
from wetterdienst.indexing.meta_index_creation import (
    reset_meta_index_cache,
)
from wetterdienst.download.download import download_climate_observations_data_parallel
from wetterdienst.parsing_data.parse_data_from_files import (
    parse_climate_observations_data,
)
from wetterdienst.additionals.geo_location import get_nearby_stations
from wetterdienst.data_collection import (
    collect_climate_observations_data,
    collect_radolan_data,
)
from wetterdienst.api import DWDStationRequest, DWDRadolanRequest

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
