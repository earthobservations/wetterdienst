# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Met Office (UK) observation metadata.

Data comes from **MIDAS Open**, the Met Office's UK Open Government Licence subset of its land
surface station archive, hosted at CEDA (https://catalogue.ceda.ac.uk/uuid/dbd451271eb04662beade68da43546e1/).
It is *not* the (paid, forecast-only) Met Office Weather DataHub -- MIDAS Open is the historical
archive: annual releases, each covering data up to the end of the previous complete year, so
"recent" data lags roughly 6-12 months behind real time.

Each of the 8 MIDAS Open datasets is one flat CSV per (station, year) in BADC-CSV format (a header
metadata block, then a bare ``data`` line, then a normal CSV table), and all datasets are either
``daily`` or ``hourly``. Every dataset carries far more raw columns than are mapped below --
quality-control flags (``*_q``), estimation/interpolation flags (``*_j``), housekeeping columns
(``id``, ``id_type``, ``met_domain_name``, ``src_id``, ``rec_st_ind``, ``version_num``,
``meto_stmp_time``, ``midas_stmp_etime``) and a handful of columns with no clean canonical
``Parameter`` match (e.g. ``min_conc_temp`` concrete minimum temperature, ``q30cm_soil_temp`` --
no ``TEMPERATURE_SOIL_MEAN_0_3M`` exists) are intentionally left unmapped rather than guessing a
canonical name. ``*_q`` columns are wired up as the per-value ``quality`` column in ``api.py`` (a
raw MIDAS ``MESQL`` compound QC flag -- see api.py -- not a linear quality level), not as separate
parameters.

Native units below were verified against real numeric values from the archive and the Met Office
GL-table column documentation (https://artefacts.ceda.ac.uk/badc_datadocs/ukmo-midas/GL_Table.html):
temperatures in °C, pressures in hPa, humidity in %, precipitation in mm, and **wind speed/gust in
knots** (confirmed: a 32-value hourly mean is a plausible ~59 km/h, absurd as m/s). ``visibility``
is stored in *decametres* and is scaled to metres in ``api.py`` (there is no decametre unit to
declare here). Radiation (``glbl_irad_amt`` etc.) is kJ/m² per the Open Data User Guide
(https://doi.org/10.5281/zenodo.7357335) and the GL-table docs, and checks out against real values
(a summer hourly peak of ~2000 kJ/m² is ~560 W/m², plausible for UK midday).
"""

from __future__ import annotations

from wetterdienst.model.metadata import build_metadata_model

_TEMPERATURE = {"unit": "degree_celsius"}
_PRECIPITATION = {"unit": "millimeter"}
_PRESSURE = {"unit": "hectopascal"}
_HUMIDITY = {"unit": "percent"}
_WIND_SPEED = {"unit": "knots"}
_WIND_DIRECTION = {"unit": "degree"}
_SUNSHINE = {"unit": "hour"}
_SNOW_DEPTH = {"unit": "centimeter"}
_RADIATION = {"unit": "kilojoule_per_square_meter"}

_DAILY_RAIN_PARAMETERS = [
    {"name": "precipitation_height", "name_original": "prcp_amt", **_PRECIPITATION},
]

_DAILY_TEMPERATURE_PARAMETERS = [
    {"name": "temperature_air_max_2m", "name_original": "max_air_temp", **_TEMPERATURE},
    {"name": "temperature_air_min_2m", "name_original": "min_air_temp", **_TEMPERATURE},
    {"name": "temperature_air_min_0_05m", "name_original": "min_grss_temp", **_TEMPERATURE},
]

# hail_day_id / thunder_day_flag are deliberately not mapped: confirmed live they carry opaque
# codes (e.g. 0/9), not the boolean occurrence the WEATHER_TYPE_* parameters denote, so exposing
# them would misrepresent the data.
_DAILY_WEATHER_PARAMETERS = [
    {"name": "sunshine_duration", "name_original": "drv_24hr_sun_dur", **_SUNSHINE},
    {"name": "snow_depth", "name_original": "snow_depth", **_SNOW_DEPTH},
    {"name": "snow_depth_new", "name_original": "frsh_snw_amt", **_SNOW_DEPTH},
]

_HOURLY_RAIN_PARAMETERS = [
    {"name": "precipitation_height", "name_original": "prcp_amt", **_PRECIPITATION},
    {"name": "precipitation_duration", "name_original": "prcp_dur", "unit": "minute"},
]

_HOURLY_WEATHER_PARAMETERS = [
    {"name": "wind_direction", "name_original": "wind_direction", **_WIND_DIRECTION},
    {"name": "wind_speed", "name_original": "wind_speed", **_WIND_SPEED},
    {"name": "wind_gust_max", "name_original": "q10mnt_mxgst_spd", **_WIND_SPEED},
    # native decametres; scaled to metres in api.py (_SCALE)
    {"name": "visibility_range", "name_original": "visibility", "unit": "meter"},
    {"name": "pressure_air_sea_level", "name_original": "msl_pressure", **_PRESSURE},
    {"name": "pressure_air_site", "name_original": "stn_pres", **_PRESSURE},
    {"name": "temperature_air_mean_2m", "name_original": "air_temperature", **_TEMPERATURE},
    {"name": "temperature_dew_point_mean_2m", "name_original": "dewpoint", **_TEMPERATURE},
    {"name": "humidity", "name_original": "rltv_hum", **_HUMIDITY},
    {"name": "sunshine_duration", "name_original": "wmo_hr_sun_dur", **_SUNSHINE},
    {"name": "snow_depth", "name_original": "snow_depth", **_SNOW_DEPTH},
    {"name": "cloud_cover_total", "name_original": "cld_ttl_amt_id", "unit": "one_eighth"},
    {"name": "weather", "name_original": "prst_wx_id", "unit": "dimensionless"},
]

_MEAN_WIND_PARAMETERS = [
    {"name": "wind_direction", "name_original": "mean_wind_dir", **_WIND_DIRECTION},
    {"name": "wind_speed", "name_original": "mean_wind_speed", **_WIND_SPEED},
    {"name": "wind_direction_gust_max", "name_original": "max_gust_dir", **_WIND_DIRECTION},
    {"name": "wind_gust_max", "name_original": "max_gust_speed", **_WIND_SPEED},
]

_RADIATION_PARAMETERS = [
    {"name": "radiation_global", "name_original": "glbl_irad_amt", **_RADIATION},
    {"name": "radiation_sky_short_wave_diffuse", "name_original": "difu_irad_amt", **_RADIATION},
    {"name": "radiation_sky_short_wave_direct", "name_original": "direct_irad", **_RADIATION},
]

_SOIL_TEMPERATURE_PARAMETERS = [
    {"name": "temperature_soil_mean_0_05m", "name_original": "q5cm_soil_temp", **_TEMPERATURE},
    {"name": "temperature_soil_mean_0_1m", "name_original": "q10cm_soil_temp", **_TEMPERATURE},
    {"name": "temperature_soil_mean_0_2m", "name_original": "q20cm_soil_temp", **_TEMPERATURE},
    {"name": "temperature_soil_mean_0_5m", "name_original": "q50cm_soil_temp", **_TEMPERATURE},
    {"name": "temperature_soil_mean_1m", "name_original": "q100cm_soil_temp", **_TEMPERATURE},
]


def _dataset(name: str, midas_dataset: str, parameters: list[dict]) -> dict:
    return {
        "name": name,
        # the MIDAS Open dataset slug, e.g. "uk-daily-rain-obs" -- used to build archive paths
        "name_original": midas_dataset,
        "grouped": True,
        "parameters": parameters,
    }


def _resolution(name: str, datasets: list[dict]) -> dict:
    return {
        "name": name,
        "name_original": name,
        "periods": ["historical"],
        "date_required": False,
        "datasets": datasets,
    }


MetOfficeObservationMetadata = {
    "name_short": "MetOffice",
    "name_english": "Met Office",
    "name_local": "Met Office",
    "country": "United Kingdom",
    "copyright": "© Crown Copyright, Met Office, MIDAS Open, Open Government Licence v3.0",
    "url": "https://catalogue.ceda.ac.uk/uuid/dbd451271eb04662beade68da43546e1/",
    "kind": "observation",
    "timezone": "Europe/London",
    "timezone_data": "UTC",
    "resolutions": [
        _resolution(
            "daily",
            [
                _dataset("rain", "uk-daily-rain-obs", _DAILY_RAIN_PARAMETERS),
                _dataset("temperature", "uk-daily-temperature-obs", _DAILY_TEMPERATURE_PARAMETERS),
                _dataset("weather", "uk-daily-weather-obs", _DAILY_WEATHER_PARAMETERS),
            ],
        ),
        _resolution(
            "hourly",
            [
                _dataset("rain", "uk-hourly-rain-obs", _HOURLY_RAIN_PARAMETERS),
                _dataset("weather", "uk-hourly-weather-obs", _HOURLY_WEATHER_PARAMETERS),
                _dataset("wind", "uk-mean-wind-obs", _MEAN_WIND_PARAMETERS),
                _dataset("radiation", "uk-radiation-obs", _RADIATION_PARAMETERS),
                _dataset("soil_temperature", "uk-soil-temperature-obs", _SOIL_TEMPERATURE_PARAMETERS),
            ],
        ),
    ],
}
MetOfficeObservationMetadata = build_metadata_model(MetOfficeObservationMetadata, "MetOfficeObservationMetadata")
