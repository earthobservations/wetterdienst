import { copyFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { defineNuxtModule } from 'nuxt/kit'

// Serves Swagger UI from this origin (GH-3094). `/docs` used to be the backend's page, which loads
// `swagger-ui-dist@5` from jsdelivr without a hash, as a script of this origin. The two files the page needs
// are copied out of the installed package into the build directory (not the package's 12 MB of bundles,
// presets and source maps) and published under `/_swagger-ui/`, in the development server as in the build.
// `server/routes/docs.ts` is the page that loads them.
const FILES = ['swagger-ui-bundle.js', 'swagger-ui.css']
const BASE_URL = '/_swagger-ui'

export default defineNuxtModule({
  meta: { name: 'swagger-ui' },
  setup(_options, nuxt) {
    const dist = dirname(createRequire(import.meta.url).resolve('swagger-ui-dist/package.json'))
    const dir = join(nuxt.options.buildDir, 'swagger-ui')
    // after Nuxt has emptied its build directory, which `setup` runs before
    nuxt.hook('build:before', () => {
      mkdirSync(dir, { recursive: true })
      for (const file of FILES)
        copyFileSync(join(dist, file), join(dir, file))
    })
    nuxt.hook('nitro:config', (nitroConfig) => {
      // a day: the URL names no version, and a new one should reach the pages that have the old
      nitroConfig.publicAssets = [...(nitroConfig.publicAssets ?? []), { dir, baseURL: BASE_URL, maxAge: 86_400 }]
    })
  },
})
