import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { measurement as measurementEn } from '~~/i18n/measurement/en'
import { methods as methodsDe } from '~~/i18n/methods/de'
import { methods as methodsEn } from '~~/i18n/methods/en'
import MeasurementPage from '~/pages/measurement.vue'
import MethodsPage from '~/pages/methods.vue'
import { WORK_IDS, workAnchor } from '~/utils/ask/works'
import { TOPICS } from '~/utils/measurement'
import { SEARCH_LOCALES, searchIndexFor } from '../../../modules/search-index/build'

// What the search leads to is on the page it leads to (GH-3790): the index is made from the sources, and a source can name an entry
// that a page does not draw. Here the pages are drawn and every anchor the index names is looked for in them, so a topic, a chip or a
// work that the index has and the page has not fails, and so does a chip of the texts that the page does not show.

const anchorsOf = (page: string) => [...new Set(searchIndexFor('en').docs.map(doc => doc[4]).filter(target => target.startsWith(`${page}#`)).map(target => target.slice(page.length + 1)))]

describe('the anchors the search leads to on "How weather is measured"', () => {
  it('are an element of the drawn page, for every entry', async () => {
    const wrapper = await mountSuspended(MeasurementPage)
    const root = wrapper.element as Element
    for (const topic of TOPICS)
      expect(root.querySelector(`[id="${topic}"]`), topic).not.toBeNull()
    for (const anchor of anchorsOf('/measurement'))
      expect(root.querySelector(`[id="${anchor}"]`), anchor).not.toBeNull()
    // an entry of the texts has its topic: the texts and the list of topics are the same
    expect(Object.keys(measurementEn).sort()).toEqual([...TOPICS].sort())
  })
})

describe('the anchors the search leads to on the methods', () => {
  it('are an element of the drawn page, for every chip of the texts, every work and every anchor of the index, in each language of the texts', async () => {
    const wrapper = await mountSuspended(MethodsPage)
    const root = wrapper.element as Element
    for (const texts of [methodsEn, methodsDe]) {
      for (const chip of Object.keys(texts.chips))
        expect(root.querySelector(`[id="${chip}"]`), chip).not.toBeNull()
    }
    for (const id of WORK_IDS)
      expect(root.querySelector(`[id="${workAnchor(id)}"]`), id).not.toBeNull()
    for (const locale of SEARCH_LOCALES) {
      for (const [, , , , to] of searchIndexFor(locale).docs.filter(doc => doc[4].startsWith('/methods#')))
        expect(root.querySelector(`[id="${to.slice('/methods#'.length)}"]`), `${locale}: ${to}`).not.toBeNull()
    }
  })
})
