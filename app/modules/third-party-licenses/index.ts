import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { addVitePlugin, defineNuxtModule, useLogger } from 'nuxt/kit'
import { collectNotices, DEVELOPMENT_NOTICE, needsMoreThanNotice, renderNotices } from './licenses'

// The licence notices of what the browser is served (GH-3469), at `/third-party-licenses.txt`. The MIT, BSD, ISC
// and Apache licences of the bundled packages ask that the copyright notice and the permission text go with the
// code, and the minifier drops the comments in the files that carried them. The client build knows which packages
// its chunks and assets hold (not the ones that only build the app), so a plugin of that build reads the module ids
// of the finished bundle, and the file is made from the packages' own LICENSE and NOTICE files: a dependency that
// reaches the bundle is in the file by construction, with nothing to keep up by hand. Nitro publishes it at the
// root of the app, and the page's footer links to it. The file is a build product (`.nuxt/`), not a file of the
// repository.
const FILE = 'third-party-licenses.txt'

export default defineNuxtModule({
  meta: { name: 'third-party-licenses' },
  setup(_options, nuxt) {
    const logger = useLogger('third-party-licenses')
    const require = createRequire(import.meta.url)
    const dir = join(nuxt.options.buildDir, 'third-party-licenses')
    const file = join(dir, FILE)

    const resolvePackage = (name: string) => {
      try {
        return dirname(require.resolve(`${name}/package.json`))
      }
      catch {
        throw new Error(`third-party-licenses: cannot find ${name}, which the app serves to the browser (SERVED_APART)`)
      }
    }

    // after Nuxt has emptied its build directory, which `setup` runs before
    nuxt.hook('build:before', () => {
      mkdirSync(dir, { recursive: true })
      // the development server has no bundle to read: the file says so rather than being a 404 behind the link
      if (nuxt.options.dev)
        writeFileSync(file, DEVELOPMENT_NOTICE)
    })

    // the client build only: the server build holds no code the browser runs
    if (!nuxt.options.dev) {
      addVitePlugin({
        name: 'third-party-licenses',
        apply: 'build',
        generateBundle(_options, bundle) {
          const ids: string[] = []
          for (const output of Object.values(bundle)) {
            if (output.type === 'chunk')
              ids.push(...Object.keys(output.modules ?? {}))
            else
              ids.push(...(output.originalFileNames ?? []))
          }
          const notices = collectNotices(ids, resolvePackage)
          for (const notice of needsMoreThanNotice(notices))
            logger.warn(`${notice.name}@${notice.version} is under "${notice.license || 'no declared licence'}", which asks for more than a notice: read it`)
          mkdirSync(dir, { recursive: true })
          writeFileSync(file, renderNotices(notices))
          logger.success(`${notices.length} packages in ${FILE}`)
        },
      }, { server: false })
    }

    // a production build without the file would publish a link to a 404: it stops instead
    nuxt.hook('nitro:build:before', () => {
      if (!nuxt.options.dev && !existsSync(file))
        throw new Error(`third-party-licenses: the client build wrote no ${FILE}`)
    })

    nuxt.hook('nitro:config', (nitroConfig) => {
      nitroConfig.publicAssets = [...(nitroConfig.publicAssets ?? []), { dir, baseURL: '/', maxAge: 86_400 }]
    })
  },
})
