import { defineVitestProject } from '@nuxt/test-utils/config'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: 'unit',
          include: ['tests/unit/*.{test,spec}.ts'],
          environment: 'node',
        },
      },
      await defineVitestProject({
        test: {
          name: 'nuxt',
          include: ['tests/nuxt/**/*.{test,spec}.ts'],
          environment: 'nuxt',
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
