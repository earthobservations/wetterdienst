<script setup lang="ts">
import type { PollenAnswer, UvAnswer } from '~/composables/useUvPollen'
import type { PollenType } from '~/utils/uv-pollen'
import { DateTime } from 'luxon'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { formatDayMonth, weekdayShort } from '~/utils/format'
import { dayOfRow, daysFromToday, forecastDays, hasNoForecast, isOutOfSeason, POLLEN_TYPES, pollenClass, pollenFill, pollenParameter, rememberedPart, rememberPart, selectedPart, UV_COLORS, uvClass } from '~/utils/uv-pollen'

// The "UV & pollen" panel of the Forecast (GH-4501), below the meteogram of a station in Germany: DWD's UV index of the nearest of its 38
// places, and the pollen load of the part-regions of the station's state, each for today, tomorrow and the day after. Each part is
// its own request (`useUvPollen`), so that the panel shows what has come: a part that failed or has nothing to say is not there, and
// without either, neither is the panel.
//
// Nothing is told by colour alone (WCAG 1.4.1): the UV index is a number with its WHO class in words, the pollen load is a bar with
// DWD's name of the class beside it, and a day with no value is a dash that a screen reader reads as "no value".
const props = defineProps<{
  uv: UvAnswer | null
  pollen: PollenAnswer | null
  /** The time zone of the station: which date is Today. DWD's days are German calendar dates, which is the station's date for any station in Germany */
  zone: string
}>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()

// the date it is today at the station, a computed of its own so that what reads it runs again at midnight and not with each tick
const now = ref(Date.now())
const today = computed(() => DateTime.fromMillis(now.value, { zone: props.zone }).toISODate()!)
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  clock = setInterval(() => {
    now.value = Date.now()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(clock))

interface DayHead {
  day: string
  /** `Today`, `Tomorrow`, or the weekday */
  label: string
  /** `27.11.` */
  date: string
}

function headOf(day: string): DayHead {
  const away = daysFromToday(day, today.value)
  const date = DateTime.fromISO(day)
  return {
    day,
    label: away === 0 ? t('uvPollen.today') : away === 1 ? t('uvPollen.tomorrow') : weekdayShort(date, formatLanguage.value),
    date: formatDayMonth(date, formatLanguage.value),
  }
}

// ---- the UV index ----
const uvDays = computed(() => {
  if (!props.uv)
    return []
  const rows = props.uv.rows
  return forecastDays(rows, today.value).map((day) => {
    const value = rows.find(row => dayOfRow(row) === day)?.value ?? null
    const index = value === null ? null : Math.round(value)
    const cls = uvClass(value)
    return { ...headOf(day), index, cls, colors: cls ? UV_COLORS[cls] : null }
  })
})

// ---- the pollen load ----
const chosen = ref<string | null>(null)
// the choice remembered for the state, read when its answer comes (a different state is another memory)
watch(() => props.pollen?.state, (state) => {
  chosen.value = state ? rememberedPart(state) : null
}, { immediate: true })
const part = computed(() => props.pollen ? selectedPart(props.pollen.parts, chosen.value) : null)

const chips: (HTMLButtonElement | null)[] = []

/** The arrow keys, Home and End move the choice along the chips, round the ends, and the focus with it */
function onChipKey(event: KeyboardEvent, index: number) {
  const parts = props.pollen?.parts ?? []
  const last = parts.length - 1
  const target = event.key === 'ArrowRight' || event.key === 'ArrowDown'
    ? (index + 1) % (last + 1)
    : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
      ? (index + last) % (last + 1)
      : event.key === 'Home' ? 0 : event.key === 'End' ? last : -1
  if (target < 0)
    return
  event.preventDefault()
  choose(parts[target]!.id)
  void nextTick(() => chips[target]?.focus())
}

function choose(id: string) {
  chosen.value = id
  if (props.pollen)
    rememberPart(props.pollen.state, id)
}

const pollenDays = computed(() => props.pollen ? forecastDays(props.pollen.rows, today.value) : [])
const partRows = computed(() => {
  const days = new Set(pollenDays.value)
  return props.pollen && part.value
    ? props.pollen.rows.filter(row => row.station_id === part.value!.id && days.has(dayOfRow(row) ?? ''))
    : []
})
// what the selected part has to say: a grid, or one line: that no load is expected (every level is 0, as DWD writes it out of season),
// or that DWD gives nothing for it (no row, or no value at all, which is not a 0: a sibling part may have rows while this one has none)
const outOfSeason = computed(() => isOutOfSeason(partRows.value))
const noForecast = computed(() => hasNoForecast(partRows.value))
const pollenHeads = computed(() => pollenDays.value.map(headOf))
const pollenGrid = computed(() => POLLEN_TYPES.map(type => ({
  type,
  cells: pollenDays.value.map((day) => {
    const level = partRows.value.find(row => row.parameter === pollenParameter(type) && dayOfRow(row) === day)?.value ?? null
    return { day, level, cls: pollenClass(level), fill: pollenFill(level) }
  }),
})))

const hasUv = computed(() => !!props.uv && uvDays.value.length > 0)
const hasPollen = computed(() => !!props.pollen && !!part.value && pollenDays.value.length > 0)

const titleId = useId()
const uvTitleId = useId()
const pollenTitleId = useId()
const typeName = (type: PollenType) => t(`uvPollen.pollen.type.${type}`)
</script>

<template>
  <section v-if="hasUv || hasPollen" :aria-labelledby="titleId" class="rounded-xl border border-gray-200 dark:border-gray-800 bg-default shadow-sm p-4 space-y-5" data-testid="uv-pollen-panel">
    <h3 :id="titleId" class="flex items-center gap-2 text-base font-bold text-highlighted">
      <UIcon name="i-ph-sun-horizon" class="size-5 shrink-0 text-primary-600 dark:text-primary-500" aria-hidden="true" />
      {{ t('uvPollen.title') }}
    </h3>

    <!-- the UV index of the nearest place: the number in the colour of its WHO class, and the class in words under it -->
    <section v-if="hasUv && uv" :aria-labelledby="uvTitleId" data-testid="uv-part">
      <h4 :id="uvTitleId" class="text-sm font-semibold text-highlighted">
        {{ t('uvPollen.uv.title', { place: uv.place.station.name ?? uv.place.station.station_id, km: Math.round(uv.place.distanceKm) }) }}
      </h4>
      <ul class="mt-2 grid grid-cols-3 gap-2 sm:gap-3 list-none p-0 m-0" data-testid="uv-days">
        <li v-for="d in uvDays" :key="d.day" class="min-w-0 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/40 px-1.5 py-2 text-center" data-testid="uv-day">
          <div class="text-xs font-semibold text-toned">
            {{ d.label }}
          </div>
          <div class="text-xs text-muted tabular-nums">
            {{ d.date }}
          </div>
          <div
            class="mx-auto mt-1.5 flex size-10 items-center justify-center rounded-full text-lg font-extrabold tabular-nums ring-1 ring-black/30 dark:ring-white/40"
            :class="d.colors ? '' : 'bg-gray-100 dark:bg-gray-800 text-toned'"
            :style="d.colors ? { backgroundColor: d.colors.fill, color: d.colors.text } : undefined"
            data-testid="uv-index"
          >
            <span class="sr-only">{{ t('uvPollen.uv.index') }}{{ ' ' }}</span>
            <template v-if="d.index !== null">
              {{ d.index }}
            </template>
            <template v-else>
              <span aria-hidden="true">–</span><span class="sr-only">{{ t('uvPollen.noValue') }}</span>
            </template>
          </div>
          <div v-if="d.cls" class="mt-1 text-xs font-semibold text-highlighted" data-testid="uv-class">
            {{ t(`uvPollen.uv.class.${d.cls}`) }}
          </div>
        </li>
      </ul>
      <p class="mt-2 text-xs text-muted" data-testid="uv-credit">
        {{ t('uvPollen.uv.credit') }}
      </p>
    </section>

    <!-- the pollen load of the part-regions of the state: chips for the parts, the grid of the selected one, or a line where there is no load -->
    <section v-if="hasPollen && pollen && part" :aria-labelledby="pollenTitleId" data-testid="pollen-part">
      <h4 :id="pollenTitleId" class="text-sm font-semibold text-highlighted">
        {{ t('uvPollen.pollen.title', { state: pollen.state }) }}
      </h4>
      <!-- one choice out of a few: a radio group, with one stop of Tab (the chosen chip); the arrow keys move along it and choose, Home and End go to the ends -->
      <div class="mt-2 flex flex-wrap gap-2" role="radiogroup" :aria-label="t('uvPollen.pollen.regions', { state: pollen.state })" data-testid="pollen-chips">
        <button
          v-for="(p, index) in pollen.parts"
          :key="p.id"
          :ref="(element) => { chips[index] = element as HTMLButtonElement | null }"
          type="button"
          role="radio"
          :aria-checked="p.id === part.id"
          :tabindex="p.id === part.id ? 0 : -1"
          :data-part="p.id"
          class="inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-start text-sm leading-snug transition-colors cursor-pointer"
          :class="p.id === part.id
            ? 'border-primary-600 dark:border-primary-400 bg-primary-50 dark:bg-primary-950/40 font-semibold text-highlighted'
            : 'border-gray-300 dark:border-gray-700 bg-transparent text-toned hover:bg-gray-100 dark:hover:bg-gray-800'"
          @click="choose(p.id)"
          @keydown="onChipKey($event, index)"
        >
          <!-- the chosen chip has a check as well as a colour -->
          <UIcon v-if="p.id === part.id" name="i-ph-check-bold" class="size-3.5 shrink-0" aria-hidden="true" />
          <span class="min-w-0">{{ p.label }}</span>
        </button>
      </div>

      <p v-if="noForecast" class="mt-3 flex items-start gap-2 text-sm text-toned" data-testid="pollen-no-forecast">
        <UIcon name="i-ph-flower-tulip" class="mt-0.5 size-4 shrink-0 text-muted" aria-hidden="true" />
        {{ t('uvPollen.pollen.noForecast') }}
      </p>
      <p v-else-if="outOfSeason" class="mt-3 flex items-start gap-2 text-sm text-toned" data-testid="pollen-out-of-season">
        <UIcon name="i-ph-flower-tulip" class="mt-0.5 size-4 shrink-0 text-muted" aria-hidden="true" />
        {{ t('uvPollen.pollen.outOfSeason') }}
      </p>
      <table v-else class="mt-3 w-full table-fixed border-collapse text-sm" data-testid="pollen-grid">
        <caption class="sr-only">
          {{ t('uvPollen.pollen.caption', { region: part.label }) }}
        </caption>
        <thead>
          <tr>
            <th scope="col" class="w-[27%] pb-1.5 pe-2 text-start align-bottom text-xs font-semibold text-muted">
              {{ t('uvPollen.pollen.typeHeader') }}
            </th>
            <th v-for="h in pollenHeads" :key="h.day" scope="col" class="pb-1.5 px-1 text-center align-bottom font-normal">
              <span class="block text-xs font-semibold text-toned">{{ h.label }}</span>
              <span class="block text-xs text-muted tabular-nums">{{ h.date }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in pollenGrid" :key="row.type" class="border-t border-gray-200 dark:border-gray-800" data-testid="pollen-row">
            <th scope="row" class="py-1.5 pe-2 text-start align-middle text-sm font-medium text-highlighted">
              {{ typeName(row.type) }}
            </th>
            <td v-for="cell in row.cells" :key="cell.day" class="px-1 py-1.5 text-center align-middle" data-testid="pollen-cell">
              <template v-if="cell.cls">
                <!-- three segments, each of a step of 1: a level of 1.5 fills one and a half -->
                <span class="mx-auto mb-1 flex w-full max-w-14 gap-0.5" aria-hidden="true">
                  <span v-for="i in 3" :key="i" class="h-1.5 flex-1 overflow-hidden rounded-sm bg-gray-200 dark:bg-gray-700">
                    <span class="block h-full bg-orange-600 dark:bg-orange-400" :style="{ width: `${Math.min(1, Math.max(0, cell.fill * 3 - (i - 1))) * 100}%` }" />
                  </span>
                </span>
                <span class="block text-xs leading-tight text-toned" data-testid="pollen-class">{{ t(`uvPollen.pollen.level.${cell.cls}`) }}</span>
              </template>
              <template v-else>
                <span class="text-muted" aria-hidden="true">–</span><span class="sr-only">{{ t('uvPollen.noValue') }}</span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="mt-2 text-xs text-muted" data-testid="pollen-credit">
        {{ t('uvPollen.pollen.credit') }}
      </p>
    </section>
  </section>
</template>
