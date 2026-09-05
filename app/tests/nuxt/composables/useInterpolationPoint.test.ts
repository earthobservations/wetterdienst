import type { InterpolationSelection } from '~/types/station-selection-state.type'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { useInterpolationPoint } from '~/composables/useInterpolationPoint'

// Harness so the composable's watchers run inside a real setup context, as they do in the
// selection component.
function harness(initial: Partial<InterpolationSelection> = {}) {
  return defineComponent({
    setup() {
      const modelValue = ref<InterpolationSelection>({ source: 'manual', ...initial })
      return { modelValue, ...useInterpolationPoint(modelValue) }
    },
    render: () => h('div'),
  })
}

/** The watchers settle over a few ticks, one feeding the next. */
async function settle() {
  for (let index = 0; index < 4; index++)
    await nextTick()
}

const station = { station_id: '02290', name: 'Feldberg', state: '', latitude: 47.9, longitude: 8.0, height: 1000 }

describe('the point an interpolation answers for', () => {
  it('takes position and altitude from a chosen station', async () => {
    const wrapper = await mountSuspended(harness({ source: 'station' }))
    wrapper.vm.fromStation(station as never)
    await settle()
    expect(wrapper.vm.modelValue.latitude).toBe(47.9)
    expect(wrapper.vm.modelValue.longitude).toBe(8.0)
    expect(wrapper.vm.modelValue.elevation).toBe(1000)
    // and the box shows it, rather than the query carrying a height the form does not
    expect(wrapper.vm.elevationInput).toBe('1000')
  })

  it('keeps a station\'s coordinates when its elevation arrives', async () => {
    // the elevation reaches the box through a watcher, which once fed the watcher that rebuilds
    // the model from the manual boxes -- empty in station mode -- and cleared the coordinates,
    // leaving the form unable to fetch at all
    const wrapper = await mountSuspended(harness({ source: 'station' }))
    wrapper.vm.fromStation(station as never)
    await settle()
    expect(wrapper.vm.modelValue.latitude).toBe(47.9)
    expect(wrapper.vm.modelValue.longitude).toBe(8.0)
  })

  it('leaves the elevation unset for a station the provider gives no height for', async () => {
    // FMI, IPMA, LHMT, the Environment Agency, WSV and IMGW's hydrology report none for any
    // station; null is not undefined, and reached `.toString()` on the way to the query
    const wrapper = await mountSuspended(harness({ source: 'station' }))
    wrapper.vm.fromStation({ ...station, height: null } as never)
    await settle()
    expect(wrapper.vm.modelValue.elevation).toBeUndefined()
    expect(wrapper.vm.elevationInput).toBe('')
    expect(wrapper.vm.modelValue.latitude).toBe(47.9)
  })

  it('takes a typed elevation without disturbing the coordinates', async () => {
    const wrapper = await mountSuspended(harness())
    wrapper.vm.latitudeInput = '52.52'
    wrapper.vm.longitudeInput = '13.40'
    await settle()
    wrapper.vm.elevationInput = '250'
    await settle()
    expect(wrapper.vm.modelValue).toMatchObject({ latitude: 52.52, longitude: 13.4, elevation: 250 })
  })

  it('leaves the elevation unset while its box is empty', async () => {
    const wrapper = await mountSuspended(harness())
    wrapper.vm.latitudeInput = '52.52'
    wrapper.vm.longitudeInput = '13.40'
    await settle()
    // nothing typed: the readings are interpolated as they come
    expect(wrapper.vm.modelValue.elevation).toBeUndefined()
  })

  it('shows a station\'s coordinates in the boxes, not only in the model', async () => {
    // the boxes were seeded once at setup while the model was written by the station, so switching
    // back to manual showed empty coordinates against a model that held them -- and typing one of
    // them then read the other box, still empty, and wiped a coordinate nobody had touched
    const wrapper = await mountSuspended(harness({ source: 'station' }))
    wrapper.vm.fromStation(station as never)
    await settle()
    expect(wrapper.vm.latitudeInput).toBe('47.9')
    expect(wrapper.vm.longitudeInput).toBe('8')

    wrapper.vm.latitudeInput = '48'
    await settle()
    expect(wrapper.vm.modelValue.latitude).toBe(48)
    expect(wrapper.vm.modelValue.longitude).toBe(8)
  })

  it('forgets a station\'s height when the point is described afresh', async () => {
    // pick a summit, then switch to typing coordinates: carrying its 1000 m into a city at 34 m
    // reduces every reading to a height the point does not have, six degrees of air temperature
    const wrapper = await mountSuspended(harness({ source: 'station' }))
    wrapper.vm.fromStation(station as never)
    await settle()
    expect(wrapper.vm.modelValue.elevation).toBe(1000)

    wrapper.vm.forgetElevation()
    await settle()
    expect(wrapper.vm.modelValue.elevation).toBeUndefined()
    expect(wrapper.vm.elevationInput).toBe('')
  })

  it('refuses a number no answer can be given for', async () => {
    // `1e400` parses to Infinity, which would travel into the model, into a shared link and on to
    // the API. The explorer's own query parser rejects it; the boxes have to agree
    const wrapper = await mountSuspended(harness())
    wrapper.vm.latitudeInput = '1e400'
    wrapper.vm.elevationInput = '1e400'
    await settle()
    expect(wrapper.vm.modelValue.latitude).toBeUndefined()
    expect(wrapper.vm.modelValue.elevation).toBeUndefined()
  })

  it('clears the elevation when its box is emptied', async () => {
    const wrapper = await mountSuspended(harness({ elevation: 250 }))
    wrapper.vm.elevationInput = ''
    await settle()
    expect(wrapper.vm.modelValue.elevation).toBeUndefined()
  })
})
