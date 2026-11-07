<script setup lang="ts">
import type { PlacedStation, Point } from '~/utils/map-tool'
import * as L from 'leaflet'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { OSM_ATTRIBUTION, OSM_TILES } from '~/utils/map-tiles'
import { HOME_VIEW } from '~/utils/map-tool'

// The map of the map tool (GH-3650), from the design of #3580. Stations are dots drawn on canvas tiles rather than
// markers: a station is no stop of the keyboard, so Tab does not walk through the thousands of the forecast's points,
// and the panel beside the map (its search, its list of the stations near the centre, and "Pick the centre of the
// map") is the way to a station for a keyboard and a screen reader. The map itself pans by the arrow keys and zooms
// by + and - and by its buttons (WCAG 2.1.1, 2.5.7). Leaflet is the one the station pickers use, and the tiles are
// theirs (utils/map-tiles.ts); like theirs it is loaded apart from the page (the page loads this component lazily).
//
// A click anywhere picks a place; the page finds the station nearest to it.

const props = defineProps<{
  stations: PlacedStation[]
  selected: PlacedStation | null
  /** Where a place was picked, when it is not the station itself */
  place: Point | null
  /** The name of the map, which says what it shows */
  label: string
  /** Raised for a station picked outside the map (the address, the list): the map moves to it, once */
  recentre?: number
}>()

const emit = defineEmits<{
  /** A click on the map, and how far from it a dot under the pointer can be (twelve pixels), in kilometres */
  pick: [point: Point & { tolerance: number }]
  /** The view of the map after each move: its centre, which the panel lists the nearest stations of, and its zoom */
  view: [view: Point & { zoom: number }]
}>()

const container = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let dots: L.GridLayer | null = null
let selection: L.CircleMarker | null = null
let placeMarker: L.CircleMarker | null = null
let link: L.Polyline | null = null

const { t } = useI18n()
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// The map is a light surface in both colour schemes (main.css), so its marks are one set of colours: the station
// dots in the brand's dark blue with a halo of the map's own tone (5.7:1 against it), and the one chosen in the sun's
// yellow inside a navy edge (8.2:1), told apart from the dots by its size and its edge, not by colour alone.
const DOT = { fill: '#2358a8', halo: '#ffffff' }
const NAVY = '#17335f'
const SUN = '#ffc93c'

/** The radius of a dot, by zoom: points at the scale of a continent, discs at the scale of a town */
function radius(zoom: number) {
  return zoom < 5 ? 1.75 : zoom < 7 ? 2.75 : zoom < 9 ? 3.75 : 5
}

const DotLayer = L.GridLayer.extend({
  createTile(this: L.GridLayer, coords: L.Coords) {
    const tile = document.createElement('canvas')
    const size = this.getTileSize()
    const ratio = window.devicePixelRatio || 1
    tile.width = size.x * ratio
    tile.height = size.y * ratio
    tile.style.width = `${size.x}px`
    tile.style.height = `${size.y}px`
    const context = tile.getContext('2d')
    const owner = (this as unknown as { _map: L.Map })._map
    if (!context || !owner)
      return tile
    context.scale(ratio, ratio)
    const r = radius(coords.z)
    const origin = L.point(coords.x * size.x, coords.y * size.y)
    // the tile's box in degrees, a dot's width wider: a cheap test before a projection
    const pad = r + 2
    const northWest = owner.unproject(origin.subtract([pad, pad]), coords.z)
    const southEast = owner.unproject(origin.add(size).add([pad, pad]), coords.z)
    context.fillStyle = DOT.fill
    context.strokeStyle = DOT.halo
    context.lineWidth = 1
    for (const station of props.stations) {
      if (station.latitude > northWest.lat || station.latitude < southEast.lat || station.longitude < northWest.lng || station.longitude > southEast.lng)
        continue
      const at = owner.project([station.latitude, station.longitude], coords.z).subtract(origin)
      context.beginPath()
      context.arc(at.x, at.y, r, 0, Math.PI * 2)
      context.fill()
      if (r > 2)
        context.stroke()
    }
    return tile
  },
})

function drawSelection() {
  if (!map)
    return
  selection?.remove()
  placeMarker?.remove()
  link?.remove()
  selection = placeMarker = link = null
  const station = props.selected
  if (!station)
    return
  if (props.place) {
    link = L.polyline([[props.place.latitude, props.place.longitude], [station.latitude, station.longitude]], {
      color: NAVY,
      weight: 2,
      dashArray: '4 5',
      interactive: false,
    }).addTo(map)
    placeMarker = L.circleMarker([props.place.latitude, props.place.longitude], {
      radius: 6,
      color: NAVY,
      weight: 2.5,
      fillColor: '#ffffff',
      fillOpacity: 1,
      interactive: false,
    }).addTo(map)
  }
  selection = L.circleMarker([station.latitude, station.longitude], {
    radius: 9,
    color: NAVY,
    weight: 3,
    fillColor: SUN,
    fillOpacity: 1,
    interactive: false,
  }).addTo(map)
}

/** The picks from outside the map that it has moved to */
let recentred = 0

/** Brings the selection into view where it is not, without moving a map that already shows it; centres on a pick from outside */
function reveal() {
  if (!map || !props.selected)
    return
  const target = L.latLng(props.selected.latitude, props.selected.longitude)
  if ((props.recentre ?? 0) > recentred) {
    recentred = props.recentre ?? 0
    map.setView(target, Math.max(map.getZoom(), 8), { animate: !reducedMotion.value })
    return
  }
  if (map.getBounds().pad(-0.1).contains(target))
    return
  map.setView(target, Math.max(map.getZoom(), 7), { animate: !reducedMotion.value })
}

function emitView() {
  if (!map)
    return
  const centre = map.getCenter()
  emit('view', { latitude: centre.lat, longitude: centre.lng, zoom: map.getZoom() })
}

/** The centre of the view, which the panel's "Pick the centre of the map" picks as a place */
function centre(): Point | null {
  const point = map?.getCenter()
  return point ? { latitude: point.lat, longitude: point.lng } : null
}

defineExpose({ centre })

onMounted(() => {
  if (!container.value)
    return
  map = L.map(container.value, {
    center: [HOME_VIEW.latitude, HOME_VIEW.longitude],
    zoom: HOME_VIEW.zoom,
    minZoom: 2,
    maxZoom: 16,
    zoomControl: false,
    attributionControl: false,
    worldCopyJump: true,
    zoomAnimation: !reducedMotion.value,
    fadeAnimation: !reducedMotion.value,
    markerZoomAnimation: !reducedMotion.value,
  })
  // the buttons at the bottom right, clear of the chips over the map's top, in the language of the page
  L.control.zoom({ position: 'bottomright', zoomInTitle: t('mapTool.zoomIn'), zoomOutTitle: t('mapTool.zoomOut') }).addTo(map)
  L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map)
  L.tileLayer(OSM_TILES, { attribution: OSM_ATTRIBUTION, maxZoom: 19, className: 'station-map-tiles' }).addTo(map)
  dots = new (DotLayer as unknown as new (options: L.GridLayerOptions) => L.GridLayer)({ pane: 'overlayPane', updateWhenZooming: false, noWrap: false }).addTo(map)
  map.on('click', (event) => {
    const owner = map!
    const beside = owner.containerPointToLatLng(owner.latLngToContainerPoint(event.latlng).add([12, 0]))
    emit('pick', { latitude: event.latlng.lat, longitude: event.latlng.lng, tolerance: owner.distance(event.latlng, beside) / 1000 })
  })
  map.on('moveend', emitView)
  drawSelection()
  reveal()
  emitView()
})

// the map is laid out by the page: it grows and shrinks with the window, and a map that is not told about its size
// draws its tiles for the old one
useResizeObserver(container, () => map?.invalidateSize({ animate: false }))

onBeforeUnmount(() => {
  map?.remove()
  map = null
})

watch(() => props.stations, () => dots?.redraw())
watch(() => [props.selected, props.place, props.recentre], () => {
  drawSelection()
  reveal()
})
</script>

<template>
  <div ref="container" class="station-map" role="application" :aria-label="label" aria-roledescription="map" />
</template>

<style>
.station-map {
  width: 100%;
  height: 100%;
  min-height: 18rem;
  /* the tone the tiles are seen through, which is also what the focus ring is measured against */
  background: #e8ecf2;
  border-radius: calc(var(--ui-radius) * 2);
  font: inherit;
}
/* Calm tiles: OpenStreetMap's colours, faded, so that the stations are what the eye finds */
.station-map .station-map-tiles {
  filter: saturate(0.35) brightness(1.03) contrast(0.92);
}
@media (forced-colors: active) {
  .station-map .station-map-tiles {
    filter: grayscale(1) contrast(0.8);
  }
}

/* The zoom buttons and the attribution, in the app's colours and sizes (24 px and more: WCAG 2.5.8) */
.station-map .leaflet-bar {
  border: 1px solid #828da1;
  border-radius: calc(var(--ui-radius) * 1.5);
  overflow: hidden;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.12);
}
.station-map .leaflet-bar a {
  width: 2.5rem;
  height: 2.5rem;
  line-height: 2.5rem;
  background: #ffffff;
  color: var(--color-ink-950);
  border-bottom-color: var(--color-ink-200);
  font-size: 1.25rem;
}
.station-map .leaflet-bar a:hover {
  background: var(--color-ink-100);
}
.station-map .leaflet-control-attribution {
  padding: 0.125rem 0.5rem;
  background: rgb(255 255 255 / 0.92);
  color: var(--color-ink-600);
  font-size: 0.75rem;
  border-top-left-radius: var(--ui-radius);
}
.station-map .leaflet-control-attribution a {
  color: var(--color-ink-700);
  text-decoration: underline;
}
@media (prefers-reduced-motion: reduce) {
  .station-map .leaflet-tile {
    transition: none;
  }
}
</style>
