# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tell the stations that have data files on the DWD server and no line in the station description (GH-3258).

The description of a dataset is where the name and the position of a station come from, so the observation and
derived networks list the stations that are in both the description and the file index. A station that has files and
no line is not a station of the catalogue, and no request can name it, which is DWD's to fix, so what is left to do
is to say it: a station that cannot be found is then explained.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

log = logging.getLogger(__name__)

# the stations named in one message, the rest is counted: a dataset of 10 minutes lists a handful, none more than 12
_NAMED = 20


def warn_files_without_description(
    network: str, dataset: str, file_ids: Iterable[str], listed_ids: Iterable[str]
) -> None:
    """Log the stations of the file index that the description does not list, if there are any.

    :param network: the network, such as `dwd/observation`
    :param dataset: the resolution and dataset, such as `daily/climate_summary`
    :param file_ids: the ids the data files of the dataset name
    :param listed_ids: the ids the description of the dataset lists
    """
    unlisted = sorted(set(file_ids) - set(listed_ids))
    if not unlisted:
        return
    named = ", ".join(unlisted[:_NAMED])
    if len(unlisted) > _NAMED:
        named = f"{named} and {len(unlisted) - _NAMED} more"
    log.warning(
        "%s %s: the server has data files of %d station(s) that its station description does not list, so they are "
        "not offered as stations and their data cannot be requested: %s (GH-3258)",
        network,
        dataset,
        len(unlisted),
        named,
    )
