import type { Ref } from 'vue'
import type { InterpolationSelection } from '~/types/station-selection-state.type'
import type { PlaceInLink } from '~/utils/place-link'

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

/** Whether coordinates are the position of a place, to the four decimals a link keeps it with */
function isPositionOf(place: { latitude: number, longitude: number }, point: { latitude?: number, longitude?: number }): boolean {
  return point.latitude !== undefined && point.longitude !== undefined
    && Math.abs(point.latitude - place.latitude) < 0.00006 && Math.abs(point.longitude - place.longitude) < 0.00006
}

/**
 * Wire the point an interpolation or summary answers for to the boxes that describe it.
 *
 * Three values, filled from two places: the coordinates and the elevation are typed in manual
 * mode, while choosing a station writes all three at once. Keeping that straight is the whole of
 * this, and getting it wrong is quiet -- a query that carries an elevation the form does not show, or
 * a station whose coordinates are cleared by an elevation arriving after them.
 */
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
    const point = { latitude: numberFromBox(latitude), longitude: numberFromBox(longitude) }
    modelValue.value = {
      ...modelValue.value,
      ...point,
      // coordinates typed over the place's are no longer its position (GH-3791): the place is not kept beside them
      place: modelValue.value.place && isPositionOf(modelValue.value.place, point) ? modelValue.value.place : undefined,
    }
  })

  watch(elevationInput, (elevation) => {
    // optional: left empty, the readings are interpolated as they come
    const parsed = numberFromBox(elevation)
    if (parsed !== modelValue.value.elevation)
      modelValue.value = { ...modelValue.value, elevation: parsed }
  })

  /**
   * What a station says about the point: its position, and its altitude where the provider
   * reports one. A station without a position, e.g. a postcode of dwd/derived
   * climate_correction_factor, leaves the point unset.
   *
   * Given apart from the writing so that a caller changing something else at the same time can
   * put both into one assignment -- two writes in a tick have the second spreading a model the
   * first has already replaced, and the first is lost.
   */
  function pointFromStation(station: Station | undefined): Partial<InterpolationSelection> {
    return {
      station,
      latitude: station?.latitude ?? undefined,
      longitude: station?.longitude ?? undefined,
      elevation: station?.elevation ?? undefined,
    }
  }

  /** Take the point from a station. */
  function fromStation(station: Station | undefined) {
    modelValue.value = { ...modelValue.value, ...pointFromStation(station), place: undefined }
  }

  /**
   * Take the point from a place found by its name (GH-3791): its position, and the place itself, to be shown with it. A place has no height, so no
   * elevation is taken from it, and one that was there (a station's, or typed) is left out: the readings are not brought to a height the place does not have.
   */
  function fromPlace(place: PlaceInLink) {
    modelValue.value = { ...modelValue.value, source: 'manual', station: undefined, latitude: place.latitude, longitude: place.longitude, elevation: undefined, place }
  }

  return { latitudeInput, longitudeInput, elevationInput, fromStation, fromPlace, pointFromStation }
}
