import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import { ParameterSelection } from '#components'
import { dailyClimateSummaryCoverage } from '../fixtures/coverage'

// The component starts its /api/coverage request without awaiting it in setup -- awaiting would
// suspend the whole page behind it -- so mountSuspended() now returns before the answer lands.
// Anything that reads what coverage feeds has to wait for initialization to finish first.
//
// Every wrapper is unmounted after its test: a component left mounted shares the `/api/coverage`
// entry of the next test's, and its credential checks answer the next test's coverage too
const mountedWrappers: Array<{ unmount: () => void }> = []
afterEach(() => {
  for (const wrapper of mountedWrappers.splice(0))
    wrapper.unmount()
})

async function mountReady(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(ParameterSelection, { props })
  mountedWrappers.push(wrapper)
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
    mountedWrappers.push(wrapper)

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

  it('lists a credentialed network unless its credentials are missing', async () => {
    // the list says whether the credentials are configured and nothing of whether they are accepted:
    // that is a check of its own (GH-2641), which the tests of the credential checks below cover
    const network = (configured: boolean) => ({ auth: true, configured, date_required: false })
    registerEndpoint('/api/coverage', () => ({
      aemet: { configured: network(true), missing: network(false) },
      knmi: { missing: network(false) },
    }))

    const wrapper = await mountReady({ modelValue: { provider: 'aemet' } })

    const vm = wrapper.vm as any
    expect(vm.networks).toEqual(['configured'])
    expect(vm.providers).toEqual(['aemet'])
  })

  it('does not offer a standalone network, which has no stations, parameters or coverage', async () => {
    // `dwd/radar` and `dwd/alerts` answer a 404 to the coverage the selects read next (GH-2641)
    const network = (kind: string) => ({ auth: false, configured: true, kind, date_required: false })
    registerEndpoint('/api/coverage', () => ({
      dwd: { observation: network('observation'), mosmix: network('forecast'), radar: network('radar'), alerts: network('alerts') },
      standalone: { alerts: network('alerts') },
    }))

    const wrapper = await mountReady({ modelValue: { provider: 'dwd' } })

    const vm = wrapper.vm as any
    expect(vm.networks).toEqual(['observation', 'mosmix'])
    // a provider with nothing but a standalone network is no provider to choose
    expect(vm.providers).toEqual(['dwd'])
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
          JSON.stringify(dailyClimateSummaryCoverage()),
          { status: 200 },
        ),
      )

    const wrapper = await mountReady({
      modelValue: {
        provider: 'dwd',
        network: 'observation',
        resolution: 'daily',
        dataset: 'climate_summary',
        parameters: ['temperature_air_max_2m'],
      },
    })

    const vm = wrapper.vm as any
    vm.clearParameters()
    await wrapper.vm.$nextTick()

    expect(vm.parameters).toEqual([])
  })
})

// Whether the backend accepts a network's credentials is a request to the provider, which the list
// of every provider no longer waits for: the page lists them, then asks per network (GH-2564)
describe('parameterSelection credential checks', () => {
  // the list says whether the credentials are configured and not whether they are accepted
  const credentialed = (configured = true) => ({ auth: true, configured, date_required: false })
  const open = { auth: false, configured: true, date_required: false }
  const mountSelection = (props: Record<string, unknown> = { modelValue: {} }) => mountReady(props)

  // A hold on the mocked endpoint, opened where the order of the answers matters
  function gate() {
    let release!: () => void
    const released = new Promise<void>((resolve) => {
      release = resolve
    })
    return { released, release }
  }

  beforeEach(() => {
    clearNuxtData()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders and lists a credentialed network before its credentials have been checked', async () => {
    const hold = gate()
    const asked: unknown[] = []
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: open }, aemet: { observation: credentialed() } }))
    registerEndpoint('/api/auth', async (event) => {
      asked.push(getQuery(event))
      await hold.released
      return { provider: 'aemet', network: 'observation', auth: true, configured: true, valid: false }
    })

    // mountReady() waits for initialization, which waits for coverage and for nothing else
    const wrapper = await mountSelection({ modelValue: { provider: 'aemet' } })
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(asked).toHaveLength(1))
    expect(asked).toEqual([{ provider: 'aemet', network: 'observation' }])
    expect(vm.coveragePending).toBe(false)
    expect(vm.providers).toEqual(['aemet', 'dwd'])
    // the unanswered check does not hold the selects: the provider could be chosen from the URL
    expect(vm.provider).toBe('aemet')
    expect(vm.networks).toEqual(['observation'])
    expect(wrapper.findAllComponents({ name: 'USelect' })[0]!.props('disabled')).toBe(false)

    hold.release()
    await vi.waitFor(() => expect(vm.providers).toEqual(['dwd']))
    // a network chosen before it was found rejected leaves the selection with it
    await vi.waitFor(() => expect(vm.provider).toBeUndefined())
  })

  it('hides a network only when its check says the credentials are rejected', async () => {
    registerEndpoint('/api/coverage', () => ({
      aemet: { observation: credentialed() },
      knmi: { observation: credentialed() },
      metno: { frost: credentialed() },
      noaa: { ghcn: open },
    }))
    const answers: Record<string, () => unknown> = {
      aemet: () => ({ valid: false }),
      knmi: () => ({ valid: null }),
      metno: () => ({ valid: true }),
    }
    const asked: string[] = []
    registerEndpoint('/api/auth', (event) => {
      const { provider } = getQuery(event) as { provider: string }
      asked.push(provider)
      return answers[provider]!()
    })

    const wrapper = await mountSelection()
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(asked.toSorted()).toEqual(['aemet', 'knmi', 'metno']))
    await vi.waitFor(() => expect(vm.providers).toEqual(['knmi', 'metno', 'noaa']))
  })

  it('keeps a network whose check failed', async () => {
    registerEndpoint('/api/coverage', () => ({ aemet: { observation: credentialed() } }))
    let asked = 0
    registerEndpoint('/api/auth', (event) => {
      asked++
      setResponseStatus(event, 502)
      return { detail: 'Bad Gateway' }
    })

    const wrapper = await mountSelection()

    await vi.waitFor(() => expect(asked).toBe(1))
    // the request is not sent again (`retry: 0`; ofetch asks a failed GET once more by default): a
    // retry is made within a few turns of the event loop, so look after as many
    for (let turn = 0; turn < 10; turn++)
      await new Promise(resolve => setTimeout(resolve, 0))
    expect(asked).toBe(1)
    expect((wrapper.vm as any).providers).toEqual(['aemet'])
  })

  it('asks only about networks that have credentials configured', async () => {
    registerEndpoint('/api/coverage', () => ({
      aemet: { observation: credentialed() },
      knmi: { observation: credentialed(false) },
      noaa: { ghcn: open },
    }))
    const asked: string[] = []
    registerEndpoint('/api/auth', (event) => {
      asked.push((getQuery(event) as { provider: string }).provider)
      return { valid: true }
    })

    const wrapper = await mountSelection()

    await vi.waitFor(() => expect(asked).toEqual(['aemet']))
    await wrapper.vm.$nextTick()
    expect(asked).toEqual(['aemet'])
    expect((wrapper.vm as any).providers).toEqual(['aemet', 'noaa'])
  })

  it('aborts the checks it no longer needs when the page is left', async () => {
    const hold = gate()
    let asked = false
    registerEndpoint('/api/coverage', () => ({ aemet: { observation: credentialed() } }))
    registerEndpoint('/api/auth', async () => {
      asked = true
      await hold.released
      return { valid: false }
    })

    const wrapper = await mountSelection()
    await vi.waitFor(() => expect(asked).toBe(true))
    // the mocked endpoint heeds no signal, so the signal of the checks is looked at itself
    const signal: AbortSignal = (wrapper.vm as any).credentialChecks.signal
    expect(signal.aborted).toBe(false)
    wrapper.unmount()

    expect(signal.aborted).toBe(true)
    hold.release()
  })

  it('drops a network found rejected while the selection was still being restored', async () => {
    // initialization is waiting for the network's coverage when the rejection comes in, so the
    // watcher that clears the selection has to run again once initialization is over
    const hold = gate()
    registerEndpoint('/api/coverage', (event) => {
      if (getQuery(event).provider)
        return hold.released.then(() => dailyClimateSummaryCoverage())
      return { dwd: { observation: open }, aemet: { observation: credentialed() } }
    })
    registerEndpoint('/api/auth', () => ({ valid: false }))

    const wrapper = await mountSuspended(ParameterSelection, {
      props: { modelValue: { provider: 'aemet', network: 'observation' } },
    })
    mountedWrappers.push(wrapper)
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(vm.providers).toEqual(['dwd']))
    expect(vm.isInitializing).toBe(true)
    expect(vm.provider).toBe('aemet')

    hold.release()
    await vi.waitFor(() => expect(vm.isInitializing).toBe(false))
    await vi.waitFor(() => expect(vm.provider).toBeUndefined())
    expect(vm.network).toBeUndefined()
  })
})
