import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { defineComponent, ref } from 'vue'
import { UInputNumber } from '#components'

// The numeric settings in Explorer moved from raw `<input type="number">` to `UInputNumber`, which
// displays through `Intl.NumberFormat` rather than showing the raw value. Fractions are the whole
// point of three of them -- a skip threshold stepping by 0.05, a min gain by 0.01, a nearby-station
// distance in tenths of a km -- and a `formatOptions` with too few digits silently rounds them away
// in the field (`maximumFractionDigits: 0` renders 0.05 as "0"). The default keeps three digits,
// which covers every step used here, so none is passed. These pin that.

/** Mount a UInputNumber with a bound ref, mirroring how the settings use it. */
async function mountNumber(props: Record<string, unknown>, initial: number) {
  const model = ref(initial)
  const wrapper = await mountSuspended(defineComponent({
    components: { UInputNumber },
    setup: () => ({ model, props }),
    template: `<UInputNumber v-model="model" v-bind="props" />`,
  }), { attachTo: document.body })
  return { wrapper, model, input: () => wrapper.find('input').element as HTMLInputElement }
}

describe('numeric explorer settings', () => {
  it.each([
    ['skip threshold', { min: 0, max: 1, step: 0.05 }, 0.05],
    ['min gain of value pairs', { min: 0, max: 1, step: 0.01 }, 0.01],
    ['nearby station distance', { min: 0, step: 0.1 }, 1.5],
  ])('shows %s without rounding the fraction away', async (_name, props, value) => {
    const { input } = await mountNumber(props, value)
    expect(input().value).toBe(String(value))
  })

  it('keeps whole numbers whole for the station count', async () => {
    const { input } = await mountNumber({ min: 0, step: 1 }, 3)
    expect(input().value).toBe('3')
  })

  it('reflects a changed model value back into the field', async () => {
    const { wrapper, model, input } = await mountNumber(
      { min: 0, max: 1, step: 0.05 },
      0.05,
    )
    model.value = 0.25
    await wrapper.vm.$nextTick()
    expect(input().value).toBe('0.25')
  })
})
