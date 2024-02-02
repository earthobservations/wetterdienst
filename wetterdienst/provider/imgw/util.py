from io import BytesIO
from typing import Optional

from wetterdienst import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import _download_file


def _try_download_file(url: str, settings: Settings, ttl: CacheExpiry) -> Optional[BytesIO]:
    try:
        return _download_file(url=url, settings=settings, ttl=ttl)
    except Exception:
        return None
