import * as glossaryCs from '~~/i18n/glossary/cs'
import * as glossaryDa from '~~/i18n/glossary/da'
import * as glossaryDe from '~~/i18n/glossary/de'
import * as glossaryDeHh from '~~/i18n/glossary/de-hh'
import * as glossaryEn from '~~/i18n/glossary/en'
import * as glossaryEs from '~~/i18n/glossary/es'
import * as glossaryFr from '~~/i18n/glossary/fr'
import * as glossaryIt from '~~/i18n/glossary/it'
import * as glossaryLb from '~~/i18n/glossary/lb'
import * as glossaryNl from '~~/i18n/glossary/nl'
import * as glossaryPl from '~~/i18n/glossary/pl'

/** One curated catalog per UI locale; `tests/unit/i18n-parity.test.ts` keeps their keys in step. */
const glossaries: Record<string, typeof glossaryEn> = {
  'cs': glossaryCs,
  'da': glossaryDa,
  'de': glossaryDe,
  'de-hh': glossaryDeHh,
  'en': glossaryEn,
  'es': glossaryEs,
  'fr': glossaryFr,
  'it': glossaryIt,
  'lb': glossaryLb,
  'nl': glossaryNl,
  'pl': glossaryPl,
}

/**
 * Maps backend identifiers (parameters, resolutions, datasets) to human-friendly
 * labels.
 *
 * Lookup chain (hybrid, app-first):
 *   1. curated glossary for the active locale
 *   2. prettified raw id (underscores -> spaces, capitalised)
 *
 * When the `friendlyLabels` setting is off, the raw backend id is returned
 * unchanged so power users see exactly what the API uses.
 */
export function useParameterLabel() {
  const { locale } = useI18n()
  const { settings } = useSettings()

  const glossary = computed(() => glossaries[locale.value] ?? glossaryEn)

  function prettify(id: string): string {
    return id
      .replace(/_/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/\b\w/g, c => c.toUpperCase())
  }

  function lookup(map: Record<string, string>, id?: string | null): string {
    if (!id)
      return ''
    if (!settings.value.friendlyLabels)
      return id
    return map[id] ?? prettify(id)
  }

  const parameterLabel = (id?: string | null) => lookup(glossary.value.parameters, id)
  const resolutionLabel = (id?: string | null) => lookup(glossary.value.resolutions, id)
  const datasetLabel = (id?: string | null) => lookup(glossary.value.datasets, id)

  return { parameterLabel, resolutionLabel, datasetLabel }
}
