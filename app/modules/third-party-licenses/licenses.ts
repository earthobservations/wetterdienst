import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// The logic of the third-party notices (GH-3469), apart from Nuxt so that a test can read it: which packages a
// bundle holds, what each one's licence says and the file all of it is written to. `index.ts` is the module
// that feeds it the bundle of the client build.

/** One package that is served to the browser */
export interface Notice {
  name: string
  version: string
  /** The SPDX expression the package declares, or an empty string when it declares none */
  license: string
  /** Where the package is said to live, for a reader who wants the source */
  homepage: string
  /** The texts of its LICENSE, COPYING and NOTICE files, as the package ships them, by file name */
  texts: { file: string, text: string }[]
}

/**
 * Licences whose terms are a notice (a copyright line and the permission text) and nothing more: the ones the
 * browser bundle holds today. A licence that is not here (LGPL, MPL, GPL, a licence with an advertising clause, an
 * unknown one) fails the check of the e2e suite until someone has read it and added it, with the reason.
 */
export const NOTICE_ONLY_LICENSES = new Set([
  '0BSD',
  'Apache-2.0',
  'BSD-2-Clause',
  'BSD-3-Clause',
  'CC0-1.0',
  'ISC',
  'MIT',
  'Unlicense',
])

/**
 * The package a module of the bundle belongs to, as the directory of its package.json, or null for a module of
 * the app itself or a virtual one. pnpm nests the real directory (`node_modules/.pnpm/<id>/node_modules/<name>`),
 * so the last `node_modules/` of the path is the one that names the package.
 */
export function packageDirOf(moduleId: string): string | null {
  // virtual modules (`\0vite/preload-helper`) and the query of a plugin (`?vue&type=style`) are no path
  const path = moduleId.replace(/^\0/, '').replace(/[?#].*$/, '').replaceAll('\\', '/')
  const marker = '/node_modules/'
  const at = path.lastIndexOf(marker)
  if (at === -1)
    return null
  const rest = path.slice(at + marker.length).split('/')
  const length = rest[0]?.startsWith('@') ? 2 : 1
  if (rest.length < length + 1)
    return null
  return path.slice(0, at + marker.length) + rest.slice(0, length).join('/')
}

// LICENSE, LICENSE.md, LICENSE-MIT, COPYING, NOTICE.txt, and the spelling of leaflet.markercluster, MIT-LICENCE.txt
const LICENSE_FILE = /^(?:[a-z0-9]+[-_.])?(?:licen[cs]e|copying|notice|unlicen[cs]e)(?:[-._].*)?$/i

/** The license field of a package.json: a string, or the object or the list older packages wrote */
function declaredLicense(pkg: Record<string, any>): string {
  const field = pkg.license ?? pkg.licenses
  if (typeof field === 'string')
    return field
  if (Array.isArray(field))
    return field.map(entry => (typeof entry === 'string' ? entry : entry?.type)).filter(Boolean).join(' OR ')
  return typeof field?.type === 'string' ? field.type : ''
}

function homepageOf(pkg: Record<string, any>): string {
  if (typeof pkg.homepage === 'string')
    return pkg.homepage
  const repository = typeof pkg.repository === 'string' ? pkg.repository : pkg.repository?.url
  return typeof repository === 'string' ? repository.replace(/^git\+/, '').replace(/\.git$/, '') : ''
}

/**
 * What a package's own files leave out, filled in by hand from the package's repository. Each is applied only where
 * the package is silent: a declared licence or a shipped licence file is never replaced.
 * - suncalc 2.1.0 ships a BSD-2-Clause LICENSE and declares no `license` field.
 * - vaul-vue 0.4.1 (Nuxt UI's drawer) ships no licence file and declares none; its repository,
 *   github.com/unovue/vaul-vue, is MIT, and `fallbacks/vaul-vue.LICENSE` is that repository's LICENSE.
 * - @duckdb/duckdb-wasm declares MIT and ships no licence file; `fallbacks/duckdb-wasm.LICENSE` is the LICENSE of
 *   github.com/duckdb/duckdb-wasm.
 * - The Iconify icon sets (@iconify-json/*) ship an `info.json` (author, licence, link) and no licence text.
 *   `fallbacks/lucide.LICENSE` and `fallbacks/heroicons.LICENSE` are the LICENSE files of github.com/lucide-icons/lucide
 *   and github.com/tailwindlabs/heroicons; simple-icons is CC0 and asks for nothing, so its `info.json` is the text.
 */
const UNDECLARED: Record<string, { license?: string, textFile?: string }> = {
  'suncalc': { license: 'BSD-2-Clause' },
  'vaul-vue': { license: 'MIT', textFile: 'vaul-vue.LICENSE' },
  '@duckdb/duckdb-wasm': { textFile: 'duckdb-wasm.LICENSE' },
  '@iconify-json/lucide': { textFile: 'lucide.LICENSE' },
  '@iconify-json/heroicons': { textFile: 'heroicons.LICENSE' },
}

/**
 * Files of a package that carry licence text and that the app serves, but are not named like a licence file: the
 * notices Swagger UI's build extracted from the libraries inside `swagger-ui-bundle.js`.
 */
const SIDECARS: Record<string, string[]> = {
  'swagger-ui-dist': ['swagger-ui-bundle.js.LICENSE.txt'],
}

/**
 * Packages that are one file with libraries bundled in, which end it with a block of their licence comments
 * (`/*! Bundled license information: ... *` + `/`): the file to read it from. plotly.js-basic-dist-min is one, and
 * the minifier of the app drops that block from the chunk.
 */
const BUNDLED_COMMENT: Record<string, string> = {
  'plotly.js-basic-dist-min': 'plotly-basic.min.js',
}

const FALLBACKS = join(dirname(fileURLToPath(import.meta.url)), 'fallbacks')

/** The block of licence comments at the end of a bundled file, or null */
export function bundledLicenseComment(source: string): string | null {
  const start = source.lastIndexOf('/*! Bundled license information')
  if (start === -1)
    return null
  const end = source.indexOf('\n*/', start)
  return end === -1 ? null : source.slice(start + 3, end).trim()
}

/** The notice of the package in a directory: what its package.json declares and the texts it ships */
export function readNotice(dir: string): Notice {
  const pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'))
  const read = (file: string) => readFileSync(join(dir, file), 'utf8').replaceAll('\r\n', '\n').trim()
  const files = [
    ...readdirSync(dir).filter(file => LICENSE_FILE.test(file) && statSync(join(dir, file)).isFile()).sort(),
    ...(SIDECARS[pkg.name] ?? []),
  ]
  const texts = files.map(file => ({ file, text: read(file) })).filter(entry => entry.text !== '')
  const notice: Notice = { name: pkg.name, version: pkg.version, license: declaredLicense(pkg), homepage: homepageOf(pkg), texts }
  const gap = UNDECLARED[notice.name]
  if (gap?.license && notice.license === '')
    notice.license = gap.license
  if (gap?.textFile && texts.length === 0)
    texts.push({ file: `${gap.textFile} (the repository's, the package ships none)`, text: readFileSync(join(FALLBACKS, gap.textFile), 'utf8').trim() })
  if (texts.length === 0 && existsSync(join(dir, 'info.json'))) {
    const info = JSON.parse(read('info.json'))
    texts.push({ file: 'info.json', text: `Icons by ${info.author?.name} (${info.author?.url}), licence ${info.license?.title} (${info.license?.url})` })
  }
  const bundled = BUNDLED_COMMENT[notice.name]
  const comment = bundled ? bundledLicenseComment(read(bundled)) : null
  if (comment)
    texts.push({ file: `${bundled} (the libraries bundled in the file)`, text: comment })
  return notice
}

/**
 * Packages served to the browser by something other than a chunk of the client build, so the build cannot name
 * them. Each is a file of the package that the app copies out and serves (`modules/swagger-ui.ts` for Swagger UI) or
 * that the server answers with (the icons the page asks `/_nuxt_icon` for, from the three sets
 * `nuxt.config.ts` installs).
 */
export const SERVED_APART = ['swagger-ui-dist', '@iconify-json/lucide', '@iconify-json/heroicons', '@iconify-json/simple-icons']

/** The notices of the packages a set of module ids and the packages served apart come from, one per name and version */
export function collectNotices(moduleIds: Iterable<string>, resolvePackage: (name: string) => string | null): Notice[] {
  const dirs = new Set<string>()
  for (const id of moduleIds) {
    const dir = packageDirOf(id)
    if (dir && existsSync(join(dir, 'package.json')))
      dirs.add(dir)
  }
  for (const name of SERVED_APART) {
    const dir = resolvePackage(name)
    if (dir)
      dirs.add(dir)
  }
  const byKey = new Map<string, Notice>()
  for (const dir of dirs) {
    const notice = readNotice(dir)
    byKey.set(`${notice.name}@${notice.version}`, notice)
  }
  return [...byKey.values()].sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version))
}

/** The packages that need more than a notice: the licence they declare is not in {@link NOTICE_ONLY_LICENSES} */
export function needsMoreThanNotice(notices: Notice[]): Notice[] {
  return notices.filter((notice) => {
    const alternatives = notice.license.replace(/[()]/g, '').split(/\s+(?:OR|AND)\s+/i).map(part => part.trim())
    // "A OR B" is met by one of them; "A AND B" by both, so the stricter reading (every part) is the one used
    // for AND and the looser for OR
    const all = /\sAND\s/i.test(notice.license)
    const known = alternatives.map(part => NOTICE_ONLY_LICENSES.has(part))
    return notice.license === '' || !(all ? known.every(Boolean) : known.some(Boolean))
  })
}

const RULE = '='.repeat(78)

/** The text of the file: what it is, then every package with the licence texts it ships */
export function renderNotices(notices: Notice[]): string {
  const parts = [
    [
      'Third-party licences of the Wetterdienst app',
      '',
      'The pages of this app run code of the open-source packages below, and the app serves their files (icons,',
      'Swagger UI, the DuckDB WebAssembly module). Each package is listed with the licence it declares and the',
      'licence and notice files it ships, as they are, because those licences ask that the copyright notice and the',
      'permission text accompany the code. This file is generated by the production build from the packages the',
      'build holds (modules/third-party-licenses); the app itself is MIT-licensed.',
      '',
      `${notices.length} packages.`,
    ].join('\n'),
  ]
  for (const notice of notices) {
    const head = [`${RULE}\n${notice.name}@${notice.version}`, `Licence: ${notice.license || 'not declared by the package'}`]
    if (notice.homepage)
      head.push(`Source: ${notice.homepage}`)
    const body = notice.texts.length
      ? notice.texts.map(entry => `--- ${entry.file} ---\n\n${entry.text}`).join('\n\n')
      : 'The package ships no licence file; the licence above is what its package.json declares.'
    parts.push(`${head.join('\n')}\n\n${body}`)
  }
  return `${parts.join('\n\n')}\n`
}

/** What the development server answers in place of the file: the notices are generated from a production build */
export const DEVELOPMENT_NOTICE = 'The third-party licences are generated by the production build (pnpm run build); the development server has no bundle to read them from.\n'
