<script setup lang="ts">
import type { Point } from '~/utils/map-tool'
import type { RadarFrame } from '~/utils/radar'
import type { StormCell } from '~/utils/storm-cells'
import { defineAsyncComponent } from 'vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'
import ProcessingNote from '~/components/ProcessingNote.vue'
import RadarLegend from '~/components/RadarLegend.vue'
import RadarPlayer from '~/components/RadarPlayer.vue'
import RadarStormCells from '~/components/RadarStormCells.vue'
import UseMyLocation from '~/components/UseMyLocation.vue'
import { cellsShownOn, describeFrame, formatFrameTime, frameKey, frameUrl, isUnavailable, isWithinBounds, leafletBounds, RADAR_VIEW } from '~/utils/radar'
import { cellView } from '~/utils/storm-cells'

// The Radar tool (GH-3788): DWD's precipitation radar over Germany as a loop of the last two hours and DWD's forecast of the next two, on
// the map of the map tool (`StationMap.vue`, here with no stations), with a player (play and pause, a slider over the frames, the time in
// the reader's zone, observed or forecast marked in words and by an icon), the legend of the colours in mm/h with numbers, and DWD's
// KONRAD3D thunderstorm cells on top (GH-4208), each in a list of its own with where it is and a press that centres the map on it.
//
// The frames are PNG images the backend draws (`GET /api/radar/frames` lists them, `GET /api/radar/frame` is one): the player loads them
// 5 at a time into the browser's cache (the server serves 32 requests at once), drops a frame that fails, and the loop starts by itself
// once they are all in hand, unless the system asks for less motion. The list is asked for again every 5 minutes, the cells every 5
// minutes while they are on. A radar that is more than 20 minutes behind is told stale, and cells of a scan over 20 minutes old are not
// drawn. The forecast is an extrapolation of the recent movement of the rain, not a weather model, and the page says so.
//
// The reader's own position (GH-4287) is the map tool's "Use my location" (`UseMyLocation.vue`, `useMyLocation`: asked only on a press,
// rounded to about 1 km in the browser, kept only with the tick): the map marks it and centres on it, and the marker can be hidden. The
// radar is the same picture for everyone, so the position goes to no request of the backend; it is only drawn.

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
useHead({ title: () => t('radar.title') })

// the map's code, Leaflet with it, is loaded apart from the page: the panel is there before the map is
const StationMap = defineAsyncComponent({
  loader: () => import('~/components/StationMap.vue'),
  errorComponent: MapStationsNotLoaded,
})

// from 72 rem the panel is beside the map; below it the map comes first and the panel is under it, in the order the window shows
// them (WCAG 1.3.2, 2.4.3)
const wide = useMediaQuery('(min-width: 72rem)')
const parts = computed(() => wide.value ? ['panel', 'stage'] as const : ['stage', 'panel'] as const)
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// ---- the radar ------------------------------------------------------------------------------------------------------

const radar = useRadarFrames(() => true)
const loop = computed(() => radar.loop.value)
const frames = computed(() => loop.value?.frames ?? [])
const player = useRadarPlayer(frames, { autoplay: () => !reducedMotion.value })

/**
 * The frame whose picture is on the map: the one the loop is at, once its image is in hand. A frame the reader moved to that is not in yet
 * leaves the one before on the map and does not blank it, and the chip over the map says what is on the map (not where the player stands);
 * the player says its frame is loading. A picture is taken off only where the list is empty; where a new list has other keys for the frames (a new run) it stays until the frame at its time is in (N1).
 */
const picture = ref<RadarFrame | null>(null)
watch(player.shown, (frame) => {
  if (frame)
    picture.value = frame
}, { immediate: true })
// Taken off only where the list has no frame at all. With every new list the 24 frames of the forecast are of a new run (new keys), so a reader
// on a forecast frame would see the map go blank for as long as the new image takes (2 to 16 s): the picture stays, its image is in the
// browser's cache, until the frame at the same time of the new list is loaded and takes its place (`player.shown`).
watch(frames, (list) => {
  if (!list.length)
    picture.value = null
})
const overlay = computed(() => loop.value && picture.value ? { url: frameUrl(picture.value), bounds: leafletBounds(loop.value.bounds), opacity: 0.8 } : null)

const now = computed(() => radar.now.value)
const current = computed(() => player.current.value)
const pictureWords = computed(() => picture.value ? describeFrame(t, picture.value, formatLanguage.value, now.value) : null)
/** The player stands at a frame whose picture is not on the map yet: its image is on its way */
const frameLoading = computed(() => Boolean(current.value) && (!picture.value || frameKey(current.value!) !== frameKey(picture.value)))

const newestObserved = computed(() => frames.value.filter(frame => frame.kind === 'observation').at(-1) ?? null)
const newestTime = computed(() => newestObserved.value ? formatFrameTime(newestObserved.value.at, formatLanguage.value, now.value) : '')
const loopRange = computed(() => {
  const first = frames.value[0]
  const last = frames.value.at(-1)
  return first && last ? t('radar.loopRange', { from: formatFrameTime(first.at, formatLanguage.value, now.value), to: formatFrameTime(last.at, formatLanguage.value, now.value) }) : ''
})
/** The frames still on their way, for the status: nothing once they are all in hand or dropped */
const loading = computed(() => {
  const { loaded, failed, total } = player.progress.value
  return total > 0 && loaded + failed < total ? t('radar.loadingFrames', { loaded: loaded + failed, total }) : ''
})
const skipped = computed(() => player.progress.value.failed)
/**
 * What the live region says of the loading of the frames (M2): once when it starts and once when it is over, never the count, which is
 * 49 changes (and some 25 more with every list). A new list is loaded silently; the visible counter is no live region.
 */
const framesLive = ref('')
let framesStarted = false
let framesAnnounced = false
watch(() => player.progress.value, ({ loaded, failed, total }) => {
  if (total === 0)
    return
  if (!framesStarted) {
    framesStarted = true
    framesLive.value = t('radar.framesLoadingLive')
  }
  if (!framesAnnounced && loaded + failed >= total) {
    framesAnnounced = true
    // none of them came: a failure is said, not "loaded"
    framesLive.value = loaded === 0 ? t('radar.framesNone') : t('radar.framesReady')
  }
}, { immediate: true })
/** The backend has no radar (a 404, a 501: a server without the `radar` extra): no Retry would help */
const unavailable = computed(() => isUnavailable(radar.error.value))

/** The credit of the radar for the map's own: the provider's credit line and the licence as a link to its terms */
const radarCredit = computed(() => {
  const credit = loop.value?.credit
  if (!credit)
    return null
  const license = credit.license
  return { text: credit.attribution ?? t('radar.creditRadar'), license: license ? { label: license.spdx ?? license.name, url: license.url } : null }
})

// ---- the thunderstorm cells of DWD's radar (GH-4208) ---------------------------------------------------------------

const cellsOn = ref(true)
const storm = useStormCells(() => cellsOn.value)
/**
 * The cells the map draws: none where they are off, the scan has not come, or it is out of date (more than 20 minutes old: the list
 * keeps it and says so, and the map does not draw cells that were true then as the sky now)
 */
const stormCells = computed(() => cellsOn.value && storm.scan.value && !storm.outdated.value ? storm.scan.value.cells : undefined)
/**
 * The cells are the latest scan's, so they are shown on the frames within 15 minutes of it and not on an older one or one of the forecast,
 * where they fade out of the map and the panel says so (the maintainer's decision, GH-3788)
 */
const cellsOnFrame = computed(() => cellsShownOn(picture.value, storm.scan.value?.referenceTime ?? null))
const cellsFaded = computed(() => Boolean(stormCells.value) && !cellsOnFrame.value)
const stormCredit = computed(() => {
  const credit = storm.scan.value?.credit
  if (!credit?.attribution)
    return null
  const license = credit.license
  return { text: credit.attribution, license: license ? { label: license.spdx ?? license.name, url: license.url } : null }
})
/** The credit lines of the map: one where the radar and the cells are DWD's under the same terms (they are), a line each where they are not; the cells' only while they are on the map */
const credits = computed(() => {
  const radarLine = radarCredit.value
  const cellsLine = stormCells.value?.length && cellsOnFrame.value ? stormCredit.value : null
  if (radarLine && cellsLine && radarLine.text === cellsLine.text && radarLine.license?.url === cellsLine.license?.url)
    return [radarLine]
  return [radarLine, cellsLine].filter(credit => credit !== null)
})

const announcement = ref('')
/** A press on a cell of the list: the map centres on it, once for each press (`StationMap.vue`) */
const cellCentre = ref<({ count: number } & NonNullable<ReturnType<typeof cellView>>) | null>(null)
let cellPresses = 0
/**
 * Centres the map on a cell of the list, as a click on a group does, and says so in a status. The focus stays on the cell's row, where the
 * reader is in the list; on a phone, where the map is over the panel, the map is brought into view.
 */
function centreCell(cell: StormCell) {
  const view = cellView(cell)
  if (!view)
    return
  cellCentre.value = { count: ++cellPresses, ...view }
  announcement.value = t('radar.cellsCentred', { id: cell.id })
  if (!wide.value)
    document.querySelector('.radar-stage')?.scrollIntoView({ block: 'start', behavior: reducedMotion.value ? 'auto' : 'smooth' })
}

// ---- the reader's own position (GH-4287) ----------------------------------------------------------------------------

/** The position the reader gave by "Use my location", rounded to about 1 km: set by a press, so a remembered position is shown only on one */
const myPosition = ref<Point | null>(null)
/** Counts the presses that gave a position: the map centres on it once for each */
const locateCount = ref(0)
/** The marker can be hidden and shown again; a press of the button shows it */
const markerShown = ref(true)
const { position: rememberedPosition } = useMyLocation()
// "Forget my position" takes the marker off the map
watch(rememberedPosition, (now) => {
  if (!now)
    myPosition.value = null
})
/** Whether the position is within the box of the radar's images; null while the answer with that box is not in */
const insideRadar = computed(() => myPosition.value && loop.value ? isWithinBounds(myPosition.value, loop.value.bounds) : null)
/** What the map marks and centres on: a position outside the radar is not (the map stays on the data), and a hidden one is not */
const markedPosition = computed(() => myPosition.value && markerShown.value && insideRadar.value !== false ? myPosition.value : null)
/** What is said of the position, politely, under the button (a status of the component) */
const positionStatus = computed(() => {
  if (!myPosition.value)
    return ''
  if (insideRadar.value === false)
    return t('radar.positionOutside')
  return markerShown.value ? t('radar.positionShown') : t('radar.positionHidden')
})

/** A press of "Use my location" that gave a position: it is shown again if it was hidden, and the map comes into view on a phone, where it is over the panel */
async function onPosition(point: Point) {
  myPosition.value = point
  markerShown.value = true
  locateCount.value++
  if (!wide.value && insideRadar.value !== false) {
    await nextTick()
    document.querySelector('.radar-stage')?.scrollIntoView({ block: 'start', behavior: reducedMotion.value ? 'auto' : 'smooth' })
  }
}

const licenseLink = computed(() => loop.value?.credit?.license ?? null)
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('radar.title')" :lede="t('radar.subtitle')" :about-label="t('radar.aboutButton')">
      <template #about>
        <div class="space-y-3 text-muted">
          <p>{{ t('radar.about1') }}</p>
          <p>{{ t('radar.about2') }}</p>
          <p>{{ t('radar.about3') }}</p>
          <p class="text-sm" data-testid="radar-sources">
            {{ t('radar.aboutSources') }}
            <NuxtLink to="https://www.dwd.de/DE/leistungen/radvor/radvor.html" external target="_blank" rel="noopener" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">
              {{ t('radar.aboutDwdLink') }}
            </NuxtLink>
          </p>
        </div>
      </template>
    </PageHeader>

    <div class="page-body">
      <div class="radar-tool">
        <template v-for="part in parts" :key="part">
          <!-- The panel: beside the map on a wide screen, under it on a phone -->
          <section v-if="part === 'panel'" class="radar-panel" aria-labelledby="radar-loop-title" data-testid="radar-panel">
            <p class="sr-only" role="status" data-testid="radar-panel-announcement">
              {{ announcement }}
            </p>
            <!-- the loading of the frames, told once at its start and once at its end, not 49 times (the counter in the card is no live region) -->
            <p class="sr-only" role="status" data-testid="radar-frames-live">
              {{ framesLive }}
            </p>

            <section class="radar-card" data-testid="radar-loop">
              <h2 id="radar-loop-title" class="radar-card-title">
                <UIcon name="i-ph-cloud-rain" class="radar-card-icon" />
                {{ t('radar.loopTitle') }}
              </h2>

              <p v-if="radar.status.value === 'idle' || radar.status.value === 'pending'" class="radar-card-note radar-note-row" role="status" data-testid="radar-loading">
                <UIcon name="i-ph-circle-notch" class="size-4 shrink-0 motion-safe:animate-spin" />
                {{ t('common.loading') }}
              </p>

              <p v-else-if="radar.status.value === 'error' && unavailable" class="radar-card-note radar-note-row radar-warning" role="alert" data-testid="radar-unavailable">
                <UIcon name="i-ph-warning" class="size-4 shrink-0" />
                {{ t('radar.unavailable') }}
              </p>

              <div v-else-if="radar.status.value === 'error'" class="flex flex-col items-start gap-2">
                <p class="radar-card-note" role="alert" data-testid="radar-failed">
                  {{ t('radar.failed') }}
                </p>
                <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="radar-retry" @click="radar.retry()" />
              </div>

              <template v-else-if="loop">
                <p v-if="!frames.length" class="radar-card-note" data-testid="radar-empty">
                  {{ t('radar.empty') }}
                </p>
                <template v-else>
                  <p class="radar-card-note" data-testid="radar-range">
                    {{ loopRange }}
                  </p>
                  <p v-if="newestTime" class="radar-card-note" data-testid="radar-newest">
                    {{ t('radar.newest', { time: newestTime }) }}
                  </p>
                </template>
                <p v-if="radar.stale.value" class="radar-card-note radar-note-row radar-warning" data-testid="radar-stale">
                  <UIcon name="i-ph-warning" class="size-4 shrink-0" />
                  {{ t('radar.stale') }}
                </p>
                <p v-if="loading" class="radar-card-note radar-note-row" data-testid="radar-frames-loading">
                  <UIcon name="i-ph-circle-notch" class="size-4 shrink-0 motion-safe:animate-spin" />
                  {{ loading }}
                </p>
                <p v-if="skipped" class="radar-card-note radar-note-row radar-warning" data-testid="radar-skipped">
                  <UIcon name="i-ph-warning" class="size-4 shrink-0" />
                  {{ t('radar.framesSkipped', { count: skipped }) }}
                </p>
                <div v-if="radar.refreshFailed.value" class="flex flex-col items-start gap-2" data-testid="radar-refresh-failed">
                  <p class="radar-card-note radar-note-row radar-warning" role="alert">
                    <UIcon name="i-ph-warning" class="size-4 shrink-0" />
                    {{ t('radar.refreshFailed', { time: newestTime }) }}
                  </p>
                  <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="radar.retry()" />
                </div>
              </template>
            </section>

            <!-- the reader's own position (GH-4287): "Use my location" as on the map, and the way to hide its marker -->
            <section class="radar-card" aria-labelledby="radar-position-title" data-testid="radar-position">
              <h2 id="radar-position-title" class="radar-card-title">
                <UIcon name="i-ph-map-pin" class="radar-card-icon" />
                {{ t('radar.positionTitle') }}
              </h2>
              <UseMyLocation use="radar" :status="positionStatus" @position="onPosition" />
              <UButton
                v-if="myPosition && insideRadar !== false"
                type="button"
                color="neutral"
                variant="outline"
                size="sm"
                :icon="markerShown ? 'i-ph-eye-slash' : 'i-ph-eye'"
                :label="markerShown ? t('radar.positionHide') : t('radar.positionShow')"
                data-testid="radar-position-toggle"
                @click="markerShown = !markerShown"
              />
            </section>

            <!-- the thunderstorm cells of the latest scan, in words (GH-4208) -->
            <RadarStormCells
              v-model:on="cellsOn"
              :scan="storm.scan.value"
              :status="storm.status.value"
              :refresh-failed="storm.refreshFailed.value"
              :outdated="storm.outdated.value"
              :faded-on-frame="cellsFaded"
              @retry="storm.retry()"
              @centre="centreCell"
            />

            <!-- the credit of the radar, and under it what wetterdienst did to the frames (GH-3799) -->
            <section class="radar-card" data-testid="radar-credit">
              <p class="radar-card-note">
                {{ t('radar.creditRadar') }}
                <template v-if="loop?.credit?.attribution">
                  {{ loop.credit.attribution }}.
                </template>
                <template v-if="licenseLink">
                  {{ t('providers.licence') }}{{ t('common.colon') }}
                  <NuxtLink :to="licenseLink.url" external target="_blank" rel="noopener" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">
                    {{ licenseLink.name }}
                  </NuxtLink>.
                </template>
              </p>
              <ProcessingNote radar />
            </section>
          </section>

          <!-- The map, the player under it and the legend of its colours -->
          <div v-else class="radar-stage" data-testid="radar-stage">
            <div class="radar-canvas">
              <div v-if="pictureWords && picture" class="radar-chip" :data-kind="picture.kind" aria-hidden="true" data-testid="radar-chip">
                <UIcon :name="picture.kind === 'forecast' ? 'i-ph-fast-forward-fill' : 'i-ph-eye-fill'" class="size-4 shrink-0" />
                {{ pictureWords.time }} · {{ pictureWords.ahead ?? pictureWords.kind }}
              </div>
              <ClientOnly>
                <StationMap
                  :stations="[]"
                  :selected="null"
                  :place="null"
                  :label="t('radar.mapLabel')"
                  no-fullscreen
                  :open-on="RADAR_VIEW"
                  :overlay="overlay"
                  :cells="stormCells"
                  :cells-faded="cellsFaded"
                  :credits="credits"
                  :centre-on="cellCentre"
                  :position="markedPosition"
                  :position-label="t('radar.positionMarker')"
                  :locate="locateCount"
                />
              </ClientOnly>
            </div>

            <RadarPlayer
              :frames="player.playable.value"
              :index="player.index.value"
              :playing="player.playing.value"
              :now="now"
              :reduced-motion="reducedMotion"
              :loading="frameLoading"
              @toggle="player.toggle()"
              @seek="player.seek($event)"
              @step="player.step($event)"
            />

            <RadarLegend v-if="loop" :legend="loop.legend" />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style>
/* The layout of the tool: the panel beside the map from 72 rem (the map tool's breakpoint and columns); below it one column, the map first
   and the panel under it. */
.radar-tool {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
@media (min-width: 72rem) {
  .radar-tool {
    grid-template-columns: minmax(20rem, 26rem) minmax(0, 1fr);
    gap: 2rem;
  }
}

/* The stage: the map, the player under it and the legend. It keeps its place while the panel, which can be long, scrolls on a wide screen. */
.radar-stage {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  min-width: 0;
}
@media (min-width: 72rem) {
  .radar-stage {
    position: sticky;
    top: calc(var(--header-height) + 1rem);
  }
}
.radar-canvas {
  position: relative;
  isolation: isolate;
  height: clamp(18rem, 46dvh, 30rem);
}
@media (min-width: 72rem) {
  .radar-canvas {
    height: clamp(22rem, calc(100dvh - var(--header-height) - 21rem), 44rem);
  }
}
/* the narrow layout runs edge to edge: the map has the window's width */
@media screen and (width < 40rem) {
  .radar-canvas {
    margin-inline: calc(-1 * var(--bleed-start)) calc(-1 * var(--bleed-end));
  }
}
/* a window too low for a map and its panel beside it (a phone on its side, zoom): the stage scrolls with the page */
@media (max-height: 30rem) {
  .radar-stage {
    position: static;
  }
  .radar-canvas {
    height: 20rem;
  }
}
/* which frame is on the map, over its top left corner: the time, and observed or forecast in words with an icon; a forecast has a dashed edge as the player's has */
.radar-chip {
  position: absolute;
  z-index: 1001;
  inset-inline-start: 0.75rem;
  top: 0.75rem;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--ui-border-accented);
  border-radius: 999px;
  background: var(--ui-bg);
  color: var(--ui-text-highlighted);
  font-size: 0.8125rem;
  font-weight: 600;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.15);
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.radar-chip[data-kind="forecast"] {
  border-style: dashed;
  border-width: 2px;
}

/* The panel: a card beside the map; under it on a phone */
.radar-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}
.radar-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2.5);
  background: var(--ui-bg);
}
.radar-card > :where(div, figure, ul) {
  align-self: stretch;
}
.radar-card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.radar-card-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--ui-text-toned);
}
.radar-card-note {
  font-size: 0.875rem;
  color: var(--ui-text-muted);
}
.radar-note-row {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
}
.radar-warning {
  color: var(--ui-text-toned);
}
/* in the narrow layout the cards run edge to edge, as the map tool's do */
@media screen and (width < 40rem) {
  .radar-card {
    margin-inline: -1rem;
    padding-inline: 1rem;
    border-radius: 0;
    border-inline-width: 0;
  }
}
</style>
