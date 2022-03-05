# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, Tuple

import requests


def download_road_weather_observations_parallel(
    remote_files: List[str],
) -> List[Tuple[str, bytes]]:
    """
    Wrapper for ``_download_dwd_data`` to provide a multiprocessing feature.
    :param remote_files:    List of requested files
    :return:                List of downloaded files
    """
    # with ThreadPoolExecutor() as executor: # this is not a real parallel download
    #     files_in_bytes = executor.map(
    #         _download_road_weather_observations_data,
    #         remote_files
    #     )
    files_in_bytes = []
    for file in remote_files:
        files_in_bytes.append(_download_road_weather_observations_data(file))

    return list(zip(remote_files, files_in_bytes))


def _download_road_weather_observations_data(remote_file: str) -> bytes:
    """
    This function downloads the road weather station data for which the link is
    provided. It checks the shortened filepath for its parameters, creates the
    full filepath and downloads then file(s) according to the set up folder.
    Args:
        remote_file: contains path to file that should be downloaded
            and the path to the folder to store the files
    Returns:
        stores data on local file system
    """

    return requests.get(remote_file).content
