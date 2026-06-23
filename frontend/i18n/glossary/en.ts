/**
 * Friendly English labels for backend identifiers.
 *
 * Keys are the humanized snake_case names the REST API returns (parameter
 * `name`, resolution and dataset ids). This is a curated set covering the most
 * common DWD observation values; anything not listed falls back to a prettified
 * version of the raw id (see `useParameterLabel`). Keep entries plain so
 * non-experts understand them. Mirrors the keys in `de.ts`.
 */

export const parameters: Record<string, string> = {
  // Temperature
  temperature_air_mean_2m: 'Air temperature (2 m)',
  temperature_air_mean_0_05m: 'Air temperature (5 cm)',
  temperature_air_max_2m: 'Maximum temperature (2 m)',
  temperature_air_max_0_05m: 'Maximum temperature (5 cm)',
  temperature_air_min_2m: 'Minimum temperature (2 m)',
  temperature_air_min_0_05m: 'Minimum temperature near ground (5 cm)',
  temperature_dew_point_mean_2m: 'Dew point (2 m)',
  temperature_wet_mean_2m: 'Wet-bulb temperature (2 m)',
  temperature_soil_mean_0_05m: 'Soil temperature (5 cm)',
  temperature_soil_mean_0_1m: 'Soil temperature (10 cm)',
  temperature_soil_mean_0_2m: 'Soil temperature (20 cm)',
  temperature_soil_mean_0_5m: 'Soil temperature (50 cm)',
  temperature_soil_mean_1m: 'Soil temperature (1 m)',

  // Humidity & moisture
  humidity: 'Relative humidity',
  humidity_absolute: 'Absolute humidity',
  pressure_vapor: 'Vapour pressure',

  // Air pressure
  pressure_air_site: 'Air pressure (station)',
  pressure_air_sea_level: 'Air pressure (sea level)',

  // Wind
  wind_speed: 'Wind speed',
  wind_direction: 'Wind direction',
  wind_gust_max: 'Maximum wind gust',
  wind_gust_max_last_3h: 'Maximum wind gust (3 h)',
  wind_gust_max_last_6h: 'Maximum wind gust (6 h)',
  wind_force_beaufort: 'Wind force (Beaufort)',

  // Precipitation
  precipitation_height: 'Precipitation amount',
  precipitation_height_max: 'Maximum precipitation amount',
  precipitation_form: 'Precipitation form',
  precipitation_duration: 'Precipitation duration',
  precipitation_index: 'Precipitation (yes/no)',

  // Sunshine & radiation
  sunshine_duration: 'Sunshine duration',
  radiation_global: 'Global radiation',
  radiation_sky_short_wave_diffuse: 'Diffuse sky radiation',
  radiation_sky_long_wave: 'Long-wave radiation',

  // Snow
  snow_depth: 'Snow depth',
  snow_depth_new: 'Fresh snow depth',
  water_equivalent_snow_depth: 'Snow water equivalent',

  // Clouds & visibility
  cloud_cover_total: 'Total cloud cover',
  cloud_cover_total_index: 'Cloud cover',
  cloud_height: 'Cloud base height',
  visibility_range: 'Visibility',

  // Other
  weather: 'Weather',
  quality: 'Quality',
}

export const resolutions: Record<string, string> = {
  '1_minute': 'Every minute',
  '5_minutes': 'Every 5 minutes',
  '10_minutes': 'Every 10 minutes',
  '15_minutes': 'Every 15 minutes',
  'hourly': 'Hourly',
  '6_hour': 'Every 6 hours',
  'subdaily': 'Several times a day',
  'daily': 'Daily',
  'monthly': 'Monthly',
  'annual': 'Annual',
}

export const datasets: Record<string, string> = {
  // DWD observation
  climate_summary: 'Climate summary',
  precipitation: 'Precipitation',
  precipitation_more: 'Precipitation (extended)',
  temperature_air: 'Air temperature',
  temperature_soil: 'Soil temperature',
  temperature_extreme: 'Temperature extremes',
  wind: 'Wind',
  wind_extreme: 'Wind gusts',
  wind_synoptic: 'Wind (synoptic)',
  sun: 'Sunshine',
  solar: 'Solar radiation',
  cloudiness: 'Cloudiness',
  cloud_type: 'Cloud type',
  pressure: 'Air pressure',
  visibility: 'Visibility',
  moisture: 'Moisture',
  dew_point: 'Dew point',
  weather_phenomena: 'Weather phenomena',
  weather_phenomena_more: 'Weather phenomena (extended)',
  water_equivalent: 'Snow water equivalent',
  // DWD observation – urban climate
  urban_precipitation: 'Urban precipitation',
  urban_pressure: 'Urban air pressure',
  urban_sun: 'Urban sunshine',
  urban_temperature_air: 'Urban air temperature',
  urban_temperature_soil: 'Urban soil temperature',
  urban_wind: 'Urban wind',
  // DWD MOSMIX
  small: 'MOSMIX-S',
  large: 'MOSMIX-L',
  // DWD DMO (numerical weather prediction)
  icon: 'ICON (global)',
  icon_eu: 'ICON-EU',
  // DWD derived
  radiation_global: 'Global radiation',
  sunshine_duration: 'Sunshine duration',
  soil: 'Soil',
  heating_degreedays: 'Heating degree days',
  cooling_degreehours_13: 'Cooling degree hours (13 °C)',
  cooling_degreehours_16: 'Cooling degree hours (16 °C)',
  cooling_degreehours_18: 'Cooling degree hours (18 °C)',
  climate_correction_factor: 'Climate correction factor',
  // IMGW (Poland)
  hydrology: 'Hydrology',
  climate: 'Climate',
  synop: 'SYNOP',
  // Generic (NOAA, Geosphere, ECCC, …)
  data: 'Observations',
}
