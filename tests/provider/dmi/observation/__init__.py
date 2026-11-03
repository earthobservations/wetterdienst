# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.


def country_of(station_id: str) -> str:
    """DMI's country code of the stations the tests read: `04xxx` Greenland, 06011 Faroe Islands, the rest Denmark."""
    if station_id.startswith("04"):
        return "GRL"
    return "FRO" if station_id == "06011" else "DNK"
