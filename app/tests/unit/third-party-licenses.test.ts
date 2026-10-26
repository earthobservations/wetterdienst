import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import {
  bundledLicenseComment,
  collectNotices,
  needsMoreThanNotice,
  packageDirOf,
  readNotice,
  renderNotices,
  SERVED_APART,
} from '../../modules/third-party-licenses/licenses'

// The notices of what the browser is served (GH-3469): which package a module of the bundle belongs to, what is
// read from the package, and what is written. That the file lists every package of the real bundle is
// `tests/e2e/third-party-licenses.spec.ts`, which needs a production build.

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
    expect(vaul.texts).toHaveLength(1)
    expect(vaul.texts[0]!.text).toContain('Permission is hereby granted')

    const duckdb = readNotice(makePackage(join(root, 'duckdb'), { name: '@duckdb/duckdb-wasm', version: '1', license: 'MIT' }))
    expect(duckdb.texts[0]!.text).toContain('DuckDB')

    const shipped = readNotice(makePackage(join(root, 'vaul-vue-2'), { name: 'vaul-vue', version: '9', license: 'ISC' }, { LICENSE: 'Their own text' }))
    expect(shipped.license).toBe('ISC')
    expect(shipped.texts).toEqual([{ file: 'LICENSE', text: 'Their own text' }])
  })

  it('adds the licence comments a bundled file ends with', () => {
    const file = '/*! plotly */\nvar a=1;\n/*! Bundled license information:\n\nleft-pad/index.js:\n  (* MIT *)\n*/\n\nreturn a;'
    expect(bundledLicenseComment(file)).toBe('Bundled license information:\n\nleft-pad/index.js:\n  (* MIT *)')
    expect(bundledLicenseComment('var a=1')).toBeNull()

    const notice = readNotice(makePackage(join(root, 'plotly'), { name: 'plotly.js-basic-dist-min', version: '3', license: 'MIT' }, { 'LICENSE': 'Plotly MIT', 'plotly-basic.min.js': file }))
    expect(notice.texts.map(entry => entry.text)).toEqual(['Plotly MIT', expect.stringContaining('left-pad/index.js')])
  })
})

describe('the packages of a bundle', () => {
  const served = new Map<string, string>()
  const resolvePackage = (name: string) => served.get(name) ?? null

  it('are one notice per name and version, from the module ids of every chunk, sorted by name', () => {
    const z = makePackage(join(root, 'bundle', 'node_modules', 'z'), { name: 'z', version: '1.0.0', license: 'MIT' })
    const b = makePackage(join(root, 'bundle', 'node_modules', '@s', 'b'), { name: '@s/b', version: '2.0.0', license: 'ISC' })
    const notices = collectNotices([`${z}/index.js`, `${z}/other.js`, `${b}/x.js?query`, '/app/app/app.vue', '\0virtual'], resolvePackage)
    expect(notices.map(notice => `${notice.name}@${notice.version}`)).toEqual(['@s/b@2.0.0', 'z@1.0.0'])
  })

  it('include what the app serves apart from its chunks', () => {
    for (const name of SERVED_APART)
      served.set(name, makePackage(join(root, 'apart', name), { name, version: '1.0.0', license: 'MIT' }, { 'swagger-ui-bundle.js.LICENSE.txt': 'bundled' }))
    const notices = collectNotices([], resolvePackage)
    expect(notices.map(notice => notice.name).sort()).toEqual([...SERVED_APART].sort())
  })

  it('are all installed, and have a licence text, for what the app serves apart', () => {
    const require = createRequire(import.meta.url)
    for (const name of SERVED_APART) {
      const notice = readNotice(dirname(require.resolve(`${name}/package.json`)))
      expect(notice.texts.length, name).toBeGreaterThan(0)
      expect(needsMoreThanNotice([notice]), name).toEqual([])
    }
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
