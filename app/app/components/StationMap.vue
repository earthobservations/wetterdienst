<script setup lang="ts">
import type { Cluster, Grouping } from '~/utils/map-cluster'
import type { PlacedStation, Point, ReportingRule } from '~/utils/map-tool'
import type { StormCell } from '~/utils/storm-cells'
import * as L from 'leaflet'
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { clusterAt, clusterRadius, clusterStations, clusterText, isGroupedAt, reportingSweep, viewForCluster, worldPixels } from '~/utils/map-cluster'
import { OSM_ATTRIBUTION, OSM_TILES } from '~/utils/map-tiles'
import { clickReach, dotRadius, HOME_VIEW, SELECTED_EDGE_PX, SELECTED_RADIUS_PX } from '~/utils/map-tool'
import { creditHtml } from '~/utils/provider-credit'
import { drawable, hasMotion, MARK_SIZE, markSvg, styleOf } from '~/utils/storm-cells'

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
//
// The Radar tool (GH-3788) is the same map without stations: a picture laid over the tiles (`overlay`, a frame of DWD's precipitation
// radar, stretched over its bounds), the thunderstorm cells of DWD's KONRAD3D over it (GH-4208: the outline of each cell, every
// surface of it, in the colour and the edge of its severity, and at its centre a mark with the severity's number and, where it has a
// motion, a dashed arrow in the calculated direction, `utils/storm-cells.ts`), the credit of both in the map's attribution, and a view
// it opens on (`openOn`). The picture and the cells are no stop of the keyboard and take no click: the text of the radar is the page's
// legend and its player, and the text of the cells is their list.

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
  /** What the mark of the position is called for a screen reader (the Radar tool); none where the page names it itself */
  positionLabel?: string
  /** Raised for each press that gave a position: the map centres on it, once */
  locate?: number
  /** How the stations are grouped at the outer zooms (GH-4079), null for none: every station is its own dot */
  grouping?: Grouping | null
  /** Whether the map stays where it is for the station picked, though it is off the screen (a pick carried to another layer from a place the reader has moved away from, GH-4078) */
  hold?: boolean
  /** Whether the panel of the layers button is open: a press on the map then closes it, and its click is no pick of a place and no zoom on a group (GH-4209) */
  panelOpen?: boolean
  /** The element that says what the dots and the discs of the map are (the legend, which is in the layers panel, as a text): the map's description */
  describedBy?: string
  /** Whether the map's stage is full screen (GH-4227): the button with the zoom buttons says so, and its label is the one for leaving */
  fullscreen?: boolean
  /** No full-screen button with the zoom buttons: the Radar tool's player is beside the map, not in it */
  noFullscreen?: boolean
  /** A picture over the tiles (GH-3788): where it lies (`[[south, west], [north, east]]`, Leaflet's default CRS, which the radar's images are in) and how opaque it is; swapped when `url` changes, once the new one has been decoded, so that the loop does not flicker */
  overlay?: { url: string, bounds: [[number, number], [number, number]], opacity?: number } | null
  /** The part of the world the map opens on, instead of the home view of the stations: the box of the radar's images */
  openOn?: [[number, number], [number, number]]
  /** The thunderstorm cells to draw over the picture (GH-4208); undefined where they are off */
  cells?: StormCell[]
  /** The cells are not for the frame on the picture (an older one, or one of the forecast): they fade out, and are drawn again when it is */
  cellsFaded?: boolean
  /** The credit of the layers drawn over the tiles (the radar's, the cells'): each a line of the map's attribution, the licence a link to its terms */
  credits?: Array<{ text: string, license: { label: string, url: string } | null }>
  /** A press on a cell of the list: the map centres on it, once for each press (`count`), as a click on a group does */
  centreOn?: { count: number, latitude: number, longitude: number, bounds: { south: number, west: number, north: number, east: number } } | null
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
  /** The button of the full screen was pressed (GH-4227): the page enters or leaves it, the map keeps its view */
  fullscreen: []
}>()

const container = ref<HTMLDivElement | null>(null)
/** The place of the full-screen button, the first of the bar of the zoom buttons: the button is the component's own, teleported into it (GH-4227) */
const fullscreenHost = shallowRef<HTMLElement | null>(null)
let map: L.Map | null = null
let dots: L.GridLayer | null = null
let selection: L.CircleMarker | null = null
let placeMarker: L.CircleMarker | null = null
let link: L.Polyline | null = null
let positionMarks: L.CircleMarker[] = []
let overlayLayer: L.ImageOverlay | null = null
/** The picture `overlayLayer` shows now (its `url` is set only once the next one is ready) */
let overlayShown: string | null = null
let cellLayer: L.LayerGroup | null = null
let attribution: L.Control.Attribution | null = null
/** The credit lines of the layers now in the map's attribution, to be taken out again */
let creditsShown: string[] = []

/**
 * The pane of the marks of the station picked, the place and the reader's position: over the overlay pane the dots and the
 * groups are drawn in (400) and under Leaflet's markers (600), so that the disc of the station picked is seen above a group
 * its station is in (GH-4079), as above a dot
 */
const MARKS_PANE = 'station-marks'
/** The panes of the radar's picture, under the dots (400), the cells' outlines over the dots (420) and their marks over the outlines (430), all under the marks of the station picked (450) */
const RADAR_PANE = 'radar'
const CELLS_PANE = 'storm-cells'
const CELL_MARKS_PANE = 'storm-cell-marks'
/** The zoom a press on a cell of the list goes no farther than */
const CELL_ZOOM_LIMIT = 10

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

/**
 * The radar's picture over the tiles: one image overlay, laid over the bounds the answer gives, no stop of the keyboard and no click. A new
 * frame is decoded off the page first and set when it is ready, so the loop does not blink to nothing between two frames; a frame that is
 * not the latest asked for by the time it is ready is dropped.
 */
async function drawOverlay() {
  if (!map)
    return
  const spec = props.overlay
  if (!spec) {
    overlayLayer?.remove()
    overlayLayer = null
    overlayShown = null
    return
  }
  const bounds = L.latLngBounds(spec.bounds)
  if (!overlayLayer) {
    overlayLayer = L.imageOverlay(spec.url, bounds, { opacity: spec.opacity ?? 0.75, pane: RADAR_PANE, interactive: false, alt: '', className: 'station-map-radar' }).addTo(map)
    overlayShown = spec.url
    return
  }
  overlayLayer.setBounds(bounds)
  overlayLayer.setOpacity(spec.opacity ?? 0.75)
  if (spec.url === overlayShown)
    return
  const wanted = spec.url
  // the image is in the browser's cache (the page loaded it), so decoding it is quick; a browser without `decode` swaps at once
  const image = new Image()
  image.src = wanted
  try {
    await image.decode?.()
  }
  catch {
    // a frame that does not decode is set anyway: the page has told which frames failed
  }
  if (!overlayLayer || props.overlay?.url !== wanted)
    return
  overlayLayer.setUrl(wanted)
  overlayShown = wanted
}

/**
 * The thunderstorm cells: each cell's outline as a polygon (every surface of it, holes as holes) in the colour, edge and fill of its
 * severity, and its mark at its centre. None takes a click or a key: no `interactive`, no `keyboard` (a Leaflet marker is a button
 * for the keyboard unless told it is not), and the mark is hidden from assistive technology (its svg is `aria-hidden`).
 */
function drawCells() {
  if (!map)
    return
  cellLayer?.remove()
  cellLayer = null
  const cells = drawable(props.cells ?? [])
  if (!cells.length)
    return
  const layer = L.layerGroup()
  for (const cell of cells) {
    const style = styleOf(cell.severity)
    if (cell.outline.length) {
      L.polygon(cell.outline as L.LatLngExpression[][][], {
        color: style.color,
        weight: style.weight,
        dashArray: style.dashArray ?? undefined,
        fillColor: style.color,
        fillOpacity: style.fillOpacity,
        lineJoin: 'round',
        interactive: false,
        pane: CELLS_PANE,
      }).addTo(layer)
    }
    const at = cell.latitude !== null && cell.longitude !== null ? [cell.latitude, cell.longitude] as L.LatLngTuple : outlineCentre(cell)
    if (!at)
      continue
    L.marker(at, {
      icon: L.divIcon({
        html: markSvg(cell),
        className: `storm-cell-mark${hasMotion(cell) ? ' storm-cell-mark-moving' : ''}`,
        iconSize: [MARK_SIZE, MARK_SIZE],
        iconAnchor: [MARK_SIZE / 2, MARK_SIZE / 2],
      }),
      interactive: false,
      keyboard: false,
      pane: CELL_MARKS_PANE,
    }).addTo(layer)
  }
  layer.addTo(map)
  cellLayer = layer
}

/** Where the mark goes for a cell with no centre: the middle of its outline's box */
function outlineCentre(cell: StormCell): L.LatLngTuple | null {
  const points = cell.outline.flat(2)
  if (!points.length)
    return null
  const centre = L.latLngBounds(points).getCenter()
  return [centre.lat, centre.lng]
}

/** The credit of what is drawn over the tiles in the map's attribution: the map says where what is on it is from */
function drawCredits() {
  if (!attribution)
    return
  for (const line of creditsShown)
    attribution.removeAttribution(line)
  creditsShown = (props.credits ?? []).map(creditHtml)
  for (const line of creditsShown)
    attribution.addAttribution(line)
}

/** The presses on a cell that the map has centred on */
let centred = 0

/**
 * Centres on the cell of a press of the list, as a click on a group of stations does (`viewForCluster`): on its centre, at the zoom
 * that fits its outline, at least one in and no farther than 10, where a cell is a few kilometres wide and a town is seen.
 */
function centreOnCell() {
  const target = props.centreOn
  if (!map || !target || target.count <= centred)
    return
  centred = target.count
  const owner = map
  const view = viewForCluster(
    target,
    box => owner.getBoundsZoom(L.latLngBounds([box.south, box.west], [box.north, box.east]), false, L.point(48, 48)),
    owner.getZoom(),
    CELL_ZOOM_LIMIT,
    owner.getMaxZoom(),
  )
  owner.setView([view.latitude, view.longitude], view.zoom, { animate: !reducedMotion.value })
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
  // over the radar's picture, which has every colour of the legend (and, over the dark blues, no navy to be seen), the ring is a solid white disc
  // with a heavier navy edge: it is seen on any of them, and it is no cell's mark (a coloured disc with a number and an arrow)
  const over = Boolean(props.openOn)
  positionMarks = [
    L.circleMarker(at, over
      ? { radius: 13, color: NAVY, weight: 3.5, fillColor: '#ffffff', fillOpacity: 0.95, interactive: false, pane: MARKS_PANE }
      : { radius: 12, color: NAVY, weight: 2, fillColor: '#ffffff', fillOpacity: 0.55, interactive: false, pane: MARKS_PANE }).addTo(map),
    L.circleMarker(at, { radius: over ? 5 : 4, color: '#ffffff', weight: 2, fillColor: NAVY, fillOpacity: 1, interactive: false, pane: MARKS_PANE }).addTo(map),
  ]
  // the mark is a picture of one thing: the ring is named, the dot inside it is not read a second time
  if (props.positionLabel) {
    const [ring, dot] = positionMarks.map(mark => mark.getElement())
    ring?.setAttribute('role', 'img')
    ring?.setAttribute('aria-label', props.positionLabel)
    dot?.setAttribute('aria-hidden', 'true')
  }
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
  if (props.hold || map.getBounds().pad(-0.1).contains(target))
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
  // the classes of this component's own are set by hand, not by a `:class` binding: Vue would write the whole `class` again on a change and take
  // away the `leaflet-container` (and the rest) that Leaflet puts on the element
  container.value.classList.toggle('station-map-fractional', Boolean(props.openOn))
  container.value.classList.toggle('station-map-cells-faded', Boolean(props.cellsFaded))
  map = L.map(container.value, {
    center: [HOME_VIEW.latitude, HOME_VIEW.longitude],
    zoom: HOME_VIEW.zoom,
    minZoom: 2,
    maxZoom: 16,
    zoomControl: false,
    attributionControl: false,
    // the radar opens on Germany's box, which a whole zoom would cut or leave half empty: a quarter of a zoom fits it
    zoomSnap: props.openOn ? 0.25 : 1,
    worldCopyJump: true,
    zoomAnimation: !reducedMotion.value,
    fadeAnimation: !reducedMotion.value,
    markerZoomAnimation: !reducedMotion.value,
  })
  // the credit and the buttons at the bottom right, clear of the layers button at the map's top right. Leaflet stacks the
  // controls of a bottom corner from its edge up, in the order they were added: the credit is added first, so it is at the
  // very bottom, under the zoom buttons (GH-4209)
  attribution = L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map)
  const zoom = L.control.zoom({ position: 'bottomright', zoomInTitle: t('mapTool.zoomIn'), zoomOutTitle: t('mapTool.zoomOut') }).addTo(map)
  // the full-screen button sits with the zoom buttons (GH-4227), at the head of their bar, so that the three are one control
  // that the pointer and the keyboard meet in a row. Leaflet makes the bar; the button in it is Vue's (teleported), so that its
  // label and state follow the page's
  const host = L.DomUtil.create('div', 'station-map-fullscreen')
  // a press on it is no press on the map (Leaflet does this for each of its own buttons, not for the bar)
  L.DomEvent.disableClickPropagation(host)
  zoom.getContainer()?.prepend(host)
  fullscreenHost.value = host
  L.tileLayer(OSM_TILES, { attribution: OSM_ATTRIBUTION, maxZoom: 19, className: 'station-map-tiles' }).addTo(map)
  map.createPane(MARKS_PANE).style.zIndex = '450'
  map.createPane(RADAR_PANE).style.zIndex = '250'
  map.createPane(CELLS_PANE).style.zIndex = '420'
  map.createPane(CELL_MARKS_PANE).style.zIndex = '430'
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
  // the radar's own view, where the page has one: the box of its images, as large as the map fits
  if (props.openOn)
    map.fitBounds(props.openOn, { animate: false })
  void drawOverlay()
  drawCells()
  drawCredits()
  drawSelection()
  drawPosition()
  reveal()
  centreOnPosition()
  emitView()
})

// the map is laid out by the page: it grows and shrinks with the window, and a map that is not told about its size
// draws its tiles for the old one
useResizeObserver(container, () => map?.invalidateSize({ animate: false }))

// The stage goes full screen or comes back (GH-4227): the map is told its new size at once and after the layout has settled
// (the browser's full screen changes the window a moment after the state does), and keeps its centre, zoom, layers and the
// station picked, since it is the same element that has grown, not a new one
const fullscreenButton = ref<HTMLButtonElement | null>(null)
watch(() => props.fullscreen, () => {
  map?.invalidateSize({ animate: false })
  void nextTick(() => map?.invalidateSize({ animate: false }))
  requestAnimationFrame(() => map?.invalidateSize({ animate: false }))
}, { flush: 'post' })
defineExpose({
  /** The focus into the map (the container of Leaflet is a stop of the keyboard that pans and zooms by keys) */
  focusMap: () => container.value?.focus({ preventScroll: true }),
  /** The focus back to the full-screen button */
  focusFullscreenButton: () => fullscreenButton.value?.focus({ preventScroll: true }),
})

onBeforeUnmount(() => {
  if (pointerFrame)
    cancelAnimationFrame(pointerFrame)
  map?.remove()
  map = null
  overlayLayer = null
  overlayShown = null
  cellLayer = null
  attribution = null
  creditsShown = []
})

watch(() => [props.stations, props.reporting, props.grouping], () => {
  forgetClusters()
  dots?.redraw()
})
watch(() => props.overlay, () => void drawOverlay(), { deep: true })
watch(() => props.cells, drawCells)
watch(() => props.cellsFaded, faded => container.value?.classList.toggle('station-map-cells-faded', Boolean(faded)))
watch(() => props.credits, drawCredits)
watch(() => props.centreOn, centreOnCell)
watch(() => [props.selected, props.place, props.recentre, props.position], () => {
  drawSelection()
  reveal()
})
watch(() => [props.position, props.locate, props.positionLabel], () => {
  drawPosition()
  centreOnPosition()
})
</script>

<template>
  <div ref="container" class="station-map" role="application" :aria-label="label" :aria-roledescription="t('nav.map')" :aria-describedby="describedBy" />
  <!-- by its action (GH-4227): the name is what pressing does, and it changes with the state ("Full screen", "Exit full screen"), as a button that is not a toggle does -->
  <Teleport v-if="fullscreenHost && !noFullscreen" :to="fullscreenHost">
    <button
      ref="fullscreenButton"
      type="button"
      class="station-map-fullscreen-button"
      :aria-label="fullscreen ? t('mapTool.fullscreenExit') : t('mapTool.fullscreenEnter')"
      :title="fullscreen ? t('mapTool.fullscreenExit') : t('mapTool.fullscreenEnter')"
      data-testid="map-fullscreen"
      @click="emit('fullscreen')"
    >
      <UIcon :name="fullscreen ? 'i-ph-arrows-in' : 'i-ph-arrows-out'" class="size-5" aria-hidden="true" />
    </button>
  </Teleport>
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
/* the narrow layout runs edge to edge (GH-4227): the map has no corners of a card */
@media screen and (max-width: 39.99rem) {
  .station-map {
    border-radius: 0;
  }
}
/* Calm tiles: OpenStreetMap's colours, faded, so that the stations are what the eye finds */
.station-map .station-map-tiles {
  filter: saturate(0.35) brightness(1.03) contrast(0.92);
}
/* a map that opens on a box is zoomed by a quarter, where the browser draws the tiles scaled and leaves hairlines between them: an edge of no colour hides them */
.station-map.station-map-fractional .station-map-tiles img.leaflet-tile {
  outline: 1px solid transparent;
}
/* the radar's picture (GH-3788): the classes are pixels (a pixel is a class, never a blend), which the browser stretches over the bounds
   without smoothing them; it takes no pointer */
.station-map .station-map-radar {
  pointer-events: none;
  image-rendering: pixelated;
}
/* the cells that are not for the frame shown fade out (GH-3788): their panes, so that the outlines and the marks go together */
.station-map .leaflet-storm-cells-pane,
.station-map .leaflet-storm-cell-marks-pane {
  transition: opacity 0.4s;
}
.station-map.station-map-cells-faded .leaflet-storm-cells-pane,
.station-map.station-map-cells-faded .leaflet-storm-cell-marks-pane {
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .station-map .leaflet-storm-cells-pane,
  .station-map .leaflet-storm-cell-marks-pane {
    transition: none;
  }
}
/* the mark of a thunderstorm cell (utils/storm-cells.ts): an svg the size of its icon, no box of its own */
.station-map .storm-cell-mark {
  background: none;
  border: 0;
}
.station-map .storm-cell-mark svg {
  display: block;
  overflow: visible;
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
.station-map .leaflet-bar a:hover,
.station-map .station-map-fullscreen-button:hover {
  background: var(--color-ink-100);
}
/* the full-screen button, the head of the bar of the zoom buttons: the same 40 px square, the same white and ink */
.station-map .station-map-fullscreen-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  background: #ffffff;
  color: var(--color-ink-950);
  border-bottom: 1px solid var(--color-ink-200);
  cursor: pointer;
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
