# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parse description PDF files from DWD CDC server.

Derived from https://gist.github.com/amotl/ffc9d4b864660c93bed53d59547a5fce.

Setup:

    pip install PyPDF2 tabulate

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
    """Parse the parameters section of a DWD climate data set description."""
    data = {}
    parameter = None
    capture = False
    buffer = StringIO()
    for line in text.split("\n"):
        line_cleaned = line.strip()
        if line_cleaned == line_cleaned.upper() and not line_cleaned.isnumeric():
            if line_cleaned != parameter:
                more = buffer.getvalue()
                if more and "eor" not in more:
                    more = more.strip()
                    if parameter == "RSKF":
                        # Remove some anomaly.
                        more = more.replace("0\n1\n", "1\n")
                        # Replace newlines after digits with "-".
                        more = re.sub(r"^(\d+)\n(.*)", r"\g<1>- \g<2>", more, flags=re.MULTILINE)
                        # Remove all newlines _within_ text descriptions, per item.
                        more = re.sub(r"\n(?!\d+)", " ", more, flags=re.DOTALL)
                    else:
                        more = more.replace("\n", " ")
                    if parameter != "-":
                        data[parameter.lower()] = more
                buffer.truncate(0)
                buffer.seek(0)
            parameter = line_cleaned
            capture = True

        elif capture:
            buffer.write(line_cleaned)
            buffer.write("\n")
    return data


def read_description(url: str, language: str = "en") -> dict:
    """Read the description of a DWD climate data set from a PDF file."""
    if language == "en":
        sections = {
            "parameters": "csv content description",
            "quality_information": "Quality information",
        }
    elif language == "de":
        sections = {
            "parameters": "Parameter",
            "quality_information": "Qualitätsinformation",
        }
    else:
        msg = "Only language 'en' or 'de' supported"
        raise ValueError(msg)
    data = OrderedDict()
    # Read "Parameters" section.
    document = read_pdf(url)
    document = re.sub(r"www\.dwd\.de\n-\n\d+\n-\n", "", document)
    parameters_text = parse_section(document, sections["parameters"])
    data["parameters"] = parse_parameters(parameters_text)
    # Read "Quality information" section.
    data["quality_information"] = parse_section(document, sections["quality_information"])
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
        "air_temperature/recent/DESCRIPTION_obsgermany_climate_10min_tu_recent_en.pdf"
    )
    hourly_solar = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/"
        "solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf"
    )
    daily_kl = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/"
        "kl/recent/DESCRIPTION_obsgermany_climate_daily_kl_recent_en.pdf"
    )

    for item in ten_minutes_air, hourly_solar, daily_kl:
        print(item)  # noqa: T201
        process(item)
        print()  # noqa: T201
