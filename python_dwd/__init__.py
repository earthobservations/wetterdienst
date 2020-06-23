from python_dwd.metadata_dwd import metadata_for_dwd_data
from python_dwd.file_path_handling.file_list_creation import \
    create_file_list_for_dwd_server
from python_dwd.file_path_handling.file_index_creation import reset_file_index_cache
from python_dwd.download.download import download_dwd_data
from python_dwd.parsing_data.parse_data_from_files import parse_dwd_data
from python_dwd.additionals.geo_location import get_nearest_station
from python_dwd.data_collection import collect_dwd_data
from python_dwd.dwd_station_request import DWDStationRequest


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
