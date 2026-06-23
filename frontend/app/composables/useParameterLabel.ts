import * as glossaryDe from '~~/i18n/glossary/de'
import * as glossaryEn from '~~/i18n/glossary/en'

/**
 * Maps backend identifiers (parameters, resolutions, datasets) to human-friendly
 * labels.
 *
 * Lookup chain (hybrid, frontend-first):
 *   1. curated glossary for the active locale
 *   2. prettified raw id (underscores -> spaces, capitalised)
 *
 * When the `friendlyLabels` setting is off, the raw backend id is returned
 * unchanged so power users see exactly what the API uses.
 */
export function useParameterLabel() {
  const { locale } = useI18n()
  const { settings } = useSettings()

  const glossary = computed(() => (locale.value === 'de' ? glossaryDe : glossaryEn))

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
