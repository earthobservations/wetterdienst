# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A stub of DWD's Stationslexikon, for the tests of `dwd/observation` that read its stations (GH-4073).

The page is `statlex_html.html?view=nasPublication` of 2026-11-16: an ISO-8859-1 HTML table with one row for each
station and product, whose header the stub copies as it is (`Stations-<br>kennung` and all) and whose rows are real
ones, with their markup: the number has a line break after it, the end date one before it, the umlauts are entities
(`Hamburg-Fuhlsb&uuml;ttel`), an empty river basin is `&nbsp;`. The rows were picked for what the reader has to tell:

- Berlin-Dahlem `00403`, Hamburg-Fuhlsbüttel `01975` (the two the issue names) and Aachen `00003`: a number of five
  digits, in `SY` (and `MN`, which has the same number for Aachen and Hamburg), beside the numbers of other products
  (`03319`, `46552`) that are no WMO numbers;
- Aachen-Brand `14152`, Donaueschingen `00011`, Arolsen `00197` and the others: an `MN` and an `SY` row with an id of
  DWD's own (`H808`, `Q870`, `L131`), which is no WMO number (3247 of the 3760 rows of the two products are like it);
- Altastenberg `00098` and Kahler Asten `02483`: two ids that have the one number `10427`, as the station moved in
  1954;
- Aach `00001` and Altenau `00106`: a station with no row of `SY` or `MN`;
- Berlin-Tempelhof `00433`, Dresden-Klotzsche `01048` (a number) and Großenkneten `00044` (an id of DWD's own), which
  the stations of `dwd/derived` (the degree days, the soil) have as ids too (GH-4162).
"""

from __future__ import annotations

#: the headers of the columns as the page writes them, in the order of its rows
HEADERS = (
    "Stationsname",
    "Stations_ID",
    "Kennung",
    "Stations-<br>kennung",
    "Breite",
    "L&#228;nge",
    "Stations-<br>h&#246;he",
    "Flussgebiet",
    "Bundesland",
    "Beginn",
    "Ende",
)

# `|`-separated: name (as the page writes it), Stations_ID, Kennung, Stationskennung, Breite, Laenge, Stationshoehe,
# Flussgebiet, Bundesland, Beginn, Ende
ROWS: tuple[str, ...] = (
    "Aach|1|KL|02783|47.841|8.849|478||BW|01.01.1937|30.06.1986",
    "Aach|1|RR|70191|47.841|8.849|478||BW|01.01.1912|30.06.1986",
    "Aachen|3|KL|02205|50.7827|6.0941|202|803100|NW|01.01.1891|31.03.2011",
    "Aachen|3|MN|10501|50.7827|6.0941|202|803100|NW|01.10.2008|03.04.2012",
    "Aachen|3|RR|80310|50.7827|6.0941|202|803100|NW|01.01.1891|31.03.2011",
    "Aachen|3|SY|10501|50.7827|6.0941|202|803100|NW|01.04.1950|01.04.2011",
    "Aachen-Brand (KA)|14152|MN|H808|50.749|6.186|213||NW|11.03.2012|15.11.2026",
    "Aachen-Brand (KA)|14152|RR|87411|50.749|6.186|213||NW|11.11.2012|14.11.2026",
    "Aachen-Brand (KA)|14152|SY|H808|50.749|6.186|213||NW|12.11.2012|14.11.2026",
    "Altastenberg|98|KL|01593|51.189|8.468|784|787230|NW|15.02.1887|31.12.1954",
    "Altastenberg|98|SY|10427|51.189|8.468|784|787230|NW|01.01.1949|06.12.1954",
    "Altenau|106|KL|03971|51.798|10.443|500|541120|NI|01.01.1973|29.02.1996",
    "Altenau|106|RR|54112|51.798|10.443|500|541120|NI|01.01.1973|29.02.1996",
    "Arolsen-Volkhardinghausen, Bad|197|MN|L131|51.322|9.056|365||HE|14.01.2008|15.11.2026",
    "Arolsen-Volkhardinghausen, Bad|197|SY|L131|51.322|9.056|365||HE|01.08.2008|14.11.2026",
    "Berlin-Dahlem (FU)|403|KL|03319|52.454|13.302|51|467270|BE|01.01.1950|14.11.2026",
    "Berlin-Dahlem (FU)|403|RR|46552|52.454|13.302|51|467270|BE|01.01.1950|14.11.2026",
    "Berlin-Dahlem (FU)|403|SY|10381|52.454|13.302|51|467270|BE|01.01.1955|14.11.2026",
    "Berlin-Tempelhof|433|MN|10384|52.4676|13.402|48|467420|BE|17.11.2008|15.11.2026",
    "Berlin-Tempelhof|433|SY|10384|52.4676|13.402|48|467420|BE|01.01.1949|14.11.2026",
    "Dresden-Klotzsche|1048|MN|10488|51.1278|13.7543|228|415390|SN|03.11.2008|15.11.2026",
    "Dresden-Klotzsche|1048|SY|10488|51.1278|13.7543|228|415390|SN|01.07.1975|14.11.2026",
    "Donaueschingen (Landeplatz)|11|FF|02937|47.974|8.521|680||BW|01.09.1980|14.11.2026",
    "Donaueschingen (Landeplatz)|11|MN|Q870|47.974|8.521|680||BW|03.12.2008|15.11.2026",
    "Donaueschingen (Landeplatz)|11|SY|Q870|47.974|8.521|680||BW|01.01.2009|14.11.2026",
    "Falkenberg,Kr.Rottal-Inn|1332|KL|04524|48.483|12.724|471|922320|BY|01.07.1966|14.11.2026",
    "Falkenberg,Kr.Rottal-Inn|1332|MN|P674|48.483|12.724|471|922320|BY|08.12.2004|15.11.2026",
    "Falkenberg,Kr.Rottal-Inn|1332|SY|P674|48.483|12.724|471|922320|BY|01.03.2005|14.11.2026",
    "Gro&szlig;enkneten|44|MN|E426|52.934|8.237|44|564030|NI|08.02.2007|15.11.2026",
    "Gro&szlig;enkneten|44|SY|E426|52.934|8.237|44|564030|NI|01.01.1979|14.11.2026",
    "Hamburg-Fuhlsb&uuml;ttel|1975|KL|01459|53.633|9.988|11|487580|HH|01.01.1936|14.11.2026",
    "Hamburg-Fuhlsb&uuml;ttel|1975|MN|10147|53.633|9.988|11|487580|HH|30.04.2008|15.11.2026",
    "Hamburg-Fuhlsb&uuml;ttel|1975|RR|48558|53.633|9.988|11|487580|HH|01.01.1936|14.11.2026",
    "Hamburg-Fuhlsb&uuml;ttel|1975|SY|10147|53.633|9.988|11|487580|HH|01.01.1949|14.11.2026",
    "Kahler Asten|2483|KL|01594|51.1803|8.4891|839|512550|NW|01.11.1926|14.11.2026",
    "Kahler Asten|2483|MN|10427|51.1803|8.4891|839|512550|NW|31.05.2006|15.11.2026",
    "Kahler Asten|2483|SY|10427|51.1803|8.4891|839|512550|NW|07.12.1954|14.11.2026",
    "Kubsch&uuml;tz, Kr. Bautzen|314|KL|03382|51.16|14.504|234|462250|SN|01.12.1863|14.11.2026",
    "Kubsch&uuml;tz, Kr. Bautzen|314|MN|O384|51.16|14.504|234|462250|SN|13.07.2003|15.11.2026",
    "Kubsch&uuml;tz, Kr. Bautzen|314|SY|O384|51.16|14.504|234|462250|SN|01.05.2004|14.11.2026",
    "N&uuml;mbrecht auf dem Lindchen|3657|MN|H767|50.908|7.554|341||NW|25.10.2005|10.09.2015",
    "N&uuml;mbrecht auf dem Lindchen|3657|SY|H767|50.908|7.554|341||NW|31.10.2005|10.09.2015",
)


def cells(line: str) -> list[str]:
    """Write the cells of a row as the page writes them: the number and the end date have a line break beside them."""
    name, station_id, product, number, latitude, longitude, height, basin, state, begin, end = line.split("|")
    return [
        f"<td>{name}</td>",
        f"<td align=right>{station_id}</td>",
        f"<td align=center>{product}</td>",
        f"<td align=right>{number}\n</td>",
        f"<td align=right>{latitude}</td>",
        f"<td align=right>{longitude}</td>",
        f"<td align=right>{height}</td>",
        f"<td align=right>{basin or '&nbsp;'}</td>",
        f"<td align=center>{state}</td>",
        f"<td>{begin}</td>",
        f"<td>\n{end}</td>",
    ]


def page(
    rows: tuple[str, ...] = ROWS,
    headers: tuple[str, ...] = HEADERS,
    order: tuple[int, ...] = tuple(range(len(HEADERS))),
) -> bytes:
    """Write the page of the Stationslexikon that has the given rows, ISO-8859-1 encoded as DWD serves it.

    `headers` are the texts of the `th` cells (a cell of another tag is a `td` cell), and `order` says which column of
    the stub goes into each place, for a page that has its columns in another order.
    """
    head = "".join(f"<th width=7%>{headers[place]}</th>\n" for place in order if place < len(headers))
    body = "\n".join("<tr>" + "".join(cells(line)[place] for place in order) + "</tr>\n" for line in rows)
    text = (
        '\n<html><body><font face="ARIAL">\n'
        '<head><meta http-equiv="content-type" content="text/html; charset=ISO-8859-1" />\n'
        "<title>Stationslexikon  -- Klimadaten Deutschland  --</title></head>\n"
        "<table border=1>\n"
        "<tr><th colspan=11 align=center valign=middle><h1>Stationslexikon</h1></th></tr>\n"
        f'<tr style="background-color:#2D4B9B; color: white;">\n{head}</tr>\n\n{body}</table></font></body></html>\n'
    )
    return text.encode("latin-1")


STATIONSLEXIKON = page()

#: the WMO number the reader must give each station of the stub, by `Stations_ID` padded to five digits
EXPECTED_WMO_IDS = {
    "00003": "10501",
    "00098": "10427",
    "00403": "10381",
    "00433": "10384",
    "01048": "10488",
    "01975": "10147",
    "02483": "10427",
}
