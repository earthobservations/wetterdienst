from wetterdienst.enumerations.parameter_enumeration import Parameter  # noqa:F401
from wetterdienst.enumerations.time_resolution_enumeration import (  # noqa:F401
    TimeResolution,
)
from wetterdienst.enumerations.period_type_enumeration import PeriodType  # noqa:F401
from wetterdienst.parse_metadata import metadata_for_dwd_data  # noqa:F401
from wetterdienst.file_path_handling.file_list_creation import (  # noqa:F401
    create_file_list_for_dwd_server,
)
from wetterdienst.indexing.file_index_creation import (  # noqa:F401
    reset_file_index_cache,
)
from wetterdienst.indexing.meta_index_creation import (  # noqa:F401
    reset_meta_index_cache,
)
from wetterdienst.download.download import download_dwd_data_parallel  # noqa:F401
from wetterdienst.parsing_data.parse_data_from_files import parse_dwd_data  # noqa:F401
from wetterdienst.additionals.geo_location import get_nearby_stations  # noqa:F401
from wetterdienst.data_collection import collect_dwd_data  # noqa:F401
from wetterdienst.dwd_station_request import DWDStationRequest  # noqa:F401


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
