import { DateRangeSelector } from '#components'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

describe('dateRangeSelector Component', () => {
  it('renders with optional date range', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        modelValue: { startDate: undefined, endDate: undefined },
      },
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('Optional')
  })

  it('renders with required date range', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: true,
        modelValue: { startDate: undefined, endDate: undefined },
      },
    })

    expect(wrapper.text()).toContain('Required')
  })

  it('shows required badge for high resolution', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        resolution: '1_minute',
        modelValue: { startDate: undefined, endDate: undefined },
      },
    })

    expect(wrapper.text()).toContain('Required')
  })

  it('validates date range order', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: true,
        modelValue: {
          startDate: '2024-12-31',
          endDate: '2024-01-01',
        },
      },
    })

    const exposed = wrapper.vm as any
    expect(exposed.isValid).toBe(false)
    expect(exposed.validationError).toContain('End date must be after start date')
  })

  it('validates successfully with correct date range', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: true,
        modelValue: {
          startDate: '2024-01-01',
          endDate: '2024-12-31',
        },
      },
    })

    const exposed = wrapper.vm as any
    expect(exposed.isValid).toBe(true)
    expect(exposed.validationError).toBeNull()
  })

  it('estimates values for high resolution', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        resolution: '10_minutes',
        stationCount: 1,
        parameterCount: 1,
        modelValue: {
          startDate: '2024-01-01',
          endDate: '2024-01-02',
        },
      },
    })

    expect(wrapper.text()).toMatch(/144/)
  })

  it('warns when exceeding max values', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        resolution: '1_minute',
        stationCount: 10,
        parameterCount: 10,
        modelValue: {
          startDate: '2024-01-01',
          endDate: '2024-12-31',
        },
      },
    })

    const exposed = wrapper.vm as any
    expect(exposed.exceedsLimit).toBe(true)
    expect(wrapper.text()).toMatch(/max:/)
  })
})
