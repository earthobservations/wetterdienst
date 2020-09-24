"""
**DWD download utilities**
"""
import logging
from io import BytesIO

from wetterdienst.download.https_handling import create_dwd_session

logger = logging.getLogger(__name__)


def download_file_from_dwd(url: str) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param url:    The url to the file on the dwd server ("https://www.

    :return:            Bytes of the file.
    """
    dwd_session = create_dwd_session()

    logger.info(f"Downloading resource {url}")
    r = dwd_session.get(url)
    r.raise_for_status()

    return BytesIO(r.content)
