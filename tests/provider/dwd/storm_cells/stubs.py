# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Real KONRAD3D scans of DWD, a hand-made one, and what serves them in place of the download.

The real scans (`files/`) are as DWD published them in `weather/radar/konrad3d/` on 2026-11-15 to 2026-11-17, nothing
changed but the third:

- `KONRAD3D_20261115T222000.xml`: an empty scan, which 8 of 10 are: a complete `head` and a self-closing `<cells/>`
- `KONRAD3D_20261117T221500.xml`: two cells (5 and 53), each one polygon, both of severity 1, `gust_flag` 1
- `KONRAD3D_20261117T202500.xml`: three cells of the ten of that scan (the other seven are cut, `head` and the three
  cells are whole): `40*` and `1*`-style split cells with a predecessor, `38` and `32` not split

`parts_scan()` is made by hand: the format description allows several polygons for one cell and several `cells`
for several times, which no real scan has had, and DWD's two missing values (the number and `not-a-date-time`) in
elements the parser reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

_FILES = Path(__file__).parent / "files"

EMPTY_SCAN: bytes = (_FILES / "KONRAD3D_20261115T222000.xml").read_bytes()
TWO_CELLS_SCAN: bytes = (_FILES / "KONRAD3D_20261117T221500.xml").read_bytes()
SPLIT_CELLS_SCAN: bytes = (_FILES / "KONRAD3D_20261117T202500.xml").read_bytes()

DIRECTORY = "https://opendata.dwd.de/weather/radar/konrad3d/"


def square(latitude: float, longitude: float, half: float = 0.05) -> tuple[str, str]:
    """Give the two lists of a square outline of `half` degrees around a centre, counter-clockwise, not closed."""
    lats = [latitude - half, latitude - half, latitude + half, latitude + half]
    lons = [longitude - half, longitude + half, longitude + half, longitude - half]
    return " ".join(f"{value:.5f}" for value in lats), " ".join(f"{value:.5f}" for value in lons)


def cell_xml(
    identifier: str = "1",
    *,
    latitude: float = 50.0,
    longitude: float = 10.0,
    polygons: Sequence[tuple[str, str]] | None = None,
    severity: str = "1",
    gust_flag: str = "1",
    code: str = "2026070112000000000000",
    predecessors: Sequence[tuple[str, str]] = (),
    forecast: Sequence[tuple[str, str, str]] | None = None,
    first_detection: str = "2026-07-01T12:00:00Z",
    split: str = "false",
    merge: str = "false",
    reference_time: str = "2026-07-01T12:00:00Z",
) -> str:
    """Write a `feature` of the elements the parser reads, with what a test varies as arguments.

    `predecessors` are `(code, probability)`, `forecast` is `(time, latitude, longitude)` for each position; the default
    is two positions, one and two steps ahead, going due north.
    """
    polygons = polygons if polygons is not None else [square(latitude, longitude)]
    forecast = (
        forecast
        if forecast is not None
        else [
            ("2026-07-01T12:05:00Z", f"{latitude + 0.05:.5f}", f"{longitude:.5f}"),
            ("2026-07-01T12:10:00Z", f"{latitude + 0.10:.5f}", f"{longitude:.5f}"),
        ]
    )
    polygon_xml = "".join(
        f'<polygon no="{number}" unit="degrees"><latitudes>{lats}</latitudes><longitudes>{lons}</longitudes></polygon>'
        for number, (lats, lons) in enumerate(polygons)
    )
    predecessor_xml = "".join(
        f"<predecessor><identifier>0</identifier><code>{code_}</code><time>2026-07-01T11:55:00Z</time>"
        f'<probability unit="%">{probability}</probability></predecessor>'
        for code_, probability in predecessors
    )
    forecast_xml = "".join(
        f'<centroid_forecast forecast_time="{time}"><geodetic_coordinate><latitude unit="degrees">{lat}</latitude>'
        f'<longitude unit="degrees">{lon}</longitude></geodetic_coordinate><uncertainty_ellipse>'
        '<major_axis unit="km">3.000</major_axis><minor_axis unit="km">2.000</minor_axis>'
        '<angle unit="degrees">45.00</angle></uncertainty_ellipse></centroid_forecast>'
        for time, lat, lon in forecast
    )
    return f"""<feature identifier="{identifier}" type="3D_reflectivity_feature">
<metadata><identifier>{identifier}</identifier><code>{code}</code>
<reference_time format="ISO 8601">{reference_time}</reference_time></metadata>
<geometry><covered_area unit="km^2">30.0</covered_area>
<centroid_3d><geodetic_coordinate><latitude unit="degrees">{latitude}</latitude>
<longitude unit="degrees">{longitude}</longitude></geodetic_coordinate></centroid_3d>
<echo_top_msl unit="m">9000</echo_top_msl>
<polygons_projected><geodetic_coordinates>{polygon_xml}</geodetic_coordinates></polygons_projected></geometry>
<intensity><severity unit="severity_points">{severity}</severity>
<severity_decimal unit="severity_points">1.20</severity_decimal>
<hail_flag>0</hail_flag><heavy_rain_flag>2</heavy_rain_flag><gust_flag>{gust_flag}</gust_flag>
<maximum_estimated_wind_gust unit="km/h">-1000000000.000</maximum_estimated_wind_gust>
<cell_based_VIL unit="kg/m^2">12.5</cell_based_VIL>
<max_value unit="dBZ">58.0</max_value>
<heavy_rain_potential unit="mm">27.5</heavy_rain_potential></intensity>
<tracking><reference_time_first_detection format="ISO 8601">{first_detection}</reference_time_first_detection>
<number_detections>3</number_detections>
<mergers><merge_event>{merge}</merge_event>
<reference_time_last_merge format="ISO 8601">not-a-date-time</reference_time_last_merge></mergers>
<splits><split_event>{split}</split_event></splits>
<predecessors>{predecessor_xml}</predecessors>
<cell_speed unit="km/h">60.0</cell_speed></tracking>
<forecast><centroid_forecasts>{forecast_xml}</centroid_forecasts></forecast>
</feature>"""


def scan_xml(*blocks: tuple[str, Sequence[str]], created: str = "2026-07-01T12:05:10Z") -> bytes:
    """Write a scan of `cells` blocks, each `(reference_time, [feature, ...])`; the `head` has the first's time."""
    cells = "".join(
        f'<cells reference_time="{time}" ensemble_member_id="0">{"".join(features)}</cells>'
        for time, features in blocks
    )
    return (
        '<?xml version="1.0" ?><konrad3d data_model_name="KONRAD3D" data_model_version="1.7"><head>'
        f'<metadata><reference_time format="ISO 8601">{blocks[0][0]}</reference_time>'
        f"<ensemble_member_id>0</ensemble_member_id></metadata><product><creation-date>{created}</creation-date>"
        f"</product></head>{cells}</konrad3d>"
    ).encode()


def parts_scan() -> bytes:
    """Write the scan made by hand: two `cells` blocks, the first with a merger whose outline is in two parts.

    Cell `7#` of 12:00 has two polygons (a square at 50.0, 10.0 and another at 50.5, 10.5), two predecessors (the one
    DWD is sure of, 100 %, listed second) and `gust_flag` of DWD's missing value; cell `8` of the block of 12:05 is
    one square at 49.0, 8.0.
    """
    merged = cell_xml(
        "7#",
        polygons=[square(50.0, 10.0), square(50.5, 10.5)],
        merge="true",
        gust_flag="-1000000000",
        code="2026070112000000000001",
        predecessors=[("2026070111550000000000", "0.00"), ("2026070111550000000003", "100.00")],
    )
    other = cell_xml(
        "8", latitude=49.0, longitude=8.0, code="2026070112050000000000", reference_time="2026-07-01T12:05:00Z"
    )
    return scan_xml(("2026-07-01T12:00:00Z", [merged]), ("2026-07-01T12:05:00Z", [other]))


#: where the cells of `three_cells_scan` are: Hamburg, Berlin and Munich
HAMBURG = (53.55, 10.0)
BERLIN = (52.5, 13.4)
MUNICH = (48.14, 11.58)


def three_cells_scan() -> bytes:
    """Write a scan of 12:00 UTC: Hamburg (severity 0), Berlin (2) and Munich (3), squares of 0.1 degrees."""
    cells = [
        cell_xml("1", latitude=HAMBURG[0], longitude=HAMBURG[1], severity="0"),
        cell_xml("2", latitude=BERLIN[0], longitude=BERLIN[1], severity="2"),
        cell_xml("3", latitude=MUNICH[0], longitude=MUNICH[1], severity="3"),
    ]
    return scan_xml(("2026-07-01T12:00:00Z", cells))


def listing(*times: str, other: Sequence[str] = ()) -> list[dict[str, str]]:
    """Give the entries of the directory listing for scans at these times (`YYYYMMDDThhmmss`) and any other names."""
    names = [f"KONRAD3D_{time}.xml" for time in times] + list(other)
    return [{"name": f"{DIRECTORY}{name}", "type": "file"} for name in names]


def serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]) -> list[str]:
    """Make `DwdStormCellsRequest.query` list these scans (name to content) and download them, nothing from the network.

    Gives the URLs downloaded, in order.
    """
    from wetterdienst.util.network import File  # noqa: PLC0415

    downloaded: list[str] = []

    def fake_listing(*_args: object, **_kwargs: object) -> list[dict[str, str]]:
        return [{"name": f"{DIRECTORY}{name}", "type": "file"} for name in files]

    def fake_download(url: str, *_args: object, **_kwargs: object) -> File:
        from io import BytesIO  # noqa: PLC0415

        downloaded.append(url)
        return File(url=url, content=BytesIO(files[url.rsplit("/", 1)[-1]]), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec", fake_listing)
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api.download_file", fake_download)
    return downloaded
