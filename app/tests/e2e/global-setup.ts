import type { FullConfig } from '@playwright/test'
import process from 'node:process'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7890'

async function checkBackendHealth() {
  console.warn('\n🔍 Checking backend health...')
  console.warn(`   Backend URL: ${BACKEND_URL}`)

  try {
    const response = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    })

    if (response.ok) {
      const data = await response.json()
      console.warn('✅ Backend is healthy and responding')
      console.warn(`   Status: ${data.status}`)
      console.warn('')
      return true
    }
    else {
      console.error(`❌ Backend returned status ${response.status}`)
      return false
    }
  }
  catch (error: any) {
    console.error('\n❌ BACKEND HEALTH CHECK FAILED!\n')
    console.error('━'.repeat(60))
    console.error('The Wetterdienst backend is not running or not accessible.')
    console.error(`Expected backend at: ${BACKEND_URL}`)
    console.error('━'.repeat(60))
    console.error('\n📋 To start the backend:\n')
    console.error('   Option 1 - Using Docker (Recommended):')
    console.error('   $ cd .. && docker compose --profile backend up -d\n')
    console.error('   Option 2 - Local Python:')
    console.error('   $ cd .. && pip install -e .')
    console.error('   $ wetterdienst restapi --listen 0.0.0.0:7890\n')
    console.error('━'.repeat(60))
    console.error(`Error: ${error.message}`)
    console.error('━'.repeat(60))
    console.error('')

    return false
  }
}

/**
 * The suite never reaches komoot's Photon: the app's server must be asking the stand-in (`tests/e2e/mock-photon.mjs`), which `playwright.config.ts` makes
 * it do for a server it starts. A server that was already running (`reuseExistingServer`, a dev server of somebody's own) is not trusted until it has said
 * so: `GET /_search/places?probe=1` answers where the server would send its requests, and only a server started with `NUXT_PLACES_E2E=1` answers it (any
 * other is a 422 and asked nobody). Anything but the stand-in on this machine stops the run before a test can type a letter.
 */
async function checkPlacesStandIn() {
  const port = process.env.E2E_PORT || '4000'
  const app = process.env.BASE_URL || `http://localhost:${port}`
  const expected = `http://127.0.0.1:${process.env.E2E_PHOTON_PORT || Number(port) + 100}/api/`
  let base: unknown
  try {
    const response = await fetch(`${app}/_search/places?probe=1`, { signal: AbortSignal.timeout(10_000) })
    base = response.ok ? (await response.json() as { photon_base?: unknown }).photon_base : undefined
  }
  catch {
    base = undefined
  }
  if (base !== expected) {
    throw new Error(
      `Refusing to run: the app at ${app} does not say it asks the stand-in for Photon (${expected}) for places, so a test that types in the search could reach komoot's server. `
      + `It said ${JSON.stringify(base)}. Stop that server and let Playwright start its own (it sets NUXT_PLACES_E2E=1 and NUXT_PLACES_PHOTON_BASE), `
      + `or start yours with NUXT_PLACES_E2E=1 NUXT_PLACES_PHOTON_BASE=${expected} and run the stand-in (node tests/e2e/mock-photon.mjs).`,
    )
  }
}

export default async function globalSetup(_config: FullConfig) {
  // before everything else, also where the backend is mocked: the app's own server is the one that asks Photon
  await checkPlacesStandIn()

  // the accessibility spec (A11Y=1) answers every /api/* request itself and needs no backend
  if (process.env.A11Y === '1')
    return

  const isHealthy = await checkBackendHealth()

  if (!isHealthy) {
    throw new Error(
      `Backend not available at ${BACKEND_URL}. Please start the backend before running E2E tests.`,
    )
  }
}
