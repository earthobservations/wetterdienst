import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { DateRangeSelector } from '#components'

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

describe('dateRangeSelector start and clear (GH-3457)', () => {
  const window = { unit: 'months', count: 8, startDate: '2026-02-27', endDate: '2026-10-26', rows: 480_000 } as const

  it('says an edit, with the field changed', async () => {
    const modelValue = { startDate: undefined, endDate: undefined } as { startDate?: string, endDate?: string }
    const wrapper = await mountSuspended(DateRangeSelector, { props: { required: false, modelValue } })
    await wrapper.findAll('input[type="date"]')[0]!.setValue('2020-02-01')
    expect(modelValue.startDate).toBe('2020-02-01')
    expect(wrapper.emitted('edited')).toHaveLength(1)
    await wrapper.findAll('input[type="date"]')[0]!.setValue('')
    expect(modelValue.startDate).toBeUndefined()
    expect(wrapper.emitted('edited')).toHaveLength(2)
  })

  it('clears both dates with one button, and says so', async () => {
    const modelValue = { startDate: '2020-01-01', endDate: '2020-12-31' } as { startDate?: string, endDate?: string }
    const wrapper = await mountSuspended(DateRangeSelector, { props: { required: false, modelValue } })
    const button = wrapper.find('[data-testid="clear-date-range"]')
    expect(button.text()).toBe('Clear date range')
    await button.trigger('click')
    expect(modelValue).toEqual({ startDate: undefined, endDate: undefined })
    expect(wrapper.emitted('cleared')).toHaveLength(1)
    expect(wrapper.emitted('edited')).toBeUndefined()
  })

  it('has no button to clear what is empty, or what has to be there', async () => {
    const empty = await mountSuspended(DateRangeSelector, { props: { required: false, modelValue: {} } })
    expect(empty.find('[data-testid="clear-date-range"]').exists()).toBe(false)
    const required = await mountSuspended(DateRangeSelector, { props: { required: true, modelValue: { startDate: '2020-01-01', endDate: '2020-12-31' } } })
    expect(required.find('[data-testid="clear-date-range"]').exists()).toBe(false)
  })

  it('words the default range under the fields, in a status the fields are described by', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: { required: false, defaultWindow: window, modelValue: { startDate: '2026-02-27', endDate: '2026-10-26' } },
    })
    const status = wrapper.find('[role="status"]')
    expect(status.text()).toBe('Default range: the newest data (8 months, about 480,000 rows), so that the server can send it at once. Clear the date range to ask for everything.')
    for (const input of wrapper.findAll('input[type="date"]'))
      expect(input.attributes('aria-describedby')).toBe(status.attributes('id'))
  })

  it('keeps an empty status for a range that is the user\'s, with no description to point at', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, { props: { required: false, modelValue: { startDate: '2026-02-27' } } })
    expect(wrapper.find('[role="status"]').text()).toBe('')
    expect(wrapper.find('input[type="date"]').attributes('aria-describedby')).toBeUndefined()
  })
})
