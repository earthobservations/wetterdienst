# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A failed download is raised by the networks that read one file per station, month or feed (GH-2461).

Eleven networks logged the failure and went on with nothing -- an empty frame, `None`, or the next file -- so an
upstream outage read as a station without data. Each now raises it as a `DownloadError`, except a 404 where that is
how the network says a file is not there, and except `NoInternetError`, which stays quiet. `dwd/swsmos`, the twelfth,
is tested beside its other run tests.
"""

import datetime as dt
import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.period import Period
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dwd.phenology import api as phenology_api
from wetterdienst.provider.dwd.phenology.metadata import DwdPhenologyMetadata
from wetterdienst.provider.dwd.poi import api as poi_api
from wetterdienst.provider.dwd.poi.metadata import DwdPoiMetadata
from wetterdienst.provider.fmi.observation import api as fmi_api
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.lhmt.observation import api as lhmt_api
from wetterdienst.provider.meteofrance.observation import api as meteofrance_observation_api
from wetterdienst.provider.meteofrance.observation.metadata import MeteoFranceObservationMetadata
from wetterdienst.provider.meteofrance.synop import api as meteofrance_synop_api
from wetterdienst.provider.meteofrance.synop.metadata import MeteoFranceSynopMetadata
from wetterdienst.provider.metoffice.observation import api as metoffice_api
from wetterdienst.provider.rmi.observation import api as rmi_api
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")
_URL = "https://example.invalid/data/file.csv?key=secret"


def _settings() -> Settings:
    return Settings(cache_disable=True)


def _values(values_class: type, **sr: object) -> Any:  # noqa: ANN401
    """Build a values object that holds only what the site under test reads off its `sr`."""
    values = object.__new__(values_class)
    values.sr = SimpleNamespace(stations=SimpleNamespace(settings=_settings()), **sr)
    return values


def _phenology(module: Any) -> object:  # noqa: ANN401
    values = _values(module.DwdPhenologyValues)
    values._files = {}  # noqa: SLF001
    values._station_ids = {"1"}  # noqa: SLF001
    dataset = DwdPhenologyMetadata["annual"]["annual_beet"]
    return values._load(dataset, Period.RECENT)  # noqa: SLF001


def _poi(module: Any) -> object:  # noqa: ANN401
    return _values(module.DwdPoiValues)._collect_station_parameter_or_dataset(  # noqa: SLF001
        "10381",
        DwdPoiMetadata["hourly"]["data"],
    )


def _chmi(module: Any) -> object:  # noqa: ANN401
    return _values(module.ChmiObservationValues)._download(_URL, _settings(), "0-20000-0-11406")  # noqa: SLF001


def _fmi(module: Any) -> object:  # noqa: ANN401
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    return _values(module.FmiObservationValues)._collect_window(  # noqa: SLF001
        "100971",
        "tday",
        "fmi::observations::weather::daily::timevaluepair",
        None,
        start,
        start + dt.timedelta(days=1),
        _settings(),
    )


def _ipma(module: Any) -> object:  # noqa: ANN401
    return _values(module.IpmaObservationValues)._observations_feed()  # noqa: SLF001


def _dmi(module: Any) -> object:  # noqa: ANN401
    # the read as a whole: the pager raises `NoInternetError` for the collect to end the windows quietly
    start = dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
    values = _values(module.DmiObservationValues, start=start, end=start + dt.timedelta(days=1))
    dataset = module.DmiObservationMetadata["hourly"].datasets[0]
    return values._collect_station_parameter_or_dataset("06180", dataset)  # noqa: SLF001


def _rmi(module: Any) -> object:  # noqa: ANN401
    values = _values(module.RmiObservationValues)
    return list(values._iter_value_pages("layer", "filter", pl.Schema({}), _settings()))  # noqa: SLF001


def _metoffice(module: Any) -> object:  # noqa: ANN401
    return _values(module.MetOfficeObservationValues)._download(_URL, _settings(), None)  # noqa: SLF001


def _lhmt(module: Any) -> object:  # noqa: ANN401
    # the read as a whole: `_download_day` hands `NoInternetError` to the collect, which ends the days quietly
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    values = _values(module.LhmtObservationValues, start=start, end=start)
    return values._collect_station_parameter_or_dataset(  # noqa: SLF001
        "vilniaus-ams",
        module.LhmtObservationMetadata["hourly"]["data"],
    )


def _meteofrance_synop(module: Any, year: int | None = None) -> object:  # noqa: ANN401
    """Ask for a day of one year, by default the current one: the only year whose file can be missing."""
    year = year or dt.datetime.now(tz=UTC).year
    values = _values(
        module.MeteoFranceSynopValues,
        start=dt.datetime(year, 1, 1, tzinfo=UTC),
        end=dt.datetime(year, 1, 2, tzinfo=UTC),
    )
    return values._collect_station_parameter_or_dataset(  # noqa: SLF001
        "07149",
        MeteoFranceSynopMetadata["subdaily"]["data"],
    )


def _meteofrance_observation(module: Any) -> object:  # noqa: ANN401
    values = _values(module.MeteoFranceObservationValues, start=None, end=None)
    return values._collect_station_parameter_or_dataset(  # noqa: SLF001
        "07005001",
        MeteoFranceObservationMetadata["daily"]["core"],
    )


# (module, driver, whether a 404 is dropped: the file is simply not there)
_SITES = [
    pytest.param(phenology_api, _phenology, False, id="dwd/phenology"),
    pytest.param(poi_api, _poi, True, id="dwd/poi"),
    pytest.param(chmi_api, _chmi, True, id="chmi"),
    pytest.param(fmi_api, _fmi, False, id="fmi"),
    pytest.param(ipma_api, _ipma, False, id="ipma"),
    pytest.param(dmi_api, _dmi, False, id="dmi"),
    pytest.param(rmi_api, _rmi, False, id="rmi"),
    pytest.param(metoffice_api, _metoffice, True, id="metoffice"),
    pytest.param(lhmt_api, _lhmt, True, id="lhmt"),
    pytest.param(meteofrance_synop_api, _meteofrance_synop, True, id="meteofrance/synop"),
    pytest.param(
        meteofrance_observation_api,
        _meteofrance_observation,
        True,
        id="meteofrance/observation",
    ),
]


def _gives_nothing(result: object) -> bool:
    """Say whether a site's answer holds no data: `None`, no items, or a frame without rows."""
    if result is None:
        return True
    if isinstance(result, pl.DataFrame):
        return result.is_empty()
    return not result


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch) -> Callable[[Any, Exception, int], None]:
    """Make every download of a provider module answer with a failure."""

    def serve(module: Any, error: Exception, status: int) -> None:  # noqa: ANN401
        def download_file(*, url: str = _URL, **_: object) -> File:
            return File(url=url, content=error, status=status)

        monkeypatch.setattr(module, "download_file", download_file)
        if module is meteofrance_observation_api:
            # the department's resources come from a listing, and are fetched through a helper
            resource = {"title": "Q_07_previous-1950-2024_RR-T-Vent", "url": _URL}
            monkeypatch.setattr(module, "_get_climate_resources", lambda *_args, **_kwargs: [resource])
            monkeypatch.setattr(module, "_match_department_resources", lambda resources, *_args: resources)
            monkeypatch.setattr(
                module,
                "_download_climate_resources",
                lambda resources, _settings: {
                    r["url"]: File(url=r["url"], content=error, status=status) for r in resources
                },
            )

    return serve


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(TimeoutError(), 408, id="timeout"),
        pytest.param(OSError("503 Service Unavailable"), 503, id="server-error"),
    ],
)
@pytest.mark.parametrize(("module", "driver", "drops_404"), _SITES)
def test_a_failed_download_is_raised(
    serve: Callable[[Any, Exception, int], None],
    module: Any,  # noqa: ANN401
    driver: Callable[[Any], object],
    drops_404: bool,  # noqa: ARG001, FBT001
    error: Exception,
    status: int,
) -> None:
    """A timeout or a 5xx after the retries raises, where it used to read as a station without data."""
    serve(module, error, status)

    with pytest.raises(DownloadError) as excinfo:
        driver(module)

    assert excinfo.value.__cause__ is error


@pytest.mark.parametrize(("module", "driver", "drops_404"), _SITES)
def test_a_404_is_dropped_where_the_file_is_simply_not_there(
    serve: Callable[[Any, Exception, int], None],
    module: Any,  # noqa: ANN401
    driver: Callable[[Any], object],
    drops_404: bool,  # noqa: FBT001
) -> None:
    """A 404 gives no data where a file can be absent (a station-month, a year), and raises where it cannot (an API)."""
    serve(module, FileNotFoundError("404 Not Found"), 404)

    if drops_404:
        assert _gives_nothing(driver(module))
    else:
        with pytest.raises(DownloadError, match="404 Not Found"):
            driver(module)


@pytest.mark.parametrize(("module", "driver", "drops_404"), _SITES)
def test_no_connection_at_all_stays_quiet(
    serve: Callable[[Any, Exception, int], None],
    caplog: pytest.LogCaptureFixture,
    module: Any,  # noqa: ANN401
    driver: Callable[[Any], object],
    drops_404: bool,  # noqa: ARG001, FBT001
) -> None:
    """A `NoInternetError` gives no data and no warning, as before, so working offline still returns empty."""
    serve(module, NoInternetError("offline"), 503)
    caplog.set_level(logging.WARNING)

    assert _gives_nothing(driver(module))
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_a_404_for_a_past_synop_year_is_raised(serve: Callable[[Any, Exception, int], None]) -> None:
    """Every year's file holds every station, and only the current year's can be missing, so any other 404 raises."""
    serve(meteofrance_synop_api, FileNotFoundError("404 Not Found"), 404)

    with pytest.raises(DownloadError, match="404 Not Found"):
        _meteofrance_synop(meteofrance_synop_api, year=2020)


def test_fmi_drops_the_400_for_a_station_it_does_not_know(serve: Callable[[Any, Exception, int], None]) -> None:
    """FMI answers 400 "Unknown 'fmisid' value!" for a few stations of its own catalogue, which have no data."""
    serve(fmi_api, OSError("400 Bad Request"), 400)

    assert _gives_nothing(_fmi(fmi_api))


def test_metoffice_raises_a_404_for_a_station_metadata_file_every_station_depends_on(
    serve: Callable[[Any, Exception, int], None],
) -> None:
    """A station-year can be absent from the archive, but the dataset's station-metadata file cannot."""
    serve(metoffice_api, FileNotFoundError("404 Not Found"), 404)
    values = _values(metoffice_api.MetOfficeObservationValues)

    with pytest.raises(DownloadError, match="404 Not Found"):
        values._station_slug_and_county("00009", "uk-daily-rain-obs", "202407", _settings(), None)  # noqa: SLF001
