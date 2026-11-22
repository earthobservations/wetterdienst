import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { clearNuxtData } from '#app'
import GlossaryPage from '~/pages/glossary.vue'
import MeasurementPage from '~/pages/measurement.vue'
import { TOPICS } from '~/utils/measurement'

// "How weather is measured" (GH-3787): the page, its anchors and the table of contents, the language of its texts, and
// the glossary's links to it.

const SetLocale = defineComponent({
  setup() {
    const { setLocale } = useI18n()
    return { setLocale }
  },
  render: () => h('div'),
})

async function useLocale(code: string) {
  const harness = await mountSuspended(SetLocale)
  await (harness.vm as any).setLocale(code)
  await nextTick()
}

/** The levels of the headings of a page, in the order of the page */
function headingLevels(root: Element): number[] {
  return [...root.querySelectorAll('h1, h2, h3, h4, h5, h6')].map(heading => Number(heading.tagName.slice(1)))
}

describe('the page in English', () => {
  beforeAll(() => useLocale('en'))

  it('has one title, the two sections and an entry for each anchor, with its heading', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    expect(wrapper.findAll('h1').map(h => h.text())).toEqual(['How weather is measured'])
    const articles = wrapper.findAll('article')
    expect(articles.map(article => article.attributes('id'))).toEqual([...TOPICS])
    for (const article of articles) {
      const heading = article.find('h3')
      // the heading is what names the entry and what the focus goes to (an anchor's target)
      expect(heading.attributes('id')).toBe(`${article.attributes('id')}-title`)
      expect(heading.attributes('tabindex')).toBe('-1')
      expect(article.attributes('aria-labelledby')).toBe(heading.attributes('id'))
    }
    expect(wrapper.findAll('h2').map(h => h.text())).toEqual(['Contents', 'Sources and edition', 'What is measured, and how', 'Reading the data'])
  })

  it('has its headings in order: no level is skipped on the way down', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    const levels = headingLevels(wrapper.element)
    expect(levels[0]).toBe(1)
    for (let index = 1; index < levels.length; index++)
      expect(levels[index]! - levels[index - 1]!, `heading ${index}`).toBeLessThanOrEqual(1)
    // the entries are third-level headings under the section, their parts fourth-level
    expect(levels).toContain(4)
    expect(levels).not.toContain(5)
  })

  it('has a table of contents of links to the entries, which are links and so keyboard operable', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    const toc = wrapper.find('nav[aria-labelledby="measurement-toc"]')
    expect(toc.exists()).toBe(true)
    const links = toc.findAll('a')
    expect(links.map(link => link.attributes('href'))).toEqual(TOPICS.map(topic => `/measurement#${topic}`))
    // each link is a real <a href>: Tab reaches it and Enter follows it, with no script of the page involved
    for (const link of links)
      expect(link.element.tagName).toBe('A')
    expect(links[0]!.text()).toBe('Air and soil temperature')
  })

  it('gives each entry a link to its own anchor, named by the entry', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    for (const topic of TOPICS) {
      const article = wrapper.find(`article#${topic}`)
      const own = article.findAll('a').find(link => link.attributes('href') === `/measurement#${topic}`)
      expect(own, topic).toBeDefined()
      expect(own!.attributes('aria-label')).toContain(article.find('h3').text())
    }
  })

  it('says for each entry what its source is in plain words and cites it, with a link that leaves the app safely', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    const wind = wrapper.find('article#wind')
    expect(wind.text()).toContain('World Meteorological Organization')
    const cite = wind.findAll('a').find(link => link.text().includes('WMO-No. 8'))!
    expect(cite.text()).toContain('2024 edition')
    expect(cite.attributes('href')).toMatch(/^https:\/\/library\.wmo\.int\//)
    expect(cite.attributes('target')).toBe('_blank')
    expect(cite.attributes('rel')).toContain('noopener')
  })

  it('names the glossary parameters an entry explains, with a link that shows them in the glossary', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    const wind = wrapper.find('article#wind')
    expect(wind.text()).toContain('wind_gust_*')
    const link = wind.findAll('a').find(a => a.attributes('href')?.startsWith('/glossary'))!
    expect(link.attributes('href')).toBe('/glossary?topic=wind')
    // an entry that explains no parameter has no such section
    expect(wrapper.find('article#time').text()).not.toContain('Glossary fields')
  })

  it('shows no note: the text is in the language of the page', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    expect(wrapper.find('[data-testid="measurement-note"]').exists()).toBe(false)
    expect(wrapper.find('article#wind [lang]').exists()).toBe(false)
  })
})

describe('the page in German', () => {
  beforeAll(() => useLocale('de'))
  afterAll(() => useLocale('en'))

  it('reads in German, with no note', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    expect(wrapper.find('h1').text()).toBe('So wird Wetter gemessen')
    expect(wrapper.find('article#temperature h3').text()).toBe('Luft- und Bodentemperatur')
    expect(wrapper.find('article#wind').text()).toContain('Die Beaufortskala')
    expect(wrapper.find('[data-testid="measurement-note"]').exists()).toBe(false)
    expect(wrapper.find('nav[aria-labelledby="measurement-toc"] h2').text()).toBe('Inhalt')
  })
})

describe('the page in a language that has no text of its own yet', () => {
  afterAll(() => useLocale('en'))

  it('shows each entry in English, with a note in the reader\'s language, and says the language of the text', async () => {
    await useLocale('fr')
    const wrapper = await mountSuspended(MeasurementPage)
    // the interface is French, the entries are English
    expect(wrapper.find('h1').text()).toBe('Comment la météo est mesurée')
    expect(wrapper.find('article#wind h3').text()).toBe('Wind: mean speed and gusts')
    expect(wrapper.find('article#wind h3').attributes('lang')).toBe('en')
    const notes = wrapper.findAll('[data-testid="measurement-note"]')
    expect(notes).toHaveLength(TOPICS.length)
    expect(notes[0]!.text()).toBe('Cette entrée n\'est pas encore traduite dans ta langue et s\'affiche en anglais.')
    // a part of the text says the language too, not only its heading
    expect(wrapper.find('article#wind section [lang="en"], article#wind div[lang="en"]').exists()).toBe(true)
  })

  it('shows Low German the German text, and says so', async () => {
    await useLocale('de-hh')
    const wrapper = await mountSuspended(MeasurementPage)
    expect(wrapper.find('article#temperature h3').text()).toBe('Luft- und Bodentemperatur')
    expect(wrapper.find('article#temperature h3').attributes('lang')).toBe('de')
    expect(wrapper.find('[data-testid="measurement-note"]').text()).toContain('Hochdüütsch')
  })
})

describe('the page in Luxembourgish', () => {
  afterAll(() => useLocale('en'))

  it('is shown the German text, like Low German, and told so in its own language', async () => {
    await useLocale('lb')
    const wrapper = await mountSuspended(MeasurementPage)
    expect(wrapper.find('article#temperature h3').text()).toBe('Luft- und Bodentemperatur')
    expect(wrapper.find('article#temperature h3').attributes('lang')).toBe('de')
    expect(wrapper.find('[data-testid="measurement-note"]').text()).toContain('Däitsch')
  })
})

describe('an anchor', () => {
  it('puts the focus on the heading of the entry', async () => {
    await useLocale('en')
    const router = useRouter()
    await router.push('/measurement')
    const wrapper = await mountSuspended(MeasurementPage, { attachTo: document.body })
    await router.push('/measurement#snow')
    await vi.waitFor(() => expect(document.activeElement?.id).toBe('snow-title'))
    wrapper.unmount()
  })

  it('leaves the focus where it is for a hash that is no entry', async () => {
    const router = useRouter()
    await router.push('/measurement')
    const wrapper = await mountSuspended(MeasurementPage, { attachTo: document.body })
    ;(document.activeElement as HTMLElement | null)?.blur()
    await router.push('/measurement#nothing')
    await nextTick()
    expect(document.activeElement === document.body || document.activeElement === null || document.activeElement.id !== 'nothing-title').toBe(true)
    wrapper.unmount()
  })
})

describe('the glossary', () => {
  const entries = [
    { name: 'wind_gust_max', unit_type: 'speed', unit: 'meter_per_second', unit_symbol: 'm/s', description: 'Maximum wind gust.' },
    { name: 'temperature_air_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Temperature of the air two metres above the ground.' },
    { name: 'sunshine_duration_normal', unit_type: 'duration', unit: 'hour', unit_symbol: 'h', description: 'Climatological normal of the sunshine duration for the period.' },
    { name: 'humidity_relative', unit_type: 'fraction', unit: 'percent', unit_symbol: '%', description: 'Relative humidity.' },
    { name: 'temperature_dew_point_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Dew point at 2 m above ground.' },
    { name: 'pressure_vapor', unit_type: 'pressure', unit: 'hectopascal', unit_symbol: 'hPa', description: 'Partial pressure of water vapour.' },
    { name: 'cloud_cover_total', unit_type: 'fraction', unit: 'percent', unit_symbol: '%', description: 'Total cloud cover.' },
    { name: 'weather', unit_type: 'dimensionless', unit: 'dimensionless', unit_symbol: '', description: 'Coded present weather at the time of observation.' },
    { name: 'soil_state_index', unit_type: 'dimensionless', unit: 'dimensionless', unit_symbol: '', description: 'Coded state of the ground surface.' },
    { name: 'soil_moisture_grass_sand_00cm_60cm', unit_type: 'fraction', unit: 'percent', unit_symbol: '%', description: 'Soil moisture in sand under grass.' },
    { name: 'evaporation_amount_grass_sand', unit_type: 'precipitation', unit: 'millimeter', unit_symbol: 'mm', description: 'Depth of water evaporated from sand under grass.' },
  ]
  registerEndpoint('/api/glossary', () => entries)

  async function mountGlossary(route = '/glossary') {
    clearNuxtData()
    const router = useRouter()
    await router.push(route)
    const wrapper = await mountSuspended(GlossaryPage, { route })
    await vi.waitFor(() => expect((wrapper.vm as any).pending).toBe(false), { timeout: 5000 })
    return wrapper
  }

  it('links each parameter that has an entry to it, and a parameter that has none to nothing', async () => {
    await useLocale('en')
    const wrapper = await mountGlossary()
    const hrefs = wrapper.findAll('a').map(link => link.attributes('href')).filter(href => href?.startsWith('/measurement'))
    // one link for each parameter: the relative humidity, the dew point and the vapour pressure share the humidity entry
    expect(hrefs.sort()).toEqual([
      '/measurement#clouds',
      '/measurement#evaporation',
      '/measurement#humidity',
      '/measurement#humidity',
      '/measurement#humidity',
      '/measurement#normals',
      '/measurement#present-weather',
      '/measurement#present-weather',
      '/measurement#soil-moisture',
      '/measurement#temperature',
      '/measurement#wind',
    ])
    // the link says which parameter it is for, to a screen reader that lists the links of the page
    expect(wrapper.find('a[href="/measurement#wind"]').text()).toContain('How is this measured?')
    expect(wrapper.find('a[href="/measurement#wind"]').text()).toContain('Maximum wind gust')
  })

  it('shows only the parameters of one entry for its link, and a way back to all of them', async () => {
    await useLocale('en')
    const wrapper = await mountGlossary('/glossary?topic=wind')
    const shown = (wrapper.vm as any).entries.map((entry: { name: string }) => entry.name)
    expect(shown).toEqual(['wind_gust_max'])
    expect(wrapper.find('[data-testid="glossary-topic"]').text()).toContain('Only “Wind”')
    expect(wrapper.find('[data-testid="glossary-topic"] a').attributes('href')).toBe('/glossary')
  })

  it('shows the parameters of the humidity entry, the dew point and the vapour pressure with the relative humidity', async () => {
    await useLocale('en')
    const wrapper = await mountGlossary('/glossary?topic=humidity')
    const shown = (wrapper.vm as any).entries.map((entry: { name: string }) => entry.name)
    expect([...shown].sort()).toEqual(['humidity_relative', 'pressure_vapor', 'temperature_dew_point_2m'])
    expect(wrapper.find('[data-testid="glossary-topic"]').text()).toContain('Only “Humidity and dew point”')
  })

  it('shows the parameters of the entry on present weather and the state of the ground, whose id has a hyphen', async () => {
    await useLocale('en')
    const wrapper = await mountGlossary('/glossary?topic=present-weather')
    const shown = (wrapper.vm as any).entries.map((entry: { name: string }) => entry.name)
    expect([...shown].sort()).toEqual(['soil_state_index', 'weather'])
    expect(wrapper.find('[data-testid="glossary-topic"]').text()).toContain('Only “Present weather and state of the ground”')
  })

  it('takes an entry that explains no parameter for no filter, as an id that is none', async () => {
    await useLocale('en')
    const wrapper = await mountGlossary('/glossary?topic=time')
    expect((wrapper.vm as any).entries).toHaveLength(entries.length)
    expect(wrapper.find('[data-testid="glossary-topic"]').exists()).toBe(false)
  })

  it('takes a topic that is none for no filter', async () => {
    await useLocale('en')
    const wrapper = await mountGlossary('/glossary?topic=hydrology')
    expect((wrapper.vm as any).entries).toHaveLength(entries.length)
    expect(wrapper.find('[data-testid="glossary-topic"]').exists()).toBe(false)
  })
})
