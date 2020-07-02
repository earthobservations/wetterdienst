from wetterdienst.parse_metadata import metadata_for_dwd_data
from wetterdienst.file_path_handling.file_list_creation import \
    create_file_list_for_dwd_server
from wetterdienst.indexing.file_index_creation import reset_file_index_cache
from wetterdienst.indexing.meta_index_creation import reset_meta_index_cache
from wetterdienst.download.download import download_dwd_data
from wetterdienst.parsing_data.parse_data_from_files import parse_dwd_data
from wetterdienst.additionals.geo_location import get_nearest_station
from wetterdienst.data_collection import collect_dwd_data
from wetterdienst.dwd_station_request import DWDStationRequest


# Single-sourcing the package version
# https://cjolowicz.github.io/posts/hypermodern-python-06-ci-cd/
try:
    from importlib.metadata import version, PackageNotFoundError  # type: ignore
except ImportError:  # pragma: no cover
    from importlib_metadata import version, PackageNotFoundError  # type: ignore

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
