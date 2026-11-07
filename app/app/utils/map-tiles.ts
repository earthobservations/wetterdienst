/**
 * The map tiles of every map of the app: the station pickers' (MapStations.vue) and the map tool's (StationMap.vue)
 * draw OpenStreetMap's, from the one host the Content Security Policy allows and the privacy policy names
 * (`tile.openstreetmap.org`). A map that asked another host for tiles would change both.
 */
export const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

/** The credit OpenStreetMap asks for, as the map's attribution line */
export const OSM_ATTRIBUTION = '&copy; <a href=\'https://www.openstreetmap.org/copyright\'>OpenStreetMap</a> contributors'
