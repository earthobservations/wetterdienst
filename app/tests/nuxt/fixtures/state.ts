// The keys of `useState` that a test sets, for `clearNuxtState(keys)`. An unkeyed `clearNuxtState()` clears every key of the
// app, the i18n module's (the language) among them, so what the next test sees then depends on the order the tests ran in
// (GH-4042). A test clears what it set and nothing else.

/** The position of "Use my location" and what it drives (`useMyLocation`), and the place it drops (`usePlace`) */
export const LOCATION_STATE = [
  'wd-location-position',
  'wd-location-failure',
  'wd-location-busy',
  'wd-location-remember',
  'wd-location-not-kept',
  'wd-location-not-kept-count',
  'wd-location-withdrawn',
  'wd-location-checking',
  'wd-location-loaded',
  'place',
]

/** The limits the REST API holds a request to (`useServerLimits`) */
export const SERVER_LIMITS_STATE = ['server-limits', 'server-limits-asked']

/** What the Explorer reads from the backend once per app load: its limits and its settings (`useServerSettings`) */
export const EXPLORER_STATE = [...SERVER_LIMITS_STATE, 'server-settings']
