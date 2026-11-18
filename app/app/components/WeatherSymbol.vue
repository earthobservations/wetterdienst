<script setup lang="ts">
import type { WeatherKind } from '~/utils/weather-kind'
import type { Sky } from '~/utils/weather-symbols'
import { yrSymbolFor, yrSymbolUrl } from '~/utils/weather-symbols'

// The weather of a day card as the chart draws the weather of an hour: Yr's symbol, in the light or the dark set of the page
// (GH-4193). A card is a whole day, so there is no night variant. The symbol is a picture only and is hidden from assistive technology:
// the card holds the words for the weather (`meteogram.chart.weather.<kind>`, WCAG 1.1.1). It is an `<img>` and not a mask, so it keeps its
// colours in print (an image is printed whatever the setting for backgrounds says) and in forced colours (`forced-color-adjust: none`)

const props = defineProps<{
  kind: WeatherKind
  /** the sky of the day from its cloud cover, for the kinds that say nothing of it (wind, dust, a funnel cloud) */
  sky: Sky
  /** the rain of the day in millimetres, which tells a light rain from a heavy one; null where unknown */
  precipitationMm: number | null
}>()

// the theme of the charts: it follows a switch of the scheme without a reload, and is the light one while a page is printed
const { isDark } = useChartTheme()

const symbol = computed(() => yrSymbolFor({ kind: props.kind, night: false, precipitationMm: props.precipitationMm, sky: props.sky }))
const src = computed(() => yrSymbolUrl(symbol.value, isDark.value))
</script>

<template>
  <img :src="src" alt="" aria-hidden="true" class="weather-symbol shrink-0 object-contain" :data-weather="kind" :data-symbol="symbol">
</template>

<style scoped>
.weather-symbol {
  /* the symbols are coloured pictures: kept as they are drawn in a print without background graphics and in a contrast theme */
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
  forced-color-adjust: none;
}
</style>
