# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the DWD POI, MOSMIX, DMO, derived and SWSMOS descriptions state what their sources state (GH-3136).

The sources are the German description line of the POI files, `MetElementDefinition.xml` and
`mosmix_element_weather_xls.xlsx` of the MOSMIX forecasts, the sheets of the `derived_germany` directories of the
climate data centre and `swis_swsmos_beschreibung.pdf`. Each pin is a claim an earlier description made that the
source does not (a MOSMIX wording on a SWSMOS row, a height no sheet states, "winter wheat" for what DWD calls winter
cereals), or a fact the old description left out and the data showed (the previous day of the POI rows is a UTC day,
which the 10-minute observations of 25 stations reproduce). The evidence is in the comment above
`SOURCE_DESCRIPTIONS`.
"""

import pytest

from wetterdienst.model.metadata import MetadataModel
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata
from wetterdienst.provider.dwd.dmo import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix import DwdMosmixMetadata
from wetterdienst.provider.dwd.poi import DwdPoiMetadata
from wetterdienst.provider.dwd.swsmos import DwdSwsmosMetadata


def _description(metadata: MetadataModel, resolution: str, dataset: str, name_original: str) -> str:
    """Return the description of the parameter of `name_original` in the dataset."""
    for parameter in metadata[resolution][dataset].parameters:
        if parameter.name_original == name_original:
            return parameter.description or ""
    msg = f"{name_original!r} is not in {resolution}/{dataset}"
    raise KeyError(msg)


def test_swsmos_describes_what_its_own_sheet_describes() -> None:
    """The liquid precipitation of the last hour is not "consistent with significant weather", as MOSMIX's `RRL1c` is.

    The sheet says "Niederschlag flüssig der letzten Stunde"; the wording was MOSMIX's `RRL1c`. It states no height of
    the air and dew point temperatures either, and lists six road conditions.
    """
    swsmos = [_description(DwdSwsmosMetadata, "hourly", "data", name) for name in ("RRL1c", "TL", "TD")]
    assert "significant weather" not in swsmos[0].lower()
    assert all("2 m" not in text and "2m" not in text for text in swsmos[1:])
    road = _description(DwdSwsmosMetadata, "hourly", "data", "RC")
    for code in ("1 dry", "2 moist", "3 snow", "4 hoar frost", "5 freezing wetness", "6 glaze ice"):
        assert code in road


def test_the_poi_previous_day_is_the_utc_day_reported_at_06() -> None:
    """The "previous day" columns of the German stations are a UTC day, in the 06 UTC report; the snow has no period.

    The 10-minute observations of 25 stations reproduce the maximum, minimum and mean of 2026-10-20 (reported at 06 UTC
    on 2026-10-21) for the UTC day and not for 06:00 to 06:00; the new snow was "since the previous observation",
    which the file does not state (the column is in the 06 UTC report only).
    """
    names = (
        "daily_mean_of_temperature_previous_day",
        "maximum_of_temperature_for_previous_day",
        "minimum_of_temperature_for_previous_day",
        "minimum_of_temperature_at_5_cm_above_ground_for_previous_day",
        "maximum_wind_speed_for_previous_day",
        "total_time_of_sunshine_past_day",
    )
    for name in names:
        text = _description(DwdPoiMetadata, "hourly", "data", name)
        assert "previous day (UTC" in text
        assert "06 UTC" in text
    snow = _description(DwdPoiMetadata, "hourly", "data", "depth_of_new_snow")
    assert "previous observation" not in snow
    assert "no period" in snow


def test_the_poi_radiation_of_the_hour_is_an_energy_expressed_as_power() -> None:
    """The global and diffuse irradiance of the hour is that hour's energy over 3600 s, not a reading at one moment.

    It equals the sum of DWD's 10-minute radiation (J/cm2) of the hour, times 10000 and over 3600, to within 0.9 W/m2 on
    all 250 hourly values of 10 stations. The word "mean" stays out of the description: DWD does not say it and
    `test_mean_names` holds the name to what the source states.
    """
    for name in ("global_radiation_last_hour", "diffuse_solar_radiation_last_hour"):
        text = _description(DwdPoiMetadata, "hourly", "data", name)
        assert "divided by 3600 s" in text
        assert "mean" not in text.lower()
        assert "averag" not in text.lower()


@pytest.mark.parametrize(
    ("dataset", "name_original", "said"),
    [
        ("icon", "rad1h", "not clipped at 0"),
        ("icon_eu", "rad1h", "not clipped at 0"),
        ("icon", "rads3", "not clipped at 0"),
        ("icon", "rr1", "returned as 0.0, with the number kept as `raw:`"),
        ("icon_eu", "rr1", "returned as 0.0, with the number kept as `raw:`"),
        ("icon", "rr3", "returned as 0.0, with the number kept as `raw:`"),
    ],
)
def test_the_dmo_elements_that_run_below_zero_say_what_becomes_of_it(
    dataset: str, name_original: str, said: str
) -> None:
    """ICON's `Rad1h` and `RadS3` are not clipped at 0, its `RR1` and `RR3` are 0.0 with the number as `raw:` (GH-3263).

    Read 2026-10-22: `Rad1h` negative in 411 of 1872 icon-eu values, `RadS3` in 273 of 1209 icon values, `RR1` in 3 of
    1872 icon-eu values and `RR3` in 143 of 182,714 icon values.
    """
    assert said in _description(DwdDmoMetadata, "hourly", dataset, name_original)


def test_the_mosmix_ratio_and_energy_are_not_called_irradiance_alone() -> None:
    """`Rad1h` is in kJ/m2 (J/cm2 in DMO), an energy; `RRad1` is a percentage, not an irradiance.

    `Rad1h` over the extraterrestrial radiation of the hour reproduces `RRad1` roughly (mean difference under 3 points
    at 6 stations, single hours up to about 20 points apart).
    """
    for metadata, datasets in ((DwdMosmixMetadata, ("small", "large")), (DwdDmoMetadata, ("icon", "icon_eu"))):
        for dataset in datasets:
            assert "energy" in _description(metadata, "hourly", dataset, "rad1h")
    assert "percentage" in _description(DwdMosmixMetadata, "hourly", "large", "rrad1")
    assert "3 hours" in _description(DwdMosmixMetadata, "hourly", "large", "ww3")


@pytest.mark.parametrize(
    ("metadata", "dataset"),
    [(DwdMosmixMetadata, "small"), (DwdMosmixMetadata, "large"), (DwdDmoMetadata, "icon"), (DwdDmoMetadata, "icon_eu")],
)
def test_the_weather_codes_are_the_ones_dwd_lists(metadata: MetadataModel, dataset: str) -> None:
    """`ww` and `W1W2` carry the code lists DWD publishes in `mosmix_element_weather_xls.xlsx`.

    MOSMIX's `W1W2` is two digits (every value of 8 stations of MOSMIX_L and of all 5648 stations of MOSMIX_S has
    its tens digit at least its units digit), DMO's one class.
    """
    assert "95 (thunderstorm)" in _description(metadata, "hourly", dataset, "ww")
    w1w2 = _description(metadata, "hourly", dataset, "w1w2")
    assert "9 thunderstorm" in w1w2
    assert "not reliable" in w1w2
    assert ("two digits" in w1w2) == (metadata is DwdMosmixMetadata)


def test_the_derived_soil_data_name_what_the_sheets_name() -> None:
    """Wintergetreide is winter cereals, not winter wheat; the moisture is in % nFK, a share of the field capacity."""
    for resolution in ("daily", "monthly"):
        for parameter in DwdDerivedMetadata[resolution]["soil"].parameters:
            text = parameter.description or ""
            assert "wheat" not in text.lower(), parameter.name_original
            if parameter.name_original.endswith("_ag") and "bf" in parameter.name_original:
                assert "% nFK" in text, parameter.name_original


def test_the_derived_cooling_degree_hours_state_their_unit_and_the_degree_days_their_formula() -> None:
    """The sheet's "Kelvin * day" for cooling degree hours is not a unit the values can have.

    2,562.3 for 545 cooling hours (Grossenkneten, September 2026, reference 13 degree Celsius) is K*h, and the sum of
    20 minus the daily mean over the days below 15 degree Celsius reproduces the degree days of 3 stations to 0.1.
    """
    for reference in (13, 16, 18):
        text = _description(DwdDerivedMetadata, "monthly", f"cooling_degreehours_{reference}", "Kuehlgradstunden")
        assert "in K*h" in text
        assert "Kelvin * day" in text
    degree_days = _description(DwdDerivedMetadata, "monthly", "heating_degreedays", "Monatsgradtage")
    assert "20 degree Celsius" in degree_days
    assert "15 degree Celsius" in degree_days
    assert "G(TRY, P) / G" in _description(DwdDerivedMetadata, "monthly", "climate_correction_factor", "KF")
