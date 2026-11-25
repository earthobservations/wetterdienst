<script setup lang="ts">
import type { useWarnings } from '~/composables/useWarnings'
import { formatNumber } from '~/utils/format'
import { formatFrameTime } from '~/utils/radar'
import { timestampDate } from '~/utils/timestamp'
import { drawn, withoutOutline } from '~/utils/warnings'

// The warnings of the map's layer (GH-4295), in the panel beside the map (under it on a phone): the list of every warning in force or
// announced in Germany, the most severe first, each a row that opens to DWD's own words and, opened, is drawn stronger on the map; and under
// it the warnings for areas the map cannot draw, which DWD names (the sea, a coast) and gives no outline, and which are listed and never given
// an outline of ours. It is the keyboard's and the screen reader's way to a warning, which the polygons on the map cannot be (the
// map pans by its keys; a polygon is no stop). With the layer off nothing is asked for.

const props = defineProps<{
  source: ReturnType<typeof useWarnings>
  /** The warning picked, which the map draws stronger */
  focused: string | null
}>()

defineEmits<{ focus: [id: string | null] }>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
const data = props.source

/** How many the list shows before "Show all": a day of storms has some hundred, which would push the stations out of the panel */
const LIST_LIMIT = 12
const showAll = ref(false)

const onMap = computed(() => data.snapshot.value ? drawn(data.snapshot.value.warnings, data.now.value) : [])
const aside = computed(() => data.snapshot.value ? withoutOutline(data.snapshot.value.warnings, data.now.value) : [])
const total = computed(() => onMap.value.length + aside.value.length)
const shown = computed(() => showAll.value ? onMap.value : onMap.value.slice(0, LIST_LIMIT))
const count = (value: number) => formatNumber(value, formatLanguage.value, 0)

const summary = computed(() => {
  if (data.snapshot.value)
    return total.value ? t('warnings.panelCount', { count: count(total.value) }) : t('warnings.panelNone')
  return data.status.value === 'error' ? '' : t('warnings.panelLoading')
})
const checked = computed(() => {
  const at = data.snapshot.value?.retrievedAt ? timestampDate(data.snapshot.value.retrievedAt) : null
  return at ? formatFrameTime(at.getTime(), formatLanguage.value, data.now.value) : ''
})
</script>

<template>
  <section class="warnings-panel" aria-labelledby="warnings-panel-title" data-testid="warnings-panel">
    <h3 id="warnings-panel-title" class="warnings-panel-title">
      <UIcon name="i-ph-warning" class="size-5 text-toned" aria-hidden="true" />
      {{ t('warnings.panelTitle') }}
    </h3>
    <!-- in the page from the start, and empty (screen-reader-only) while it is: a live region inserted with its text is not announced. No time in it: a refresh that changes nothing says nothing -->
    <p class="text-sm font-semibold text-highlighted empty:sr-only" role="status" data-testid="warnings-panel-summary">
      {{ summary }}
    </p>

    <div v-if="data.status.value === 'error' && !data.snapshot.value" class="flex flex-col items-start gap-2">
      <p class="text-sm text-muted" role="alert" data-testid="warnings-failed">
        {{ t('warnings.failed') }}
      </p>
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="warnings-retry" @click="data.retry()" />
    </div>

    <template v-else-if="data.snapshot.value">
      <p v-if="data.refreshFailed.value" class="warnings-panel-note" data-testid="warnings-refresh-failed">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.refreshFailed', { time: checked }) }}
      </p>
      <p v-if="data.stale.value" class="warnings-panel-note" data-testid="warnings-stale">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.stale', { time: checked }) }}
      </p>

      <WarningsList
        v-if="onMap.length"
        :warnings="shown"
        :now="data.now.value"
        :focused="focused"
        :label="t('warnings.listLabel')"
        id-prefix="warnings-map"
        announce-focus
        @focus="$emit('focus', $event)"
      />
      <UButton
        v-if="onMap.length > LIST_LIMIT"
        :label="showAll ? t('warnings.showFewer') : t('warnings.showAll', { count: count(onMap.length) })"
        :icon="showAll ? 'i-ph-caret-up' : 'i-ph-caret-down'"
        color="neutral"
        variant="ghost"
        size="sm"
        class="-ms-2 self-start"
        :aria-expanded="showAll"
        data-testid="warnings-more"
        @click="showAll = !showAll"
      />

      <div v-if="aside.length" class="warnings-aside" data-testid="warnings-aside">
        <h4 class="font-semibold text-highlighted">
          {{ t('warnings.asideTitle') }}
        </h4>
        <p class="text-sm text-muted">
          {{ t('warnings.asideNote') }}
        </p>
        <WarningsList :warnings="aside" :now="data.now.value" :label="t('warnings.asideTitle')" id-prefix="warnings-aside" />
      </div>

      <p v-if="checked" class="warnings-panel-note" data-testid="warnings-checked">
        {{ t('warnings.checked', { time: checked }) }} {{ t('warnings.refreshNote') }}
      </p>
      <ProviderCredit provider="dwd" fallback="Deutscher Wetterdienst" :terms="data.snapshot.value.credit" compact />
    </template>
  </section>
</template>

<style>
.warnings-panel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2.5);
}
.warnings-panel > :where(ul, div, p) {
  align-self: stretch;
}
.warnings-panel-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.warnings-panel-note {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
  font-size: 0.8125rem;
  color: var(--ui-text-muted);
}
.warnings-aside {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--ui-border);
}
</style>
