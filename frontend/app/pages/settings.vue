<script setup lang="ts">
const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { settings, reset } = useSettings()

const languageOptions = [
  { value: 'de', label: 'Deutsch' },
  { value: 'en', label: 'English' },
] as const

const themeOptions = computed(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
])

const explorerModeOptions = computed(() => [
  { value: 'simple', label: t('settings.explorerModeSimple') },
  { value: 'expert', label: t('settings.explorerModeExpert') },
])

// Available units per type (mirrors the backend UnitConverter).
const unitGroups = [
  { key: 'temperature', label: 'settings.unitTemperature', units: ['degree_celsius', 'degree_kelvin', 'degree_fahrenheit'] },
  { key: 'speed', label: 'settings.unitSpeed', units: ['meter_per_second', 'kilometer_per_hour', 'knots', 'beaufort'] },
  { key: 'pressure', label: 'settings.unitPressure', units: ['pascal', 'hectopascal', 'kilopascal'] },
  { key: 'precipitation', label: 'settings.unitPrecipitation', units: ['millimeter', 'liter_per_square_meter'] },
] as const

function unitItems(units: readonly string[]) {
  return units.map(u => ({ value: u, label: t(`units.${u}`) }))
}
</script>

<template>
  <UContainer class="max-w-2xl mx-auto py-8 px-4 space-y-6">
    <div class="flex items-center gap-3">
      <UIcon name="i-lucide-settings" class="text-2xl text-primary-500" />
      <div>
        <h1 class="text-3xl font-bold">
          {{ t('settings.title') }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ t('settings.subtitle') }}
        </p>
      </div>
    </div>

    <!-- Language -->
    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('settings.language') }}
        </h2>
      </template>
      <UFieldGroup>
        <UButton
          v-for="opt in languageOptions"
          :key="opt.value"
          :label="opt.label"
          color="neutral"
          :variant="locale === opt.value ? 'solid' : 'ghost'"
          @click="setLocale(opt.value)"
        />
      </UFieldGroup>
    </UCard>

    <!-- Appearance -->
    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('settings.theme') }}
        </h2>
      </template>
      <UFieldGroup>
        <UButton
          v-for="opt in themeOptions"
          :key="opt.value"
          :icon="opt.icon"
          :label="opt.label"
          color="neutral"
          :variant="colorMode.preference === opt.value ? 'solid' : 'ghost'"
          @click="colorMode.preference = opt.value"
        />
      </UFieldGroup>
    </UCard>

    <!-- Display & data -->
    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('settings.units') }}
        </h2>
      </template>
      <div class="space-y-5">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="font-medium">
              {{ t('settings.friendlyLabels') }}
            </div>
            <p class="text-sm text-gray-500 dark:text-gray-400">
              {{ t('settings.friendlyLabelsHint') }}
            </p>
          </div>
          <USwitch v-model="settings.friendlyLabels" />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="font-medium">
              {{ t('settings.explorerMode') }}
            </div>
            <p class="text-sm text-gray-500 dark:text-gray-400">
              {{ t('settings.explorerModeHint') }}
            </p>
          </div>
          <UFieldGroup>
            <UButton
              v-for="opt in explorerModeOptions"
              :key="opt.value"
              :label="opt.label"
              size="sm"
              color="neutral"
              :variant="settings.explorerMode === opt.value ? 'solid' : 'ghost'"
              @click="settings.explorerMode = opt.value as ExplorerMode"
            />
          </UFieldGroup>
        </div>

        <USeparator />

        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="font-medium">
              {{ t('settings.convertUnits') }}
            </div>
            <p class="text-sm text-gray-500 dark:text-gray-400">
              {{ t('settings.convertUnitsHint') }}
            </p>
          </div>
          <USwitch v-model="settings.convertUnits" />
        </div>

        <div v-if="settings.convertUnits" class="space-y-3">
          <div
            v-for="group in unitGroups"
            :key="group.key"
            class="flex items-center justify-between gap-4"
          >
            <label class="text-sm">{{ t(group.label) }}</label>
            <USelect
              v-model="settings.units[group.key]"
              :items="unitItems(group.units)"
              class="w-56"
            />
          </div>
        </div>
      </div>
    </UCard>

    <div class="flex items-center justify-between">
      <p class="text-xs text-gray-400">
        {{ t('settings.savedHint') }}
      </p>
      <UButton
        :label="t('settings.reset')"
        icon="i-lucide-rotate-ccw"
        color="neutral"
        variant="outline"
        size="sm"
        @click="reset"
      />
    </div>
  </UContainer>
</template>
