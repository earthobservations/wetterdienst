import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeAll, describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import MethodsPage from '~/pages/methods.vue'
import { CHIPS } from '~/utils/ask/registry'
import { WORK_IDS, workAnchor } from '~/utils/ask/works'

// "How the answers are worked out" (GH-3764): the page of the methods is written from the definitions of the chips, so a chip that is in
// the registry is on it; its anchors, the headings, the links to the works cited, and the language of the texts.

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

  it('has one title, a section for each chip of the registry and an entry for each work', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    expect(wrapper.findAll('h1').map(h => h.text())).toEqual(['How the answers are worked out'])
    expect(wrapper.findAll('article.method-section').map(article => article.attributes('id'))).toEqual(CHIPS.map(chip => chip.id))
    expect(wrapper.findAll('article[data-testid="work"]').map(article => article.attributes('id'))).toEqual(WORK_IDS.map(workAnchor))
    for (const article of wrapper.findAll('article')) {
      const heading = article.find('h3')
      // the heading is what names the entry and what the focus goes to (an anchor's target)
      expect(heading.attributes('id')).toBe(`${article.attributes('id')}-title`)
      expect(heading.attributes('tabindex')).toBe('-1')
      expect(article.attributes('aria-labelledby')).toBe(heading.attributes('id'))
    }
    expect(wrapper.findAll('h2').map(h => h.text())).toEqual(['Contents', 'How to read this page', 'The questions', 'Works cited'])
  })

  it('has its headings in order: no level is skipped on the way down', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    const levels = headingLevels(wrapper.element)
    expect(levels[0]).toBe(1)
    for (let index = 1; index < levels.length; index++)
      expect(levels[index]! - levels[index - 1]!, `heading ${index}`).toBeLessThanOrEqual(1)
    expect(levels).toContain(4)
    expect(levels).not.toContain(5)
  })

  it('has a table of contents of real links to the sections and the works', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    const toc = wrapper.find('nav[aria-labelledby="methods-toc"]')
    expect(toc.exists()).toBe(true)
    expect(toc.findAll('a').map(link => link.attributes('href'))).toEqual([...CHIPS.map(chip => `/methods#${chip.id}`), '/methods#works'])
    expect(toc.findAll('a')[0]!.text()).toBe('Will it rain tomorrow?')
  })

  it('writes every step, rule and limit of a chip from its definition, in order', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    for (const chip of CHIPS) {
      const section = wrapper.find(`article#${chip.id}`)
      expect(section.findAll('[data-step]').map(step => step.attributes('data-step'))).toEqual([...chip.explanation.steps])
      expect(section.findAll('[data-rule]').map(rule => rule.attributes('data-rule'))).toEqual(chip.explanation.rules.map(rule => rule.id))
      expect(section.findAll('[data-testid="method-formula"]')).toHaveLength(chip.explanation.formulas.length)
      // the numbers are the code's, not a text's: no name is left unfilled
      expect(section.text()).not.toMatch(/\{\w+\}/)
    }
  })

  it('marks every choice that is wetterdienst\'s own with a word, and gives its reasoning', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    for (const chip of CHIPS) {
      const section = wrapper.find(`article#${chip.id}`)
      const own = chip.explanation.rules.filter(rule => rule.own)
      expect(section.findAll('[data-own]').map(rule => rule.attributes('data-rule'))).toEqual(own.map(rule => rule.id))
      expect(section.findAll('[data-testid="own-mark"]')).toHaveLength(own.length)
      for (const rule of section.findAll('[data-own]'))
        expect(rule.find('[data-testid="own-mark"]').text()).toBe('wetterdienst\'s own choice.')
    }
  })

  it('links every source to an entry of the works cited that is there', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    const anchors = new Set(wrapper.findAll('article[data-testid="work"]').map(article => article.attributes('id')))
    const links = wrapper.findAll('a[href^="/methods#work-"]')
    expect(links.length).toBeGreaterThan(10)
    for (const link of links)
      expect(anchors.has(link.attributes('href')!.slice('/methods#'.length)), link.attributes('href')).toBe(true)
  })

  it('names the places in the works and the works with the formal citation as a link to the issuer', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    expect(wrapper.text()).toContain('WMO-No. 1203 (2017), §4.4.2')
    const work = wrapper.find('article#work-wmo-1203')
    expect(work.find('a[target="_blank"]').attributes('href')).toMatch(/^https:\/\/library\.wmo\.int\//)
    expect(work.find('a[target="_blank"]').attributes('rel')).toContain('noopener')
    expect(work.text()).toContain('Used by')
  })

  it('links the terms to "How weather is measured" and a chip to the question it answers', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    const summer = wrapper.find('article#summer')
    expect(summer.findAll('a').some(link => link.attributes('href') === '/measurement#normals')).toBe(true)
    expect(wrapper.find('[data-testid="method-ask"]').attributes('href')).toBe('/?ask=rain')
  })

  it('has no note where the text is in the language of the page', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    expect(wrapper.find('[data-testid="methods-note"]').exists()).toBe(false)
  })
})

describe('the page in other languages', () => {
  it('is in German in German, with no note', async () => {
    await useLocale('de')
    const wrapper = await mountSuspended(MethodsPage)
    expect(wrapper.findAll('h1').map(h => h.text())).toEqual(['Wie die Antworten entstehen'])
    expect(wrapper.find('article#rain h3').text()).toBe('Regnet es morgen?')
    expect(wrapper.find('[data-testid="methods-note"]').exists()).toBe(false)
    expect(wrapper.find('article#rain h3').attributes('lang')).toBeUndefined()
  })

  it('is in English in French, with the note, and says so in the language of its text', async () => {
    await useLocale('fr')
    const wrapper = await mountSuspended(MethodsPage)
    expect(wrapper.find('article#rain h3').text()).toBe('Will it rain tomorrow?')
    const notes = wrapper.findAll('[data-testid="methods-note"]')
    expect(notes).toHaveLength(CHIPS.length)
    expect(wrapper.find('article#rain h3').attributes('lang')).toBe('en')
    await useLocale('en')
  })

  it('is in German in Luxembourgish, with the note', async () => {
    await useLocale('lb')
    const wrapper = await mountSuspended(MethodsPage)
    expect(wrapper.find('article#rain h3').text()).toBe('Regnet es morgen?')
    expect(wrapper.find('article#rain h3').attributes('lang')).toBe('de')
    await useLocale('en')
  })
})
