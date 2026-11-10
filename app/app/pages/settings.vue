<script setup lang="ts">
import type { UnitSettings } from '~/composables/useSettings'
import { UNIT_TARGET_TYPES } from '~/utils/unit-targets'

const { t, locale, setLocale } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('settings.title') })
const colorMode = useColorMode()
const { settings, reset } = useSettings()
const route = useRoute()

// the Menu's sheet links to the chooser of the phone's bar (`/settings#bar`): the page scrolls to it, and the focus
// goes to its heading, so that a keyboard and a screen reader are where the page has taken the eyes (WCAG 2.4.3). The
// scroll is made here as well as by the router, which does not make it on a first load of the address, as the page is
// drawn after the browser looked for the anchor
const barHeading = useTemplateRef<HTMLElement>('barHeading')
function focusBar() {
  if (route.hash !== '#bar')
    return
  nextTick(() => {
    barHeading.value?.scrollIntoView({ block: 'start' })
    barHeading.value?.focus({ preventScroll: true })
  })
}
onMounted(focusBar)
watch(() => route.hash, focusBar)

const languageItems = languageSelectItems()
const selectedLanguage = computed({
  get: () => locale.value,
  set: (v: string) => setLocale(v as typeof locale.value),
})

// a unit's name is read in full, in the trigger and in the list (which is as wide as the trigger)
const unitSelectUi = { value: 'whitespace-normal text-left', itemLabel: 'whitespace-normal' }
const themeOptions = computed(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-ph-monitor' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-ph-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-ph-moon' },
])

// The unit choices this page offers and stores are the ones the requests of the Explorer send (GH-3878), from the
// one list of `UNIT_TARGET_TYPES`, which also says which types and units are left out.
const weatherUnitGroups = UNIT_TARGET_TYPES.filter(unitType => unitType.group === 'weather')
const otherUnitGroups = UNIT_TARGET_TYPES.filter(unitType => unitType.group === 'other')

function unitItems(units: readonly string[]) {
  return units.map(u => ({ value: u, label: t(`units.${u}`) }))
}
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('settings.title')" :lede="t('settings.subtitle')" />
    <div class="page-body" data-width="read">
      <!-- Language -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-ph-translate" class="text-primary-600 dark:text-primary-500 shrink-0" />
            <h2 class="text-lg font-bold">
              {{ t('settings.language') }}
            </h2>
          </div>
        </template>
        <USelect
          v-model="selectedLanguage"
          :items="languageItems"
          :aria-label="t('settings.language')"
          class="w-full sm:w-64"
        />
      </UCard>

      <!-- Appearance -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-ph-palette" class="text-primary-600 dark:text-primary-500 shrink-0" />
            <h2 class="text-lg font-bold">
              {{ t('settings.theme') }}
            </h2>
          </div>
        </template>
        <!-- toggle buttons: the chosen theme is told by `aria-pressed`, not by the fill alone (4.1.2, GH-3969) -->
        <UFieldGroup role="group" :aria-label="t('settings.theme')" class="w-full sm:w-auto">
          <UButton
            v-for="opt in themeOptions"
            :key="opt.value"
            :icon="opt.icon"
            :label="opt.label"
            :ui="{ base: 'flex-auto justify-center max-[24rem]:px-1.5 sm:flex-none', leadingIcon: 'max-[24rem]:hidden' }"
            color="neutral"
            :variant="colorMode.preference === opt.value ? 'solid' : 'ghost'"
            :aria-pressed="colorMode.preference === opt.value"
            @click="colorMode.preference = opt.value"
          />
        </UFieldGroup>
      </UCard>

      <!-- The order of the tools: the phone's tab bar and Menu, the wide header (one title for every width, GH-3936) -->
      <!-- not clipped: the preview of the bar stays in view (`position: sticky`) while the rows are dragged under it -->
      <UCard id="bar" :ui="{ root: 'overflow-visible' }">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-ph-sliders-horizontal" class="text-primary-600 dark:text-primary-500 shrink-0" />
            <h2 ref="barHeading" tabindex="-1" class="text-lg font-bold outline-none">
              {{ t('settings.bar.title') }}
            </h2>
          </div>
        </template>
        <TabBarChooser />
      </UCard>

      <!-- Display & data -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-ph-ruler" class="text-primary-600 dark:text-primary-500 shrink-0" />
            <h2 class="text-lg font-bold">
              {{ t('settings.units') }}
            </h2>
          </div>
        </template>
        <div class="space-y-5">
          <div class="flex items-start justify-between gap-4">
            <div>
              <label for="settings-friendly-labels" class="block font-medium">
                {{ t('settings.friendlyLabels') }}
              </label>
              <p class="text-sm text-gray-500 dark:text-gray-400">
                {{ t('settings.friendlyLabelsHint') }}
              </p>
            </div>
            <USwitch id="settings-friendly-labels" v-model="settings.friendlyLabels" />
          </div>

          <USeparator />

          <div class="flex items-start justify-between gap-4">
            <div>
              <label for="settings-convert-units" class="block font-medium">
                {{ t('settings.convertUnits') }}
              </label>
              <p class="text-sm text-gray-500 dark:text-gray-400">
                {{ t('settings.convertUnitsHint') }}
              </p>
            </div>
            <USwitch id="settings-convert-units" v-model="settings.convertUnits" />
          </div>

          <div v-if="settings.convertUnits" class="space-y-5">
            <div class="space-y-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                {{ t('settings.unitsWeather') }}
              </div>
              <div
                v-for="group in weatherUnitGroups"
                :key="group.type"
                class="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <label :for="`settings-unit-${group.type}`" class="text-sm">{{ t(group.label) }}</label>
                <USelect
                  :id="`settings-unit-${group.type}`"
                  v-model="settings.units[group.type as keyof UnitSettings]"
                  :items="unitItems(group.units)"
                  :ui="unitSelectUi"
                  class="w-full sm:w-56"
                />
              </div>
            </div>

            <div class="space-y-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                {{ t('settings.unitsOther') }}
              </div>
              <div
                v-for="group in otherUnitGroups"
                :key="group.type"
                class="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <label :for="`settings-unit-${group.type}`" class="text-sm">{{ t(group.label) }}</label>
                <USelect
                  :id="`settings-unit-${group.type}`"
                  v-model="settings.units[group.type as keyof UnitSettings]"
                  :items="unitItems(group.units)"
                  :ui="unitSelectUi"
                  class="w-full sm:w-56"
                />
              </div>
            </div>
          </div>
        </div>
      </UCard>

      <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{ t('settings.savedHint') }}
        </p>
        <UButton
          :label="t('settings.reset')"
          icon="i-ph-arrow-counter-clockwise"
          color="neutral"
          variant="outline"
          size="sm"
          :ui="{ base: 'max-w-full whitespace-normal text-left', label: 'whitespace-normal' }"
          @click="reset"
        />
      </div>
    </div>
  </div>
</template>
