import { fileURLToPath } from 'node:url'
import { defineVitestProject } from '@nuxt/test-utils/config'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    projects: [
      {
        // `shared/utils/language.ts` takes the matcher of @nuxtjs/i18n from the module's own name for its runtime
        // (`#i18n-kit`), which Nuxt sets for the app and the server and the plain Node project does not know. The path
        // is the module's `dist/runtime/kit`, which is `@internal`: a minor release of @nuxtjs/i18n may move it, and
        // this is the one place to follow it (the build and the typecheck use the module's own alias and would
        // catch the move first)
        resolve: {
          alias: { '#i18n-kit': fileURLToPath(new URL('./node_modules/@nuxtjs/i18n/dist/runtime/kit', import.meta.url)) },
        },
        test: {
          name: 'unit',
          include: ['tests/unit/*.{test,spec}.ts'],
          environment: 'node',
          setupFiles: ['tests/setup/storage.ts'],
          // a test that asserts nothing fails, in both projects (GH-4425)
          expect: { requireAssertions: true },
          // nuxt-security's middleware, run as it is by `tests/unit/mcp-proxy-security.test.ts`, imports its own
          // files without an extension, which Node does not resolve and Vite does
          server: { deps: { inline: [/nuxt-security\/dist/] } },
        },
      },
      await defineVitestProject({
        test: {
          name: 'nuxt',
          include: ['tests/nuxt/**/*.{test,spec}.ts'],
          environment: 'nuxt',
          // a fresh, empty localStorage and sessionStorage for every test, which CI's Node and a
          // developer's do not give alike (GH-3990)
          setupFiles: ['tests/setup/storage.ts'],
          expect: { requireAssertions: true },
          // Vitest's 5 s per test and 10 s per hook. The Nuxt environment boots the app in a
          // `beforeAll` of its own, and the first `mountSuspended` of a file loads the locale and
          // the component's lazy parts: about a second on a quiet machine and several times that
          // on a loaded one (a CI runner, a review beside other jobs), so the boot of a file and
          // its first test timed out now and then (GH-3484). Three times the default is room for
          // that and still a short wait for a test that hangs; a test that waits for something
          // waits on a condition (`vi.waitFor`), not on this. The unit project keeps the default.
          testTimeout: 15_000,
          hookTimeout: 30_000,
        },
      }),
    ],
  },
})
