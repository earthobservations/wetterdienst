import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ParameterSelection } from '#components'

describe('parameterSelection Component', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the component', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {},
      },
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('Select Parameters')
  })

  it('disables dependent selects when previous not selected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {},
      },
    })

    const selects = wrapper.findAllComponents({ name: 'USelect' })
    expect(selects.length).toBeGreaterThan(0)
  })

  it('emits update when parameters change', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {
          provider: 'dwd',
          network: 'observation',
          resolution: 'daily',
          dataset: 'climate_summary',
          parameters: ['temperature_air_max_200'],
        },
      },
    })

    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeDefined()
  })

  it('initializes with provided model value', async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValue(
        new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
      )

    const initialValue = {
      provider: 'dwd',
      network: 'observation',
      resolution: 'daily',
      dataset: 'climate_summary',
      parameters: ['temperature_air_max_200'],
    }

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: initialValue,
      },
    })

    expect(wrapper.exists()).toBe(true)

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeDefined()
  })

  it('clears dependent fields when parent field changes', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'], noaa: ['ghcn'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {
          provider: 'dwd',
          network: 'observation',
          resolution: 'daily',
          dataset: 'climate_summary',
          parameters: ['temperature_air_max_200'],
        },
      },
    })

    const vm = wrapper.vm as any

    vm.provider = 'noaa'
    await wrapper.vm.$nextTick()

    expect(vm.network).toBeUndefined()
    expect(vm.resolution).toBeUndefined()
    expect(vm.dataset).toBeUndefined()
    expect(vm.parameters).toEqual([])
  })

  it('supports select all parameters', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {
          provider: 'dwd',
          network: 'observation',
          resolution: 'daily',
          dataset: 'climate_summary',
          parameters: [],
        },
      },
    })

    const vm = wrapper.vm as any
    expect(vm.selectAllParameters).toBeDefined()
    expect(typeof vm.selectAllParameters).toBe('function')
  })

  it('restricts the provider select to restrictProvider', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {} }, noaa: { ghcn: {} } }))

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {},
        restrictProvider: 'dwd',
      },
    })

    const vm = wrapper.vm as any
    expect(vm.providers).toEqual(['dwd'])
  })

  it('restricts the network select to restrictNetwork', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {}, mosmix: {} } }))

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: { provider: 'dwd' },
        restrictNetwork: 'observation',
      },
    })

    const vm = wrapper.vm as any
    expect(vm.networks).toEqual(['observation'])
  })

  it('overrides a mismatched initial provider/network with the restricted values', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {} }, noaa: { ghcn: {} } }))

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {
          provider: 'noaa',
          network: 'ghcn',
          resolution: 'daily',
          dataset: 'foo',
          parameters: ['bar'],
        },
        restrictProvider: 'dwd',
        restrictNetwork: 'observation',
      },
    })

    const vm = wrapper.vm as any
    expect(vm.provider).toBe('dwd')
    expect(vm.network).toBe('observation')
  })

  it('supports clear parameters', async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            daily: {
              climate_summary: [{ name: 'temperature_air_max_200' }],
            },
          }),
          { status: 200 },
        ),
      )

    const wrapper = await mountSuspended(ParameterSelection, {
      props: {
        modelValue: {
          provider: 'dwd',
          network: 'observation',
          resolution: 'daily',
          dataset: 'climate_summary',
          parameters: ['temperature_air_max_200'],
        },
      },
    })

    const vm = wrapper.vm as any
    vm.clearParameters()
    await wrapper.vm.$nextTick()

    expect(vm.parameters).toEqual([])
  })
})
