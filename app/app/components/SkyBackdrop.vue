<script setup lang="ts">
/**
 * The sky behind the header and the head of the page (GH-3518): a gradient in the colours of the time of
 * day at the visitor's place and of its weather (main.css, `.wd-sky`), and on wide screens a drawing of it
 * in the logo's shapes, the sun with its eight rays, clouds, rain, snow, the moon and stars. Decoration:
 * nothing in it is read out, it takes no pointer, and it is not printed or drawn in forced colours.
 */
const props = withDefaults(defineProps<{
  /** The home page's band is taller: its search sits in the sky */
  tall?: boolean
}>(), { tall: false })

const { phase, weather } = useSky()

const showSun = computed(() => (phase.value === 'day' || phase.value === 'dawn' || phase.value === 'dusk') && (weather.value === 'clear' || weather.value === 'partly'))
const showMoon = computed(() => phase.value === 'night' && (weather.value === 'clear' || weather.value === 'partly'))
const showStars = computed(() => showMoon.value)
const clouds = computed(() => {
  switch (weather.value) {
    case 'partly':
      return 1
    case 'cloudy':
    case 'rain':
    case 'snow':
    case 'storm':
      return 2
    default:
      return 0
  }
})
const heavy = computed(() => weather.value === 'rain' || weather.value === 'storm')
// the sun stands lower in the morning and the evening
const sunY = computed(() => (phase.value === 'day' ? 62 : 104))
const sunFill = computed(() => (phase.value === 'dusk' ? 'color-mix(in oklab, var(--color-sun) 55%, var(--color-ember))' : 'var(--color-sun)'))
const rays = Array.from({ length: 8 }, (_, i) => {
  const angle = i * Math.PI / 4
  return { x1: Math.cos(angle) * 40, y1: Math.sin(angle) * 40, x2: Math.cos(angle) * 52, y2: Math.sin(angle) * 52 }
})
const stars: Array<[number, number]> = [[40, 30], [96, 18], [150, 52], [20, 92], [128, 110], [300, 150], [70, 150]]
const drops: Array<[number, number]> = [[0, 0], [22, 6], [44, 0], [66, 6], [88, 0]]
const flakes: Array<[number, number]> = [[0, 0], [24, 10], [48, 0], [72, 10], [96, 0], [12, 26], [60, 26]]
const maskId = useId()
</script>

<template>
  <div
    class="wd-sky pointer-events-none absolute inset-x-0 top-0 -z-10 overflow-hidden"
    :class="props.tall ? 'h-[40rem] sm:h-[36rem]' : 'h-[22rem]'"
    :data-phase="phase"
    :data-weather="weather"
    aria-hidden="true"
  >
    <svg
      class="wd-sky-art absolute hidden lg:block top-[4.5rem] right-[max(var(--wd-gutter),calc((100vw-90rem)/2+var(--wd-gutter)))] w-72 h-48"
      viewBox="0 0 320 210"
      focusable="false"
    >
      <defs>
        <mask :id="maskId">
          <rect width="320" height="210" fill="#fff" />
          <circle cx="246" cy="52" r="26" fill="#000" />
        </mask>
      </defs>
      <g v-if="showStars" class="fill-brand-300 dark:fill-ink-200">
        <circle v-for="([x, y], i) in stars" :key="i" :cx="x" :cy="y" :r="i % 3 === 0 ? 2.4 : 1.6" />
      </g>
      <circle v-if="showMoon" cx="232" cy="64" r="34" class="fill-brand-200 dark:fill-ink-200" :mask="`url(#${maskId})`" />
      <g v-if="showSun" :transform="`translate(230 ${sunY})`">
        <circle r="30" :style="{ fill: sunFill }" />
        <line
          v-for="(ray, i) in rays" :key="i" :x1="ray.x1" :y1="ray.y1" :x2="ray.x2" :y2="ray.y2"
          :style="{ stroke: sunFill }" stroke-width="9" stroke-linecap="round"
        />
      </g>
      <g v-if="clouds >= 1" :class="heavy ? 'fill-ink-300 dark:fill-ink-700' : 'fill-white dark:fill-ink-600'" opacity="0.95">
        <rect x="150" y="96" width="132" height="44" rx="22" />
        <circle cx="190" cy="94" r="28" />
        <circle cx="232" cy="88" r="34" />
      </g>
      <g v-if="clouds >= 2" :class="heavy ? 'fill-ink-400 dark:fill-ink-800' : 'fill-white/80 dark:fill-ink-700'">
        <rect x="70" y="54" width="104" height="36" rx="18" />
        <circle cx="102" cy="52" r="22" />
        <circle cx="136" cy="46" r="27" />
      </g>
      <g v-if="weather === 'rain' || weather === 'storm'" class="stroke-brand-400" stroke-width="5" stroke-linecap="round">
        <line v-for="([x, y], i) in drops" :key="i" :x1="172 + x" :y1="154 + y" :x2="164 + x" :y2="176 + y" />
      </g>
      <polygon v-if="weather === 'storm'" points="214,140 196,174 212,174 202,204 234,162 216,162 226,140" style="fill: var(--color-sun)" />
      <g v-if="weather === 'snow'" class="fill-brand-300 dark:fill-ink-200">
        <circle v-for="([x, y], i) in flakes" :key="i" :cx="170 + x" :cy="158 + y" r="5" />
      </g>
      <g v-if="weather === 'fog'" class="stroke-ink-300 dark:stroke-ink-600" stroke-width="12" stroke-linecap="round">
        <line x1="120" y1="80" x2="290" y2="80" />
        <line x1="90" y1="112" x2="260" y2="112" />
        <line x1="140" y1="144" x2="300" y2="144" />
      </g>
    </svg>
  </div>
</template>
