import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import ApiPage from '~/pages/api.vue'
import ExplorerPage from '~/pages/explorer.vue'
import HistoryPage from '~/pages/history.vue'
import ImpressumPage from '~/pages/impressum.vue'
import IndexPage from '~/pages/index.vue'
import MeteogramPage from '~/pages/meteogram.vue'
import SettingsPage from '~/pages/settings.vue'
import StripesPage from '~/pages/stripes.vue'
import SupportPage from '~/pages/support.vue'
import WidgetPage from '~/pages/widget.vue'

// German is the app's defaultLocale (nuxt.config.ts) and what most users see
// without an explicit language preference -- every page must render it, not
// just the English strings the rest of the suite happens to assert on.

const SetLocale = defineComponent({
  setup() {
    const { setLocale } = useI18n()
    return { setLocale }
  },
  render: () => h('div'),
})

describe('german (de) locale rendering', () => {
  beforeAll(async () => {
    const harness = await mountSuspended(SetLocale)
    await (harness.vm as any).setLocale('de')
    await nextTick()
  })

  it('renders the home page in German', async () => {
    const wrapper = await mountSuspended(IndexPage)
    expect(wrapper.text()).toContain('Offene Wetterdaten für Menschen')
    expect(wrapper.text()).toContain('Was möchten Sie tun?')
  })

  it('renders the API page in German', async () => {
    const wrapper = await mountSuspended(ApiPage)
    expect(wrapper.text()).toContain('Wetterdaten programmatisch abrufen')
  })

  it('renders the support page in German', async () => {
    const wrapper = await mountSuspended(SupportPage)
    expect(wrapper.text()).toContain('Unterstützen')
    expect(wrapper.text()).toContain('Fehler melden')
  })

  it('renders the impressum page in German', async () => {
    const wrapper = await mountSuspended(ImpressumPage)
    expect(wrapper.text()).toContain('Angaben gemäß § 5 DDG')
  })

  it('renders the settings page in German', async () => {
    const wrapper = await mountSuspended(SettingsPage)
    expect(wrapper.text()).toContain('Einstellungen')
    expect(wrapper.text()).toContain('Sprache')
    expect(wrapper.text()).toContain('Darstellung')
  })

  it('renders the explorer page in German', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {} } }))
    const wrapper = await mountSuspended(ExplorerPage)
    expect(wrapper.text()).toContain('Stationen und Messdaten interaktiv erkunden')
  })

  it('renders the history page in German', async () => {
    registerEndpoint('/api/coverage', () => ({ dwd: { observation: {} } }))
    const wrapper = await mountSuspended(HistoryPage)
    expect(wrapper.text()).toContain('Stationschronik')
    expect(wrapper.text()).toContain('Bitte zuerst Auflösung und Datensatz wählen')
  })

  it('renders the stripes page in German', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )
    const wrapper = await mountSuspended(StripesPage)
    expect(wrapper.text()).toContain('Klimastreifen')
    expect(wrapper.text()).toContain('Wetterelement')
  })

  it('renders the meteogram page in German', async () => {
    registerEndpoint('/api/stations', () => ({ stations: [] }))
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Wettervorhersage')
    expect(wrapper.text()).toContain('Temperatur, Niederschlag und Wind')
  })

  it('renders the widget page in German', async () => {
    const wrapper = await mountSuspended(WidgetPage)
    expect(wrapper.text()).toContain('Keine Station angegeben')
  })
})
