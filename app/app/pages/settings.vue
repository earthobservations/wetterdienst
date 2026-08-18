<script setup lang="ts">
const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { settings, reset } = useSettings()

const languageItems = languageSelectItems()
const selectedLanguage = computed({
  get: () => locale.value,
  set: (v: string) => setLocale(v as typeof locale.value),
})

const themeOptions = computed(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
])

// Available units per convertible type (mirrors the backend UnitConverter).
// Length types share the same unit list.
const LENGTH = ['millimeter', 'centimeter', 'meter', 'kilometer', 'mile', 'nautical_mile']

const weatherUnitGroups = [
  { key: 'temperature', label: 'settings.unitTemperature', units: ['degree_celsius', 'degree_kelvin', 'degree_fahrenheit'] },
  { key: 'precipitation', label: 'settings.unitPrecipitation', units: ['millimeter', 'liter_per_square_meter'] },
  { key: 'precipitation_intensity', label: 'settings.unitPrecipitationIntensity', units: ['millimeter_per_hour', 'liter_per_square_meter_per_hour'] },
  { key: 'pressure', label: 'settings.unitPressure', units: ['pascal', 'hectopascal', 'kilopascal'] },
  { key: 'speed', label: 'settings.unitSpeed', units: ['meter_per_second', 'kilometer_per_hour', 'knots', 'beaufort'] },
  { key: 'angle', label: 'settings.unitAngle', units: ['degree', 'radian', 'gradian'] },
  { key: 'fraction', label: 'settings.unitFraction', units: ['decimal', 'percent', 'one_eighth'] },
  { key: 'length_short', label: 'settings.unitLengthShort', units: LENGTH },
  { key: 'length_medium', label: 'settings.unitLengthMedium', units: LENGTH },
  { key: 'length_long', label: 'settings.unitLengthLong', units: LENGTH },
  { key: 'energy_per_area', label: 'settings.unitEnergyPerArea', units: ['joule_per_square_centimeter', 'joule_per_square_meter', 'kilojoule_per_square_meter'] },
  { key: 'power_per_area', label: 'settings.unitPowerPerArea', units: ['watt_per_square_centimeter', 'watt_per_square_meter', 'kilowatt_per_square_meter'] },
  { key: 'time', label: 'settings.unitTime', units: ['second', 'minute', 'hour'] },
  { key: 'degree_day', label: 'settings.unitDegreeDay', units: ['degree_celsius_day', 'degree_kelvin_day', 'degree_fahrenheit_day'] },
] as const

const otherUnitGroups = [
  { key: 'concentration', label: 'settings.unitConcentration', units: ['milligram_per_liter', 'gram_per_liter'] },
  { key: 'conductivity', label: 'settings.unitConductivity', units: ['microsiemens_per_centimeter', 'microsiemens_per_meter', 'siemens_per_centimeter', 'siemens_per_meter'] },
  { key: 'volume_per_time', label: 'settings.unitVolumePerTime', units: ['liter_per_second', 'cubic_meter_per_second'] },
] as const

function unitItems(units: readonly string[]) {
  return units.map(u => ({ value: u, label: t(`units.${u}`) }))
}
</script>

<template>
  <UContainer class="mx-auto max-w-2xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('settings.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('settings.subtitle') }}
      </p>
    </div>

    <!-- Language -->
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-languages" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('settings.language') }}
          </h2>
        </div>
      </template>
      <USelect
        v-model="selectedLanguage"
        :items="languageItems"
        class="w-full sm:w-64"
      />
    </UCard>

    <!-- Appearance -->
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-palette" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('settings.theme') }}
          </h2>
        </div>
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
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-ruler" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('settings.units') }}
          </h2>
        </div>
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

        <div v-if="settings.convertUnits" class="space-y-5">
          <div class="space-y-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-gray-400">
              {{ t('settings.unitsWeather') }}
            </div>
            <div
              v-for="group in weatherUnitGroups"
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

          <div class="space-y-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-gray-400">
              {{ t('settings.unitsOther') }}
            </div>
            <div
              v-for="group in otherUnitGroups"
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
