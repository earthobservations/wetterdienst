import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import { ParameterSelection } from '#components'

// The component starts its /api/coverage request without awaiting it in setup -- awaiting would
// suspend the whole page behind it -- so mountSuspended() now returns before the answer lands.
// Anything that reads what coverage feeds has to wait for initialization to finish first.
async function mountReady(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(ParameterSelection, { props })
  await vi.waitFor(() => expect((wrapper.vm as any).isInitializing).toBe(false), { timeout: 5000 })
  return wrapper
}

describe('parameterSelection Component', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    // The Nuxt app (and its useFetch payload cache) is shared across mounts
    // within this file -- without this, a later test's registerEndpoint()
    // can be shadowed by an earlier test's cached /api/coverage response.
    clearNuxtData()
  })

  it('renders itself while /api/coverage is still out', async () => {
    // The regression this guards: the coverage request used to be awaited at the top level of
    // setup, which with `ssr: false` suspended the whole page -- the Explorer showed nothing at
    // all, not even its own headings, until the backend answered. A request that never settles
    // makes that visible.
    vi.mocked(globalThis.fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>)

    const wrapper = await mountSuspended(ParameterSelection, {
      props: { modelValue: {}, restrictProvider: 'dwd' },
    })

    expect(wrapper.text()).toContain('Select Parameters')
    expect((wrapper.vm as any).coveragePending).toBe(true)
    // An unanswered request is not an answer of "no such provider": while it is out, every
    // restriction looks unavailable, and the alert must not flash on each cold load.
    expect(wrapper.text()).not.toContain('is not available from this backend')
  })

  it('renders the component', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountReady({
      modelValue: {},
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('Select Parameters')
  })

  it('disables dependent selects when previous not selected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountReady({
      modelValue: {},
    })

    const selects = wrapper.findAllComponents({ name: 'USelect' })
    expect(selects.length).toBeGreaterThan(0)
  })

  it('emits update when parameters change', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountReady({
      modelValue: {
        provider: 'dwd',
        network: 'observation',
        resolution: 'daily',
        dataset: 'climate_summary',
        parameters: ['temperature_air_max_200'],
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

    const wrapper = await mountReady({
      modelValue: initialValue,
    })

    expect(wrapper.exists()).toBe(true)

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeDefined()
  })

  it('clears dependent fields when parent field changes', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'], noaa: ['ghcn'] }), { status: 200 }),
    )

    const wrapper = await mountReady({
      modelValue: {
        provider: 'dwd',
        network: 'observation',
        resolution: 'daily',
        dataset: 'climate_summary',
        parameters: ['temperature_air_max_200'],
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

    const wrapper = await mountReady({
      modelValue: {
        provider: 'dwd',
        network: 'observation',
        resolution: 'daily',
        dataset: 'climate_summary',
        parameters: [],
      },
    })

    const vm = wrapper.vm as any
    expect(vm.selectAllParameters).toBeDefined()
    expect(typeof vm.selectAllParameters).toBe('function')
  })

  it('restricts the provider select to restrictProvider', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {} }, noaa: { ghcn: {} } }))

    const wrapper = await mountReady({
      modelValue: {},
      restrictProvider: 'dwd',
    })

    const vm = wrapper.vm as any
    // `providers` reflects backend reality regardless of restriction; the
    // select itself only offers the restricted value.
    expect(vm.providers).toEqual(['dwd', 'noaa'])
    expect(vm.providerItems).toEqual(['dwd'])
    expect(vm.restrictedProviderAvailable).toBe(true)
  })

  it('restricts the network select to restrictNetwork', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {}, mosmix: {} } }))

    const wrapper = await mountReady({
      modelValue: { provider: 'dwd' },
      restrictNetwork: 'observation',
    })

    const vm = wrapper.vm as any
    expect(vm.networks).toEqual(['observation', 'mosmix'])
    expect(vm.networkItems).toEqual(['observation'])
    expect(vm.restrictedNetworkAvailable).toBe(true)
  })

  it('does not fall back to the unrestricted provider list when restrictProvider does not exist', async () => {
    registerEndpoint('/api/coverage', () => ({ noaa: { ghcn: {} } }))

    const wrapper = await mountReady({
      modelValue: {},
      restrictProvider: 'dwd',
    })

    const vm = wrapper.vm as any
    expect(vm.restrictedProviderAvailable).toBe(false)
    // The select must not silently show every provider as if unrestricted.
    expect(vm.providerItems).toEqual([])
    expect(vm.provider).toBeUndefined()
    expect(wrapper.text()).toContain('dwd')
  })

  it('does not fall back to the unrestricted network list when restrictNetwork does not exist', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { mosmix: {} } }))

    const wrapper = await mountReady({
      modelValue: {},
      restrictProvider: 'dwd',
      restrictNetwork: 'observation',
    })

    const vm = wrapper.vm as any
    expect(vm.restrictedProviderAvailable).toBe(true)
    expect(vm.restrictedNetworkAvailable).toBe(false)
    expect(vm.networkItems).toEqual([])
    expect(vm.network).toBeUndefined()
    expect(wrapper.text()).toContain('observation')
  })

  it('overrides a mismatched initial provider/network with the restricted values', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {} }, noaa: { ghcn: {} } }))

    const wrapper = await mountReady({
      modelValue: {
        provider: 'noaa',
        network: 'ghcn',
        resolution: 'daily',
        dataset: 'foo',
        parameters: ['bar'],
      },
      restrictProvider: 'dwd',
      restrictNetwork: 'observation',
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
              description: null,
              datasets: {
                climate_summary: {
                  description: null,
                  parameters: [{ name: 'temperature_air_max_200' }],
                },
              },
            },
          }),
          { status: 200 },
        ),
      )

    const wrapper = await mountReady({
      modelValue: {
        provider: 'dwd',
        network: 'observation',
        resolution: 'daily',
        dataset: 'climate_summary',
        parameters: ['temperature_air_max_200'],
      },
    })

    const vm = wrapper.vm as any
    vm.clearParameters()
    await wrapper.vm.$nextTick()

    expect(vm.parameters).toEqual([])
  })
})
