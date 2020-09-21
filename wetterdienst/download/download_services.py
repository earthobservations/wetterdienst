"""
**DWD download utilities**
"""
import logging
from io import BytesIO
from pathlib import PurePosixPath
from typing import Union

from wetterdienst.constants.access_credentials import DWDCDCBase
from wetterdienst.download.https_handling import create_dwd_session
from wetterdienst.file_path_handling.path_handling import build_dwd_cdc_data_path

logger = logging.getLogger(__name__)


def download_file_from_dwd(
    filepath: Union[PurePosixPath, str], cdc_base: DWDCDCBase
) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param filepath:    The path that defines the file relative to
                        ``observations_germany/climate/``.
    :param cdc_base:    Foobar.

    :return:            Bytes of the file.
    """
    dwd_session = create_dwd_session()

    url = build_dwd_cdc_data_path(filepath, cdc_base)
    logger.info(f"Downloading resource {url}")
    r = dwd_session.get(url)
    r.raise_for_status()

    return BytesIO(r.content)
