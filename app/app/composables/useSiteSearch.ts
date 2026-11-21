import type { GlossaryEntry } from '#shared/types/api'
import type { Chip } from '~/utils/ask/chip'
import type { Hit, SearchIndex } from '~/utils/search-index'
import { glossaryDocs } from '~/utils/search-docs'
import { bestPerTarget, buildIndex, searchIndex } from '~/utils/search-index'

// What the search of the header finds of the app's own words (GH-3790), loaded the first time the search is opened and
// not with the page: the index of the language (`modules/search-index`, built with the app, a chunk of its own), the
// questions of "Ask the weather" (the registry of the chips, which the home page loads for itself) and the glossary.
//
// The glossary is what the glossary page loads (`GET /api/glossary`, about 500 entries), not what the build knows: its
// descriptions come from the backend, so the index of it is made here, from the answer, with the labels of the
// language the reader sees. It is asked for once for the visit and kept.
let glossaryAnswer: Promise<GlossaryEntry[]> | null = null

function glossaryEntries(): Promise<GlossaryEntry[]> {
  glossaryAnswer ??= $fetch<GlossaryEntry[]>('/api/glossary', API_ANSWER).catch((error) => {
    // forgotten, so that the next opening asks again
    glossaryAnswer = null
    throw error
  })
  return glossaryAnswer
}

export function useSiteSearch() {
  const { locale } = useI18n()
  const { settings } = useSettings()

  const pages = shallowRef<SearchIndex | null>(null)
  const glossary = shallowRef<SearchIndex | null>(null)
  const chips = shallowRef<readonly Chip[]>([])
  /** True from the opening until the index of the pages is there: what is typed meanwhile is searched when it is */
  const loading = ref(true)
  let closed = false
  onBeforeUnmount(() => {
    closed = true
  })

  /** The index of the pages, and the labels of the parameters, which come in the same file (the glossary is shown by them): null where the file cannot be loaded */
  async function loadPages(): Promise<Record<string, string> | null> {
    try {
      const { default: loaders } = await import('virtual:search-index/loaders')
      const load = loaders[locale.value] ?? loaders.en
      const loaded = await load!()
      if (!closed)
        pages.value = loaded.default
      return loaded.labels
    }
    catch {
      // a chunk that cannot be loaded (a redeploy replaced it under an open tab) leaves the search with its pages and actions
      return null
    }
  }

  async function loadChips() {
    try {
      const { CHIPS } = await import('~/utils/ask/registry')
      if (!closed)
        chips.value = CHIPS
    }
    catch {
      // as above
    }
  }

  async function loadGlossary(labelsLoaded: Promise<Record<string, string> | null>) {
    try {
      const [entries, labels] = await Promise.all([glossaryEntries(), labelsLoaded])
      // the name the glossary page shows: the label of the language, or the backend's name where the setting for plain-language labels is off
      const label = (name: string) => settings.value.friendlyLabels ? labels?.[name] ?? name : name
      if (!closed)
        glossary.value = buildIndex(glossaryDocs(entries, label))
    }
    catch {
      // the glossary is searched where it could be asked for
    }
  }

  onMounted(async () => {
    const labels = loadPages()
    await Promise.all([labels, loadChips(), loadGlossary(labels)])
    loading.value = false
  })

  return {
    loading,
    chips,
    /** The entries of the pages that answer the query, one for each place they lead to, best first */
    findPages: (query: string): Hit[] => pages.value ? bestPerTarget(searchIndex(pages.value, query)) : [],
    /** The entries of the glossary that answer the query, best first */
    findGlossary: (query: string): Hit[] => glossary.value ? searchIndex(glossary.value, query) : [],
  }
}
