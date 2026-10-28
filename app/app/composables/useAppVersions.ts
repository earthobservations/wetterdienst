import pkg from '../../package.json'

interface BackendVersion { state: 'idle' | 'pending' | 'done' | 'failed', version: string | null }

// The version of the app (its package.json, as the footer once read it) and of the backend it talks to (`/api/version`,
// which the API page and the rate limit's list of uncounted routes already know), as the one line the navigation shows
// under the settings (GH-3518). The line is mounted on demand (the drawer, the rail's popover), so the answer is kept in
// the app's state: asked once, not each time the line appears, and shown at once afterwards. Until it has answered the
// line holds "…", and where it cannot it says "unknown" and asks again the next time the line appears.
const MAX_VERSION_LENGTH = 64

export function useAppVersions() {
  const { t } = useI18n()
  const backend = useState<BackendVersion>('app-backend-version', () => ({ state: 'idle', version: null }))

  if (import.meta.client && (backend.value.state === 'idle' || backend.value.state === 'failed')) {
    backend.value = { state: 'pending', version: null }
    $fetch<{ version?: unknown }>('/api/version', { retry: 0 })
      .then((answer) => {
        // a version is a short text: anything else is not what the backend says its version is
        const version = answer?.version
        backend.value = typeof version === 'string' && version.length > 0 && version.length <= MAX_VERSION_LENGTH
          ? { state: 'done', version }
          : { state: 'failed', version: null }
      })
      .catch(() => {
        backend.value = { state: 'failed', version: null }
      })
  }

  const text = computed(() => {
    const unknown = t('nav.versionUnknown')
    const answered = backend.value.version
    return t('nav.versions', {
      app: pkg.version || unknown,
      backend: answered || (backend.value.state === 'failed' ? unknown : '…'),
    })
  })

  return { text }
}
