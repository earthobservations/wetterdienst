import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, relative } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import {
  bundledLicenseComment,
  collectNotices,
  commentAround,
  exactText,
  findPackageChain,
  findPackageDir,
  needsMoreThanNotice,
  packageDirOf,
  readNotice,
  renderNotices,
  repositoryUrl,
  SERVED_APART,
} from '../../modules/third-party-licenses/licenses'

// The notices of what the browser is served (GH-3469): which package a module of the bundle belongs to, what is
// read from the package, and what is written. That the file lists every package of the real bundle is
// `tests/e2e/third-party-licenses.spec.ts`, which needs a production build.

const realpathOf = (path: string) => realpathSync(path)
const root = mkdtempSync(join(tmpdir(), 'wd-licenses-'))
afterAll(() => rmSync(root, { recursive: true, force: true }))

function makePackage(dir: string, pkg: Record<string, unknown>, files: Record<string, string> = {}): string {
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, 'package.json'), JSON.stringify(pkg))
  for (const [name, text] of Object.entries(files))
    writeFileSync(join(dir, name), text)
  return dir
}

describe('the package a module of the bundle belongs to', () => {
  it('is the directory of the package.json, in the layout pnpm makes', () => {
    expect(packageDirOf('/app/node_modules/.pnpm/vue@3.5.44/node_modules/vue/dist/vue.runtime.esm-bundler.js'))
      .toBe('/app/node_modules/.pnpm/vue@3.5.44/node_modules/vue')
    expect(packageDirOf('/app/node_modules/leaflet/dist/leaflet-src.js')).toBe('/app/node_modules/leaflet')
  })

  it('takes both parts of a scoped name, and the innermost node_modules', () => {
    expect(packageDirOf('/app/node_modules/.pnpm/@nuxt+ui@4.11.3_x/node_modules/@nuxt/ui/dist/runtime/a.vue'))
      .toBe('/app/node_modules/.pnpm/@nuxt+ui@4.11.3_x/node_modules/@nuxt/ui')
  })

  it('drops the marker and the query of a plugin', () => {
    expect(packageDirOf('\0/app/node_modules/reka-ui/dist/Primitive.js?commonjs-proxy')).toBe('/app/node_modules/reka-ui')
    expect(packageDirOf('/app/node_modules/@nuxt/ui/dist/runtime/a.vue?vue&type=style&index=0')).toBe('/app/node_modules/@nuxt/ui')
  })

  it('is none for the app\'s own file and a virtual module', () => {
    expect(packageDirOf('/app/app/app.vue')).toBeNull()
    expect(packageDirOf('\0vite/preload-helper.js')).toBeNull()
    expect(packageDirOf('/app/node_modules/')).toBeNull()
  })
})

describe('the notice of a package', () => {
  it('holds the licence it declares and the texts of its LICENSE, COPYING and NOTICE files, as they are', () => {
    const dir = makePackage(join(root, 'a'), { name: 'a', version: '1.0.0', license: 'Apache-2.0', repository: { url: 'git+https://github.com/x/a.git' } }, {
      'LICENSE': 'Apache text\r\n',
      'NOTICE.txt': 'Notice text',
      'MIT-LICENCE.txt': 'Spelled the other way',
      'README.md': 'not a licence',
      'licensee.js': 'not a licence either',
    })
    const notice = readNotice(dir)
    expect(notice).toMatchObject({ name: 'a', version: '1.0.0', license: 'Apache-2.0', homepage: 'https://github.com/x/a' })
    expect(notice.texts).toEqual([
      { file: 'LICENSE', text: 'Apache text' },
      { file: 'MIT-LICENCE.txt', text: 'Spelled the other way' },
      { file: 'NOTICE.txt', text: 'Notice text' },
    ])
  })

  it('reads the older ways to declare a licence', () => {
    expect(readNotice(makePackage(join(root, 'b'), { name: 'b', version: '1', license: { type: 'MIT' } })).license).toBe('MIT')
    expect(readNotice(makePackage(join(root, 'c'), { name: 'c', version: '1', licenses: [{ type: 'MIT' }, { type: 'Apache-2.0' }] })).license).toBe('MIT OR Apache-2.0')
    expect(readNotice(makePackage(join(root, 'd'), { name: 'd', version: '1' })).license).toBe('')
  })

  it('takes what a package leaves out from the repository\'s files, and only then', () => {
    // suncalc declares no licence but ships the text; vaul-vue and duckdb-wasm ship no text
    const suncalc = readNotice(makePackage(join(root, 'suncalc'), { name: 'suncalc', version: '2' }, { LICENSE: 'BSD text' }))
    expect(suncalc.license).toBe('BSD-2-Clause')
    expect(suncalc.texts).toEqual([{ file: 'LICENSE', text: 'BSD text' }])

    const vaul = readNotice(makePackage(join(root, 'vaul-vue'), { name: 'vaul-vue', version: '0.4.1' }))
    expect(vaul.license).toBe('MIT')
    // the repository's LICENSE, and the licence of Vaul, of which it is a port
    expect(vaul.texts.map(entry => entry.file)).toEqual([expect.stringContaining('vaul-vue.LICENSE'), expect.stringContaining('vaul.LICENSE')])
    expect(vaul.texts[0]!.text).toContain('Permission is hereby granted')
    expect(vaul.texts[1]!.text).toContain('Emil Kowalski')

    const duckdb = readNotice(makePackage(join(root, 'duckdb'), { name: '@duckdb/duckdb-wasm', version: '1', license: 'MIT' }))
    expect(duckdb.texts[0]!.text).toContain('DuckDB')
    // and the code inside the DuckDB files, whatever the package ships: DuckDB's own third_party/ and the worker's libraries
    const inside = duckdb.texts.find(entry => entry.file.startsWith('duckdb-wasm-third-party.txt'))!.text
    for (const needle of ['08e34c447bae34eaee3723cac61f2878b6bdf787', 'third_party/re2/LICENSE', 'third_party/zstd/LICENSE', 'third_party/mbedtls/LICENSE', 'alp/algorithm/LICENSE', 'alprd/algorithm/LICENSE', 'Tencent/rapidjson', 'js-sha256@0.11.1', 'ws@8.22.0', 'wasm-feature-detect@1.6.1', 'web-worker@1.2.0', 'byte-identical'])
      expect(inside, needle).toContain(needle)
    // the first line of a text keeps its indentation
    expect(inside).toContain('---- duckdb/duckdb@v1.5.4 third_party/ska_sort/LICENSE ----\n\n          Copyright Malte Skarupke 2016.')

    const shipped = readNotice(makePackage(join(root, 'vaul-vue-2'), { name: 'vaul-vue', version: '9', license: 'ISC' }, { LICENSE: 'Their own text' }))
    expect(shipped.license).toBe('ISC')
    expect(shipped.texts.map(entry => entry.text)).toEqual(['Their own text', expect.stringContaining('Emil Kowalski')])
  })

  it('adds the licence comments a bundled file ends with', () => {
    const file = '/*! plotly */\nvar a=1;\n/*! Bundled license information:\n\nleft-pad/index.js:\n  (* MIT *)\n*/\n\nreturn a;'
    expect(bundledLicenseComment(file)).toBe('Bundled license information:\n\nleft-pad/index.js:\n  (* MIT *)')
    expect(bundledLicenseComment('var a=1')).toBeNull()

    const notice = readNotice(makePackage(join(root, 'plotly'), { name: 'plotly.js-basic-dist-min', version: '3', license: 'MIT' }, { 'LICENSE': 'Plotly MIT', 'plotly-basic.min.js': file }))
    // its LICENSE, the libraries of the fallback with what it does not reproduce, and the comment the file ends with
    expect(notice.texts.map(entry => entry.text)).toEqual(['Plotly MIT', expect.stringContaining('are listed here'), expect.stringContaining('left-pad/index.js')])
    // every package of the unminified bundle's "// node_modules/" comments, at the version of plotly.js v3.7.0's lock
    const plotly = notice.texts[1]!.text
    const packages = ['@plotly/d3', 'base64-arraybuffer', 'd3-format', 'd3-time', 'd3-time-format', 'events', 'fast-isnumeric', 'gl-mat4', 'has-hover', 'has-passive-events', 'is-browser', 'is-mobile', 'is-string-blank', 'maplibre-gl', 'mouse-event-offset', 'native-promise-only', 'object-assign', 'parse-svg-path', 'point-in-polygon', 'polybooljs', 'tinycolor2', 'world-calendars']
    expect(packages).toHaveLength(22)
    for (const name of packages)
      // the name, a space and its version: some place where the name is followed by a space and a digit
      expect(plotly.split(`${name} `).slice(1).some(rest => /^\d/.test(rest)), name).toBe(true)
    expect(plotly).toContain('maplibre-gl@4.7.1 LICENSE')
    // the one for which no text could be obtained is named in the header, and the ones that were dropped are not there
    expect(plotly).toContain('native-promise-only 0.8.1 has no licence text of its own below')
    for (const name of ['color-normalize', 'color-rgba', 'topojson-client'])
      expect(plotly, name).not.toContain(name)
  })

  it('adds the notice a package embeds for code that is not its own, and keeps the indentation of a text', () => {
    const source = 'var a\n\n\t/* Copyright (c) 2012 the authors listed at\n\thttp://en.literateprograms.org/Quickhull\n\tPermission is hereby granted */\n\n(function () {})'
    expect(commentAround(source, 'literateprograms.org')).toBe('/* Copyright (c) 2012 the authors listed at\n\thttp://en.literateprograms.org/Quickhull\n\tPermission is hereby granted */')
    expect(commentAround(source, 'nowhere')).toBeNull()
    mkdirSync(join(root, 'markercluster2', 'dist'), { recursive: true })
    writeFileSync(join(root, 'markercluster2', 'dist', 'leaflet.markercluster-src.js'), source)
    const embedded = readNotice(makePackage(join(root, 'markercluster2'), { name: 'leaflet.markercluster', version: '1', license: 'MIT' }, { LICENSE: 'MIT' }))
    expect(embedded.texts.map(entry => entry.file)).toEqual(['LICENSE', expect.stringContaining('QuickHull')])
    expect(embedded.texts[1]!.text).toContain('literateprograms.org')

    expect(exactText('\r\n\n   Indented first line\n\tsecond\n\n')).toBe('   Indented first line\n\tsecond')
  })

  it('reads the sidecar of Swagger UI, which is no licence file by name', () => {
    const swagger = readNotice(makePackage(join(root, 'swagger'), { name: 'swagger-ui-dist', version: '5', license: 'Apache-2.0' }, { 'LICENSE': 'Apache', 'swagger-ui-bundle.js.LICENSE.txt': 'react and the rest', 'swagger-ui-es-bundle.js.LICENSE.txt': 'not served' }))
    expect(swagger.texts).toEqual([{ file: 'LICENSE', text: 'Apache' }, { file: 'swagger-ui-bundle.js.LICENSE.txt', text: 'react and the rest' }])
  })

  it('gives a repository as a URL', () => {
    const url = (repository: unknown) => readNotice(makePackage(join(root, `repo-${String(repository).length}-${Math.random()}`), { name: 'r', version: '1', repository })).homepage
    expect(url('nuxt/icon')).toBe('https://github.com/nuxt/icon')
    expect(url({ type: 'git', url: 'git+https://github.com/unjs/defu.git' })).toBe('https://github.com/unjs/defu')
    expect(url({ url: 'git://github.com/o/r.git' })).toBe('https://github.com/o/r')
    expect(url({ url: 'git@github.com:o/r.git' })).toBe('https://github.com/o/r')
    expect(url({ url: 'git+ssh://git@github.com/o/r.git' })).toBe('https://github.com/o/r')
    expect(url('github:o/r')).toBe('https://github.com/o/r')
    expect(repositoryUrl('https://github.com/o/r')).toBe('https://github.com/o/r')
  })
})

describe('the packages of a bundle', () => {
  const served = new Map<string, string>()
  // a package by the chain of names to it, as the module finds it
  const resolvePackage = (chain: string[]) => served.get(chain.join(' > ')) ?? null

  it('are one notice per name and version, from the module ids of every chunk, sorted by name', () => {
    const z = makePackage(join(root, 'bundle', 'node_modules', 'z'), { name: 'z', version: '1.0.0', license: 'MIT' })
    const b = makePackage(join(root, 'bundle', 'node_modules', '@s', 'b'), { name: '@s/b', version: '2.0.0', license: 'ISC' })
    const notices = collectNotices([`${z}/index.js`, `${z}/other.js`, `${b}/x.js?query`, '/app/app/app.vue', '\0virtual'], resolvePackage)
    expect(notices.map(notice => `${notice.name}@${notice.version}`)).toEqual(['@s/b@2.0.0', 'z@1.0.0'])
  })

  it('read an asset by the file name Vite gives it, relative to its root, as well as a module by its absolute id', () => {
    const wasm = makePackage(join(root, 'rel', 'node_modules', '.pnpm', 'x@1', 'node_modules', '@x', 'wasm'), { name: '@x/wasm', version: '1.0.0', license: 'MIT' })
    const viteRoot = join(root, 'rel', 'app')
    const relativeId = relative(viteRoot, `${wasm}/dist/engine.wasm`)
    expect(relativeId.startsWith('..')).toBe(true)
    // from the Vite root it is the package; from anywhere else the same name is no file
    expect(collectNotices([relativeId], resolvePackage, viteRoot).map(notice => notice.name)).toEqual(['@x/wasm'])
    expect(collectNotices([relativeId], resolvePackage, join(root, 'elsewhere'))).toEqual([])
  })

  it('include the build tools whose code is in the chunks, which appear as virtual modules', () => {
    const chain = (...names: string[]) => names.join(' > ')
    served.set(chain('nuxt', '@nuxt/vite-builder', 'vite', 'rolldown'), makePackage(join(root, 'tools', 'rolldown'), { name: 'rolldown', version: '1.0.0', license: 'MIT' }))
    served.set(chain('nuxt', '@nuxt/vite-builder', 'vite'), makePackage(join(root, 'tools', 'vite'), { name: 'vite', version: '8.0.0', license: 'MIT' }))
    served.set(chain('nuxt', '@nuxt/vite-builder', '@vitejs/plugin-vue'), makePackage(join(root, 'tools', 'plugin-vue'), { name: '@vitejs/plugin-vue', version: '6.0.0', license: 'MIT' }))
    const names = (ids: string[]) => collectNotices(ids, resolvePackage).map(notice => notice.name)
    expect(names(['\0rolldown/runtime.js'])).toEqual(['rolldown'])
    expect(names(['\0vite/preload-helper.js', '\0vite/modulepreload-polyfill.js'])).toEqual(['vite'])
    expect(names(['\0plugin-vue:export-helper'])).toEqual(['@vitejs/plugin-vue'])
    expect(names(['\0some-other-plugin:helper'])).toEqual([])
  })

  it('include what the app serves apart from its chunks', () => {
    for (const name of SERVED_APART)
      served.set(name, makePackage(join(root, 'apart', name), { name, version: '1.0.0', license: 'MIT' }, { 'swagger-ui-bundle.js.LICENSE.txt': 'bundled' }))
    const notices = collectNotices([], resolvePackage)
    expect(notices.map(notice => notice.name).sort()).toEqual([...SERVED_APART].sort())
  })

  it('are all installed, and have a licence text, for what the app serves apart', () => {
    for (const name of SERVED_APART) {
      const notice = readNotice(findPackageDir(name, join(__dirname, '..', '..'))!)
      expect(notice.texts.length, name).toBeGreaterThan(0)
      expect(needsMoreThanNotice([notice]), name).toEqual([])
    }
  })
})

describe('looking for a package', () => {
  it('walks up the node_modules of each directory, as Node does, and through a chain', () => {
    const base = join(root, 'walk')
    makePackage(join(base, 'node_modules', 'a'), { name: 'a', version: '1.0.0' })
    // b is a dependency of a, beside it in the store of pnpm and not in the app's node_modules
    makePackage(join(base, 'node_modules', '.pnpm', 'a@1', 'node_modules', 'b'), { name: 'b', version: '2.0.0' })
    makePackage(join(base, 'node_modules', '.pnpm', 'a@1', 'node_modules', 'a'), { name: 'a', version: '1.0.0' })
    expect(findPackageDir('a', join(base, 'src', 'deep'))).toBe(realpathOf(join(base, 'node_modules', 'a')))
    expect(findPackageDir('b', base)).toBeNull()
    expect(findPackageDir('b', join(base, 'node_modules', '.pnpm', 'a@1', 'node_modules', 'a'))).toBe(realpathOf(join(base, 'node_modules', '.pnpm', 'a@1', 'node_modules', 'b')))
    expect(findPackageChain(['a', 'b'], base)).toBeNull()
    expect(findPackageChain(['nope'], base)).toBeNull()
  })
})

describe('a licence that asks for more than a notice', () => {
  const of = (license: string) => needsMoreThanNotice([{ name: 'p', version: '1', license, homepage: '', texts: [] }]).length === 1

  it('is flagged, as is one that is not declared', () => {
    for (const license of ['LGPL-3.0-or-later', 'MPL-2.0', 'GPL-3.0', 'AGPL-3.0', 'BSD-4-Clause', 'SEE LICENSE IN LICENSE.md', ''])
      expect(of(license), license).toBe(true)
  })

  it('is not flagged for the licences that ask for a notice', () => {
    for (const license of ['MIT', 'ISC', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', '0BSD', 'CC0-1.0', '(MIT OR Apache-2.0)', 'MIT OR GPL-3.0', 'MIT AND BSD-3-Clause'])
      expect(of(license), license).toBe(false)
  })

  it('is flagged when one of the terms of an AND is not a notice', () => {
    expect(of('MIT AND GPL-3.0')).toBe(true)
  })
})

describe('the file', () => {
  it('names every package with its licence and its texts, and says when a package ships none', () => {
    const text = renderNotices([
      { name: 'a', version: '1.0.0', license: 'MIT', homepage: 'https://example.org/a', texts: [{ file: 'LICENSE', text: 'MIT text of a' }] },
      { name: 'b', version: '2.0.0', license: 'ISC', homepage: '', texts: [] },
    ])
    expect(text).toContain('2 packages.')
    expect(text).toContain('a@1.0.0\nLicence: MIT\nSource: https://example.org/a\n\n--- LICENSE ---\n\nMIT text of a')
    expect(text).toContain('b@2.0.0\nLicence: ISC\n\nThe package ships no licence file')
    expect(text.endsWith('\n')).toBe(true)
  })
})
