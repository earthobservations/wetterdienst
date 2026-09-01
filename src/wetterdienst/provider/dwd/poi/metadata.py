# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD POI (Point Of Interest) current weather report metadata.

POI is the observed counterpart to MOSMIX: for every station DWD forecasts for, it publishes the
hourly weather reports of roughly the last day as ``<station_id>-BEOB.csv`` under
https://opendata.dwd.de/weather/weather_reports/poi/. The station ids are MOSMIX ids padded to five
characters with underscores, so the two networks share a station catalogue -- see ``api.py``.

``name_original`` holds DWD's own English column name from the file's first header line, including
the two names that carry a stray space (``mean_wind_direction_during_last_10 min_...`` and
``mean_wind_speed_during last_10_min_...``). They are quoted from the file rather than tidied up so
that the columns keep matching if DWD ever fixes them, which would otherwise silently drop wind.

Units are DWD's own, from the file's second header line: temperatures in degree Celsius, wind in
km/h, visibility in km, sunshine in minutes (last hour) and hours (previous day).

Two of the 41 columns are left unmapped: ``global_radiation_past_24_hours`` and
``direct_solar_radiation_last_24_hours``. Both are declared as W/m², which a 24-hour figure cannot
be. The hourly columns beside them *are* W/m²: summing a day of them as energy reproduces the daily
total DWD publishes for the same station and day in ``dwd/observation`` 10-minute solar to three
figures (Konstanz, 2026-08-31: 20.34 MJ/m² from POI against 2033.7 J/cm² measured). Against that
same total, the 24-hour column is proportional with a factor of 1.573 -- measured over 29 stations,
with a spread of 1.4% that integer rounding alone accounts for -- so it is a real daily radiation
total published in a unit of about 0.636 MJ/m² per count, which is none of the units the converter
knows and none this file declares. Mapping it would put a wrong unit on a right number, and a
consumer converting it would be out by more than half. Sum the hourly column for a daily total
instead. ``direct_solar_radiation_last_24_hours`` was empty at every station sampled; the hourly
siblings of both are mapped.

``present_weather`` is DWD's own 1..31 code table (documented at
https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/csv/poi_present_weather_zuordnung_pdf.pdf),
not WMO 4677. ``past_weather_1``/``past_weather_2`` are the BUFR 0 20 004 / 0 20 005 past-weather
codes and are only reported at the three-hourly synoptic hours, which is the period they cover.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

_TEMPERATURE = {"unit": "degree_celsius"}
_PRECIPITATION = {"unit": "millimeter"}
_WIND_SPEED = {"unit": "kilometer_per_hour"}
_RADIATION = {"unit": "watt_per_square_meter"}

DwdPoiMetadata = {
    "name_short": "DWD",
    "name_english": "German Weather Service",
    "name_local": "Deutscher Wetterdienst",
    "country": "Germany",
    "copyright": "© Deutscher Wetterdienst (DWD), POI weather reports",
    "url": "https://opendata.dwd.de/weather/weather_reports/poi/",
    "kind": "observation",
    "timezone": "Europe/Berlin",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["now"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "cloud_cover_total",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_height_layer1",
                            "name_original": "height_of_base_of_lowest_cloud_above_station",
                            "unit": "meter",
                        },
                        {
                            "name": "evapotranspiration_last_24h",
                            "name_original": "evaporation/evapotranspiration_last_24_hours",
                            "unit": "millimeter",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relative_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height_last_1h",
                            "name_original": "precipitation_amount_last_hour",
                            **_PRECIPITATION,
                        },
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "precipitation_amount_last_3_hours",
                            **_PRECIPITATION,
                        },
                        {
                            "name": "precipitation_height_last_6h",
                            "name_original": "precipitation_amount_last_6_hours",
                            **_PRECIPITATION,
                        },
                        {
                            "name": "precipitation_height_last_12h",
                            "name_original": "precipitation_last_12_hours",
                            **_PRECIPITATION,
                        },
                        {
                            "name": "precipitation_height_last_24h",
                            "name_original": "precipitation_amount_last_24_hours",
                            **_PRECIPITATION,
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pressure_reduced_to_mean_sea_level",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "global_radiation_last_hour",
                            **_RADIATION,
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse_intensity",
                            "name_original": "diffuse_solar_radiation_last_hour",
                            **_RADIATION,
                        },
                        {
                            "name": "radiation_sky_short_wave_direct_intensity",
                            "name_original": "direct_solar_radiation_last_hour",
                            **_RADIATION,
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "total_snow_depth",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "depth_of_new_snow",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "total_time_of_sunshine_during_last_hour",
                            "unit": "minute",
                        },
                        {
                            "name": "sunshine_duration_yesterday",
                            "name_original": "total_time_of_sunshine_past_day",
                            "unit": "hour",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "dry_bulb_temperature_at_2_meter_above_ground",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "temperature_at_5_cm_above_ground",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_max_2m_last_12h",
                            "name_original": "maximum_temperature_last_12_hours_2_meters_above_ground",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_min_2m_last_12h",
                            "name_original": "minimum_temperature_last_12_hours_2_meters_above_ground",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_min_0_05m_last_12h",
                            "name_original": "minimum_temperature_last_12_hours_5_cm_above_ground",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_mean_2m_yesterday",
                            "name_original": "daily_mean_of_temperature_previous_day",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_max_2m_yesterday",
                            "name_original": "maximum_of_temperature_for_previous_day",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_min_2m_yesterday",
                            "name_original": "minimum_of_temperature_for_previous_day",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_air_min_0_05m_yesterday",
                            "name_original": "minimum_of_temperature_at_5_cm_above_ground_for_previous_day",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dew_point_temperature_at_2_meter_above_ground",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "temperature_water",
                            "name_original": "sea/water_temperature",
                            **_TEMPERATURE,
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "horizontal_visibility",
                            "unit": "kilometer",
                        },
                        {
                            "name": "weather",
                            "name_original": "present_weather",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_last_3h",
                            "name_original": "past_weather_1",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_secondary_last_3h",
                            "name_original": "past_weather_2",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "mean_wind_direction_during_last_10 min_at_10_meters_above_ground",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "mean_wind_speed_during last_10_min_at_10_meters_above_ground",
                            **_WIND_SPEED,
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "maximum_wind_speed_as_10_minutes_mean_during_last_hour",
                            **_WIND_SPEED,
                        },
                        {
                            "name": "wind_speed_rolling_mean_max_yesterday",
                            "name_original": "maximum_of_10_minutes_mean_of_wind_speed_for_previous_day",
                            **_WIND_SPEED,
                        },
                        {
                            "name": "wind_gust_max_last_1h",
                            "name_original": "maximum_wind_speed_last_hour",
                            **_WIND_SPEED,
                        },
                        {
                            "name": "wind_gust_max_last_6h",
                            "name_original": "maximum_wind_speed_during_last_6_hours",
                            **_WIND_SPEED,
                        },
                        {
                            "name": "wind_gust_max_yesterday",
                            "name_original": "maximum_wind_speed_for_previous_day",
                            **_WIND_SPEED,
                        },
                    ],
                },
            ],
        },
    ],
}
DwdPoiMetadata = build_metadata_model(DwdPoiMetadata, "DwdPoiMetadata")
