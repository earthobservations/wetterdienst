# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD phenology provider."""

import csv
import datetime as dt
import io
import re
from http import HTTPStatus
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest
from wetterdienst.provider.dwd.phenology.api import _BASE_URL, _file_url, _parse_values, _periods_for
from wetterdienst.provider.dwd.phenology.metadata import (
    _OBJECTS,
    _PHASES,
    _PLANTS,
    _REPORTERS,
    DWD_PHENOLOGY_OBJECT_IDS,
    DWD_PHENOLOGY_PATHS,
    DwdPhenologyMetadata,
)
from wetterdienst.settings import Settings

UTC = ZoneInfo("UTC")

_HELP_URL = "https://opendata.dwd.de/climate_environment/CDC/help"

# one row per line, blank-padded the way DWD pads them, with the trailing `eor` column
_FILE = (
    b"Stations_id; Referenzjahr; Qualitaetsniveau; Objekt_id; Phase_id; Eintrittsdatum;"
    b"Eintrittsdatum_QB; Jultag;eor;\n"
    b"        7521;          2024;             10;              113;              5;"
    b"       20240127;                1;     27;eor;    \n"
    b"        7521;          2025;              1;              113;              5;"
    b"       20250210;                1;     41;eor;    \n"
)


def test_parse_values() -> None:
    """A file parses to tidy rows dated to the 1st of January of the reference year."""
    df = _parse_values(_FILE, object_id=113)
    assert df.to_dicts() == [
        {
            "station_id": "07521",
            "parameter": "5",
            "date": dt.datetime(2024, 1, 1, tzinfo=UTC),
            "value": 27.0,
            "quality": 10.0,
        },
        {
            "station_id": "07521",
            "parameter": "5",
            "date": dt.datetime(2025, 1, 1, tzinfo=UTC),
            "value": 41.0,
            "quality": 1.0,
        },
    ]


def test_parse_values_drops_other_objects() -> None:
    """A row for a plant the file is not named for is dropped rather than mislabelled."""
    assert _parse_values(_FILE, object_id=112).is_empty()


def test_parse_values_beet_header_variant() -> None:
    """The beet files open with a blank line, shout their headers and write REFERENZ_JAHR."""
    raw = (
        b"\n"
        b"STATIONS_ID; REFERENZ_JAHR; QUALITAETSNIVEAU; OBJEKT_ID; PHASE_ID; EINTRITTSDATUM;"
        b" EINTRITTSDATUM_QB; JULTAG; eor ;\n"
        b"       14433;          2024;             10;               25;             10;"
        b"       20240401;                1;     92; eor ;\n"
    )
    df = _parse_values(raw, object_id=25)
    assert df.to_dicts() == [
        {
            "station_id": "14433",
            "parameter": "10",
            "date": dt.datetime(2024, 1, 1, tzinfo=UTC),
            "value": 92.0,
            "quality": 10.0,
        },
    ]


def test_parse_values_latin1() -> None:
    """Content is decoded as latin-1; utf-8 would fail on the umlauts DWD writes."""
    assert _parse_values(b"Stations_id;Jultag\n", object_id=1).is_empty()
    assert _parse_values("Stations_id;Grünland\n".encode("latin-1"), object_id=1).is_empty()


def test_parse_values_empty() -> None:
    """A header-only or empty file yields an empty frame with the expected schema."""
    df = _parse_values(b"", object_id=113)
    assert df.is_empty()
    assert df.columns == ["station_id", "parameter", "date", "value", "quality"]


def test_file_url_recent() -> None:
    """The recent file is at a fixed name and needs no listing."""
    dataset = DwdPhenologyMetadata["annual"]["annual_common_hazel"]
    url = _file_url(dataset, Period.RECENT, settings=Settings())
    assert url == (f"{_BASE_URL}/annual_reporters/wild/recent/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_akt.txt")


def test_file_url_historical_picks_latest_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """Of the releases DWD leaves side by side, the one with the latest end year is read.

    The earlier ones are truncated -- the 2018 release of the mugwort series is 150 kB against
    6.5 MB for the 2024 one -- so picking any but the newest silently loses most of the record.
    """
    directory = f"{_BASE_URL}/annual_reporters/wild/historical"
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.phenology.api.list_remote_files_fsspec",
        lambda url, settings, cache_expiry: [  # noqa: ARG005
            f"{directory}/DESCRIPTION_obsgermany-phenology-annual_reporters-wild-historical_en.pdf",
            f"{directory}/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_1930_2018_hist.txt",
            f"{directory}/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_1930_2024_hist.txt",
            f"{directory}/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_1930_2019_hist.txt",
        ],
    )
    dataset = DwdPhenologyMetadata["annual"]["annual_common_hazel"]
    url = _file_url(dataset, Period.HISTORICAL, settings=Settings())
    assert url == f"{directory}/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_1930_2024_hist.txt"


def test_file_url_historical_does_not_match_a_longer_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    """`..._Obst_Apfel` must not pick up `..._Obst_Apfel_spaete_Reife_...`, which starts with it."""
    directory = f"{_BASE_URL}/annual_reporters/fruit/historical"
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.phenology.api.list_remote_files_fsspec",
        lambda url, settings, cache_expiry: [  # noqa: ARG005
            f"{directory}/PH_Jahresmelder_Obst_Apfel_1925_2024_hist.txt",
            f"{directory}/PH_Jahresmelder_Obst_Apfel_spaete_Reife_1925_2026_hist.txt",
        ],
    )
    dataset = DwdPhenologyMetadata["annual"]["annual_apple"]
    assert _file_url(dataset, Period.HISTORICAL, settings=Settings()) == (
        f"{directory}/PH_Jahresmelder_Obst_Apfel_1925_2024_hist.txt"
    )


def test_file_url_historical_without_year_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """A series published without a year range in the file name is still found."""
    directory = f"{_BASE_URL}/immediate_reporters/crops/historical"
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.phenology.api.list_remote_files_fsspec",
        lambda url, settings, cache_expiry: [  # noqa: ARG005
            f"{directory}/PH_Sofortmelder_Landwirtschaft_Kulturpflanze_Ruebe_hist.txt",
        ],
    )
    dataset = DwdPhenologyMetadata["annual"]["immediate_beet"]
    assert _file_url(dataset, Period.HISTORICAL, settings=Settings()) == (
        f"{directory}/PH_Sofortmelder_Landwirtschaft_Kulturpflanze_Ruebe_hist.txt"
    )


def test_file_url_historical_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dataset with no historical file yields None rather than a URL that 404s."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.phenology.api.list_remote_files_fsspec",
        lambda url, settings, cache_expiry: [],  # noqa: ARG005
    )
    dataset = DwdPhenologyMetadata["annual"]["annual_beet"]
    assert _file_url(dataset, Period.HISTORICAL, settings=Settings()) is None


def test_metadata_shape() -> None:
    """One dataset per source file, one parameter per phase, names unique and prefixed."""
    datasets = list(DwdPhenologyMetadata["annual"])
    assert len(datasets) == len(_PLANTS)
    assert len({dataset.name for dataset in datasets}) == len(datasets)
    prefixes = tuple(prefix for prefix, _ in _REPORTERS.values())
    for dataset in datasets:
        assert dataset.name.startswith(prefixes)
        assert dataset.grouped
        assert dataset.periods
        assert dataset.description
        assert dataset.parameters
        for parameter in dataset.parameters:
            assert parameter.name in PARAMETERS
            assert parameter.name.startswith("phenology_")
            assert parameter.unit == "dimensionless"
            assert parameter.name_original.isdigit()


def test_metadata_tables_agree() -> None:
    """The three lookup tables cover exactly the plants that are declared."""
    names = {dataset.name for dataset in DwdPhenologyMetadata["annual"]}
    assert set(DWD_PHENOLOGY_OBJECT_IDS) == names
    assert set(DWD_PHENOLOGY_PATHS) == names
    assert set(DWD_PHENOLOGY_OBJECT_IDS.values()) <= set(_OBJECTS)
    for _, _, _, _, _, _, phases in _PLANTS:
        assert set(phases) <= set(_PHASES)


def test_periods_from_dates() -> None:
    """Without an explicit period, the request derives one from the requested interval."""
    parameters = [("annual", "annual_common_hazel")]
    assert DwdPhenologyRequest(parameters=parameters).periods == {Period.HISTORICAL, Period.RECENT}
    assert DwdPhenologyRequest(parameters=parameters, periods="recent").periods == {Period.RECENT}
    old = DwdPhenologyRequest(parameters=parameters, start_date="1950-01-01", end_date="1960-12-31")
    assert old.periods == {Period.HISTORICAL}


def test_single_period_dataset_reads_the_period_it_is_published_under() -> None:
    """A dataset published in one period only is read from it whatever period the dates imply.

    Periods derived from a date range assume `recent` holds the last few years. The two datasets
    with no historical release at all break that assumption -- their whole record lives in the
    recent file, back to 2018 and 2021 -- so leaving those years to a derived `historical` would
    make them unreachable by any date range, and the request returned nothing. The request now
    resolves to the period the dataset actually publishes rather than reporting one it does not
    have and leaving `_periods_for` to repair it per dataset, which it still does for a request
    naming datasets with different periods.
    """
    request = DwdPhenologyRequest(
        parameters=[("annual", "annual_beet")],
        start_date="2021-01-01",
        end_date="2021-12-31",
    )
    dataset = DwdPhenologyMetadata["annual"]["annual_beet"]
    assert dataset.periods == [Period.RECENT]
    # the dates imply historical, which this dataset does not publish
    assert request.periods == {Period.RECENT}
    assert _periods_for(request.periods, dataset) == {Period.RECENT}


def test_both_period_dataset_keeps_the_derived_period() -> None:
    """A dataset published in both periods still reads only the period the dates imply."""
    dataset = DwdPhenologyMetadata["annual"]["annual_common_hazel"]
    assert _periods_for({Period.HISTORICAL}, dataset) == {Period.HISTORICAL}
    assert _periods_for({Period.RECENT}, dataset) == {Period.RECENT}
    # no explicit period reads everything the dataset publishes
    assert _periods_for(None, dataset) == {Period.HISTORICAL, Period.RECENT}


# ---------------------------------------------------------------------------
# Remote tests -- hit the live DWD opendata server.
# ---------------------------------------------------------------------------

xfail_if_dwd_unavailable = pytest.mark.xfail(strict=False, reason="DWD opendata intermittently unavailable")


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_phenology_stations_annual_reporters() -> None:
    """The Jahresmelder catalogue resolves to a populated set of German stations."""
    df = DwdPhenologyRequest(parameters=[("annual", "annual_common_hazel")], periods="recent").all().df
    assert df.height > 6000
    assert df["resolution"].unique().to_list() == ["annual"]
    assert df["dataset"].unique().to_list() == ["annual_common_hazel"]
    assert df["latitude"].min() > 47.0
    assert df["latitude"].max() < 56.0
    assert df["longitude"].min() > 5.0
    assert df["longitude"].max() < 16.0
    assert df.filter(pl.col("station_id") == "07521")["name"].to_list() == ["Goosefeld"]


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_phenology_stations_immediate_reporters_are_a_smaller_network() -> None:
    """The Sofortmelder catalogue is its own, much smaller, station list."""
    annual = DwdPhenologyRequest(parameters=[("annual", "annual_common_hazel")], periods="recent").all().df
    immediate = DwdPhenologyRequest(parameters=[("annual", "immediate_common_hazel")], periods="recent").all().df
    assert 1000 < immediate.height < annual.height
    # the two catalogues are separate lists that mostly, but not entirely, overlap: an observer can
    # report immediately without also being on the annual list
    assert len(set(immediate["station_id"]) & set(annual["station_id"])) > immediate.height * 0.9


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_phenology_values_recent() -> None:
    """Hazel flowering at Goosefeld in 2024 fell on day 27, as the source file says."""
    request = DwdPhenologyRequest(
        parameters=[("annual", "annual_common_hazel", "phenology_flowering_beginning")],
        periods="recent",
    )
    df = next(request.filter_by_station_id("07521").values.query()).df
    assert df["parameter"].unique().to_list() == ["phenology_flowering_beginning"]
    assert df["dataset"].unique().to_list() == ["annual_common_hazel"]
    row = df.filter(pl.col("date") == dt.datetime(2024, 1, 1, tzinfo=UTC)).to_dicts()[0]
    assert row["value"] == 27.0
    assert row["quality"] == 10.0


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_phenology_values_immediate_reporters() -> None:
    """The immediate reporters also carry phase 41, which no phase-definition file lists for hazel."""
    request = DwdPhenologyRequest(parameters=[("annual", "immediate_common_hazel")], periods="recent")
    df = next(request.filter_by_station_id("07532").values.query()).df
    assert set(df["parameter"]) == {"phenology_flowering_beginning", "phenology_flowering_end_observation_area"}
    row = df.filter(
        (pl.col("date") == dt.datetime(2024, 1, 1, tzinfo=UTC))
        & (pl.col("parameter") == "phenology_flowering_beginning"),
    ).to_dicts()[0]
    assert row["value"] == 57.0


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_phenology_values_historical_reaches_back() -> None:
    """A historical request returns a multi-decade series of plausible days of the year."""
    request = DwdPhenologyRequest(
        parameters=[("annual", "annual_european_beech", "phenology_leaf_unfolding_beginning")],
        start_date="1960-01-01",
        end_date="2000-12-31",
    )
    df = next(request.filter_by_station_id("07521").values.query()).df
    assert df.height > 10
    assert df["date"].min() < dt.datetime(1995, 1, 1, tzinfo=UTC)
    # beech leaf unfolding is an April/May event, so somewhere around day 90-150
    assert 60 < df["value"].min() <= df["value"].max() < 200


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_phase_table_matches_the_source() -> None:
    """The German phase names in `_PHASES` are DWD's own, from PH_Beschreibung_Phase.txt.

    Phase 68 is absent from that file and is named from the immediate reporters' phase
    definitions, which is the only place DWD spells it out, so it is not checked here.
    """
    import urllib.request  # noqa: PLC0415

    raw = urllib.request.urlopen(f"{_HELP_URL}/PH_Beschreibung_Phase.txt", timeout=60).read()  # noqa: S310
    published = {}
    rows = csv.reader(io.StringIO(raw.decode("latin-1")), delimiter=";")
    next(rows)
    for row in rows:
        if len(row) > 1 and row[0].strip().isdigit():
            published[int(row[0])] = row[1].strip()
    assert published
    declared = {phase: german for phase, (_, german, _) in _PHASES.items() if phase in published}
    assert declared == {phase: published[phase] for phase in declared}
    # every phase the source lists that any plant is observed for must be declared
    observed = {phase for *_, phases in _PLANTS for phase in phases}
    assert observed - set(_PHASES) == set()


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_plant_table_matches_the_source() -> None:
    """The plant names in `_OBJECTS` are DWD's own, from PH_Beschreibung_Pflanze.txt."""
    import urllib.request  # noqa: PLC0415

    raw = urllib.request.urlopen(f"{_HELP_URL}/PH_Beschreibung_Pflanze.txt", timeout=60).read()  # noqa: S310
    published = {}
    # records are terminated by `eor;` and wrap across lines, so split on the terminator
    for record in raw.decode("latin-1").split("eor;")[1:]:
        cells = [cell.strip() for cell in record.replace("\r", " ").replace("\n", " ").split(";")]
        if len(cells) >= 4 and cells[0].isdigit():
            botanical = "" if set(cells[3]) <= {"-"} else cells[3]
            published[int(cells[0])] = (cells[1], cells[2], botanical)
    assert published
    assert {object_id: _OBJECTS[object_id] for object_id in _OBJECTS if object_id in published} == {
        object_id: published[object_id] for object_id in _OBJECTS if object_id in published
    }
    assert set(_OBJECTS) <= set(published)


def _listing(directory: str, cache: dict[str, set[str]]) -> set[str]:
    """List one phenology directory on the DWD server, memoized across the checks below."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    if directory not in cache:
        try:
            html = urllib.request.urlopen(f"{_BASE_URL}/{directory}/", timeout=60).read()  # noqa: S310
        except urllib.error.HTTPError as error:
            # a group that publishes only one period has no directory for the other at all
            if error.code != HTTPStatus.NOT_FOUND:
                raise
            cache[directory] = set()
        else:
            cache[directory] = set(re.findall(r'href="([^"]+)"', html.decode("utf-8", "replace")))
    return cache[directory]


def _is_published(files: set[str], stem: str, period: str) -> bool:
    """Say whether one plant's file for one period is among the listed files."""
    if period == "recent":
        return f"{stem}_akt.txt" in files
    # the historical file may or may not carry the year range of the release in its name
    pattern = re.compile(rf"^{re.escape(stem)}(?:_\d{{4}}_\d{{4}})?_hist\.txt$")
    return any(pattern.match(name) for name in files)


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_every_declared_plant_and_period_is_published() -> None:
    """Every (plant, period) declared is published, and every period published is declared.

    This is what catches DWD adding a plant, retiring one, or starting to publish a `recent` file
    for a series that had none -- all of which the hand-written table here would otherwise miss.
    """
    cache: dict[str, set[str]] = {}
    wrong = []
    for reporter, group, stem, _, _, periods, _ in _PLANTS:
        for period in ("historical", "recent"):
            files = _listing(f"{reporter}/{group}/{period}", cache)
            published = _is_published(files, stem, period)
            declared = period in periods
            if published != declared:
                state = "published but not declared" if published else "declared but not published"
                wrong.append(f"{reporter}/{group}/{stem}: {period} is {state}")
    assert not wrong, "\n".join(wrong)


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_no_published_plant_is_missing_from_the_table() -> None:
    """No data file is published that no dataset claims, i.e. no plant is left unreachable."""
    cache: dict[str, set[str]] = {}
    declared = {(reporter, group, stem) for reporter, group, stem, *_ in _PLANTS}
    directories = {(reporter, group) for reporter, group, *_ in _PLANTS}
    orphans = []
    for reporter, group in sorted(directories):
        for period in ("historical", "recent"):
            for name in sorted(_listing(f"{reporter}/{group}/{period}", cache)):
                if not name.startswith("PH_") or "Beschreibung" in name:
                    continue
                stem = re.sub(r"(?:_\d{4}_\d{4})?_(?:hist|akt)\.txt$", "", name)
                # a Notiz/Spezifizierung side file rather than a data file
                if stem == name:
                    continue
                if (reporter, group, stem) not in declared:
                    orphans.append(f"{reporter}/{group}/{period}/{name}")
    assert not orphans, "\n".join(orphans)
