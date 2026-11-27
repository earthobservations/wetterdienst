<script setup lang="ts">
import type { PlaceMatch } from '#shared/utils/places'
import type { KostraQuantity } from '~/utils/kostra'
import type { Point } from '~/utils/map-tool'
import { defineAsyncComponent } from 'vue'
import KostraChart from '~/components/KostraChart.vue'
import KostraTable from '~/components/KostraTable.vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'
import PlaceField from '~/components/PlaceField.vue'
import ProviderCredit from '~/components/ProviderCredit.vue'
import SegmentedControl from '~/components/SegmentedControl.vue'
import ToolPlaceholder from '~/components/ToolPlaceholder.vue'
import UseMyLocation from '~/components/UseMyLocation.vue'
import { cellCorners, KOSTRA_UNITS, linkPoint, pointText, queryOfPoint } from '~/utils/kostra'

// The Heavy-rainfall tool (GH-4500): DWD's design rainfall (KOSTRA-DWD-2020) of a point in Germany, the rain of a duration that comes
// back every N years, which drains and retention basins are sized with. The point is chosen by a place's name (`PlaceField`), "Use my
// location" (`UseMyLocation`, rounded to about 1 km in the browser) or a click on the small map, and is kept in the link (`?lat=&lon=`),
// which is the page's one source of the point: a link, the back button and every way of choosing go through it.
//
// What the page shows is the table of the 5 km cell of DWD's grid that holds the point: 22 durations (5 minutes to 7 days) by 9 return
// periods (1 to 100 years), as the depth in mm or the intensity in l/(s·ha) with DWD's uncertainty of each value, one depth-duration curve
// for each return period, and the cell outlined on the map. The values are DWD's estimates for the cell, not measurements at the point.
// A point outside DWD's grid (outside Germany and a border of about 10 km, or in the sea) is told in words, not as a failure.

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
useHead({ title: () => t('kostra.title') })

// the map's code, Leaflet with it, is loaded apart from the page: the panel is there before the map is
const StationMap = defineAsyncComponent({
  loader: () => import('~/components/StationMap.vue'),
  errorComponent: MapStationsNotLoaded,
})

// ---- the point -----------------------------------------------------------------------------------------------------

/** The point of the link: the page's one source of it */
const point = computed(() => linkPoint(route.query))

/** How the point was chosen, for what the panel says of it: a link says nothing, a place has its name, the map and the position are told as that */
type Source = 'link' | 'place' | 'map' | 'position'
const source = ref<Source>('link')
const placeName = ref('')
const positionStatus = ref('')

/** Where the map is to move to, once for each `count` (a place, the position, the point of a link: not a click on the map, which is where the reader looks) */
const goTo = ref<{ latitude: number, longitude: number, count: number, zoom: number } | null>(null)
let moves = 0
/** The zoom of the map's view, from its own events: a click far out also brings the cell into view */
const mapZoom = ref(0)
const VIEW_ZOOM = 11
const CLICK_ZOOM = 9

function moveTo(at: Point, zoom = VIEW_ZOOM) {
  goTo.value = { latitude: at.latitude, longitude: at.longitude, count: ++moves, zoom }
}

function setPoint(at: Point, from: Source) {
  source.value = from
  if (from !== 'position')
    positionStatus.value = ''
  if (from !== 'place')
    placeName.value = ''
  // replaced, not pushed: each point is not a page of the history, and the link always holds the one in view
  void router.replace({ query: { ...route.query, ...queryOfPoint(at) } }).catch(() => {})
}

function onPlace(place: PlaceMatch) {
  const at = { latitude: place.latitude, longitude: place.longitude }
  setPoint(at, 'place')
  placeName.value = [place.name, place.region].filter(Boolean).join(', ')
  moveTo(at)
}
function onPosition(at: Point) {
  setPoint(at, 'position')
  positionStatus.value = t('kostra.positionUsed')
  moveTo(at)
}
function onPick(at: Point) {
  setPoint(at, 'map')
  // a cell is 5 km: at the zoom of a country it is a dot, so the map comes in to where it is seen; nearer in it stays where it is
  if (mapZoom.value < CLICK_ZOOM - 1)
    moveTo(at, CLICK_ZOOM)
}

// a link opens on its point
if (point.value)
  moveTo(point.value)

// ---- the answer ----------------------------------------------------------------------------------------------------

const kostra = useKostra(point)
const table = computed(() => kostra.table.value)
const corners = computed(() => table.value ? cellCorners(table.value.cell) : null)
const status = computed(() => kostra.status.value)

const quantity = ref<KostraQuantity>('depth')
const quantityOptions = computed(() => [
  { value: 'depth' as const, label: `${t('kostra.quantity.depth')} (${KOSTRA_UNITS.depth})` },
  { value: 'intensity' as const, label: `${t('kostra.quantity.intensity')} (${KOSTRA_UNITS.intensity})` },
])

const resultId = useId()
const noteId = useId()
const cellCentre = computed(() => table.value
  ? `${table.value.cell.latitude.toFixed(4)}, ${table.value.cell.longitude.toFixed(4)}`
  : '')

/** What the panel says of the point */
const pointSummary = computed(() => {
  if (!point.value)
    return ''
  const coordinates = pointText(point.value)
  switch (source.value) {
    case 'place': return `${placeName.value} (${coordinates})`
    case 'position': return t('kostra.pointPosition', { point: coordinates })
    case 'map': return t('kostra.pointMap', { point: coordinates })
    default: return coordinates
  }
})
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('kostra.title')" :lede="t('kostra.subtitle')" :about-label="t('kostra.aboutButton')">
      <template #about>
        <div class="space-y-3 text-muted">
          <p>{{ t('kostra.about1') }}</p>
          <p>{{ t('kostra.about2') }}</p>
          <p>{{ t('kostra.about3') }}</p>
          <p class="text-sm" data-testid="kostra-sources">
            {{ t('kostra.aboutSources') }}
            <NuxtLink to="https://www.dwd.de/DE/leistungen/kostra_dwd_rasterdaten/kostra_dwd_rasterdaten.html" external target="_blank" rel="noopener" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">
              {{ t('kostra.aboutDwdLink') }}
            </NuxtLink>
          </p>
        </div>
      </template>
    </PageHeader>

    <div class="page-body">
      <div class="kostra-tool">
        <!-- the point: its name, "Use my location", and what is told of it; beside the map on a wide screen, over it on a phone -->
        <section class="kostra-card kostra-panel" aria-labelledby="kostra-point-title" data-testid="kostra-panel">
          <h2 id="kostra-point-title" class="kostra-card-title">
            <UIcon name="i-ph-map-pin" class="kostra-card-icon" />
            {{ t('kostra.pointTitle') }}
          </h2>
          <PlaceField :label="t('kostra.placeLabel')" @pick="onPlace" />
          <UseMyLocation use="kostra" :status="positionStatus" @position="onPosition" />
          <p class="kostra-note" data-testid="kostra-map-hint">
            {{ t('kostra.mapHint') }}
          </p>
          <p v-if="point" class="kostra-point" role="status" data-testid="kostra-point">
            <span class="font-semibold">{{ t('kostra.pointLabel') }}{{ t('common.colon') }}</span> {{ pointSummary }}
          </p>
        </section>

        <div class="kostra-stage" data-testid="kostra-stage-map">
          <ClientOnly>
            <StationMap
              :stations="[]"
              :selected="null"
              :place="null"
              :label="t('kostra.mapLabel')"
              no-fullscreen
              :position="point"
              :position-label="t('kostra.pointMarker')"
              :box="corners"
              :go-to="goTo"
              @pick="onPick"
              @view="mapZoom = $event.zoom"
            />
          </ClientOnly>
        </div>
      </div>

      <!-- the answer: told as it comes, in the tree from the start so that a screen reader hears it arrive -->
      <section :id="resultId" class="kostra-result" aria-labelledby="kostra-result-title" :aria-busy="status === 'pending'" data-testid="kostra-result">
        <h2 id="kostra-result-title" class="sr-only">
          {{ t('kostra.resultTitle') }}
        </h2>

        <ToolPlaceholder v-if="status === 'idle'" tool="kostra" />

        <p v-else-if="status === 'pending'" class="kostra-notice" role="status" data-testid="kostra-loading">
          <UIcon name="i-ph-circle-notch" class="size-5 shrink-0 motion-safe:animate-spin" />
          {{ t('kostra.loading') }}
        </p>

        <!-- a point outside DWD's grid is a fact about the place, told in words and not as a failure -->
        <div v-else-if="status === 'outside'" class="kostra-notice" role="status" data-testid="kostra-outside">
          <UIcon name="i-ph-map-pin-line" class="size-5 shrink-0" />
          <p>{{ t('kostra.outside') }}</p>
        </div>

        <div v-else-if="status === 'error'" class="flex flex-col items-start gap-2" data-testid="kostra-failed">
          <p class="kostra-notice kostra-failure" role="alert">
            <UIcon name="i-ph-warning" class="size-5 shrink-0" />
            <span>{{ t('kostra.failed') }} <span v-if="kostra.detail.value" class="block text-sm" data-testid="kostra-failed-detail">{{ kostra.detail.value }}</span></span>
          </p>
          <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="kostra-retry" @click="kostra.retry()" />
        </div>

        <template v-else-if="table">
          <div class="kostra-head">
            <div>
              <h3 class="kostra-result-title">
                {{ t('kostra.resultHeading') }}
              </h3>
              <p class="kostra-note" data-testid="kostra-cell">
                {{ t('kostra.cell', { cell: table.cell.indexRc, centre: cellCentre }) }}
              </p>
            </div>
            <SegmentedControl v-model="quantity" :options="quantityOptions" :label="t('kostra.quantitySwitch')" :controls="resultId" />
          </div>

          <p :id="noteId" class="kostra-estimate" data-testid="kostra-estimate">
            <UIcon name="i-ph-info" class="size-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{{ t('kostra.estimateNote') }}</span>
          </p>

          <KostraChart :table="table" :quantity="quantity" :described-by="noteId" />

          <KostraTable :table="table" :quantity="quantity" />

          <p class="kostra-note" data-testid="kostra-uncertainty-note">
            {{ t('kostra.uncertaintyNote') }}
          </p>

          <ProviderCredit provider="dwd" fallback="Deutscher Wetterdienst" :terms="table.credit" data-testid="kostra-credit" />
        </template>
      </section>
    </div>
  </div>
</template>

<style>
/* The layout of the tool: the point's panel and the map side by side from 72 rem (the radar's breakpoint), one column below it; the
   answer under both, the width of the page. */
.kostra-tool {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: stretch;
}
@media (min-width: 72rem) {
  .kostra-tool {
    grid-template-columns: minmax(20rem, 26rem) minmax(0, 1fr);
    gap: 2rem;
  }
}
.kostra-stage {
  position: relative;
  isolation: isolate;
  min-width: 0;
  height: clamp(16rem, 46dvh, 22rem);
}
@media (min-width: 72rem) {
  .kostra-stage {
    height: auto;
    min-height: 22rem;
  }
}
/* the narrow layout runs edge to edge: the map has the window's width */
@media screen and (width < 40rem) {
  .kostra-stage {
    margin-inline: calc(-1 * var(--bleed-start)) calc(-1 * var(--bleed-end));
    /* a grid item with a negative margin is not stretched by it: the width is said */
    width: calc(100% + var(--bleed-start) + var(--bleed-end));
  }
}
.kostra-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.75rem;
  padding: 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2.5);
  background: var(--ui-bg);
}
.kostra-card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.kostra-card-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--ui-text-toned);
}
.kostra-note {
  font-size: 0.875rem;
  color: var(--ui-text-muted);
}
.kostra-point {
  font-size: 0.875rem;
  color: var(--ui-text);
  overflow-wrap: anywhere;
}
@media screen and (width < 40rem) {
  .kostra-card {
    margin-inline: -1rem;
    padding-inline: 1rem;
    border-radius: 0;
    border-inline-width: 0;
  }
}
.kostra-result {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.5rem;
  min-width: 0;
}
.kostra-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.75rem 1.5rem;
}
.kostra-result-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.kostra-estimate {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 1.5);
  background: var(--ui-bg-muted, var(--ui-bg));
  font-size: 0.875rem;
  color: var(--ui-text);
}
.kostra-notice {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2);
  font-size: 0.9375rem;
  color: var(--ui-text);
}
.kostra-failure {
  color: var(--ui-text-toned);
}
</style>
