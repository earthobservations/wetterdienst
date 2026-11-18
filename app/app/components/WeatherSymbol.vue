<script setup lang="ts">
import type { WeatherKind } from '~/utils/weather-kind'
import type { Sky } from '~/utils/weather-symbols'
import { yrSymbolFor, yrSymbolUrl } from '~/utils/weather-symbols'

// The weather of a day card as the chart draws the weather of an hour: Yr's symbol, in the light or the dark set of the page
// (GH-4193). A card is a whole day, so there is no night variant. The symbol is a picture only and is hidden from assistive technology:
// the card holds the words for the weather (`meteogram.chart.weather.<kind>`, WCAG 1.1.1). It is an `<img>` and not a mask, so it keeps its
// colours in print (an image is printed whatever the setting for backgrounds says) and in forced colours (`forced-color-adjust: none`).
// Yr has no symbol for wind, a dust or sand storm or a funnel cloud: they are drawn as the sky of the day with a small badge in its lower
// corner, which says what the sky does not: a sun under a funnel cloud would read as a fine day (GH-3965). The size is the parent's class.

const props = defineProps<{
  kind: WeatherKind
  /** the sky of the day from its cloud cover, which the symbol of the kinds Yr has no symbol for is drawn as */
  sky: Sky
  /** the rate of the day's wettest hour in millimetres an hour, which tells a light rain from a heavy one as an hour's amount does; null where unknown */
  precipitationMm: number | null
}>()

// the Phosphor icons of the badges: literals, which @nuxt/icon bundles with the page
const BADGES: Partial<Record<WeatherKind, string>> = {
  wind: 'i-ph-wind',
  dust: 'i-ph-wind',
  funnelCloud: 'i-ph-tornado',
}

// the theme of the charts: it follows a switch of the scheme without a reload, and is the light one while a page is printed
const { isDark } = useChartTheme()

const symbol = computed(() => yrSymbolFor({ kind: props.kind, night: false, precipitationMm: props.precipitationMm, sky: props.sky }))
const src = computed(() => yrSymbolUrl(symbol.value, isDark.value))
const badge = computed(() => BADGES[props.kind] ?? null)
</script>

<template>
  <span class="weather-symbol relative inline-block shrink-0" aria-hidden="true">
    <img :src="src" alt="" aria-hidden="true" class="size-full object-contain" :data-weather="kind" :data-symbol="symbol">
    <!-- the disc is the page's background, so that the icon reads on the coloured symbol in both modes -->
    <span v-if="badge" class="weather-badge absolute -bottom-0.5 -end-0.5 flex size-[52%] items-center justify-center rounded-full border border-default bg-default" :data-badge="kind">
      <UIcon :name="badge" class="size-[80%] text-highlighted" />
    </span>
  </span>
</template>

<style scoped>
.weather-symbol img,
.weather-badge {
  /* the symbols are coloured pictures and the badge a disc: kept as they are drawn in a print without background graphics and in a contrast theme */
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
  forced-color-adjust: none;
}
</style>
