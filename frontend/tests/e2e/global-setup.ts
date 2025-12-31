import type { FullConfig } from '@playwright/test'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:3000'

async function checkBackendHealth() {
  console.log('\n🔍 Checking backend health...')
  console.log(`   Backend URL: ${BACKEND_URL}`)
  
  try {
    const response = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    })
    
    if (response.ok) {
      const data = await response.json()
      console.log('✅ Backend is healthy and responding')
      console.log(`   Status: ${data.status}`)
      console.log('')
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
    console.error('   $ wetterdienst restapi --listen 0.0.0.0:3000\n')
    console.error('━'.repeat(60))
    console.error(`Error: ${error.message}`)
    console.error('━'.repeat(60))
    console.error('')
    
    return false
  }
}

export default async function globalSetup(config: FullConfig) {
  const isHealthy = await checkBackendHealth()
  
  if (!isHealthy) {
    throw new Error(
      `Backend not available at ${BACKEND_URL}. Please start the backend before running E2E tests.`
    )
  }
}
