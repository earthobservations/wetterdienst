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
/**
 * Read a box as the number it names, or nothing.
 *
 * Finite, not merely not-NaN: `1e400` parses to Infinity, which would travel into the model, into
 * a shared link, and on to an API that can give no answer for it.
 */
function numberFromBox(value: string | number): number | undefined {
  const parsed = Number.parseFloat(String(value))
  return Number.isFinite(parsed) ? parsed : undefined
}

export function useInterpolationPoint(modelValue: Ref<InterpolationSelection>) {
  // `string`, which is what `UInput` declares its model to be -- though one of type number writes
  // a number back through it at runtime, so everything reading a box says which it wants rather
  // than trusting the annotation
  const latitudeInput = ref<string>(modelValue.value.latitude?.toString() ?? '')
  const longitudeInput = ref<string>(modelValue.value.longitude?.toString() ?? '')
  const elevationInput = ref<string>(modelValue.value.elevation?.toString() ?? '')

  // choosing a station writes all three straight into the model, so the boxes follow it -- or they
  // show empty while the query carries a point the user cannot see. All three, not the elevation
  // alone: with the coordinate boxes left stale, typing one of them made the watcher below read
  // the other box, still empty, and wipe a coordinate nobody had touched
  function follow(box: Ref<string>, value: number | undefined) {
    const shown = value?.toString() ?? ''
    // against the box as text: it may hold a number, and `'1000' !== 1000` would write on every
    // change, each write firing the box's own watcher again
    if (shown !== String(box.value))
      box.value = shown
  }
  watch(() => modelValue.value.latitude, latitude => follow(latitudeInput, latitude))
  watch(() => modelValue.value.longitude, longitude => follow(longitudeInput, longitude))
  watch(() => modelValue.value.elevation, elevation => follow(elevationInput, elevation))

  // the coordinates and the elevation are watched apart. These boxes hold only what was typed into
  // them, which in station mode is nothing, so writing all three together let an elevation arriving
  // from a station take that station's coordinates out with it
  watch([latitudeInput, longitudeInput], ([latitude, longitude]) => {
    modelValue.value = {
      ...modelValue.value,
      latitude: numberFromBox(latitude),
      longitude: numberFromBox(longitude),
    }
  })

  watch(elevationInput, (elevation) => {
    // optional: left empty, the readings are interpolated as they come
    const parsed = numberFromBox(elevation)
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
