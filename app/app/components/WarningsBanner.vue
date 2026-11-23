<script setup lang="ts">
import { useWarnings } from '~/composables/useWarnings'
import { termsOfProvider } from '~/utils/provider-credit'
import { formatFrameTime } from '~/utils/radar'
import { timestampDate } from '~/utils/timestamp'
import { inWarningBox, warningsAt, withoutOutline } from '~/utils/warnings'

// The warnings of DWD that are in force or announced for a position (GH-4295), as a banner: in the Forecast, over the chart of the station,
// and in the map's panel, over the cards of the station picked. The position is told to be in a warning only by the polygon of the warning, tested
// here against the snapshot the page holds (`warningsAt`). The warnings that DWD gives by area name alone (the sea, a coast: the community product
// has no polygon for them) cannot be placed, so nothing is said of them for the position, except that there are some and where they are listed
// (the map's list). Outside DWD's box (Germany and the sea round it) no warnings source covers the place: there is no banner at all (GH-4328), since a
// box that says "nothing here" on every foreign station looks like an alert and takes the best space of a phone for a message nobody acts on, and nothing
// is asked for. The Forecast's credits say instead that its warnings are Germany's only (`meteogram.warningsNote`).
//
// It is one line where there is nothing to read (loading, a failure, a quiet day), so that a quiet day does not push the chart
// down: "No DWD warning for this position · Checked: 14:07 · Source: Deutscher Wetterdienst", with a button for the notes, the licence and the processing note. A
// warning for the position opens it to its title, its rows and the full notes. The summary is a polite status (`role="status"`), which a screen
// reader says when it comes or changes and never as an interruption; it carries no time, so a refresh that changes nothing is not said again.
// `source` is the page's own polled snapshot (the map's, which also draws it); with none, the banner asks for the snapshot itself.

const props = withDefaults(defineProps<{
  point: { latitude: number, longitude: number }
  source?: ReturnType<typeof useWarnings>
  /** Makes the ids unique where the page has more than one banner */
  idPrefix?: string
  /** Offers the map's list for the warnings that name only an area (the Forecast has no list of its own) */
  mapLink?: boolean
}>(), { source: undefined, idPrefix: 'warnings-banner', mapLink: false })

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
const { data: providerList } = useProviders()
const covered = computed(() => inWarningBox(props.point))
// nothing is asked for a place DWD does not warn for
const data = props.source ?? useWarnings(() => covered.value)

const here = computed(() => data.snapshot.value ? warningsAt(data.snapshot.value.warnings, props.point, data.now.value) : [])
const namedOnly = computed(() => data.snapshot.value ? withoutOutline(data.snapshot.value.warnings, data.now.value).length : 0)

const status = computed(() => {
  if (data.snapshot.value)
    return here.value.length ? 'some' : 'none'
  return data.status.value === 'error' ? 'error' : 'loading'
})
const compact = computed(() => status.value !== 'some')
const summary = computed(() => {
  switch (status.value) {
    case 'some': return t('warnings.bannerSome', { count: here.value.length })
    case 'none': return t('warnings.bannerNoneShort')
    case 'error': return t('warnings.bannerFailed')
    default: return t('warnings.bannerLoading')
  }
})
/** When the snapshot in hand was asked for, in the reader's zone */
const checked = computed(() => {
  const at = data.snapshot.value?.retrievedAt ? timestampDate(data.snapshot.value.retrievedAt) : null
  return at ? formatFrameTime(at.getTime(), formatLanguage.value, data.now.value) : ''
})
/** DWD's credit line, from the answer's own terms, else from the list of providers */
const attribution = computed(() => data.snapshot.value?.credit?.attribution ?? termsOfProvider(providerList.value?.providers, 'dwd')?.attribution ?? 'Deutscher Wetterdienst')
const titleId = computed(() => `${props.idPrefix}-title`)
const detailsId = computed(() => `${props.idPrefix}-details`)
const detailsOpen = ref(false)
</script>

<template>
  <section v-if="covered" class="warnings-banner" :class="[`warnings-banner-${status}`, { 'warnings-banner-compact': compact }]" :aria-labelledby="titleId" data-testid="warnings-banner">
    <!-- the title is the section's name for a screen reader; it is seen where there is a warning to read under it -->
    <h3 :id="titleId" class="warnings-banner-title" :class="{ 'sr-only': compact }">
      <UIcon name="i-ph-warning" class="warnings-banner-icon" aria-hidden="true" />
      {{ t('warnings.bannerTitle') }}
    </h3>
    <UIcon v-if="compact" name="i-ph-warning" class="warnings-banner-icon" aria-hidden="true" />
    <!-- in the page from the start, so that a change of its text is announced -->
    <p class="text-sm text-toned" role="status" data-testid="warnings-banner-summary">
      {{ summary }}
    </p>

    <UButton v-if="status === 'error'" :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="data.retry()" />

    <!-- a quiet day, in the line: when it was asked, whose it is, and a button for the notes -->
    <template v-if="status === 'none'">
      <span v-if="checked" class="warnings-banner-note" data-testid="warnings-banner-checked">· {{ t('warnings.checked', { time: checked }) }}</span>
      <span class="warnings-banner-note" data-testid="warnings-banner-attribution">· {{ attribution }}</span>
      <!-- an icon with a name (a line that is one line is the point of it): "About these warnings", with the state of the notes it opens -->
      <button type="button" class="warnings-banner-details-button" :aria-label="t('warnings.bannerDetails')" :title="t('warnings.bannerDetails')" :aria-expanded="detailsOpen" :aria-controls="detailsId" data-testid="warnings-banner-details-button" @click="detailsOpen = !detailsOpen">
        <UIcon name="i-ph-info" class="size-5" aria-hidden="true" />
        <UIcon :name="detailsOpen ? 'i-ph-caret-up' : 'i-ph-caret-down'" class="size-3.5" aria-hidden="true" />
      </button>
    </template>

    <template v-if="status === 'some' || status === 'none'">
      <WarningsList v-if="here.length" :warnings="here" :now="data.now.value" :label="t('warnings.bannerListLabel')" :id-prefix="idPrefix" />
      <p v-if="namedOnly" class="warnings-banner-note warnings-banner-wide" data-testid="warnings-banner-named">
        {{ t('warnings.bannerNamedOnly', { count: namedOnly }) }}
        <NuxtLink v-if="mapLink" to="/map?warnings=1" class="underline underline-offset-2" data-testid="warnings-banner-map">
          {{ t('warnings.bannerOpenMap') }}
        </NuxtLink>
      </p>
      <!-- a refresh that failed and a snapshot that is old are two things, and both are said where both hold -->
      <p v-if="data.refreshFailed.value" class="warnings-banner-note warnings-banner-wide" data-testid="warnings-banner-refresh-failed">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.refreshFailed', { time: checked }) }}
      </p>
      <p v-if="data.stale.value" class="warnings-banner-note warnings-banner-wide" data-testid="warnings-banner-stale">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.stale', { time: checked }) }}
      </p>
      <!-- the notes of a quiet day are behind the button; with a warning they are here -->
      <div v-show="status === 'some' || detailsOpen" :id="detailsId" class="warnings-banner-details" data-testid="warnings-banner-details">
        <p v-if="status === 'none'" class="warnings-banner-note">
          {{ t('warnings.bannerNone') }}
        </p>
        <p v-if="status === 'some' && checked" class="warnings-banner-note" data-testid="warnings-banner-checked">
          {{ t('warnings.checked', { time: checked }) }}
        </p>
        <p class="warnings-banner-note">
          {{ t('warnings.coverage') }}
        </p>
        <ProviderCredit provider="dwd" fallback="Deutscher Wetterdienst" :terms="data.snapshot.value?.credit ?? null" compact />
      </div>
    </template>
  </section>
</template>

<style>
.warnings-banner {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.75rem 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2.5);
  background: var(--ui-bg);
}
.warnings-banner > :where(ul, div, p) {
  align-self: stretch;
}
/* one line where there is nothing to read, and the same height while it loads, so that a quiet day moves nothing under it */
.warnings-banner-compact {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.5rem;
  /* the height of the quiet line with its 44 px button: the loading line is as high, so that nothing under the banner moves */
  min-height: 3.375rem;
  padding: 0.25rem 0.75rem;
}
/* in the line the parts are centred on it (the column layout stretches them) */
.warnings-banner-compact > p,
.warnings-banner-compact > span,
.warnings-banner-compact > button {
  align-self: center;
}
.warnings-banner-compact > .warnings-banner-wide,
.warnings-banner-compact > .warnings-banner-details {
  flex: 1 0 100%;
}
.warnings-banner-details {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  align-items: flex-start;
}
.warnings-banner-details-button {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  justify-content: center;
  min-width: 2.75rem;
  min-height: 2.75rem;
  margin-inline-start: auto;
  color: var(--ui-text-toned);
  cursor: pointer;
}
/* a position with warnings has a heavier edge: the colour of the levels is on the rows' marks, not on the banner */
.warnings-banner-some {
  border-color: var(--ui-border-accented);
  border-width: 2px;
}
.warnings-banner-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.warnings-banner-icon {
  flex: none;
  width: 1.25rem;
  height: 1.25rem;
  color: var(--ui-text-toned);
}
.warnings-banner-note {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.25rem 0.375rem;
  font-size: 0.8125rem;
  color: var(--ui-text-muted);
}
span.warnings-banner-note {
  display: inline;
}
</style>
