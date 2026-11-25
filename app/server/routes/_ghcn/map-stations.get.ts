// The stations of NOAA GHCN daily for the map (GH-4267), as columns, kept for a day: see `~/server/utils/ghcnStations`. The list is the
// process's one (`sharedGhcnMapList`), which the search of the header reads as well (`/_search/stations`, GH-3790).
export default ghcnMapStationsHandler({ list: sharedGhcnMapList })
