import type { Ref } from 'vue'
import type { InterpolationSelection } from '~/types/station-selection-state.type'

/**
 * Wire the point an interpolation or summary answers for to the boxes that describe it.
 *
 * Three values, filled from two places: the coordinates and the elevation are typed in manual
 * mode, while choosing a station writes all three at once. Keeping that straight is the whole of
 * this, and getting it wrong is quiet -- a query that carries a height the form does not show, or
 * a station whose coordinates are cleared by an elevation arriving after them.
 */
export function useInterpolationPoint(modelValue: Ref<InterpolationSelection>) {
  const latitudeInput = ref<string>(modelValue.value.latitude?.toString() ?? '')
  const longitudeInput = ref<string>(modelValue.value.longitude?.toString() ?? '')
  const elevationInput = ref<string>(modelValue.value.elevation?.toString() ?? '')

  // choosing a station writes all three straight into the model, so the boxes follow it -- or they
  // show empty while the query carries a point the user cannot see. All three, not the elevation
  // alone: with the coordinate boxes left stale, typing one of them made the watcher below read
  // the other box, still empty, and wipe a coordinate nobody had touched
  function follow(box: Ref<string>, value: number | undefined) {
    const shown = value?.toString() ?? ''
    if (shown !== box.value)
      box.value = shown
  }
  watch(() => modelValue.value.latitude, latitude => follow(latitudeInput, latitude))
  watch(() => modelValue.value.longitude, longitude => follow(longitudeInput, longitude))
  watch(() => modelValue.value.elevation, elevation => follow(elevationInput, elevation))

  // the coordinates and the elevation are watched apart. These boxes hold only what was typed into
  // them, which in station mode is nothing, so writing all three together let an elevation arriving
  // from a station take that station's coordinates out with it
  watch([latitudeInput, longitudeInput], ([latitude, longitude]) => {
    const latitudeNumber = Number.parseFloat(latitude)
    const longitudeNumber = Number.parseFloat(longitude)
    modelValue.value = {
      ...modelValue.value,
      latitude: Number.isNaN(latitudeNumber) ? undefined : latitudeNumber,
      longitude: Number.isNaN(longitudeNumber) ? undefined : longitudeNumber,
    }
  })

  watch(elevationInput, (elevation) => {
    const elevationNumber = Number.parseFloat(elevation)
    // optional: left empty, the readings are interpolated as they come
    const parsed = Number.isNaN(elevationNumber) ? undefined : elevationNumber
    if (parsed !== modelValue.value.elevation)
      modelValue.value = { ...modelValue.value, elevation: parsed }
  })

  /** Take the point from a station: its position, and its altitude where the provider reports one. */
  function fromStation(station: Station | undefined) {
    modelValue.value = {
      ...modelValue.value,
      station,
      latitude: station?.latitude,
      longitude: station?.longitude,
      elevation: station?.height ?? undefined,
    }
  }

  return { latitudeInput, longitudeInput, elevationInput, fromStation }
}
