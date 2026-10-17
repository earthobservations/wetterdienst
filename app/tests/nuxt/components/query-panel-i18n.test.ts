import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import QueryPanel from '~/components/QueryPanel.vue'

// The SQL panel's own text was English in every language, written into the template and the script
// (GH-2610). It is in the catalogs now, under `query.*`; these hold the panel to them in some of the
// languages, Luxembourgish (GH-2970) and Low German (GH-2969) among them, whose text is not natively
// reviewed (see i18n/TERMS.md).

// the panel's DuckDB, answered by DuckDB-wasm's Node build rather than the browser's bundles
vi.mock('@duckdb/duckdb-wasm', async () => {
  const { nodeDuckDB } = await import('../../duckdb-node')
  const db = await nodeDuckDB()
  return {
    getPlatformFeatures: async () => ({ wasmExceptions: true }),
    ConsoleLogger: class {},
    AsyncDuckDB: class {
      async instantiate() {}
      async connect() {
        const conn = db.connect()
        return {
          query: async (sql: string) => conn.query(sql),
          send: async (sql: string) => conn.send(sql),
          cancelSent: async () => conn.cancelSent(),
          close: async () => conn.close(),
        }
      }

      async terminate() {}
    },
  }
})
vi.stubGlobal('Worker', class {})

const data = [{ station_id: '01048', resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', timestamp: '2020-01-01T00:00:00.000000+00:00', value: 1.5, quality_flags: '10' }]

async function setLocale(locale: string) {
  const harness = await mountSuspended(defineComponent({
    setup: () => ({ setLocale: useI18n().setLocale }),
    render: () => h('div'),
  }))
  await (harness.vm as unknown as { setLocale: (locale: string) => Promise<void> }).setLocale(locale)
  harness.unmount()
}

afterEach(async () => {
  await setLocale('en')
})

/** What the panel says in query mode, per language: the button that enters it, and the chrome inside. */
const said = {
  'de': { enable: 'Mit SQL-Abfrage transformieren', inside: ['SQL-Abfrage-Transformation', 'Abfrage ausführen', 'Abbrechen', 'Beispielabfragen', 'Fragen Sie die Tabelle data mit Standard-SQL ab.', 'Verfügbare Spalten:'] },
  'fr': { enable: 'Transformer avec une requête SQL', inside: ['Transformation par requête SQL', 'Exécuter la requête', 'Annuler', 'Exemples de requêtes', 'Interrogez la table data avec du SQL standard.', 'Colonnes disponibles :'] },
  'pl': { enable: 'Przekształć zapytaniem SQL', inside: ['Przekształcenie zapytaniem SQL', 'Uruchom zapytanie', 'Anuluj', 'Przykładowe zapytania', 'Odpytaj tabelę data za pomocą standardowego SQL.', 'Dostępne kolumny:'] },
  'lb': { enable: 'Mat enger SQL-Ufro transforméieren', inside: ['SQL-Ufro-Transformatioun', 'Ufro ausféieren', 'Ofbriechen', 'Beispillufroen', 'Frot d\'Tabell data mat Standard-SQL of.', 'Verfügbar Kolonnen:'] },
  'de-hh': { enable: 'Mit SQL-Afraag transformeren', inside: ['SQL-Afraag-Transformatschoon', 'Afraag utföhren', 'Afbreken', 'Bispelafraagen', 'Frag de Tabell data mit Standard-SQL af.', 'Verfögbare Spalten:'] },
} as const

describe('queryPanel in the active language', () => {
  it.each(Object.keys(said) as (keyof typeof said)[])('says its buttons, hint and examples in %s', async (locale) => {
    await setLocale(locale)
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!) } })
    try {
      expect(wrapper.find('button').text()).toBe(said[locale].enable)
      await wrapper.find('button').trigger('click')
      await flushPromises()
      for (const text of said[locale].inside)
        expect(wrapper.text(), `${locale}: ${text}`).toContain(text)
      // the hint's table name and the columns stay code, in the language's sentence
      expect(wrapper.findAll('code').map(code => code.text())).toContain('data')
      expect(wrapper.findAll('code').map(code => code.text())).toContain(Object.keys(data[0]!).join(', '))
    }
    finally {
      wrapper.unmount()
    }
  })

  it('names the example queries in the language', async () => {
    await setLocale('de')
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!) } })
    try {
      await wrapper.find('button').trigger('click')
      await flushPromises()
      const labels = wrapper.findAll('details button').map(button => button.text())
      expect(labels).toEqual(['Alle Daten (begrenzt)', 'Nach Parameter filtern', 'Nach Zeitstempel aggregieren', 'Nach Wertebereich filtern', 'Nur aktuelle Daten'])
    }
    finally {
      wrapper.unmount()
    }
  })

  it('tells that there is no data to query in the language', async () => {
    await setLocale('de')
    const wrapper = await mountSuspended(QueryPanel, { props: { data: [], expectedColumns: [] } })
    try {
      await wrapper.find('button').trigger('click')
      await wrapper.findAll('button').find(button => button.text() === 'Abfrage ausführen')!.trigger('click')
      await vi.waitFor(() => expect(wrapper.text()).toContain('Keine Daten zum Abfragen vorhanden'))
    }
    finally {
      wrapper.unmount()
    }
  })
})
