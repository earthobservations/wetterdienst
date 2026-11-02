import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'
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

  it('hands the focus of the button it removes to the two fields as a group, not to a date input (GH-3722)', async () => {
    const modelValue = reactive({ startDate: '2020-01-01', endDate: '2020-12-31' }) as { startDate?: string, endDate?: string }
    const wrapper = await mountSuspended(DateRangeSelector, { attachTo: document.body, props: { required: false, modelValue } })
    const button = wrapper.find('[data-testid="clear-date-range"]')
    ;(button.element as HTMLElement).focus()
    await button.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="clear-date-range"]').exists()).toBe(false))
    // a date input focused from script may open its picker on iOS: the group takes it, and a Tab reaches the input
    const group = wrapper.find('[role="group"]')
    expect(document.activeElement).toBe(group.element)
    expect(wrapper.findAll('input[type="date"]').some(input => input.element === document.activeElement)).toBe(false)
    // it has the name of the selector, which a screen reader says on arriving
    expect(group.attributes('aria-labelledby')).toBeTruthy()
    expect(wrapper.find(`#${group.attributes('aria-labelledby')}`).text()).toBe('Date Range')
    expect(group.element.contains(wrapper.findAll('input[type="date"]')[0]!.element)).toBe(true)
    wrapper.unmount()
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
    await vi.waitFor(() => expect(status.text()).toBe('Default range: the newest data (8 months, about 480,000 rows), so that the server can send it at once. Clear the date range to ask for everything.'))
    for (const input of wrapper.findAll('input[type="date"]'))
      expect(input.attributes('aria-describedby')).toBe(status.attributes('id'))
  })

  it('does not offer to clear a default range that has to be there: the note leaves the way out unsaid', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: { required: false, resolution: '1_minute', defaultWindow: window, modelValue: { startDate: '2026-02-27', endDate: '2026-10-26' } },
    })
    const status = wrapper.find('[role="status"]')
    await vi.waitFor(() => expect(status.text()).toBe('Default range: the newest data (8 months, about 480,000 rows), so that the server can send it at once.'))
    expect(wrapper.find('[data-testid="clear-date-range"]').exists()).toBe(false)
  })

  it('keeps an empty status for a range that is the user\'s, with no description to point at', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, { props: { required: false, modelValue: { startDate: '2026-02-27' } } })
    expect(wrapper.find('[role="status"]').text()).toBe('')
    expect(wrapper.find('input[type="date"]').attributes('aria-describedby')).toBeUndefined()
  })

  it('writes a note that is there at the start into the status after the status is in the page, where it is announced (GH-3722)', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = await mountSuspended(DateRangeSelector, {
        props: { required: false, defaultWindow: window, modelValue: { startDate: '2026-02-27', endDate: '2026-10-26' } },
      })
      const status = wrapper.find('[role="status"]')
      // an element that came with its text is no change to a live region: it is the fields' description only
      expect(status.text()).toBe('')
      vi.advanceTimersByTime(150)
      await nextTick()
      expect(status.text()).toContain('Default range: the newest data')
      // the same element, so the text was put into a status that was in the page
      expect(wrapper.find('[role="status"]').element).toBe(status.element)
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('writes a note that comes later at once: it is a change already', async () => {
    const wrapper = await mountSuspended(DateRangeSelector, {
      props: { required: false, modelValue: { startDate: '2026-02-27', endDate: '2026-10-26' } },
    })
    const status = wrapper.find('[role="status"]')
    expect(status.text()).toBe('')
    await wrapper.setProps({ defaultWindow: window })
    expect(status.text()).toContain('Default range: the newest data')
  })

  it('does not write into a selector that is gone', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = await mountSuspended(DateRangeSelector, {
        props: { required: false, defaultWindow: window, modelValue: { startDate: '2026-02-27', endDate: '2026-10-26' } },
      })
      expect(vi.getTimerCount()).toBeGreaterThan(0)
      wrapper.unmount()
      expect(vi.getTimerCount()).toBe(0)
    }
    finally {
      vi.useRealTimers()
    }
  })
})
