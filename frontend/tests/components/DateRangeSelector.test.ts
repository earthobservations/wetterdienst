import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import DateRangeSelector from '~/components/DateRangeSelector.vue'

describe('dateRangeSelector', () => {
  it('should render the component', async () => {
    const component = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        modelValue: {},
      },
    })
    expect(component.html()).toBeTruthy()
    expect(component.text()).toContain('Date Range')
  })

  it('should show required badge when required is true', async () => {
    const component = await mountSuspended(DateRangeSelector, {
      props: {
        required: true,
        modelValue: {},
      },
    })
    expect(component.text()).toContain('Required')
  })

  it('should show optional badge when required is false', async () => {
    const component = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        modelValue: {},
      },
    })
    expect(component.text()).toContain('Optional')
  })

  it('should render start and end date inputs', async () => {
    const component = await mountSuspended(DateRangeSelector, {
      props: {
        required: false,
        modelValue: {},
      },
    })
    expect(component.text()).toContain('Start Date')
    expect(component.text()).toContain('End Date')
  })
})
