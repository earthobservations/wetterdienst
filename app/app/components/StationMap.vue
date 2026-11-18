<script setup lang="ts">
import type { Cluster, Grouping } from '~/utils/map-cluster'
import type { PlacedStation, Point, ReportingRule } from '~/utils/map-tool'
import * as L from 'leaflet'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { clusterAt, clusterRadius, clusterStations, clusterText, isGroupedAt, reportingSweep, viewForCluster, worldPixels } from '~/utils/map-cluster'
import { OSM_ATTRIBUTION, OSM_TILES } from '~/utils/map-tiles'
import { clickReach, dotRadius, HOME_VIEW, SELECTED_EDGE_PX, SELECTED_RADIUS_PX } from '~/utils/map-tool'

// The map of the map tool (GH-3650), from the design of #3580. Stations are dots drawn on canvas tiles rather than
// markers: a station is no stop of the keyboard, so Tab does not walk through the thousands of the forecast's points,
// and the panel beside the map (its search, its list of the stations near the centre, and "Pick the centre of the
// map") is the way to a station for a keyboard and a screen reader. The map itself pans by the arrow keys and zooms
// by + and - and by its buttons (WCAG 2.1.1, 2.5.7). Leaflet is the one the station pickers use, and the tiles are
// theirs (utils/map-tiles.ts); like theirs it is loaded apart from the page (the page loads this component lazily).
//
// A click anywhere picks a place; the page finds the station nearest to it.
//
// At the outer zooms the stations that lie close together are one disc with their number (GH-4079, `utils/map-cluster.ts`),
// drawn on the same tiles as the dots and so no stop of the keyboard either. A click on one zooms in on its stations; the
// keyboard's way in is the map's own (the + and - keys, the buttons) and the panel. The ones that have stopped are grouped
// apart from those that report, so a group is hollow or filled like a dot is.

const props = defineProps<{
  stations: PlacedStation[]
  selected: PlacedStation | null
  /** Where a place was picked, when it is not the station itself */
  place: Point | null
  /** Which stations of the list report, where it has stopped ones to tell from them (the measuring layer): they are drawn hollow */
  reporting?: ReportingRule
  /** The name of the map, which says what it shows */
  label: string
  /** Raised for a station picked outside the map (the address, the list): the map moves to it, once */
  recentre?: number
  /** The reader's own position (GH-3651), marked as a target of its own; a press of "Use my location" raises `locate` */
  position?: Point | null
  /** Raised for each press that gave a position: the map centres on it, once */
  locate?: number
  /** How the stations are grouped at the outer zooms (GH-4079), null for none: every station is its own dot */
  grouping?: Grouping | null
  /** Whether the panel of the layers button is open: a press on the map then closes it, and its click is no pick of a place and no zoom on a group (GH-4209) */
  panelOpen?: boolean
}>()

const emit = defineEmits<{
  /**
   * A click on the map, how far from it a dot under the pointer can be (`tolerance`: the dot as drawn and a little more),
   * how far the disc of the station picked reaches (`disc`) and, for a finger, how far a station can be for a tap (`tap`;
   * none for a mouse), in kilometres
   */
  pick: [point: Point & { tolerance: number, tap: number, disc: number }]
  /** The view of the map after each move: its centre, which the panel lists the nearest stations of, and its zoom */
  view: [view: Point & { zoom: number }]
  /** A click on a group of `count` stations, `reporting` of them reporting (null where the layer has no status): the map has zoomed in on them */
  group: [count: number, reporting: number | null]
}>()

const container = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let dots: L.GridLayer | null = null
let selection: L.CircleMarker | null = null
let placeMarker: L.CircleMarker | null = null
let link: L.Polyline | null = null
let positionMarks: L.CircleMarker[] = []

/**
 * The pane of the marks of the station picked, the place and the reader's position: over the overlay pane the dots and the
 * groups are drawn in (400) and under Leaflet's markers (600), so that the disc of the station picked is seen above a group
 * its station is in (GH-4079), as above a dot
 */
const MARKS_PANE = 'station-marks'

const { t } = useI18n()
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
// a finger is a wider pointer than a mouse, and taps a wider ring
const coarsePointer = useMediaQuery('(pointer: coarse)')

// The map is a light surface in both colour schemes (main.css), so its marks are one set of colours: the station
// dots in the brand's dark blue with a halo of the map's own tone (5.7:1 against it), and the one chosen in the sun's
// yellow inside a navy edge (8.2:1), told apart from the dots by its size and its edge, not by colour alone.
const DOT = { fill: '#2358a8', halo: '#ffffff' }
const NAVY = '#17335f'
const SUN = '#ffc93c'

/** The groups of the stations at a zoom, those of every status together: made once for a zoom, until the list or the grouping changes */
let clusterCache = new Map<string, Cluster[]>()
/** Whether each station reports, asked of the rule once for the list (it reads a date), not once for each zoom */
let statusCache: Map<PlacedStation, boolean> | null = null

function clustersFor(zoom: number): Cluster[] {
  const grouping = props.grouping
  if (!grouping)
    return []
  const key = String(zoom)
  let found = clusterCache.get(key)
  if (!found) {
    const rule = props.reporting
    if (rule && !statusCache)
      statusCache = new Map(props.stations.map(station => [station, rule(station)]))
    const status = statusCache
    found = clusterStations(props.stations, zoom, grouping.radius, undefined, status ? station => status.get(station) ?? true : undefined)
    clusterCache.set(key, found)
  }
  return found
}

function forgetClusters() {
  clusterCache = new Map()
  statusCache = null
}

/**
 * A group: a disc with its number, as filled as its stations report. All of them report: a filled disc with a light number, as
 * a dot that reports is filled. None does: a hollow disc, a ring with a number in the dot's blue. A mix: the hollow disc with
 * a band round its edge, filled from the top clockwise for the share that reports (`reportingSweep`), a number in the dot's blue
 * on the light of the middle. The edges are the dots' (blue on the map's light halo), so the share is a difference of shape,
 * not of colour alone (WCAG 1.4.1, 1.4.11).
 */
function drawCluster(context: CanvasRenderingContext2D, x: number, y: number, count: number, reporting: number) {
  const radius = clusterRadius(count)
  const sweep = reportingSweep(reporting, count)
  const filled = sweep >= 2 * Math.PI
  context.beginPath()
  context.arc(x, y, radius, 0, Math.PI * 2)
  context.fillStyle = filled ? DOT.fill : DOT.halo
  context.strokeStyle = filled ? DOT.halo : DOT.fill
  context.lineWidth = filled ? 2 : 2.5
  context.fill()
  context.stroke()
  if (!filled && sweep > 0) {
    // the band is inside the edge (2.5 px), as wide as the middle can spare for its number: 2 px for a small group, 5 for a large
    const band = Math.min(5, Math.max(2, radius - 10))
    context.beginPath()
    context.arc(x, y, radius - 1.25 - band / 2, -Math.PI / 2, -Math.PI / 2 + sweep)
    context.strokeStyle = DOT.fill
    context.lineWidth = band
    context.stroke()
    // and the inner edge of the band, so that the part of it that is hollow is told from the middle
    context.beginPath()
    context.arc(x, y, radius - 1.25 - band, 0, Math.PI * 2)
    context.lineWidth = 1
    context.stroke()
  }
  context.fillStyle = filled ? DOT.halo : DOT.fill
  context.font = '700 12px system-ui, sans-serif'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillText(clusterText(count), x, y + 0.5)
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
    const r = dotRadius(coords.z)
    const origin = L.point(coords.x * size.x, coords.y * size.y)
    // at the outer zooms the stations that are close are groups: the tile has the groups, and the stations that are alone
    const grouped = isGroupedAt(props.grouping ?? null, coords.z)
    // the tile's box in degrees, a dot's width (a group's, where there are groups) wider: a cheap test before a projection
    const pad = (grouped ? clusterRadius(1e5) : r) + 2
    const northWest = owner.unproject(origin.subtract([pad, pad]), coords.z)
    const southEast = owner.unproject(origin.add(size).add([pad, pad]), coords.z)
    const inBox = (point: Point) => !(point.latitude > northWest.lat || point.latitude < southEast.lat || point.longitude < northWest.lng || point.longitude > southEast.lng)
    const groups = grouped ? clustersFor(coords.z).filter(cluster => inBox(cluster)) : []
    // the stations in this tile, the ones that have stopped first so that those that report are drawn over them
    const inTile = grouped ? [] : props.stations.filter(station => inBox(station))
    // a station that is alone keeps its own kind, as a dot
    const alone = groups.filter(group => group.station)
    const stopped = grouped
      ? alone.filter(group => group.reporting === 0).map(group => group.station!)
      : props.reporting ? inTile.filter(station => !props.reporting!(station)) : []
    const running = grouped
      ? alone.filter(group => group.reporting > 0).map(group => group.station!)
      : props.reporting ? inTile.filter(station => props.reporting!(station)) : inTile
    // a station that has stopped is a hollow dot: a ring in the dot's blue (5.7:1 against the map) round the light of the
    // map's halo, so that it differs from a dot that reports by its shape, not by its colour alone (WCAG 1.4.1, 1.4.11).
    // Its outer edge is the dot's edge (`r`), so a station that has stopped is never larger than one that reports, and at
    // the scale of a continent (r under 2) the ring is thinner, so that the light of its middle is still there
    const ring = r > 4 ? 1.75 : r > 2 ? 1.5 : 1
    context.fillStyle = DOT.halo
    context.strokeStyle = DOT.fill
    context.lineWidth = ring
    for (const station of stopped) {
      const at = owner.project([station.latitude, station.longitude], coords.z).subtract(origin)
      context.beginPath()
      context.arc(at.x, at.y, r - ring / 2, 0, Math.PI * 2)
      context.fill()
      context.stroke()
    }
    context.fillStyle = DOT.fill
    context.strokeStyle = DOT.halo
    context.lineWidth = 1
    for (const station of running) {
      const at = owner.project([station.latitude, station.longitude], coords.z).subtract(origin)
      context.beginPath()
      context.arc(at.x, at.y, r, 0, Math.PI * 2)
      context.fill()
      if (r > 2)
        context.stroke()
    }
    // the groups over the dots
    for (const group of groups) {
      if (group.count < 2)
        continue
      const at = owner.project([group.latitude, group.longitude], coords.z).subtract(origin)
      drawCluster(context, at.x, at.y, group.count, group.reporting)
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
      pane: MARKS_PANE,
    }).addTo(map)
    // the target of the reader's own position is that place: it is not drawn twice
    const atPosition = props.position && props.position.latitude === props.place.latitude && props.position.longitude === props.place.longitude
    if (!atPosition) {
      placeMarker = L.circleMarker([props.place.latitude, props.place.longitude], {
        radius: 6,
        color: NAVY,
        weight: 2.5,
        fillColor: '#ffffff',
        fillOpacity: 1,
        interactive: false,
        pane: MARKS_PANE,
      }).addTo(map)
    }
  }
  selection = L.circleMarker([station.latitude, station.longitude], {
    radius: SELECTED_RADIUS_PX,
    color: NAVY,
    weight: SELECTED_EDGE_PX,
    fillColor: SUN,
    fillOpacity: 1,
    interactive: false,
    pane: MARKS_PANE,
  }).addTo(map)
}

/** The reader's own position: a ring round a dot, in navy, which no station's mark is (the yellow disc, the white ring) */
function drawPosition() {
  if (!map)
    return
  for (const mark of positionMarks)
    mark.remove()
  positionMarks = []
  if (!props.position)
    return
  const at: L.LatLngExpression = [props.position.latitude, props.position.longitude]
  positionMarks = [
    L.circleMarker(at, { radius: 12, color: NAVY, weight: 2, fillColor: '#ffffff', fillOpacity: 0.55, interactive: false, pane: MARKS_PANE }).addTo(map),
    L.circleMarker(at, { radius: 4, color: '#ffffff', weight: 2, fillColor: NAVY, fillOpacity: 1, interactive: false, pane: MARKS_PANE }).addTo(map),
  ]
}

/** The presses of "Use my location" that the map has moved to */
let located = 0

/** Centres on the reader's position for a press that gave one, at a zoom where a station of the neighbourhood is seen */
function centreOnPosition() {
  if (!map || !props.position || (props.locate ?? 0) <= located)
    return
  located = props.locate ?? 0
  map.setView([props.position.latitude, props.position.longitude], Math.max(map.getZoom(), 9), { animate: !reducedMotion.value })
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

/** The group of stations under a point of the map, or null: where the stations are not grouped at this zoom, or the point is on the station picked */
function groupAt(latlng: L.LatLng): Cluster | null {
  if (!map)
    return null
  const zoom = map.getZoom()
  if (!isGroupedAt(props.grouping ?? null, zoom))
    return null
  // a copy of the world beside the first has longitudes beyond 180, which are the same places
  const at = latlng.wrap()
  const pixel = worldPixels(at.lat, at.lng, zoom)
  // the disc of the station picked is drawn over the groups, and a click on it is on that station
  const selected = props.selected
  if (selected) {
    const disc = worldPixels(selected.latitude, selected.longitude, zoom)
    if (Math.hypot(disc.x - pixel.x, disc.y - pixel.y) <= clickReach(zoom, false).disc)
      return null
  }
  return clusterAt(clustersFor(zoom), pixel)
}

/** A click on a group zooms in on its stations (no more than to where every station is its own dot); it is no pick of a place */
function zoomInOnGroup(latlng: L.LatLng): boolean {
  const owner = map
  const group = groupAt(latlng)
  if (!owner || !group || !props.grouping)
    return false
  // centred on the disc, not on the middle of its stations' box, which is somewhere else for a group that is lopsided (GH-4209)
  const view = viewForCluster(
    group,
    box => owner.getBoundsZoom(L.latLngBounds([box.south, box.west], [box.north, box.east]), false, L.point(48, 48)),
    owner.getZoom(),
    props.grouping.separateFrom,
    owner.getMaxZoom(),
  )
  owner.setView([view.latitude, view.longitude], view.zoom, { animate: !reducedMotion.value })
  emit('group', group.count, props.reporting ? group.reporting : null)
  return true
}

let pointerFrame = 0
/** Whether the next click of the map belongs to the press that closed the panel of the layers button */
let swallowClick = false

function emitView() {
  if (!map)
    return
  const centre = map.getCenter()
  emit('view', { latitude: centre.lat, longitude: centre.lng, zoom: map.getZoom() })
}

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
  // the credit and the buttons at the bottom right, clear of the layers button at the map's top right. Leaflet stacks the
  // controls of a bottom corner from its edge up, in the order they were added: the credit is added first, so it is at the
  // very bottom, under the zoom buttons (GH-4209)
  L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map)
  L.control.zoom({ position: 'bottomright', zoomInTitle: t('mapTool.zoomIn'), zoomOutTitle: t('mapTool.zoomOut') }).addTo(map)
  L.tileLayer(OSM_TILES, { attribution: OSM_ATTRIBUTION, maxZoom: 19, className: 'station-map-tiles' }).addTo(map)
  map.createPane(MARKS_PANE).style.zIndex = '450'
  dots = new (DotLayer as unknown as new (options: L.GridLayerOptions) => L.GridLayer)({ pane: 'overlayPane', updateWhenZooming: false, noWrap: false }).addTo(map)
  // a press on the map while the panel of the layers button is open closes the panel, and the click that belongs to that press is
  // swallowed, a click on a group's disc included. The flag is set by the press (the capture phase is before the panel's own
  // handler closes it) and taken by its click; a press that is no click (a drag) leaves it for the next press to set again
  container.value.addEventListener('pointerdown', () => {
    swallowClick = props.panelOpen ?? false
  }, true)
  map.on('click', (event) => {
    if (swallowClick) {
      swallowClick = false
      return
    }
    const owner = map!
    if (zoomInOnGroup(event.latlng))
      return
    const reach = clickReach(owner.getZoom(), coarsePointer.value)
    // pixels to kilometres at the place clicked
    const kilometres = (pixels: number) => pixels === 0 ? 0 : owner.distance(event.latlng, owner.containerPointToLatLng(owner.latLngToContainerPoint(event.latlng).add([pixels, 0]))) / 1000
    // a copy of the world beside the first (the map repeats it) has longitudes beyond 180, which are the same places
    const at = event.latlng.wrap()
    emit('pick', { latitude: at.lat, longitude: at.lng, tolerance: kilometres(reach.dot), tap: kilometres(reach.tap), disc: kilometres(reach.disc) })
  })
  map.on('moveend', emitView)
  // a pointer over a group says it can be clicked
  map.on('mousemove', (event) => {
    if (pointerFrame)
      return
    pointerFrame = requestAnimationFrame(() => {
      pointerFrame = 0
      container.value?.classList.toggle('station-map-over-group', groupAt(event.latlng) !== null)
    })
  })
  drawSelection()
  drawPosition()
  reveal()
  centreOnPosition()
  emitView()
})

// the map is laid out by the page: it grows and shrinks with the window, and a map that is not told about its size
// draws its tiles for the old one
useResizeObserver(container, () => map?.invalidateSize({ animate: false }))

onBeforeUnmount(() => {
  if (pointerFrame)
    cancelAnimationFrame(pointerFrame)
  map?.remove()
  map = null
})

watch(() => [props.stations, props.reporting, props.grouping], () => {
  forgetClusters()
  dots?.redraw()
})
watch(() => [props.selected, props.place, props.recentre, props.position], () => {
  drawSelection()
  reveal()
})
watch(() => [props.position, props.locate], () => {
  drawPosition()
  centreOnPosition()
})
</script>

<template>
  <div ref="container" class="station-map" role="application" :aria-label="label" :aria-roledescription="t('nav.map')" />
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
/* over a group of stations: a click zooms in on it */
.station-map.station-map-over-group {
  cursor: pointer;
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
