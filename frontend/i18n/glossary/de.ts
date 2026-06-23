/**
 * Friendly German labels for backend identifiers.
 *
 * Keys are the humanized snake_case names the REST API returns (parameter
 * `name`, resolution and dataset ids). This is a curated set covering the most
 * common DWD observation values; anything not listed falls back to a prettified
 * version of the raw id (see `useParameterLabel`). Keep entries neutral and
 * plain so non-experts understand them.
 */

export const parameters: Record<string, string> = {
  // Temperature
  temperature_air_mean_2m: 'Lufttemperatur (2 m)',
  temperature_air_mean_0_05m: 'Lufttemperatur (5 cm)',
  temperature_air_max_2m: 'Höchsttemperatur (2 m)',
  temperature_air_max_0_05m: 'Höchsttemperatur (5 cm)',
  temperature_air_min_2m: 'Tiefsttemperatur (2 m)',
  temperature_air_min_0_05m: 'Tiefsttemperatur am Boden (5 cm)',
  temperature_dew_point_mean_2m: 'Taupunkt (2 m)',
  temperature_wet_mean_2m: 'Feuchttemperatur (2 m)',
  temperature_soil_mean_0_05m: 'Bodentemperatur (5 cm)',
  temperature_soil_mean_0_1m: 'Bodentemperatur (10 cm)',
  temperature_soil_mean_0_2m: 'Bodentemperatur (20 cm)',
  temperature_soil_mean_0_5m: 'Bodentemperatur (50 cm)',
  temperature_soil_mean_1m: 'Bodentemperatur (1 m)',

  // Humidity & moisture
  humidity: 'Relative Luftfeuchte',
  humidity_absolute: 'Absolute Luftfeuchte',
  pressure_vapor: 'Dampfdruck',

  // Air pressure
  pressure_air_site: 'Luftdruck (Station)',
  pressure_air_sea_level: 'Luftdruck (Meereshöhe)',

  // Wind
  wind_speed: 'Windgeschwindigkeit',
  wind_direction: 'Windrichtung',
  wind_gust_max: 'Maximale Windböe',
  wind_gust_max_last_3h: 'Maximale Windböe (3 h)',
  wind_gust_max_last_6h: 'Maximale Windböe (6 h)',
  wind_force_beaufort: 'Windstärke (Beaufort)',

  // Precipitation
  precipitation_height: 'Niederschlagsmenge',
  precipitation_height_max: 'Maximale Niederschlagsmenge',
  precipitation_form: 'Niederschlagsart',
  precipitation_duration: 'Niederschlagsdauer',
  precipitation_index: 'Niederschlag (ja/nein)',

  // Sunshine & radiation
  sunshine_duration: 'Sonnenscheindauer',
  radiation_global: 'Globalstrahlung',
  radiation_sky_short_wave_diffuse: 'Diffuse Himmelsstrahlung',
  radiation_sky_long_wave: 'Langwellige Strahlung',

  // Snow
  snow_depth: 'Schneehöhe',
  snow_depth_new: 'Neuschneehöhe',
  water_equivalent_snow_depth: 'Wasseräquivalent der Schneedecke',

  // Clouds & visibility
  cloud_cover_total: 'Gesamtbedeckung',
  cloud_cover_total_index: 'Bedeckungsgrad',
  cloud_height: 'Wolkenuntergrenze',
  visibility_range: 'Sichtweite',

  // Other
  weather: 'Wetter',
  quality: 'Qualität',
}

export const resolutions: Record<string, string> = {
  '1_minute': 'Jede Minute',
  '5_minutes': 'Alle 5 Minuten',
  '10_minutes': 'Alle 10 Minuten',
  '15_minutes': 'Alle 15 Minuten',
  'hourly': 'Stündlich',
  '6_hour': 'Alle 6 Stunden',
  'subdaily': 'Mehrmals täglich',
  'daily': 'Täglich',
  'monthly': 'Monatlich',
  'annual': 'Jährlich',
}

export const datasets: Record<string, string> = {
  // DWD Beobachtung
  climate_summary: 'Klima-Übersicht',
  precipitation: 'Niederschlag',
  precipitation_more: 'Niederschlag (erweitert)',
  temperature_air: 'Lufttemperatur',
  temperature_soil: 'Bodentemperatur',
  temperature_extreme: 'Temperatur-Extremwerte',
  wind: 'Wind',
  wind_extreme: 'Windspitzen',
  wind_synoptic: 'Wind (synoptisch)',
  sun: 'Sonnenschein',
  solar: 'Solarstrahlung',
  cloudiness: 'Bewölkung',
  cloud_type: 'Wolkenart',
  pressure: 'Luftdruck',
  visibility: 'Sichtweite',
  moisture: 'Feuchte',
  dew_point: 'Taupunkt',
  weather_phenomena: 'Wetterereignisse',
  weather_phenomena_more: 'Wetterereignisse (erweitert)',
  water_equivalent: 'Wasseräquivalent der Schneedecke',
  // DWD Beobachtung – Stadtklima
  urban_precipitation: 'Stadtklima: Niederschlag',
  urban_pressure: 'Stadtklima: Luftdruck',
  urban_sun: 'Stadtklima: Sonnenschein',
  urban_temperature_air: 'Stadtklima: Lufttemperatur',
  urban_temperature_soil: 'Stadtklima: Bodentemperatur',
  urban_wind: 'Stadtklima: Wind',
  // DWD MOSMIX
  small: 'MOSMIX-S',
  large: 'MOSMIX-L',
  // DWD DMO (numerische Wettervorhersage)
  icon: 'ICON (global)',
  icon_eu: 'ICON-EU',
  // DWD Abgeleitete Produkte
  radiation_global: 'Globalstrahlung',
  sunshine_duration: 'Sonnenscheindauer',
  soil: 'Boden',
  heating_degreedays: 'Heizgradtage',
  cooling_degreehours_13: 'Kühlgradstunden (13 °C)',
  cooling_degreehours_16: 'Kühlgradstunden (16 °C)',
  cooling_degreehours_18: 'Kühlgradstunden (18 °C)',
  climate_correction_factor: 'Klimakorrekturfaktor',
  // IMGW (Polen)
  hydrology: 'Hydrologie',
  climate: 'Klima',
  synop: 'SYNOP',
  // Generisch (NOAA, Geosphere, ECCC, …)
  data: 'Beobachtungen',
}
