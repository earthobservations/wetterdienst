import { existsSync, readdirSync, readFileSync, realpathSync, statSync } from 'node:fs'
import { dirname, isAbsolute, join, resolve } from 'node:path'
import process from 'node:process'
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
  // the fonts (@fontsource-variable/geist and geist-mono, GH-3518), read: the OFL asks that the copyright line and
  // the licence text go with the font, which the file does (the whole text), that the font is not sold by itself, and
  // that a modified font does not carry the reserved name; the app serves the files as they are
  'OFL-1.1',
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

/** A repository field as a URL a reader can open: `owner/repo`, `github:o/r`, `git@host:o/r.git`, `git://`, `git+ssh://` */
export function repositoryUrl(repository: string): string {
  const url = repository.trim()
    .replace(/^git\+/, '')
    .replace(/^git:\/\//, 'https://')
    .replace(/^ssh:\/\/git@/, 'https://')
    .replace(/^git@([^:/]+):/, 'https://$1/')
    .replace(/^(github|gitlab|bitbucket):/, (_, host: string) => `https://${host}.${host === 'bitbucket' ? 'org' : 'com'}/`)
    .replace(/\.git$/, '')
  return /^[\w.-]+\/[\w.-]+$/.test(url) ? `https://github.com/${url}` : url
}

function homepageOf(pkg: Record<string, any>): string {
  if (typeof pkg.homepage === 'string')
    return pkg.homepage
  const repository = typeof pkg.repository === 'string' ? pkg.repository : pkg.repository?.url
  return typeof repository === 'string' ? repositoryUrl(repository) : ''
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
 *   `fallbacks/phosphor.LICENSE` is the LICENSE file of github.com/phosphor-icons/core; simple-icons is CC0 and asks for
 *   nothing, so its `info.json` is the text.
 */
const UNDECLARED: Record<string, { license?: string, textFile?: string }> = {
  'suncalc': { license: 'BSD-2-Clause' },
  'vaul-vue': { license: 'MIT', textFile: 'vaul-vue.LICENSE' },
  '@duckdb/duckdb-wasm': { textFile: 'duckdb-wasm.LICENSE' },
  '@iconify-json/ph': { textFile: 'phosphor.LICENSE' },
}

/**
 * Texts added to a package whether or not it ships a licence of its own, for the code that is inside its files and
 * has a licence of its own. Each file of `fallbacks/` says in its header where its texts are from and at which version.
 * - @duckdb/duckdb-wasm: DuckDB's LICENSE, those of its `third_party/` and ICU, which the WASM modules link
 *   statically, and js-sha256 and ws, which the worker bundles.
 * - plotly.js-basic-dist-min: the libraries bundled in the file that can be identified in it; the header of the
 *   file says which others are not reproduced.
 * - vaul-vue is a port of Vaul (Emil Kowalski, MIT), which its README says; the repository's LICENSE of the port does
 *   not carry Vaul's.
 */
const EXTRA_TEXTS: Record<string, { file: string, label: string }[]> = {
  '@duckdb/duckdb-wasm': [{ file: 'duckdb-wasm-third-party.txt', label: 'the code inside the DuckDB files' }],
  'plotly.js-basic-dist-min': [{ file: 'plotly-third-party.txt', label: 'the libraries bundled in the file' }],
  'vaul-vue': [{ file: 'vaul.LICENSE', label: 'Vaul\'s, of which vaul-vue is a port' }],
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

/**
 * A licence notice a package embeds in one of its own files, for code that is not the package's: leaflet.markercluster's
 * dist/leaflet.markercluster-src.js carries QuickHull under its own MIT notice (copyright "2012 the authors listed
 * at literateprograms.org"). The comment around the marker text is copied from the file as it is.
 */
const EMBEDDED_COMMENT: Record<string, { file: string, marker: string, label: string }> = {
  'leaflet.markercluster': { file: 'dist/leaflet.markercluster-src.js', marker: 'literateprograms.org', label: 'QuickHull, embedded in dist/leaflet.markercluster-src.js' },
}

/** The `/* ... *` + `/` comment around the first place `marker` is found in a source, or null */
export function commentAround(source: string, marker: string): string | null {
  const at = source.indexOf(marker)
  const start = source.lastIndexOf('/*', at)
  const end = source.indexOf('*/', at)
  return at === -1 || start === -1 || end === -1 ? null : source.slice(start, end + 2)
}

const FALLBACKS = join(dirname(fileURLToPath(import.meta.url)), 'fallbacks')

/** A text as the file has it: line ends as `\n`, no blank lines before or after, and the indentation of its first line kept */
export function exactText(text: string): string {
  return text.replaceAll('\r\n', '\n').replace(/^(?:[ \t]*\n)+/, '').replace(/\s+$/, '')
}

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
  const read = (file: string) => exactText(readFileSync(join(dir, file), 'utf8'))
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
    texts.push({ file: `${gap.textFile} (the repository's, the package ships none)`, text: exactText(readFileSync(join(FALLBACKS, gap.textFile), 'utf8')) })
  if (texts.length === 0 && existsSync(join(dir, 'info.json'))) {
    const info = JSON.parse(read('info.json'))
    texts.push({ file: 'info.json', text: `Icons by ${info.author?.name} (${info.author?.url}), licence ${info.license?.title} (${info.license?.url})` })
  }
  for (const extra of EXTRA_TEXTS[notice.name] ?? [])
    texts.push({ file: `${extra.file} (${extra.label})`, text: exactText(readFileSync(join(FALLBACKS, extra.file), 'utf8')) })
  const embedded = EMBEDDED_COMMENT[notice.name]
  const embeddedText = embedded && existsSync(join(dir, embedded.file)) ? commentAround(read(embedded.file), embedded.marker) : null
  if (embedded && embeddedText)
    texts.push({ file: embedded.label, text: embeddedText })
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
export const SERVED_APART = ['swagger-ui-dist', '@iconify-json/ph', '@iconify-json/simple-icons']

/**
 * The directory of a package, looked for the way Node does: in the `node_modules` of the directory and of each one
 * above it, from `from` up. This works for a package whose `exports` hide its package.json, which `require.resolve`
 * of `<name>/package.json` does not. The real path, because pnpm links the packages.
 */
export function findPackageDir(name: string, from: string): string | null {
  for (let dir = resolve(from); ; dir = dirname(dir)) {
    const candidate = join(dir, 'node_modules', name)
    if (existsSync(join(candidate, 'package.json')))
      return realpathSync(candidate)
    if (dirname(dir) === dir)
      return null
  }
}

/**
 * The packages named in a chain (`['nuxt', '@nuxt/vite-builder', 'vite']`), each looked for from the one before:
 * the way to a package that is a dependency of a dependency, which pnpm does not link into the app's `node_modules`.
 */
export function findPackageChain(chain: string[], from: string): string | null {
  let dir: string | null = from
  for (const name of chain) {
    dir = findPackageDir(name, dir)
    if (!dir)
      return null
  }
  return dir
}

/**
 * The code the build tools put in the chunks themselves, as the virtual modules they appear as, and the chain of
 * packages that gets to it from the app: `rolldown/runtime.js` (the module wrapper), Vite's preload helper and
 * modulepreload polyfill, and the export helper of @vitejs/plugin-vue.
 */
const BUILD_HELPERS: [prefix: string, chain: string[]][] = [
  ['rolldown/', ['nuxt', '@nuxt/vite-builder', 'vite', 'rolldown']],
  ['vite/', ['nuxt', '@nuxt/vite-builder', 'vite']],
  ['plugin-vue:', ['nuxt', '@nuxt/vite-builder', '@vitejs/plugin-vue']],
]

/**
 * The notices of the packages a set of module ids and the packages served apart come from, one per name and version.
 * `resolvePackage` finds a package by a chain of names (see {@link findPackageChain}); `root` is what a relative id is
 * relative to: Vite writes the file names of an asset relative to its root (`../node_modules/.pnpm/...`), where a
 * module id is absolute.
 */
export function collectNotices(moduleIds: Iterable<string>, resolvePackage: (chain: string[]) => string | null, root = process.cwd()): Notice[] {
  const dirs = new Set<string>()
  const add = (dir: string | null) => {
    if (dir && existsSync(join(dir, 'package.json')))
      dirs.add(dir)
  }
  const helpers = new Set<string>()
  for (const id of moduleIds) {
    if (id.startsWith('\0')) {
      const helper = BUILD_HELPERS.find(([prefix]) => id.startsWith(`\0${prefix}`))
      if (helper)
        helpers.add(helper[0])
    }
    add(packageDirOf(id.includes('node_modules') && !isAbsolute(id.replace(/^\0/, '')) ? resolve(root, id.replace(/^\0/, '')) : id))
  }
  for (const prefix of helpers)
    add(resolvePackage(BUILD_HELPERS.find(([candidate]) => candidate === prefix)![1]))
  for (const name of SERVED_APART)
    add(resolvePackage([name]))
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
      'The entries of @duckdb/duckdb-wasm, plotly.js-basic-dist-min and leaflet.markercluster (QuickHull) also',
      'reproduce the licences of the code that is inside their files, and say what they cover. This file lists',
      'the notices found by this process and is not a legal guarantee of completeness.',
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
