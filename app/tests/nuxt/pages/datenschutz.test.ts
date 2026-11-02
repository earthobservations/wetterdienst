import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { useRouter } from '#imports'
import App from '~/app.vue'
import DatenschutzPage from '~/pages/datenschutz.vue'
import ImpressumPage from '~/pages/impressum.vue'
import { OPERATOR } from '~/utils/operator'

// The privacy policy is German for the German locales (the binding text) and English for every other,
// at /datenschutz and its alias /privacy. The operator it names is the one of the Impressum.

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

describe('privacy policy page', () => {
  afterAll(async () => {
    // the other files of the run start from the default language
    await useLocale('en')
  })

  describe('in German', () => {
    beforeAll(() => useLocale('de'))

    it('renders the German text with its title and every section', async () => {
      const wrapper = await mountSuspended(DatenschutzPage)
      expect(wrapper.find('h1').text()).toBe('Datenschutzerklärung')
      const text = wrapper.text()
      expect(text).toContain('Hetzner')
      expect(text).toContain('Art. 6 Abs. 1 lit. f DSGVO')
      expect(text).toContain('Hamburgische Beauftragte für Datenschutz und Informationsfreiheit')
      expect(text).toContain('wd_lang')
      expect(wrapper.find('[lang]').attributes('lang')).toBe('de')
    })

    it('also serves Low German readers the German text', async () => {
      await useLocale('de-hh')
      const wrapper = await mountSuspended(DatenschutzPage)
      expect(wrapper.find('h1').text()).toBe('Datenschutzerklärung')
      await useLocale('de')
    })

    it('sets the document title (WCAG 2.4.2)', async () => {
      await mountSuspended(DatenschutzPage)
      await nextTick()
      expect(document.title).toContain('Datenschutzerklärung')
    })

    it('says that no retention period is set for the logs, and names no number of days for them', async () => {
      const text = (await mountSuspended(DatenschutzPage)).text()
      expect(text).toContain('Eine feste Speicherdauer ist nicht eingestellt')
      // the cookie's 365 days are the one lifetime the text states
      expect(text).not.toMatch(/\b(?!365\b)\d+\s*Tage\b/)
    })
  })

  describe('in English', () => {
    beforeAll(() => useLocale('en'))

    it('renders the English text and says which version is binding', async () => {
      const wrapper = await mountSuspended(DatenschutzPage)
      expect(wrapper.find('h1').text()).toBe('Privacy policy')
      const text = wrapper.text()
      expect(text).toContain('legally binding')
      expect(text).toContain('Art. 6(1)(f) GDPR')
      expect(text).toContain('Hamburg Commissioner for Data Protection and Freedom of Information')
      expect(wrapper.find('[lang]').attributes('lang')).toBe('en')
    })

    it('is what a reader of a language without a text of its own gets', async () => {
      await useLocale('fr')
      const wrapper = await mountSuspended(DatenschutzPage)
      expect(wrapper.find('h1').text()).toBe('Privacy policy')
      await useLocale('en')
    })

    it('has one h1 and its sections as h2, none skipped (WCAG 1.3.1)', async () => {
      const wrapper = await mountSuspended(DatenschutzPage)
      expect(wrapper.findAll('h1')).toHaveLength(1)
      expect(wrapper.findAll('h2').length).toBeGreaterThan(5)
      expect(wrapper.findAll('h3, h4, h5, h6')).toHaveLength(0)
    })
  })

  describe('the operator', () => {
    const ORIGINAL = { ...OPERATOR }
    afterEach(() => {
      Object.assign(OPERATOR, ORIGINAL)
    })

    it.each(['de', 'en'])('is written out of the same object as the Impressum\'s in %s', async (code) => {
      await useLocale(code)
      // a value that exists nowhere in the pages: it can only come from the shared object
      OPERATOR.street = 'Teststraße 99'
      OPERATOR.email = 'test@example.org'
      const privacy = await mountSuspended(DatenschutzPage)
      const impressum = await mountSuspended(ImpressumPage)
      for (const wrapper of [privacy, impressum]) {
        expect(wrapper.text()).toContain('Teststraße 99')
        expect(wrapper.html()).toContain('mailto:test@example.org')
      }
    })

    it('shows the address of the Impressum', async () => {
      const text = (await mountSuspended(DatenschutzPage)).text()
      expect(text).toContain('Falkenbergsweg 26')
      expect(text).toContain('21149 Hamburg')
      expect(text).toContain('benjamin@eobs.org')
    })
  })

  describe('the routes', () => {
    it('serves /datenschutz and /privacy', async () => {
      const router = useRouter()
      const german = router.resolve('/datenschutz')
      const english = router.resolve('/privacy')
      expect(german.matched).toHaveLength(1)
      expect(english.matched).toHaveLength(1)
      expect(english.matched[0]!.aliasOf?.path).toBe('/datenschutz')
    })
  })

  describe('the footer', () => {
    it('links it next to the Impressum, in the same style', async () => {
      registerEndpoint('/api/version', () => ({ version: '0.0.0' }))
      const wrapper = await mountSuspended(App, { route: '/' })
      const legal = wrapper.find('a[href="/impressum"]')
      const privacy = wrapper.find('a[href="/datenschutz"]')
      expect(legal.exists()).toBe(true)
      expect(privacy.exists()).toBe(true)
      expect(privacy.classes().sort()).toEqual(legal.classes().sort())
      // the two are neighbours in the footer's legal line, not the header's nav
      expect(privacy.element.closest('ul')).toBe(legal.element.closest('ul'))
      expect(privacy.element.closest('footer')).not.toBeNull()
    })
  })
})
