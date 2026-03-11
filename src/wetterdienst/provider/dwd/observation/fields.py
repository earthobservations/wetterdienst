# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parse description PDF files from DWD CDC server.

Derived from https://gist.github.com/amotl/ffc9d4b864660c93bed53d59547a5fce.

Setup:

    pip install pypdf tabulate

Synopsis:

    python dwd_description_pdf.py
"""

import re
from collections import OrderedDict
from io import StringIO

from tabulate import tabulate

from wetterdienst.util.pdf import read_pdf


def parse_section(text: str, headline: str) -> str:
    """Parse a section from a DWD climate data set description."""
    capture = False
    buffer = StringIO()
    for line in text.split("\n"):
        if line.strip().startswith(headline):
            capture = True
        if line.strip() == "":
            capture = False
        if capture:
            buffer.write(line)
            buffer.write("\n")
    return buffer.getvalue()


def parse_parameters(text: str) -> dict:
    """Parse the parameters table from a DWD CSV content description section.

    Handles the current PDF format where each row starts with an all-caps column
    name followed by description, unit, type and format on the same line (with
    possible line wraps for long values).
    """
    # Identifiers that appear as cell-wrap or header artifacts, not parameter names.
    _skip = frozenset({"NUMBER", "VARCHAR2", "CSV", "EOR", "-"})

    data = {}
    current_param: str | None = None
    current_desc_parts: list[str] = []

    def save_current() -> None:
        if current_param and current_param not in _skip:
            desc = " ".join(p for p in current_desc_parts if p)
            # Strip trailing TYPE and FORMAT suffix (NUMBER .../VARCHAR2 ...)
            desc = re.sub(r"\s+(?:NUMBER|VARCHAR2)\b.*$", "", desc, flags=re.IGNORECASE).strip()
            data[current_param.lower()] = desc

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Each parameter row begins with an all-caps identifier (letters, digits,
        # underscores) followed by a space and the description / metadata.
        match = re.match(r"^([A-Z][A-Z0-9_]+)\s+(.*)", stripped)
        if match:
            save_current()
            current_param = match.group(1)
            rest = match.group(2).strip()
            current_desc_parts = [rest] if rest else []
        elif current_param is not None:
            current_desc_parts.append(stripped)

    save_current()
    return data


def read_description(url: str, language: str = "en") -> dict:
    """Read the description of a DWD climate data set from a PDF file."""
    if language == "en":
        csv_header = "csv content description"
        quality_header = "Quality Information"
    elif language == "de":
        csv_header = "CSV Inhaltsbeschreibung"
        quality_header = "Qualitätsinformation"
    else:
        msg = "Only language 'en' or 'de' supported"
        raise ValueError(msg)
    data = OrderedDict()
    document = read_pdf(url)
    document = re.sub(r"www\.dwd\.de\n-\n\d+\n-\n", "", document)
    # Extract CSV content section using position-based boundaries.
    csv_start = document.lower().find(csv_header.lower())
    quality_start = document.find(quality_header)
    if csv_start != -1:
        csv_end = quality_start if quality_start > csv_start else len(document)
        data["parameters"] = parse_parameters(document[csv_start:csv_end])
    else:
        data["parameters"] = {}
    data["quality_information"] = document[quality_start:] if quality_start != -1 else ""
    return data


def process(url: str) -> None:
    """Process a DWD climate data set description."""
    parameters = read_description(url)

    # Output as JSON.
    # import json; print(json.dumps(parameters, indent=4))  # noqa: ERA001

    # Output as ASCII table.
    print(tabulate(list(parameters.items()), tablefmt="psql"))  # noqa: T201


if __name__ == "__main__":  # pragma: no cover
    ten_minutes_air = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/"
        "air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf"
    )
    hourly_solar = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/"
        "solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf"
    )
    daily_kl = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/"
        "kl/DESCRIPTION_obsgermany-climate-daily-kl_en.pdf"
    )

    for item in ten_minutes_air, hourly_solar, daily_kl:
        print(item)  # noqa: T201
        process(item)
        print()  # noqa: T201
