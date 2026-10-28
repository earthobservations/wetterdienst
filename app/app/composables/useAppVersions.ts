import pkg from '../../package.json'

// The version of the app (its package.json, as the footer once read it) and of the backend it talks to (`/api/version`,
// which the footer, the API page and the rate limit's list of uncounted routes already know), as the one line the
// navigation shows under the settings. Not awaited: the line holds "…" for the backend until it has answered, and says
// "unknown" where it cannot (GH-3518).
export function useAppVersions() {
  const { t } = useI18n()
  const { data, status } = useFetch<{ version?: string }>('/api/version')

  const text = computed(() => {
    const unknown = t('nav.versionUnknown')
    const app = pkg.version || unknown
    const answered = data.value?.version
    const backend = answered || (status.value === 'pending' ? '…' : unknown)
    return t('nav.versions', { app, backend })
  })

  return { text }
}
