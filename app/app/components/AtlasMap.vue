<script setup lang="ts">
import type { PlacedStation } from '~/utils/atlas'
import * as L from 'leaflet'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

// The map of the home page (GH-3518). Stations are dots drawn on canvas tiles rather than markers: a
// hundred thousand of them (NOAA GHCN) draw at once, and none is a stop of the keyboard. Choosing a
// station by keyboard or screen reader is the list and the search beside the map, and choosing a place
// is the "centre of the map" button; the map itself pans by the arrow keys and zooms by + and - and its
// buttons (WCAG 2.1.1, 2.5.7).
//
// A click anywhere picks a place; the page finds the station nearest to it.

const props = defineProps<{
  stations: PlacedStation[]
  selected: PlacedStation | null
  /** Where a place was picked, when it is not the station itself */
  place: { latitude: number, longitude: number } | null
  /** The name of the map, which says what it shows */
  label: string
}>()

const emit = defineEmits<{
  /** A click on the map, and how far from it a dot under the pointer can be: twelve pixels, in kilometres */
  pick: [point: { latitude: number, longitude: number, tolerance: number }]
  view: [view: { latitude: number, longitude: number, zoom: number }]
}>()

const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

const container = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let dots: L.GridLayer | null = null
let selection: L.CircleMarker | null = null
let placeMarker: L.CircleMarker | null = null
let link: L.Polyline | null = null

const { t } = useI18n()
const colorMode = useColorMode()
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

/** The dot's colours: the brand's dark blue on the light map, its light blue on the dark one, each with a halo of the map's own tone */
function palette() {
  return colorMode.value === 'dark'
    ? { fill: '#a9c6f1', halo: '#0b1222' }
    : { fill: '#2459b0', halo: '#ffffff' }
}

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
    const { fill, halo } = palette()
    context.fillStyle = fill
    context.strokeStyle = halo
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
      color: '#17335f',
      weight: 2,
      dashArray: '4 5',
      interactive: false,
      className: 'atlas-link',
    }).addTo(map)
    placeMarker = L.circleMarker([props.place.latitude, props.place.longitude], {
      radius: 6,
      color: '#17335f',
      weight: 2.5,
      fillColor: '#ffffff',
      fillOpacity: 1,
      interactive: false,
    }).addTo(map)
  }
  // the logo's yellow with its navy edge: told apart from the other dots by its size and edge, not by colour alone
  selection = L.circleMarker([station.latitude, station.longitude], {
    radius: 9,
    color: '#17335f',
    weight: 3,
    fillColor: '#ffc93c',
    fillOpacity: 1,
    interactive: false,
    className: 'atlas-selected',
  }).addTo(map)
}

/** Brings the selection into view where it is not, without moving a map that already shows it */
function reveal() {
  if (!map || !props.selected)
    return
  const target = L.latLng(props.selected.latitude, props.selected.longitude)
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

/** The centre of the view, which the page's "centre of the map" button picks as a place */
function centre() {
  const point = map?.getCenter()
  return point ? { latitude: point.lat, longitude: point.lng } : null
}

defineExpose({ centre })

onMounted(() => {
  if (!container.value)
    return
  map = L.map(container.value, {
    center: [51.2, 10.4],
    zoom: 6,
    minZoom: 2,
    maxZoom: 16,
    zoomControl: false,
    attributionControl: false,
    worldCopyJump: true,
    zoomAnimation: !reducedMotion.value,
    fadeAnimation: !reducedMotion.value,
    markerZoomAnimation: !reducedMotion.value,
  })
  // the controls at the bottom right, clear of the panel at the left and the filters at the top
  L.control.zoom({
    position: 'bottomright',
    zoomInTitle: t('atlas.zoomIn'),
    zoomOutTitle: t('atlas.zoomOut'),
  }).addTo(map)
  L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map)
  L.tileLayer(OSM_TILES, { attribution: OSM_ATTRIBUTION, maxZoom: 19, className: 'atlas-tiles' }).addTo(map)
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

onBeforeUnmount(() => {
  map?.remove()
  map = null
})

watch(() => props.stations, () => dots?.redraw())
watch(() => colorMode.value, () => dots?.redraw())
watch(() => [props.selected, props.place], () => {
  drawSelection()
  reveal()
})
</script>

<template>
  <div ref="container" class="atlas-map" role="application" :aria-label="label" aria-roledescription="map" />
</template>

<style>
.atlas-map {
  width: 100%;
  height: 100%;
  /* the tone the tiles are seen through, which is also what the focus ring is measured against */
  background: #e8ecf2;
  font: inherit;
}
.dark .atlas-map {
  background: #1a2233;
}
/* Calm tiles: OpenStreetMap's colours, faded, so that the stations are what the eye finds. In dark mode the
   same tiles, inverted and turned back to their hues. */
.atlas-map .atlas-tiles {
  filter: saturate(0.35) brightness(1.03) contrast(0.92);
}
.dark .atlas-map .atlas-tiles {
  filter: invert(1) hue-rotate(180deg) saturate(0.3) brightness(0.85) contrast(0.9);
}
@media (forced-colors: active) {
  .atlas-map .atlas-tiles {
    filter: grayscale(1) contrast(0.8);
  }
}

/* The focus ring of the map is drawn inside its edge, which is the edge of the window on a phone */
.atlas-map.leaflet-container:focus-visible {
  outline: 3px solid var(--ui-color-primary-800);
  outline-offset: -3px;
}
.dark .atlas-map.leaflet-container:focus-visible {
  outline-color: var(--color-sun);
}

/* The zoom buttons and the attribution, in the app's colours and sizes (24 px and more: WCAG 2.5.8) */
.atlas-map .leaflet-bar {
  border: 1px solid var(--ui-border-accented);
  border-radius: calc(var(--ui-radius) * 1.5);
  overflow: hidden;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.12);
}
.atlas-map .leaflet-bar a {
  width: 2.5rem;
  height: 2.5rem;
  line-height: 2.5rem;
  background: var(--ui-bg);
  color: var(--ui-text-highlighted);
  border-bottom-color: var(--ui-border);
  font-size: 1.25rem;
}
.atlas-map .leaflet-bar a:hover {
  background: var(--ui-bg-elevated);
}
.atlas-map .leaflet-bar a:focus-visible {
  outline-offset: -3px;
}
.atlas-map .leaflet-control-attribution {
  padding: 0.125rem 0.5rem;
  background: color-mix(in oklab, var(--ui-bg) 92%, transparent);
  color: var(--ui-text-muted);
  font-size: 0.75rem;
  border-top-left-radius: var(--ui-radius);
}
.atlas-map .leaflet-control-attribution a {
  color: var(--ui-text-toned);
  text-decoration: underline;
}
.atlas-map .leaflet-control-attribution a:focus-visible {
  outline-offset: -2px;
}
/* on a phone the sheet's rounded edge lies over the foot of the map: the controls stand clear of it */
@media (max-width: 1023.98px) {
  .atlas-map .leaflet-bottom {
    bottom: 1.25rem;
  }
}
@media (prefers-reduced-motion: reduce) {
  .atlas-map .leaflet-tile {
    transition: none;
  }
}
</style>
