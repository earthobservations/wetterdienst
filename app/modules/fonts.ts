import { copyFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { defineNuxtModule } from 'nuxt/kit'

// The two typefaces of the app (GH-3518), served from this origin like Swagger UI (`modules/swagger-ui.ts`): the
// files are copied out of the installed Fontsource packages into the build directory and published under
// `/_typefaces/` (`/_fonts/` is @nuxt/fonts', which Nuxt UI installs), in the development server as in the build.
// Under a name that does not change with each build, so that the shell can ask for the body face before the app's
// script has run (`app.head.link` in nuxt.config.ts): the page is drawn by that script, and a face that arrived after
// it would move the text it had laid out in the fallback.
//
// Only the upright faces, and only the Latin and Latin Extended subsets, which every locale of the app is written in
// (the extended one has the letters of Czech, Polish and Luxembourgish); the browser takes a subset only when a page
// holds a letter of its range (`unicode-range` in main.css).
export const FONT_BASE_URL = '/_typefaces'

export const FONT_FILES: { pkg: string, files: string[] }[] = [
  {
    pkg: '@fontsource-variable/atkinson-hyperlegible-next',
    files: ['atkinson-hyperlegible-next-latin-wght-normal.woff2', 'atkinson-hyperlegible-next-latin-ext-wght-normal.woff2'],
  },
  {
    pkg: '@fontsource-variable/atkinson-hyperlegible-mono',
    files: ['atkinson-hyperlegible-mono-latin-wght-normal.woff2', 'atkinson-hyperlegible-mono-latin-ext-wght-normal.woff2'],
  },
]

export default defineNuxtModule({
  meta: { name: 'fonts' },
  setup(_options, nuxt) {
    const require = createRequire(import.meta.url)
    const dir = join(nuxt.options.buildDir, 'fonts')
    // after Nuxt has emptied its build directory, which `setup` runs before
    nuxt.hook('build:before', () => {
      mkdirSync(dir, { recursive: true })
      for (const { pkg, files } of FONT_FILES) {
        // by its LICENSE, which the package's `exports` names (its package.json is not)
        const source = join(dirname(require.resolve(`${pkg}/LICENSE`)), 'files')
        for (const file of files)
          copyFileSync(join(source, file), join(dir, file))
      }
    })
    nuxt.hook('nitro:config', (nitroConfig) => {
      // a day, as Swagger UI's: the URL names no version, and a new one should reach the pages that have the old
      nitroConfig.publicAssets = [...(nitroConfig.publicAssets ?? []), { dir, baseURL: FONT_BASE_URL, maxAge: 86_400 }]
    })
  },
})
