import { placesSearchWarning } from '../utils/placesSearch'

// Once, when the server starts: a value of `NUXT_PLACES_SEARCH` that is neither one of the words for on nor one of those for off switches the place
// search off (so that a typing mistake never leaves it running), and the operator is told which value did it (GH-3791).
export default defineNitroPlugin(() => {
  const message = placesSearchWarning(useRuntimeConfig().placesSearch)
  if (message)
    console.warn(`[wetterdienst-app] ${message}`)
})
