import { verificationWarning } from '../utils/googleSiteVerification'

// Once, when the server starts: a value that is no name is ignored (`server/middleware/google-site-verification.ts`),
// and the operator is told, since the file would otherwise just not be there (GH-4108).
export default defineNitroPlugin(() => {
  const message = verificationWarning(useRuntimeConfig().googleSiteVerification)
  if (message)
    console.warn(`[wetterdienst-app] ${message}`)
})
