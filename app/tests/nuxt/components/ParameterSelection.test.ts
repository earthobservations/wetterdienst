import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { clearNuxtData } from '#app'
import { ParameterSelection } from '#components'
import { dailyClimateSummaryCoverage } from '../fixtures/coverage'
import { networksAnswer } from '../fixtures/providers'

// The component starts its /api/providers request without awaiting it in setup -- awaiting would
// suspend the whole page behind it -- so mountSuspended() now returns before the answer lands.
// Anything that reads what the list of networks feeds has to wait for initialization to finish first.
//
// Every wrapper is unmounted after its test: a component left mounted shares the `/api/providers`
// entry of the next test's, and its credential checks answer the next test's list too
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
    // can be shadowed by an earlier test's cached /api/providers response.
    clearNuxtData()
  })

  it('renders itself while /api/providers is still out', async () => {
    // The regression this guards: the request for the networks used to be awaited at the top level of
    // setup, which with `ssr: false` suspended the whole page -- the Explorer showed nothing at
    // all, not even its own headings, until the backend answered. A request that never settles
    // makes that visible.
    vi.mocked(globalThis.fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>)

    const wrapper = await mountSuspended(ParameterSelection, {
      props: { modelValue: {}, restrictProvider: 'dwd' },
    })
    mountedWrappers.push(wrapper)

    expect(wrapper.find('h2').text()).toBe('Data')
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
    expect(wrapper.find('h2').text()).toBe('Data')
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
    // an answer: a failed request has nothing to restore and tells the parent nothing (GH-4042)
    registerEndpoint('/api/coverage', () => dailyClimateSummaryCoverage())
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: {} } }))

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
    registerEndpoint('/api/coverage', () => dailyClimateSummaryCoverage())
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: {} } }))

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
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: {} }, noaa: { ghcn: {} } }))

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
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: {}, mosmix: {} } }))

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
    registerEndpoint('/api/providers', () => networksAnswer({
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
    // a kind that is no timeseries kind is not offered, a later standalone network
    registerEndpoint('/api/providers', () => networksAnswer({
      dwd: {
        observation: network('observation'),
        mosmix: network('forecast'),
        radar: network('radar'),
        alerts: network('alerts'),
        satellite: network('satellite'),
      },
      standalone: { alerts: network('alerts') },
    }))

    const wrapper = await mountReady({ modelValue: { provider: 'dwd' } })

    const vm = wrapper.vm as any
    expect(vm.networks).toEqual(['observation', 'mosmix'])
    // a provider with nothing but a standalone network is no provider to choose
    expect(vm.providers).toEqual(['dwd'])
  })

  it('does not fall back to the unrestricted provider list when restrictProvider does not exist', async () => {
    registerEndpoint('/api/providers', () => networksAnswer({ noaa: { ghcn: {} } }))

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
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { mosmix: {} } }))

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
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: {} }, noaa: { ghcn: {} } }))

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

  it('emits the kind of the network from the coverage: a forecast\'s readings lie ahead of today (GH-3740)', async () => {
    const kinds = { mosmix: 'forecast', observation: 'observation' } as const
    registerEndpoint('/api/coverage', () => dailyClimateSummaryCoverage())
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: Object.fromEntries(Object.entries(kinds).map(([name, kind]) => [name, { auth: false, configured: false, kind }])) }))
    const kindOf = async (network: string) => {
      const wrapper = await mountReady({
        modelValue: { provider: 'dwd', network, resolution: 'daily', dataset: 'climate_summary', parameters: ['temperature_air_max_2m'] },
      })
      // what the page last got: the selection with the kind the coverage gives its network
      await vi.waitFor(() => expect((wrapper.emitted('update:modelValue') ?? []).length).toBeGreaterThan(0))
      return (wrapper.emitted('update:modelValue') ?? []).at(-1)![0] as { kind?: string }
    }
    expect((await kindOf('mosmix')).kind).toBe('forecast')
    clearNuxtData()
    expect((await kindOf('observation')).kind).toBe('observation')
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
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: open }, aemet: { observation: credentialed() } }))
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
    registerEndpoint('/api/providers', () => networksAnswer({
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
    registerEndpoint('/api/providers', () => networksAnswer({ aemet: { observation: credentialed() } }))
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
    registerEndpoint('/api/providers', () => networksAnswer({
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
    registerEndpoint('/api/providers', () => networksAnswer({ aemet: { observation: credentialed() } }))
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
    registerEndpoint('/api/coverage', () => hold.released.then(() => dailyClimateSummaryCoverage()))
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { observation: open }, aemet: { observation: credentialed() } }))
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

// The list of providers is the one request the selects are built from. A request that failed says nothing about which
// providers exist, so it is not the banner "not available from this backend", which is for an answer that arrived and does
// not list the provider (GH-4042).
describe('parameterSelection Component, the list of providers', () => {
  beforeEach(() => {
    clearNuxtData()
  })

  const RESTRICTED = { modelValue: {}, restrictProvider: 'dwd', restrictNetwork: 'observation' }
  const UNREACHABLE = 'The backend could not be reached, so the providers cannot be listed.'
  const NOT_AVAILABLE = 'is not available from this backend'
  const retryButton = (wrapper: { findAll: (selector: string) => Array<{ text: () => string, trigger: (event: string) => Promise<unknown> }> }) =>
    wrapper.findAll('button').find(button => button.text() === 'Retry')
  const serviceUnavailable = (event: Parameters<typeof setResponseStatus>[0]) => {
    setResponseStatus(event, 503)
    return { detail: 'Service Unavailable' }
  }

  it('says the backend could not be reached when the request fails with a 5xx, and does not blame the provider', async () => {
    registerEndpoint('/api/providers', serviceUnavailable)

    const wrapper = await mountReady(RESTRICTED)

    expect(wrapper.text()).toContain(UNREACHABLE)
    expect(wrapper.text()).not.toContain(NOT_AVAILABLE)
    expect(retryButton(wrapper)).toBeDefined()
  })

  it('says the same where the page restricts nothing: the selects are empty and the reader is told why', async () => {
    registerEndpoint('/api/providers', serviceUnavailable)

    const wrapper = await mountReady({ modelValue: {} })

    expect(wrapper.text()).toContain(UNREACHABLE)
    expect(retryButton(wrapper)).toBeDefined()
  })

  it('keeps the text about the provider for an answer that arrived and does not list it, with no retry', async () => {
    registerEndpoint('/api/providers', () => networksAnswer({ noaa: { ghcn: {} } }))

    const wrapper = await mountReady(RESTRICTED)

    expect(wrapper.text()).toContain('The configured provider “dwd” is not available from this backend.')
    expect(wrapper.text()).not.toContain(UNREACHABLE)
    expect(retryButton(wrapper)).toBeUndefined()
  })

  it('keeps the text about the network for an answer that lists the provider without it', async () => {
    registerEndpoint('/api/providers', () => networksAnswer({ dwd: { mosmix: {} } }))

    const wrapper = await mountReady(RESTRICTED)

    expect(wrapper.text()).toContain('The configured network “observation” is not available for this provider.')
    expect(wrapper.text()).not.toContain(UNREACHABLE)
    expect(retryButton(wrapper)).toBeUndefined()
  })

  it('shows neither while the request is out', async () => {
    registerEndpoint('/api/providers', () => new Promise(() => {}))

    const wrapper = await mountSuspended(ParameterSelection, { props: RESTRICTED })
    mountedWrappers.push(wrapper)

    expect(wrapper.text()).not.toContain(UNREACHABLE)
    expect(wrapper.text()).not.toContain(NOT_AVAILABLE)
  })

  // The backend's state, which the test changes between the first answer and the retry. `asked` counts the requests made,
  // and one failed `GET` is asked twice (ofetch retries a 503 once), so a count is compared with itself, not with a number.
  function backend(whenUp: () => unknown) {
    const state = { up: false, asked: 0 }
    registerEndpoint('/api/providers', (event) => {
      state.asked++
      return state.up ? whenUp() : serviceUnavailable(event)
    })
    return state
  }

  it('asks again on Retry, takes the banner away and restores the restricted selection from the answer', async () => {
    registerEndpoint('/api/coverage', () => dailyClimateSummaryCoverage())
    const server = backend(() => networksAnswer({ dwd: { observation: {} } }))

    const wrapper = await mountReady(RESTRICTED)
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain(UNREACHABLE)
    expect(vm.provider).toBeUndefined()
    const askedBefore = server.asked

    server.up = true
    await retryButton(wrapper)!.trigger('click')

    await vi.waitFor(() => expect(wrapper.text()).not.toContain(UNREACHABLE))
    // exactly one more request, and the answer is what the selects are built from
    expect(server.asked).toBe(askedBefore + 1)
    await vi.waitFor(() => expect(vm.isInitializing).toBe(false))
    await vi.waitFor(() => expect(vm.provider).toBe('dwd'))
    expect(vm.network).toBe('observation')
    expect(wrapper.text()).not.toContain(NOT_AVAILABLE)
    expect(retryButton(wrapper)).toBeUndefined()
  })

  it('keeps the banner and its button when the retry fails too', async () => {
    const server = backend(() => networksAnswer({ dwd: { observation: {} } }))

    const wrapper = await mountReady(RESTRICTED)
    const askedBefore = server.asked
    await retryButton(wrapper)!.trigger('click')

    await vi.waitFor(() => expect(server.asked).toBeGreaterThan(askedBefore))
    await vi.waitFor(() => expect(wrapper.text()).toContain(UNREACHABLE))
    expect(wrapper.text()).not.toContain(NOT_AVAILABLE)
    expect(retryButton(wrapper)).toBeDefined()
  })

  // A parent that holds the selection as the Explorer and History do (v-model), starting from a link's selection
  async function mountWithParent(restricted: boolean) {
    const selection = ref<any>({ provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters: ['temperature_air_max_2m'] })
    const emitted: any[] = []
    const Parent = defineComponent({
      setup: () => () => h(ParameterSelection, {
        'modelValue': selection.value,
        'onUpdate:modelValue': (value: any) => {
          emitted.push(value)
          selection.value = value
        },
        ...(restricted ? { restrictProvider: 'dwd', restrictNetwork: 'observation' } : {}),
      }),
    })
    const wrapper = await mountSuspended(Parent)
    mountedWrappers.push(wrapper)
    return { wrapper, selection, emitted }
  }

  it.each([true, false])('keeps the parent\'s selection while the backend is down, and restores it on Retry (restricted: %s)', async (restricted) => {
    registerEndpoint('/api/coverage', () => dailyClimateSummaryCoverage())
    const server = backend(() => networksAnswer({ dwd: { observation: {} } }))
    const link = { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters: ['temperature_air_max_2m'] }

    const { wrapper, selection, emitted } = await mountWithParent(restricted)
    await vi.waitFor(() => expect(wrapper.text()).toContain(UNREACHABLE))
    await vi.waitFor(() => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false))
    await new Promise(resolve => setTimeout(resolve, 100))
    // nothing could be restored, so nothing was told: the parent (and the address it writes) keeps the link's selection
    expect(emitted).toEqual([])
    expect(selection.value).toEqual(link)

    server.up = true
    await retryButton(wrapper)!.trigger('click')

    const vm = wrapper.findComponent(ParameterSelection).vm as any
    // the selects hold the link's selection again, from the first `modelValue`, and the parent is told it
    await vi.waitFor(() => {
      expect(vm.isInitializing).toBe(false)
      expect([vm.provider, vm.network, vm.resolution, vm.dataset, vm.parameters]).toEqual(['dwd', 'observation', 'daily', 'climate_summary', ['temperature_air_max_2m']])
    })
    expect(wrapper.text()).not.toContain(UNREACHABLE)
    expect(emitted.at(-1)).toMatchObject(link)
    expect(selection.value).toMatchObject(link)
  })

  it('restores from what the parent handed over first, not from what it holds by the time of the retry', async () => {
    registerEndpoint('/api/coverage', () => dailyClimateSummaryCoverage())
    const server = backend(() => networksAnswer({ dwd: { observation: {} } }))

    const { wrapper, selection } = await mountWithParent(false)
    await vi.waitFor(() => expect(wrapper.text()).toContain(UNREACHABLE))
    await vi.waitFor(() => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false))
    // a parent that moved on meanwhile (the address changed, a reset)
    selection.value = { parameters: [] }

    server.up = true
    await retryButton(wrapper)!.trigger('click')

    const vm = wrapper.findComponent(ParameterSelection).vm as any
    await vi.waitFor(() => expect([vm.provider, vm.network, vm.resolution, vm.dataset]).toEqual(['dwd', 'observation', 'daily', 'climate_summary']))
  })

  it('tells a retry that finds the provider missing apart from one that fails', async () => {
    const server = backend(() => networksAnswer({ noaa: { ghcn: {} } }))

    const wrapper = await mountReady(RESTRICTED)
    server.up = true
    await retryButton(wrapper)!.trigger('click')

    await vi.waitFor(() => expect(wrapper.text()).toContain('The configured provider “dwd” is not available from this backend.'))
    expect(wrapper.text()).not.toContain(UNREACHABLE)
    expect(retryButton(wrapper)).toBeUndefined()
  })
})
