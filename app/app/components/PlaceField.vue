<script setup lang="ts">
import type { PlaceMatch } from '#shared/utils/places'
import { isPlaceQuery } from '#shared/utils/places'

// A field that finds a place by its name (GH-3791), for a tool that takes a point and not a station (the Explorer's interpolation and summary): the places
// are OpenStreetMap's, asked for through the app's server as everywhere else (`usePlacesSearch`: from three letters, after a pause, never a position), with the
// credit under the list. It is a combobox (the menu of Nuxt UI, Reka's combobox): the field keeps the focus, the arrow keys move the option, Enter takes it,
// and a polite status says how many places there are. A place chosen is handed over (`pick`) and the field is empty again.
defineProps<{
  /** The visible label of the field */
  label: string
}>()
const emit = defineEmits<{ pick: [place: PlaceMatch] }>()

const { t } = useI18n()
const term = ref('')
const { places, failed, pending, off } = usePlacesSearch(term)

const items = computed(() => places.value.map(place => ({
  label: place.name,
  description: [t(`shell.placeKinds.${place.kind}`), place.region].filter(Boolean).join(' · '),
  value: place.id,
  icon: 'i-ph-map-pin',
})))

// the field shows nothing chosen: the place chosen is shown by the tool, under it
const model = computed({
  get: () => undefined as typeof items.value[number] | undefined,
  set: (item: { value: string } | undefined) => {
    const match = places.value.find(place => place.id === item?.value)
    if (match)
      emit('pick', match)
  },
})

const typed = computed(() => term.value.trim())
/** Why the list is empty, in the words of the list */
const emptyText = computed(() => {
  if (off.value)
    return t('place.searchOff')
  if (!isPlaceQuery(typed.value))
    return t('place.typeHint')
  if (failed.value)
    return t('shell.placesFailed')
  return pending.value ? t('ask.placeSearching') : t('shell.searchEmpty')
})

// what a screen reader is told: how many places the text has, a moment after the last key
const announced = refDebounced(computed(() => {
  if (!isPlaceQuery(typed.value) || pending.value)
    return ''
  return failed.value ? t('shell.placesFailed') : t('shell.resultsCount', places.value.length)
}), 600)
</script>

<template>
  <UFormField :label="label" :help="t('place.fieldHelp')">
    <USelectMenu
      v-model="model"
      v-model:search-term="term"
      :items="items"
      :ignore-filter="true"
      :search-input="{ placeholder: t('place.fieldPlaceholder') }"
      :placeholder="t('place.fieldPlaceholder')"
      color="primary"
      class="w-full"
      data-testid="place-field"
    >
      <template #empty>
        {{ emptyText }}
      </template>
      <template #content-bottom>
        <PlacesCredit v-if="items.length" class="border-t border-default px-3 py-2" />
      </template>
    </USelectMenu>
    <p class="sr-only" role="status" aria-live="polite" data-testid="place-field-results">
      {{ announced }}
    </p>
  </UFormField>
</template>
