import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp, UInputNumber, UPagination } from '#components'
import App from '~/app.vue'

// Nuxt UI's own strings (the pager's labels, the toaster's, the number field's role description) follow the
// @nuxtjs/i18n locale through the `ui-i18n` plugin Nuxt UI generates (GH-3955). `app/app.vue` once passed its own
// `locale` to UApp, de or en only, so in the other languages these stayed English beside the app's translated text.
// The strings are written out here, not read from `@nuxt/ui/locale`, so that a locale mapped to the wrong one, or to
// none, fails: each app locale to the Nuxt UI locale it resolves to (`resolveLocaleKey`, from the locale's `language`
// and `code`): de, de-hh -> de; en -> en_gb; the rest to the one of their own name.
const strings = {
  'de': { first: 'Erste Seite', last: 'Letzte Seite', next: 'Nächste Seite', prev: 'Vorherige Seite', page: 'Seite 2', increment: 'Erhöhen', viewport: 'Benachrichtigungen' },
  'de-hh': { first: 'Erste Seite', last: 'Letzte Seite', next: 'Nächste Seite', prev: 'Vorherige Seite', page: 'Seite 2', increment: 'Erhöhen', viewport: 'Benachrichtigungen' },
  'en': { first: 'First page', last: 'Last page', next: 'Next page', prev: 'Previous page', page: 'Page 2', increment: 'Increment', viewport: 'Notifications' },
  'fr': { first: 'Première page', last: 'Dernière page', next: 'Page suivante', prev: 'Page précédente', page: 'Page 2', increment: 'Augmenter', viewport: 'Notifications' },
  'es': { first: 'Primera página', last: 'Última página', next: 'Página siguiente', prev: 'Página anterior', page: 'Página 2', increment: 'Incrementar', viewport: 'Notificaciones' },
  'it': { first: 'Prima pagina', last: 'Ultima pagina', next: 'Pagina seguente', prev: 'Pagina precedente', page: 'Pagina 2', increment: 'Aumenta', viewport: 'Notifiche' },
  'pl': { first: 'Pierwsza strona', last: 'Ostatnia strona', next: 'Następna strona', prev: 'Poprzednia strona', page: 'Strona 2', increment: 'Zwiększ', viewport: 'Powiadomienia' },
  'nl': { first: 'Eerste pagina', last: 'Laatste pagina', next: 'Volgende pagina', prev: 'Vorige pagina', page: 'Pagina 2', increment: 'Verhogen', viewport: 'Meldingen' },
  'cs': { first: 'První stránka', last: 'Poslední stránka', next: 'Další stránka', prev: 'Předchozí stránka', page: 'Stránka 2', increment: 'Zvýšit', viewport: 'Oznámení' },
  'da': { first: 'Første side', last: 'Sidste side', next: 'Næste side', prev: 'Forrige side', page: 'Side 2', increment: 'Øg', viewport: 'Notifikationer' },
  'lb': { first: 'Éischt Säit', last: 'Lescht Säit', next: 'Nächst Säit', prev: 'Vireg Säit', page: 'Säit 2', increment: 'Inkrementéieren', viewport: 'Notifikatiounen' },
} as const
type Code = keyof typeof strings
const codes = Object.keys(strings) as Code[]

async function setLocale(code: Code) {
  await useNuxtApp().$i18n.setLocale(code as 'de')
}

afterEach(async () => {
  await setLocale('en')
})

describe('nuxt UI follows the language of the page', () => {
  it('has a table row for each locale the app has', () => {
    expect([...useNuxtApp().$i18n.localeCodes.value].sort()).toEqual([...codes].sort())
  })

  describe.each(codes)('in %s', (code) => {
    it('writes the pager\'s labels and the number field in the language', async () => {
      await setLocale(code)
      const wrapper = await mountSuspended(defineComponent({
        setup: () => () => h(UApp, null, {
          default: () => [
            h(UPagination, { total: 100, page: 2, itemsPerPage: 10 }),
            h(UInputNumber, { modelValue: 1 }),
          ],
        }),
      }))
      await flushPromises()
      const expected = strings[code]
      const labels = wrapper.findAll('nav button[aria-label]').map(button => button.attributes('aria-label'))
      expect(labels).toEqual(expect.arrayContaining([expected.first, expected.prev, expected.page, expected.next, expected.last]))
      expect(labels.filter(label => label === expected.first || label === expected.last)).toHaveLength(2)
      expect(wrapper.find(`button[aria-label="${expected.increment}"]`).exists()).toBe(true)
      wrapper.unmount()
    })
  })

  describe.each(codes)('in %s, in the whole app', (code) => {
    // the app's own UApp: it gave Nuxt UI a locale of its own, de or en, so the toaster stayed English in the others
    it('writes the toaster\'s label in the language', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ version: '0.0.0' }), { status: 200 }))
      await setLocale(code)
      await useRouter().push('/')
      const wrapper = await mountSuspended(App)
      await flushPromises()
      expect(document.querySelector(`[aria-label^="${strings[code].viewport} ("]`)).not.toBeNull()
      wrapper.unmount()
    })
  })
})
