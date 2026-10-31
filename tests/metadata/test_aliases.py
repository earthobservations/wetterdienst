# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The alias a rename keeps from 1.0 on (GH-2625), tested with an alias made here.

No rename has been made since 1.0, so the real tables of `wetterdienst.metadata.aliases` are empty and nothing in the
library answers differently for it. Each test declares a synthetic alias on a real dataset (`temperature_air_mean_2m`
of `dwd/observation` daily, under the name `air_temp`, or under that name for every dataset), and holds what the policy
promises of a name that has one: it is accepted wherever a parameter name is, it resolves to the new name, and it says
so, naming the new name, the release that renamed it and the release that may remove it.
"""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import warnings
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.baselines.common import project_version
from tests.baselines.parameters import breaking_changes, build_surface
from wetterdienst import Options
from wetterdienst.exceptions import InvalidParameterError
from wetterdienst.io.sql_filter import filter_by_sql
from wetterdienst.metadata import renamed
from wetterdienst.metadata.aliases import (
    DEPRECATED_PARAMETER,
    PARAMETER_ALIASES,
    PARAMETER_ALIASES_IN_DATASET,
    ParameterAlias,
    alias_message,
    check_alias,
    release,
)
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.ui import core, restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterator

OLD = "air_temp"
NEW = "temperature_air_mean_2m"
DATASET = ("daily", "climate_summary")
_ALIAS = ParameterAlias(new=NEW, since="1.3.0", date=dt.date(2027, 3, 1), until="2.0.0")
#: what every use of the alias says, which the tests read off the warning of each surface
_MESSAGE = alias_message(OLD, _ALIAS)


@pytest.fixture
def alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare `air_temp` an alias of `temperature_air_mean_2m` in `dwd/observation` daily/climate_summary only."""
    monkeypatch.setitem(PARAMETER_ALIASES_IN_DATASET, "DwdObservationMetadata", {DATASET: {OLD: _ALIAS}})


@pytest.fixture
def alias_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare `air_temp` an alias of `temperature_air_mean_2m` in every dataset that has the new name."""
    monkeypatch.setitem(PARAMETER_ALIASES, OLD, _ALIAS)


@pytest.fixture
def stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the station list of DWD, so that a request goes through its surface and the network is not asked."""
    frame = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
                "end_timestamp": dt.datetime(2025, 12, 31, tzinfo=dt.UTC),
                "latitude": 51.1278,
                "longitude": 13.7543,
                "elevation": 228.0,
                "name": "Dresden-Klotzsche",
                "region": "Sachsen",
            }
        ]
    )

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=frame, _df_all=frame, _stations_filter=StationsFilter.ALL)

    monkeypatch.setattr(DwdObservationRequest, "all", _all)


@pytest.fixture(autouse=True)
def _a_clean_record() -> Iterator[None]:
    """Start each test without the warnings an earlier one recorded in this thread."""
    begin_response()
    yield
    begin_response()


# --- the message -------------------------------------------------------------------------------------------------


def test_the_message_names_the_new_name_the_release_that_renamed_it_and_when_it_may_go() -> None:
    """A caller is told what to write, since when it was renamed, and the rule that says when the alias ends."""
    assert "'air_temp' was renamed to 'temperature_air_mean_2m' in 1.3.0" in _MESSAGE
    assert "until 2.0.0 at the earliest" in _MESSAGE
    assert "at least two minor releases" in _MESSAGE
    assert "major release" in _MESSAGE
    assert _MESSAGE.endswith("use 'temperature_air_mean_2m'")


# --- Python ------------------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("alias")
def test_a_request_takes_the_alias_resolves_it_and_warns() -> None:
    """The request holds the parameter under its new name, and the old one is a `DeprecationWarning`."""
    with pytest.warns(DeprecationWarning, match="'air_temp' was renamed to 'temperature_air_mean_2m' in 1.3.0") as seen:
        request = DwdObservationRequest(parameters=f"daily/climate_summary/{OLD}")

    assert [parameter.name for parameter in request.parameters] == [NEW]
    # the warning is for the code that wrote the name, not for the library
    assert seen[0].filename == __file__
    assert recorded_warnings() == [{"code": DEPRECATED_PARAMETER, "message": _MESSAGE}]


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param(f"daily/climate_summary/{OLD}", id="string"),
        pytest.param(f"daily:climate_summary:{OLD.upper()}", id="separator-and-case"),
        pytest.param(("daily", "climate_summary", OLD), id="tuple"),
        pytest.param([f"daily/climate_summary/{OLD}", f"daily/climate_summary/{NEW}"], id="with-the-new-name-too"),
    ],
)
@pytest.mark.usefixtures("alias")
def test_the_alias_is_taken_wherever_a_request_names_a_parameter(parameters: Any) -> None:  # noqa: ANN401
    """Every spelling a request takes works for the alias as for the name, and a name given twice is one parameter."""
    with pytest.warns(DeprecationWarning, match="was renamed to"):
        request = DwdObservationRequest(parameters=parameters)

    assert [parameter.name for parameter in request.parameters] == [NEW]


@pytest.mark.usefixtures("alias")
def test_the_alias_is_taken_as_an_item_or_an_attribute_of_a_dataset() -> None:
    """The metadata answers the alias with the parameter of the new name, as a request does."""
    dataset = DwdObservationMetadata["daily"]["climate_summary"]

    with pytest.warns(DeprecationWarning, match=_MESSAGE.split(":")[0].replace("(", r"\(").replace(")", r"\)")):
        assert dataset[OLD].name == NEW
    with pytest.warns(DeprecationWarning, match="was renamed to"):
        assert getattr(dataset, OLD).name == NEW


@pytest.mark.usefixtures("alias")
def test_the_alias_is_an_alias_in_its_dataset_only() -> None:
    """A dataset that is not the one declared, or that lacks the new name, refuses the name as it always did."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(InvalidParameterError, match=OLD):
            DwdObservationRequest(parameters=f"daily/more_precip/{OLD}")
        with pytest.raises(InvalidParameterError, match=OLD):
            DwdObservationRequest(parameters=f"hourly/temperature_air/{OLD}")


@pytest.mark.usefixtures("alias")
def test_a_name_that_is_no_alias_is_refused_as_it_was() -> None:
    """Declaring an alias changes nothing for any other name, and the real one warns of nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(InvalidParameterError, match="temperature_air_mean_2m_typo"):
            DwdObservationRequest(parameters=f"daily/climate_summary/{NEW}_typo")
        request = DwdObservationRequest(parameters=f"daily/climate_summary/{NEW}")
    assert [parameter.name for parameter in request.parameters] == [NEW]
    assert recorded_warnings() == []


def test_a_name_the_dataset_has_wins_over_an_alias_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """An alias is looked at only for a name the dataset does not have, so it never hides a parameter."""
    monkeypatch.setitem(
        PARAMETER_ALIASES_IN_DATASET,
        "DwdObservationMetadata",
        {
            DATASET: {
                "precipitation_amount": ParameterAlias(new=NEW, since="1.3.0", date=dt.date(2027, 3, 1), until="2.0.0")
            }
        },
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        request = DwdObservationRequest(parameters="daily/climate_summary/precipitation_amount")
    assert [parameter.name for parameter in request.parameters] == ["precipitation_amount"]


@pytest.mark.usefixtures("alias_everywhere")
def test_an_alias_of_every_dataset_holds_where_the_dataset_has_the_new_name() -> None:
    """The alias of every dataset is taken in each that has the new name, and in none that lacks it."""
    for dataset in ("daily/climate_summary", "hourly/temperature_air"):
        parameter = "temperature_air_mean_2m" if dataset.startswith("daily") else "temperature_air_2m"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if parameter == NEW:
                assert DwdObservationRequest(parameters=f"{dataset}/{OLD}").parameters[0].name == NEW
            else:
                with pytest.raises(InvalidParameterError, match=OLD):
                    DwdObservationRequest(parameters=f"{dataset}/{OLD}")


def test_the_alias_is_a_hard_rename_for_the_hint_tables_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """An alias is merged into the tables of renames, so that the hint stays when the alias ends."""
    in_dataset = copy.deepcopy(renamed.RENAMED_PARAMETERS_IN_DATASET)
    everywhere = dict(renamed.RENAMED_PARAMETERS)
    monkeypatch.setattr(renamed, "RENAMED_PARAMETERS_IN_DATASET", in_dataset)
    monkeypatch.setattr(renamed, "RENAMED_PARAMETERS", everywhere)
    monkeypatch.setitem(PARAMETER_ALIASES_IN_DATASET, "DwdObservationMetadata", {DATASET: {OLD: _ALIAS}})
    monkeypatch.setitem(PARAMETER_ALIASES, "air_temp_all", _ALIAS)

    renamed._merge_aliases()  # noqa: SLF001

    assert in_dataset["DwdObservationMetadata"][DATASET][OLD] == NEW
    assert everywhere["air_temp_all"] == NEW


# --- command line, REST and MCP ---------------------------------------------------------------------------------
# (the `DeprecationWarning` is the Python caller's: here the answer's own warning is what is read)


_PARAMETERS = f"daily/climate_summary/{OLD}"


def _warned_codes(metadata: dict[str, Any]) -> list[str]:
    return [warning["code"] for warning in metadata["warnings"]]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.usefixtures("alias", "stations")
def test_the_command_line_takes_the_alias_and_the_answer_names_the_new_name(caplog: pytest.LogCaptureFixture) -> None:
    """The answer of `stations` holds the request with the new name and the warning, and the log line says it too."""
    result = CliRunner().invoke(
        cli, ["stations", "--provider", "dwd", "--network", "observation", "--parameters", _PARAMETERS, "--all"]
    )

    assert result.exit_code == 0, result.output
    answer = _json_of(result.output)
    assert answer["metadata"]["request"]["parameters"] == [f"daily/climate_summary/{NEW}"]
    assert answer["metadata"]["warnings"] == [{"code": DEPRECATED_PARAMETER, "message": _MESSAGE}]
    assert _MESSAGE in caplog.text


def _json_of(output: str) -> dict[str, Any]:
    """Read the JSON document of a command's output, which logging may have written lines in front of."""
    import json  # noqa: PLC0415

    return json.loads(output[output.index('{"metadata"') :])


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.usefixtures("alias", "stations")
def test_rest_takes_the_alias_and_answers_the_warning_and_the_headers() -> None:
    """The answer says the new name, the `deprecated-parameter` warning, and the `Deprecation` header of the day."""
    response = TestClient(restapi.app).get(
        "/api/v1/stations",
        params={"provider": "dwd", "network": "observation", "parameters": _PARAMETERS, "all": "true"},
    )

    assert response.status_code == 200, response.text
    metadata = response.json()["metadata"]
    assert metadata["request"]["parameters"] == [f"daily/climate_summary/{NEW}"]
    assert metadata["warnings"] == [{"code": DEPRECATED_PARAMETER, "message": _MESSAGE}]
    assert response.headers["Deprecation"] == "@1803859200"
    assert response.headers["x-wetterdienst-warnings"] == DEPRECATED_PARAMETER
    assert 'rel="deprecation"' in response.headers["link"]
    # the policy has no date for the end of an alias: a release does, which the message says
    assert "Sunset" not in response.headers


@pytest.mark.usefixtures("alias", "stations")
def test_rest_answers_no_deprecation_for_the_new_name() -> None:
    """A request that writes the new name is told nothing."""
    response = TestClient(restapi.app).get(
        "/api/v1/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": f"daily/climate_summary/{NEW}",
            "all": "true",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["metadata"]["warnings"] == []
    assert "Deprecation" not in response.headers


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.usefixtures("alias", "stations")
def test_mcp_takes_the_alias_and_the_answer_holds_the_warning() -> None:
    """The MCP tool is the endpoint: it answers the new name, and the metadata block has the warning."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            result = await client.call_tool(
                "stations", {"provider": "dwd", "network": "observation", "parameters": _PARAMETERS, "all": True}
            )
            return result.structured_content

    answer = asyncio.run(call())["result"]

    assert answer["metadata"]["request"]["parameters"] == [f"daily/climate_summary/{NEW}"]
    assert _warned_codes(answer["metadata"]) == [DEPRECATED_PARAMETER]


@pytest.mark.usefixtures("alias_everywhere")
def test_the_glossary_takes_the_alias_of_every_dataset() -> None:
    """`glossary` looks a parameter up by a name: the old one finds the entry of the new."""
    with pytest.warns(DeprecationWarning, match="was renamed to"):
        entries = core.get_glossary(parameter=OLD)

    assert NEW in [entry["name"] for entry in entries]
    assert core.get_glossary(parameter="air_temp_unknown") == []


# --- options and filters ------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("alias_everywhere")
def test_a_radius_set_by_the_alias_of_every_dataset_is_set_for_the_new_name() -> None:
    """A key of `geo_station_distance` that is the old name of a renamed parameter sets the radius of the new."""
    with pytest.warns(DeprecationWarning, match="'air_temp' was renamed"):
        options = Options(geo_station_distance={OLD: 12.0})

    assert options.geo_station_distance[NEW] == 12.0
    assert OLD not in options.geo_station_distance


@pytest.mark.usefixtures("alias_everywhere")
def test_a_radius_key_that_is_no_alias_is_refused_as_it_was() -> None:
    """The other keys are checked as before."""
    with pytest.raises(ValueError, match="not in the canonical parameters"):
        Options(geo_station_distance={"air_temp_unknown": 12.0})


@pytest.mark.sql
@pytest.mark.usefixtures("alias")
def test_a_sql_filter_takes_the_alias_of_a_column_and_answers_the_frames_columns() -> None:
    """A clause that names the old parameter runs on the new column, and the answer has the frame's columns only."""
    pytest.importorskip("duckdb")
    df = pl.DataFrame({"station_id": ["a", "b"], NEW: [1.5, 7.5], f"{NEW}_quality_flags": ["10", "10"]})

    with pytest.warns(DeprecationWarning, match="'air_temp' was renamed"):
        filtered = filter_by_sql(df, f"{OLD} > 5")

    assert filtered.columns == df.columns
    assert filtered.get_column("station_id").to_list() == ["b"]
    assert recorded_warnings() == [{"code": DEPRECATED_PARAMETER, "message": _MESSAGE}]


@pytest.mark.sql
@pytest.mark.usefixtures("alias")
def test_a_sql_filter_follows_the_alias_into_the_prefixed_and_the_quality_column() -> None:
    """A wide frame's column is `<dataset>_<parameter>` and its flags `<column>_quality_flags`, as for a rename."""
    pytest.importorskip("duckdb")
    df = pl.DataFrame(
        {
            "climate_summary_temperature_air_mean_2m": [1.5, 7.5],
            "climate_summary_temperature_air_mean_2m_quality_flags": ["10", "20"],
        }
    )

    with pytest.warns(DeprecationWarning, match="was renamed to"):
        filtered = filter_by_sql(df, f"climate_summary_{OLD} > 5 AND climate_summary_{OLD}_quality_flags = '20'")

    assert filtered.columns == df.columns
    assert filtered.height == 1


@pytest.mark.sql
@pytest.mark.usefixtures("alias")
def test_a_sql_filter_on_a_column_that_is_no_alias_fails_as_it_did() -> None:
    """DuckDB's own error stands for a column that neither the frame nor an alias has."""
    duckdb = pytest.importorskip("duckdb")
    df = pl.DataFrame({NEW: [1.5]})

    with pytest.raises(duckdb.BinderException, match="not_there"):
        filter_by_sql(df, "not_there > 5")
    # an alias whose new column the frame does not hold is no column of it
    with pytest.raises(duckdb.BinderException, match="precipitation_amount"):
        filter_by_sql(pl.DataFrame({"precipitation_amount": [1.0]}), f"{OLD} > 5")


# --- the length of an alias ---------------------------------------------------------------------------------------


def _alias(**kwargs: Any) -> ParameterAlias:  # noqa: ANN401
    return ParameterAlias(**{"new": NEW, "since": "1.3.0", "date": dt.date(2027, 3, 1), "until": "2.0.0", **kwargs})


def test_the_real_aliases_are_declared_as_the_policy_has_them() -> None:
    """Every alias declared in the library is of 1.0 or later and ends in a major release after its own."""
    declared = [
        *PARAMETER_ALIASES.items(),
        *(
            entry
            for datasets in PARAMETER_ALIASES_IN_DATASET.values()
            for aliases in datasets.values()
            for entry in aliases.items()
        ),
    ]

    assert [problem for old, entry in declared for problem in check_alias(old, entry)] == []


@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        pytest.param(_alias(), None, id="a-minor-release-and-the-next-major"),
        pytest.param(_alias(since="1.0.0", until="3.0.0"), None, id="a-major-later-than-the-next"),
        pytest.param(_alias(since="0.162.0", until="1.0.0"), "a rename before 1.0.0 has no alias", id="before-1.0"),
        pytest.param(_alias(until="1.5.0"), "an alias is removed only in a major release", id="ends-in-a-minor"),
        pytest.param(_alias(until="2.0.1"), "an alias is removed only in a major release", id="ends-in-a-patch"),
        pytest.param(_alias(until="1.0.0"), "not after the major release of 1.3.0", id="ends-before-it-began"),
        pytest.param(_alias(since="2.1.0", until="2.0.0"), "not after the major release of 2.1.0", id="same-major"),
        pytest.param(_alias(since="1.x"), "is not a release", id="not-a-release"),
        pytest.param(_alias(until="2.0"), "is not a release", id="until-not-a-release"),
        pytest.param(_alias(new=OLD), "a rename to itself", id="to-itself"),
    ],
)
def test_the_length_of_an_alias_is_held_to_the_policy(entry: ParameterAlias, problem: str | None) -> None:
    """An alias is removed only in a major release, after the one that renamed it; before 1.0 there is none."""
    problems = check_alias(OLD, entry)

    if problem is None:
        assert problems == []
    else:
        assert [p for p in problems if problem in p], problems


def test_a_release_is_read_as_three_numbers() -> None:
    """The releases of the policy are `major.minor.patch`, and compare as numbers, not as text."""
    assert release("1.10.0") > release("1.9.0")
    with pytest.raises(ValueError, match="not a release"):
        release("1.0.0rc1")


def test_no_alias_outlives_the_release_that_may_remove_it() -> None:
    """From the release an alias may end in, its entry is in the plain tables of renames: it is a hint, not an alias.

    The version of `pyproject.toml` is that of the last release until the release commit, which is where this fails
    for an alias whose `until` is that version.
    """
    version = release(project_version())
    declared = [
        (old, entry)
        for datasets in PARAMETER_ALIASES_IN_DATASET.values()
        for aliases in datasets.values()
        for old, entry in aliases.items()
    ] + list(PARAMETER_ALIASES.items())

    assert [old for old, entry in declared if version >= release(entry.until)] == []


# --- the baseline ------------------------------------------------------------------------------------------------


def _baseline_with_an_alias() -> dict[str, Any]:
    surface = copy.deepcopy(build_surface())
    entry = {"new": NEW, "since": "1.3.0", "until": "2.0.0"}
    surface["aliases"] = {
        "parameters": {"air_temp_all": entry},
        "in_dataset": {"dwd/observation": {"daily/climate_summary": {OLD: entry}}},
    }
    return surface


@pytest.mark.usefixtures("alias", "alias_everywhere")
def test_the_surface_lists_the_aliases_it_declares() -> None:
    """The baseline of a release says each alias, what it became, and when it began and may end."""
    aliases = build_surface()["aliases"]
    entry = {"new": NEW, "since": "1.3.0", "until": "2.0.0"}

    assert aliases["parameters"] == {OLD: entry}
    assert aliases["in_dataset"]["dwd/observation"] == {"daily/climate_summary": {OLD: entry}}


def test_an_alias_of_the_last_release_that_is_gone_is_a_break_that_says_when_it_was_to_go() -> None:
    """An alias is removed in a major release and named as a break then, with the release it was to go in."""
    baseline = _baseline_with_an_alias()
    current = copy.deepcopy(baseline)

    assert breaking_changes(baseline, current) == []

    current["aliases"]["parameters"].clear()
    current["aliases"]["in_dataset"]["dwd/observation"]["daily/climate_summary"].clear()

    assert breaking_changes(baseline, current) == [
        "alias air_temp in dwd/observation/daily/climate_summary (since 1.3.0, until 2.0.0) was removed",
        "alias air_temp_all (since 1.3.0, until 2.0.0) was removed",
    ]


def test_a_baseline_before_the_aliases_existed_has_none_to_keep() -> None:
    """The baseline of a release that had no aliases is not a break of one that has them, or of one that has none."""
    baseline = copy.deepcopy(build_surface())
    baseline.pop("aliases", None)

    assert breaking_changes(baseline, build_surface()) == []
    assert breaking_changes(baseline, {**build_surface(), "aliases": {}}) == []


# --- the review of the first version ------------------------------------------------------------------------------


@pytest.mark.usefixtures("alias_everywhere")
def test_the_glossary_finds_what_holds_the_old_name_as_well_as_the_new_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """An alias that is a substring of other names still finds them, and the entry of the new name too."""
    monkeypatch.setitem(PARAMETER_ALIASES, "humidity_relativ", _alias())
    with pytest.warns(DeprecationWarning, match="'humidity_relativ' was renamed"):
        names = [entry["name"] for entry in core.get_glossary(parameter="humidity_relativ")]

    assert NEW in names
    assert any(name.startswith("humidity_relative") for name in names)


def _deprecations(call: Any) -> list[warnings.WarningMessage]:  # noqa: ANN401
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        call()
    return [w for w in seen if issubclass(w.category, DeprecationWarning)]


@pytest.mark.usefixtures("alias_everywhere")
def test_a_radius_alias_is_told_once_and_to_the_caller() -> None:
    """`Options(...)`, `options_from_mapping` and a request's options each warn once, at the caller's line."""
    from wetterdienst.options import options_from_mapping, resolve_options  # noqa: PLC0415

    for build in (
        lambda: Options(geo_station_distance={OLD: 12.0}),
        lambda: options_from_mapping({"geo_station_distance": {OLD: 12.0}}),
        lambda: resolve_options({"geo_station_distance": {OLD: 12.0}}),
    ):
        seen = _deprecations(build)
        assert len(seen) == 1
        assert seen[0].filename == __file__
    # a copy made by `replace` says nothing again
    options = Options(geo_station_distance={NEW: 12.0})
    assert _deprecations(lambda: options.replace(shape="wide")) == []


@pytest.mark.usefixtures("alias_everywhere")
def test_a_plain_call_is_attributed_to_the_caller() -> None:
    """The warning of a plain call of `use_alias` is at its caller too."""
    from wetterdienst.metadata.aliases import use_alias  # noqa: PLC0415

    (seen,) = _deprecations(lambda: use_alias(OLD, _ALIAS))

    assert seen.filename == __file__


@pytest.mark.usefixtures("alias_everywhere")
@pytest.mark.parametrize("order", [(OLD, NEW), (NEW, OLD)], ids=["old-first", "new-first"])
def test_a_radius_given_under_both_names_is_refused(order: tuple[str, str]) -> None:
    """Which radius is meant cannot be told, so the mapping is refused whichever name comes first."""
    from wetterdienst.options import options_from_mapping  # noqa: PLC0415

    given = {order[0]: 10.0, order[1]: 20.0}

    with pytest.raises(ValueError, match="'air_temp', which was renamed to 'temperature_air_mean_2m', and"):
        Options(geo_station_distance=given)
    with pytest.raises(ValueError, match="give the radius of the parameter once"):
        options_from_mapping({"geo_station_distance": given})


_HOSTILE = '{\'a\': 1}."does not have a column named ""air_temp""" = 1'


@pytest.mark.sql
@pytest.mark.usefixtures("alias_everywhere")
def test_text_a_clause_plants_in_an_error_is_no_missing_column() -> None:
    """A struct key spelled as DuckDB's message is a caller's mistake, a `duckdb.Error`, and no alias is used."""
    duckdb = pytest.importorskip("duckdb")
    df = pl.DataFrame({NEW: [1.0]})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(duckdb.Error) as error:
            filter_by_sql(df, _HOSTILE)
        assert recorded_warnings() == []
        # a qualified column of the clause is still an alias
        warnings.simplefilter("ignore")
        assert filter_by_sql(df, f"df.{OLD} > 0").height == 1

    assert type(error.value).__name__ == "BinderException"


@pytest.mark.sql
@pytest.mark.usefixtures("alias_everywhere")
def test_a_frame_that_has_the_old_name_is_not_aliased() -> None:
    """A column the frame has is its own, whatever an alias says."""
    df = pl.DataFrame({OLD: [1.0], NEW: [2.0]})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert filter_by_sql(df, f"{OLD} = 1").height == 1


@pytest.mark.sql
@pytest.mark.usefixtures("alias_everywhere")
def test_a_long_frame_is_not_filtered_by_the_old_name_in_its_parameter_column() -> None:
    """A long frame names the parameter in a value, and the old name there selects nothing, with no warning."""
    df = pl.DataFrame({"parameter": [NEW], "value": [1.0]})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert filter_by_sql(df, f"parameter = '{OLD}'").is_empty()
        assert filter_by_sql(df, f"parameter = '{NEW}'").height == 1


@pytest.mark.sql
def test_rest_answers_planted_text_as_a_refusal_and_a_real_alias_as_a_deprecation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Over REST the planted text is a 400 with no `Deprecation` header, and the alias of a column is told."""
    monkeypatch.setenv("WD_RESTAPI_SQL", "true")
    monkeypatch.setitem(
        PARAMETER_ALIASES, "height_old", ParameterAlias("elevation", "1.3.0", dt.date(2027, 3, 1), "2.0.0")
    )
    station = {
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "01048",
        "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
        "end_timestamp": dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
        "latitude": 51.1278,
        "longitude": 13.7543,
        "elevation": 228.0,
        "name": "Dresden-Klotzsche",
        "region": "Sachsen",
    }
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: pl.LazyFrame([station]))
    client = TestClient(restapi.app, raise_server_exceptions=False)
    params = {"provider": "dwd", "network": "observation", "parameters": "daily/kl"}

    hostile = client.get(
        "/api/v1/stations", params={**params, "sql": '{\'a\': 1}."does not have a column named ""height_old""" = 1'}
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        real = client.get("/api/v1/stations", params={**params, "sql": "height_old > 0"})

    assert hostile.status_code == 400, hostile.text
    assert "Deprecation" not in hostile.headers
    assert "deprecated-parameter" not in hostile.text
    assert real.status_code == 200, real.text
    assert real.headers["Deprecation"] == "@1803859200"
