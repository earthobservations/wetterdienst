"""
Parse description PDF files from DWD CDC server.
Derived from https://gist.github.com/amotl/ffc9d4b864660c93bed53d59547a5fce.

Setup::

    pip install PyPDF2 tabulate

Synopsis::

    python dwd_description_pdf.py
"""
import re
from io import StringIO
from tabulate import tabulate

from wetterdienst.util.pdf import read_pdf


def parse_section(text, headline):
    capture = False
    buffer = StringIO()
    for line in text.split("\n"):
        if headline in line:
            capture = True
        if line == " ":
            capture = False
        if capture:
            buffer.write(line)
            buffer.write("\n")
    payload = buffer.getvalue()
    return payload


def parse_parameters(text):
    data = {}
    parameter = None
    capture = False
    buffer = StringIO()
    for line in text.split("\n"):

        if line == line.upper() and not line.isnumeric():
            if line != parameter:
                more = buffer.getvalue()
                if more and "eor" not in more:
                    more = more.strip()
                    if parameter not in ["RSKF"]:
                        more = more.replace("\n", " ")
                    data[parameter] = more
                buffer.truncate(0)
                buffer.seek(0)
            parameter = line
            capture = True

        else:
            if capture:
                buffer.write(line)
                buffer.write("\n")
    return data


def read_description(url) -> dict:
    document = read_pdf(url)
    document = re.sub(r"www\.dwd\.de\n-\n\d+\n-\n", "", document)
    parameters_text = parse_section(document, "Parameters")
    parameters = parse_parameters(parameters_text)
    return parameters


def process(url) -> None:  # pragma: no cover

    parameters = read_description(url)

    # Output as JSON.
    # import json; print(json.dumps(parameters, indent=4))

    # Output as ASCII table.
    print(tabulate(list(parameters.items()), tablefmt="psql"))


if __name__ == "__main__":  # pragma: no cover
    ten_minutes_air = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/recent/DESCRIPTION_obsgermany_climate_10min_tu_recent_en.pdf"  # noqa:E501,B950
    hourly_solar = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf"  # noqa:E501,B950
    daily_kl = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/DESCRIPTION_obsgermany_climate_daily_kl_recent_en.pdf"  # noqa:E501,B950

    for item in ten_minutes_air, hourly_solar, daily_kl:
        print(item)
        process(item)
        print()
