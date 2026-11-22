<script setup lang="ts">
import { useWarnings } from '~/composables/useWarnings'
import { formatFrameTime } from '~/utils/radar'
import { timestampDate } from '~/utils/timestamp'
import { inWarningBox, warningsAt, withoutOutline } from '~/utils/warnings'

// The warnings of DWD that are in force or announced for a position (GH-4295), as a banner: in the Forecast, over the chart of the station,
// and in the map's panel, over the cards of the station picked. The position is told to be in a warning only by the polygon of the warning, tested
// here against the snapshot the page holds (`warningsAt`). The warnings that DWD gives by area name alone (the sea, a coast: the community product
// has no polygon for them) cannot be placed, so nothing is said of them for the position, except that there are some and where they are listed
// (the map's list). Outside DWD's box (Germany and the sea round it) no warnings source covers the place, which is said plainly.
//
// The summary is a polite status (`role="status"`), which a screen reader says when it comes or changes and never as an interruption; it carries no
// time, so a refresh that changes nothing is not said again. The rows under it open to DWD's texts (WarningEntry.vue). It has the time of
// the latest check and where a refresh failed, the credit and the processing note. `source` is the page's own polled snapshot (the map's, which also
// draws it); with none, the banner asks for the snapshot itself.

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
const data = props.source ?? useWarnings(() => true)

const covered = computed(() => inWarningBox(props.point))
const here = computed(() => data.snapshot.value ? warningsAt(data.snapshot.value.warnings, props.point, data.now.value) : [])
const namedOnly = computed(() => data.snapshot.value ? withoutOutline(data.snapshot.value.warnings, data.now.value).length : 0)

const status = computed(() => {
  if (!covered.value)
    return 'outside'
  if (data.snapshot.value)
    return here.value.length ? 'some' : 'none'
  return data.status.value === 'error' ? 'error' : 'loading'
})
const summary = computed(() => {
  switch (status.value) {
    case 'outside': return t('warnings.bannerOutside')
    case 'some': return t('warnings.bannerSome', { count: here.value.length })
    case 'none': return t('warnings.bannerNone')
    case 'error': return t('warnings.bannerFailed')
    default: return t('warnings.bannerLoading')
  }
})
/** When the snapshot in hand was asked for, in the reader's zone */
const checked = computed(() => {
  const at = data.snapshot.value?.retrievedAt ? timestampDate(data.snapshot.value.retrievedAt) : null
  return at ? formatFrameTime(at.getTime(), formatLanguage.value, data.now.value) : ''
})
const titleId = computed(() => `${props.idPrefix}-title`)
</script>

<template>
  <section class="warnings-banner" :class="`warnings-banner-${status}`" :aria-labelledby="titleId" data-testid="warnings-banner">
    <h3 :id="titleId" class="warnings-banner-title">
      <UIcon name="i-ph-warning" class="warnings-banner-icon" aria-hidden="true" />
      {{ t('warnings.bannerTitle') }}
    </h3>
    <!-- in the page from the start, so that a change of its text is announced -->
    <p class="text-sm text-toned" role="status" data-testid="warnings-banner-summary">
      {{ summary }}
    </p>

    <template v-if="status === 'error'">
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="data.retry()" />
    </template>

    <template v-if="status === 'some' || status === 'none'">
      <WarningsList v-if="here.length" :warnings="here" :now="data.now.value" :label="t('warnings.bannerListLabel')" :id-prefix="idPrefix" />
      <p v-if="namedOnly" class="warnings-banner-note" data-testid="warnings-banner-named">
        {{ t('warnings.bannerNamedOnly', { count: namedOnly }) }}
        <NuxtLink v-if="mapLink" to="/map?warnings=1" class="underline underline-offset-2" data-testid="warnings-banner-map">
          {{ t('warnings.bannerOpenMap') }}
        </NuxtLink>
      </p>
      <p v-if="data.refreshFailed.value" class="warnings-banner-note" data-testid="warnings-banner-refresh-failed">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.refreshFailed', { time: checked }) }}
      </p>
      <p v-else-if="data.stale.value" class="warnings-banner-note" data-testid="warnings-banner-stale">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.stale', { time: checked }) }}
      </p>
      <p v-if="checked" class="warnings-banner-note" data-testid="warnings-banner-checked">
        {{ t('warnings.checked', { time: checked }) }} {{ t('warnings.coverage') }}
      </p>
      <ProviderCredit provider="dwd" fallback="Deutscher Wetterdienst" :terms="data.snapshot.value?.credit ?? null" compact />
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
/* while the snapshot is on its way the banner keeps about the height of the quiet day's, so that the chart under it does not jump much when it arrives */
.warnings-banner-loading {
  min-height: 9rem;
}
/* a position with warnings has a heavier edge, the word of the title says the rest: the colour of the levels is on the rows' marks, not on the banner */
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
</style>
