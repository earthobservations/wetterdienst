import { apiBaseDeprecation } from '../utils/apiBase'

// Once, when the server starts: a deployment that still sets the old `NUXT_PUBLIC_API_BASE` keeps working and is
// told to move to `NUXT_API_BASE` (GH-3096).
export default defineNitroPlugin(() => {
  const message = apiBaseDeprecation(useRuntimeConfig().apiBase as string | undefined)
  if (message)
    console.warn(`[wetterdienst-app] ${message}`)
})
