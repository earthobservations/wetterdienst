// Lighthouse's accessibility score of every page of the production build, by hand before an app release (ACCESSIBILITY.md).
//
//   pnpm build && pnpm lighthouse [--version 13.6.0] [--port 4413] [--mock-port 4412] [--only /api,/settings]
//
// The build is served by `.output/server/index.mjs`, with `NUXT_API_BASE` on a server of this script that answers every
// `/api/*` request as the accessibility spec's mock backend does (`defaultHandlers` of mock-backend.ts), so that a page
// shows what it shows with data and no provider is reached. Each of the 17 URLs is run twice, as Lighthouse's default
// (mobile) and as `--preset=desktop`, with `npx lighthouse@<version>`, which needs the network and a Chrome (set
// `CHROME_PATH` if Lighthouse does not find it). It prints a table and the line for ACCESSIBILITY.md, and exits 1 if
// a run scores under 100. A run that Lighthouse itself fails (a page it saw no paint of) is tried once more. `--only` keeps
// the URLs that start with one of its comma-separated paths.

import { spawn } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import process from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import ts from 'typescript'

// the 16 pages of the spec's first paint (`PAGES` in accessibility.spec.ts), and the explorer with a station chosen
export const EXPLORER_WITH_STATION = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'
export const URLS = ['/', '/explorer', EXPLORER_WITH_STATION, '/stripes', '/meteogram', '/history', '/map', '/widget', '/glossary', '/providers', '/providers/dwd', '/api', '/settings', '/about', '/support', '/impressum', '/datenschutz']

const option = (name, fallback) => process.argv.includes(`--${name}`) ? process.argv[process.argv.indexOf(`--${name}`) + 1] : fallback

/** The accessibility spec's mock backend, which is TypeScript, as a module of the temporary directory */
async function loadMockBackend(directory) {
  const source = readFileSync(fileURLToPath(new URL('./mock-backend.ts', import.meta.url)), 'utf-8')
  const file = join(directory, 'mock-backend.mjs')
  writeFileSync(file, ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText)
  return import(pathToFileURL(file).href)
}

async function main() {
  const version = option('version', '13.6.0')
  const [port, mockPort] = [option('port', '4413'), option('mock-port', '4412')]
  const directory = mkdtempSync(join(tmpdir(), 'wetterdienst-lighthouse-'))
  const { ApiFailure, defaultHandlers } = await loadMockBackend(directory)
  const handlers = defaultHandlers()
  const mock = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://localhost')
    const handler = handlers[url.pathname.replace(/^\/api\//, '')]
    const send = (status, body) => {
      response.writeHead(status, { 'content-type': 'application/json' })
      response.end(JSON.stringify(body))
    }
    if (!handler)
      return send(501, { detail: `not mocked: ${url.pathname}` })
    const body = await handler(url, {})
    return body instanceof ApiFailure ? send(body.status, { ...body.extra, detail: body.detail }) : send(200, body)
  })
  await new Promise(resolve => mock.listen(Number(mockPort), resolve))

  const app = spawn('node', ['server/index.mjs'], {
    cwd: fileURLToPath(new URL('../../../.output', import.meta.url)),
    env: { ...process.env, PORT: port, WD_E2E: '1', NUXT_API_BASE: `http://localhost:${mockPort}/api` },
    stdio: 'ignore',
  })
  const stop = () => {
    app.kill()
    mock.close()
  }
  try {
    // the server is up when a page answers
    for (let attempt = 0; ; attempt++) {
      try {
        if ((await fetch(`http://localhost:${port}/`)).ok)
          break
      }
      catch {}
      if (attempt > 60)
        throw new Error('the build did not start: run `pnpm build` first')
      await new Promise(resolve => setTimeout(resolve, 500))
    }

    const scores = []
    const only = option('only', '').split(',').filter(Boolean)
    for (const path of URLS.filter(url => !only.length || only.some(prefix => url.startsWith(prefix)))) {
      for (const device of ['mobile', 'desktop']) {
        const output = join(directory, `${scores.length}.json`)
        // not `spawnSync`: it would stop this process's own mock backend, which the page being scored asks for its data
        const run = () => new Promise(resolve => spawn('npx', ['--yes', `lighthouse@${version}`, `http://localhost:${port}${path}`, '--only-categories=accessibility', '--chrome-flags=--headless=new', '--output=json', `--output-path=${output}`, '--quiet', ...(device === 'desktop' ? ['--preset=desktop'] : [])], { stdio: 'inherit' }).on('close', status => resolve({ status })))
        const result = (await run()).status === 0 ? { status: 0 } : await run()
        if (result.status !== 0)
          throw new Error(`lighthouse failed on ${path} (${device})`)
        const report = JSON.parse(readFileSync(output, 'utf-8'))
        const failed = report.categories.accessibility.auditRefs.filter(ref => report.audits[ref.id].score === 0).map(ref => ref.id)
        scores.push({ path, device, score: Math.round(report.categories.accessibility.score * 100), failed, version: report.lighthouseVersion, chrome: report.environment?.hostUserAgent })
        console.warn(`${String(scores.at(-1).score).padStart(3)}  ${device.padEnd(7)} ${path}${failed.length ? `  ${failed.join(', ')}` : ''}`)
      }
    }
    const below = scores.filter(entry => entry.score < 100)
    const counts = Object.entries(Object.groupBy(scores, entry => entry.score)).map(([score, list]) => `${list.length} x ${score}`).join(', ')
    console.warn(`\nLighthouse ${scores[0].version}, ${scores[0].chrome}\n${new Set(scores.map(entry => entry.path)).size} URLs x mobile, desktop: ${counts}`)
    for (const entry of below)
      console.warn(`  ${entry.score}: ${entry.path} (${entry.device}): ${entry.failed.join(', ')}`)
    process.exitCode = below.length ? 1 : 0
  }
  finally {
    stop()
  }
}

// run as a script, and not when a test reads the list of the URLs
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  main().catch((error) => {
    console.error(error)
    process.exit(1)
  })
}
