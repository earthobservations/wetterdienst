# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The bounds of the ``range`` check, in one table keyed by canonical parameter name (GH-3676).

The values core judges a reading in the canonical unit of its unit type (``UnitConverter().targets``: °C, hPa, m/s,
mm, J/cm², a fraction as a decimal, seconds), whatever unit the source writes and whatever unit the caller asks for, so
a bound is written once per quantity and not once per reader and unit.

``RANGES`` holds the bounds of a quantity, by resolution where the quantity grows with the span (the rain of a day is
not the rain of ten minutes) and under ``"*"`` where it does not. Where several providers declared different bounds
for the same quantity and resolution the table holds the widest. A network whose own bound is narrower on purpose
(DMI's daily rain, DWD's station pressure, RMI's gusts and sunshine) has an entry in ``OVERRIDES``. ``SCOPE`` names the
quantities each network judges, so that a network is held to what it was held to and no further: adding a name to the
scope of a network is what extends the check to it. A provider adds its bounds here (``docs/contribution/services.md``).

``tests/model/test_plausibility_core.py`` holds the table to the bounds the readers declared before the checks moved to
the core (``tests/model/data/ranges_before_the_move.json``), and ``tests/provider/test_physical_ranges.py`` holds each
bound to the generous ranges of ``tests/provider/physical_ranges.py``. The bounds are generous on purpose: they find a
value that is a defect of the source, not an extreme, and none lies inside a record.

Where the bounds come from (the argument of each provider's reader, kept here with the bound). The world records are
those of the WMO World Weather and Climate Extremes Archive, table of 31 July 2025
(https://public.wmo.int/sites/default/files/2025-07/Table_Records_25Jul2025.pdf), read for the research of GH-3681:

- Air temperature -90 to 60 °C: the highest is 56.7 °C (Furnace Creek, 1913-07-10), the lowest -89.2 °C (Vostok,
  1983-07-21). The dew point has the same bounds; ISD, HadISD and WMO-No. 305 allow it down to -98 to -100 °C, so the
  lower bound is tighter than theirs (GH-3681 section 7). The road network holds -60 °C as its cold end: Germany's
  record is -45.9 °C (Funtensee, 2001), a road surface tracks the air, and the stopped sensors of station KM write
  -75.00 °C.
- Pressure at the station and at sea level, 300 to 1100 hPa, and 500 to 1090 hPa for DWD, the Météo-France synop
  (500 to 1100, sea level 850 to 1100): the highest sea level pressure the WMO table lists is 1089.1 hPa (Tosontsengel,
  2004-12-30, above 750 m; 1083.8 hPa, Agata 1968-12-31, below 750 m), the lowest 870 hPa (Typhoon Tip, 1979-10-12).
  The comments of the readers quoted 1084.8 hPa (Tosontsengel, 2001), which the table does not list today. The highest
  German station is the Zugspitze (about 700 hPa) and DWD's daily mean at the station of 25 files reads 935.1 to
  1041.6 hPa, so nothing a station reads is below 500 hPa.
- Wind speed 0 to 115 m/s: the highest gust is 113.2 m/s (Barrow Island, 1996-04-10; the comments quoted 113.3). RMI
  holds a gust to 60 m/s: the highest of its daily layer and of the hourly one is 51.05 m/s (6434, 2002-12-30), and the
  81.5 m/s of 6414 (2003-10-09, `validated: false`) is no reading.
- Rain: the most in 1 minute is 31.2 mm (Unionville MD, 1956-07-04), in 60 minutes 305 mm (Holt MO, 1947-06-22), in 12
  hours 1,144 mm and in 24 hours 1,825 mm (Foc-Foc, 1966-01-07/08), in 12 months 26,470 mm (Cherrapunji, 1860/61). The
  hourly bound of 600 mm and the 10- and 15-minute bounds rest on other lists (BoM, NWS HDSC: Shangdi 1975, 401 mm in
  an hour, is not in the WMO table). DMI covers Denmark, the Faroe Islands and Greenland, and the rain it marks
  `validity: true` runs to 183.5 mm in a day, 641.8 in a month and 3,291.3 in a year, where its `validity: false`
  values (1978 mm in a day, 17,802 mm in a month) are no gauge reading, so DMI's day is held to 500 mm, its month to
  1,500 and its year to 4,000. The largest amount of a day in a month and of 30 minutes in a day are no more than a
  day, so 500 mm.
- Sunshine cannot last longer than the span it is measured over, with a tenth to spare (DMI's hour, day and month); RMI
  holds it to the span itself, as it writes minutes to two decimals and no day holds the 3,808 minutes that were
  written (6459, 2013-03-24).
- Radiation: the solar constant is 1,361 W/m²; no day brings more than 60 MJ/m² (the top of the atmosphere at 82
  degrees north in midsummer is 48), a month is 31 such days, a year 5,000 MJ/m² (DMI's highest valid year is 4,533.2).
- Relative humidity up to 130 %: a hygrometer reads past 100 % now and then. The road holds 1 % as its lower bound
  where the others hold 0: a hygrometer that failed writes 0.1 % (P925, GH-3624).
- Snow depth -50 to 1,500 cm: an automatic gauge reads a few centimetres below zero. Heating degree days up to 20,000:
  the most of a year DMI publishes is 18,022.8 (04416 Summit, 2011). Vapour pressure up to 100 hPa.
"""

from __future__ import annotations

Bounds = tuple[float, float]

RANGES: dict[str, dict[str, Bounds]] = {
    "cloud_cover_total": {"*": (0.0, 1.0)},
    "cloud_cover_total_mean": {"*": (0.0, 1.0)},
    "count_days_cloud_cover_total_mean_gt_80pct": {"*": (0.0, 366.0)},
    "count_days_cloud_cover_total_mean_lt_20pct": {"*": (0.0, 366.0)},
    "count_days_frost": {"*": (0.0, 366.0)},
    "count_days_ice": {"*": (0.0, 366.0)},
    "count_days_precipitation_amount_ge_0_1mm": {"*": (0.0, 366.0)},
    "count_days_precipitation_amount_ge_10mm": {"*": (0.0, 366.0)},
    "count_days_precipitation_amount_ge_1mm": {"*": (0.0, 366.0)},
    "count_days_snow_cover_gt_50pct": {"*": (0.0, 366.0)},
    "count_days_summer": {"*": (0.0, 366.0)},
    "count_days_temperature_air_min_2m_lt_minus_10c": {"*": (0.0, 366.0)},
    "count_days_tropical_night": {"*": (0.0, 366.0)},
    "count_days_wind_speed_rolling_mean_max_ge_10_8mps": {"*": (0.0, 366.0)},
    "count_days_wind_speed_rolling_mean_max_ge_20_8mps": {"*": (0.0, 366.0)},
    "count_days_wind_speed_rolling_mean_max_ge_24_5mps": {"*": (0.0, 366.0)},
    "count_days_wind_speed_rolling_mean_max_ge_28_5mps": {"*": (0.0, 366.0)},
    "heating_degree_day": {"daily": (0.0, 20000.0), "monthly": (0.0, 20000.0), "annual": (0.0, 20000.0)},
    # DWD road, the only network with this name: 1 % and not 0 % at the low end, a failed hygrometer writes 0.1 %
    "humidity_relative": {"*": (0.01, 1.3)},
    "humidity_relative_max": {"*": (0.0, 1.3)},
    "humidity_relative_mean": {"*": (0.0, 1.3)},
    "humidity_relative_min": {"*": (0.0, 1.3)},
    "precipitation_amount": {
        "hourly": (0.0, 600.0),
        "daily": (0.0, 2000.0),
        "monthly": (0.0, 1500.0),
        "annual": (0.0, 4000.0),
        "15_minutes": (0.0, 300.0),
        "10_minutes": (0.0, 200.0),
    },
    "precipitation_amount_last_12h": {"hourly": (0.0, 500.0), "subdaily": (0.0, 1200.0)},
    "precipitation_amount_last_1h": {"*": (0.0, 600.0)},
    "precipitation_amount_last_24h": {"hourly": (0.0, 500.0), "subdaily": (0.0, 2000.0)},
    "precipitation_amount_last_3h": {"*": (0.0, 1200.0)},
    "precipitation_amount_last_6h": {"*": (0.0, 1200.0)},
    "precipitation_amount_max": {"*": (0.0, 500.0)},
    "precipitation_amount_max_30min": {"*": (0.0, 500.0)},
    "precipitation_intensity": {"*": (0.0, 3000.0)},
    "pressure_air_sea_level": {"10_minutes": (500.0, 1090.0), "hourly": (500.0, 1090.0), "subdaily": (850.0, 1100.0)},
    "pressure_air_sea_level_max": {"*": (300.0, 1100.0)},
    "pressure_air_sea_level_mean": {"*": (300.0, 1100.0)},
    "pressure_air_sea_level_min": {"*": (300.0, 1100.0)},
    "pressure_air_site": {
        "10_minutes": (300.0, 1100.0),
        "hourly": (300.0, 1100.0),
        "subdaily": (500.0, 1100.0),
        "daily": (300.0, 1100.0),
    },
    "pressure_air_site_mean": {"*": (500.0, 1090.0)},
    "pressure_vapor_mean": {"*": (0.0, 100.0)},
    "radiation_global": {"daily": (0.0, 6000.0), "monthly": (0.0, 186000.0), "annual": (0.0, 500000.0)},
    "radiation_global_intensity_mean": {"*": (-200.0, 2000.0)},
    "snow_depth_manual": {"*": (-50.0, 1500.0)},
    "snow_depth_max": {"*": (-50.0, 1500.0)},
    "sunshine_duration": {
        "hourly": (0.0, 3960.0),
        "daily": (0.0, 95040.0),
        "monthly": (0.0, 2946240.0),
        "annual": (0.0, 31622400.0),
        "10_minutes": (0.0, 600.0),
    },
    "temperature_air": {"*": (-60.0, 60.0)},
    "temperature_air_2m": {"*": (-90.0, 60.0)},
    "temperature_air_max_2m": {"*": (-90.0, 60.0)},
    "temperature_air_max_2m_last_12h": {"*": (-90.0, 60.0)},
    "temperature_air_max_2m_last_24h": {"*": (-90.0, 60.0)},
    "temperature_air_max_2m_mean": {"*": (-90.0, 60.0)},
    "temperature_air_mean_2m": {"*": (-90.0, 60.0)},
    "temperature_air_min_2m": {"*": (-90.0, 60.0)},
    "temperature_air_min_2m_last_12h": {"*": (-90.0, 60.0)},
    "temperature_air_min_2m_last_24h": {"*": (-90.0, 60.0)},
    "temperature_air_min_2m_mean": {"*": (-90.0, 60.0)},
    "temperature_dew_point": {"*": (-60.0, 60.0)},
    "temperature_dew_point_2m": {"*": (-90.0, 60.0)},
    "temperature_soil_mean_0_05m": {"*": (-90.0, 100.0)},
    "temperature_soil_mean_0_1m": {"*": (-90.0, 100.0)},
    "temperature_soil_mean_0_2m": {"*": (-90.0, 100.0)},
    "temperature_soil_mean_0_5m": {"*": (-90.0, 100.0)},
    "temperature_surface": {"*": (-60.0, 100.0)},
    "temperature_surface_mean": {"*": (-90.0, 100.0)},
    "visibility": {"*": (0.0, 200000.0)},
    "water_film_thickness": {"*": (0.0, 100.0)},
    "wind_direction": {"*": (0.0, 360.0)},
    "wind_direction_gust_max": {"*": (0.0, 360.0)},
    "wind_direction_mean": {"*": (0.0, 360.0)},
    "wind_gust_max": {"*": (0.0, 115.0)},
    "wind_gust_max_last_3h": {"*": (0.0, 115.0)},
    "wind_gust_max_last_6h": {"*": (0.0, 115.0)},
    "wind_speed": {"*": (0.0, 115.0)},
    "wind_speed_mean": {"*": (0.0, 115.0)},
    "wind_speed_mean_last_10min": {"*": (0.0, 115.0)},
    "wind_speed_min": {"*": (0.0, 115.0)},
    "wind_speed_rolling_mean_max": {"*": (0.0, 115.0)},
}
OVERRIDES: dict[str, dict[str, dict[str, Bounds]]] = {
    "dmi/observation": {
        "precipitation_amount": {"daily": (0.0, 500.0)},
    },
    "dwd/observation": {
        "pressure_air_site": {"10_minutes": (500.0, 1090.0), "hourly": (500.0, 1090.0), "subdaily": (500.0, 1090.0)},
    },
    "rmi/observation": {
        "sunshine_duration": {"hourly": (0.0, 3600.0), "daily": (0.0, 86400.0)},
        "wind_gust_max": {"hourly": (0.0, 60.0), "daily": (0.0, 60.0), "10_minutes": (0.0, 60.0)},
    },
}
SCOPE: dict[str, tuple[str, ...]] = {
    "dmi/observation": (
        "cloud_cover_total",
        "cloud_cover_total_mean",
        "count_days_cloud_cover_total_mean_gt_80pct",
        "count_days_cloud_cover_total_mean_lt_20pct",
        "count_days_frost",
        "count_days_ice",
        "count_days_precipitation_amount_ge_0_1mm",
        "count_days_precipitation_amount_ge_10mm",
        "count_days_precipitation_amount_ge_1mm",
        "count_days_snow_cover_gt_50pct",
        "count_days_summer",
        "count_days_temperature_air_min_2m_lt_minus_10c",
        "count_days_tropical_night",
        "count_days_wind_speed_rolling_mean_max_ge_10_8mps",
        "count_days_wind_speed_rolling_mean_max_ge_20_8mps",
        "count_days_wind_speed_rolling_mean_max_ge_24_5mps",
        "count_days_wind_speed_rolling_mean_max_ge_28_5mps",
        "heating_degree_day",
        "humidity_relative_max",
        "humidity_relative_mean",
        "humidity_relative_min",
        "precipitation_amount",
        "precipitation_amount_last_12h",
        "precipitation_amount_last_24h",
        "precipitation_amount_max",
        "precipitation_amount_max_30min",
        "pressure_air_sea_level_max",
        "pressure_air_sea_level_mean",
        "pressure_air_sea_level_min",
        "pressure_vapor_mean",
        "radiation_global",
        "radiation_global_intensity_mean",
        "snow_depth_manual",
        "snow_depth_max",
        "sunshine_duration",
        "temperature_air_max_2m",
        "temperature_air_max_2m_last_12h",
        "temperature_air_max_2m_mean",
        "temperature_air_mean_2m",
        "temperature_air_min_2m",
        "temperature_air_min_2m_last_12h",
        "temperature_air_min_2m_mean",
        "temperature_soil_mean_0_1m",
        "wind_direction_mean",
        "wind_gust_max",
        "wind_speed_mean",
        "wind_speed_rolling_mean_max",
    ),
    "dwd/observation": (
        "pressure_air_sea_level",
        "pressure_air_site",
        "pressure_air_site_mean",
        "wind_gust_max",
        "wind_gust_max_last_3h",
        "wind_gust_max_last_6h",
        "wind_speed_mean",
        "wind_speed_mean_last_10min",
        "wind_speed_min",
        "wind_speed_rolling_mean_max",
    ),
    "dwd/road": (
        "humidity_relative",
        "precipitation_amount",
        "precipitation_intensity",
        "temperature_air",
        "temperature_dew_point",
        "temperature_surface",
        "visibility",
        "water_film_thickness",
        "wind_direction",
        "wind_direction_gust_max",
        "wind_gust_max",
        "wind_speed",
    ),
    "meteofrance/synop": (
        "precipitation_amount_last_12h",
        "precipitation_amount_last_1h",
        "precipitation_amount_last_24h",
        "precipitation_amount_last_3h",
        "precipitation_amount_last_6h",
        "pressure_air_sea_level",
        "pressure_air_site",
        "temperature_air_2m",
        "temperature_air_max_2m_last_12h",
        "temperature_air_max_2m_last_24h",
        "temperature_air_min_2m_last_12h",
        "temperature_air_min_2m_last_24h",
        "temperature_dew_point_2m",
    ),
    "rmi/observation": (
        "humidity_relative_mean",
        "precipitation_amount",
        "pressure_air_site",
        "radiation_global_intensity_mean",
        "sunshine_duration",
        "temperature_air_max_2m",
        "temperature_air_mean_2m",
        "temperature_air_min_2m",
        "temperature_soil_mean_0_05m",
        "temperature_soil_mean_0_1m",
        "temperature_soil_mean_0_2m",
        "temperature_soil_mean_0_5m",
        "temperature_surface_mean",
        "wind_direction",
        "wind_gust_max",
        "wind_speed",
    ),
}
