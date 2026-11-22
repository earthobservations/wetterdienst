// A stand-in for Photon (photon.komoot.io) for the end-to-end tests (GH-3790, GH-3791): the app's server asks it for places
// (`NUXT_PLACES_PHOTON_BASE`, which `playwright.config.ts` points here), so that no automated test ever calls komoot's public server.
//
//   GET /api/?q=&lang=&limit=   GeoJSON as Photon answers, for a few texts; an unsupported `lang` is a 400, as on komoot's server
//   GET /__requests             what was asked, with the headers that came with it: the tests read them to see what the app's server sends
//   DELETE /__requests          forgets them
//   GET /__health               for Playwright's wait
//
// The texts: "bad tölz" and "paris" answer places (real answers, see below); "gedrosselt" answers a 429, "kaputt" a 500, "nichts" no hit. Run by hand: `node tests/e2e/mock-photon.mjs 4100`.
import { readFileSync } from 'node:fs'
import { createServer } from 'node:http'
import process from 'node:process'

const port = Number(process.argv[2] || process.env.E2E_PHOTON_PORT || 4100)
/** @type {Array<{ url: string, headers: Record<string, string | string[] | undefined> }>} */
let requests = []

// The answers are real ones of komoot's server, saved (tests/fixtures/photon-badtoelz.json and photon-paris.json: twelve hits each, with the streets, the
// buildings and the boundaries that the app's server leaves out, and the same town as a node, a relation and a boundary); the names of the countries are
// put into the language asked for, as Photon does
const fixture = name => JSON.parse(readFileSync(new URL(`../fixtures/${name}.json`, import.meta.url), 'utf8'))
const COUNTRIES = {
  DE: { en: 'Germany', de: 'Deutschland', fr: 'Allemagne' },
  FR: { en: 'France', de: 'Frankreich', fr: 'France' },
  US: { en: 'United States', de: 'Vereinigte Staaten', fr: 'États-Unis' },
}
function inLanguage(body, lang) {
  for (const hit of body.features) {
    const names = COUNTRIES[hit.properties.countrycode]
    if (names && lang && names[lang])
      hit.properties.country = names[lang]
  }
  return body
}

const server = createServer((request, response) => {
  const url = new URL(request.url ?? '/', 'http://localhost')
  const json = (status, body) => {
    response.writeHead(status, { 'content-type': 'application/json' })
    response.end(JSON.stringify(body))
  }
  if (url.pathname === '/__health')
    return json(200, { ok: true })
  if (url.pathname === '/__requests') {
    if (request.method === 'DELETE') {
      requests = []
      return json(200, [])
    }
    return json(200, requests)
  }
  if (url.pathname !== '/api/' && url.pathname !== '/api')
    return json(404, { message: 'not found' })
  requests.push({ url: request.url ?? '', headers: { ...request.headers } })
  const lang = url.searchParams.get('lang')
  if (lang && !['default', 'de', 'en', 'fr'].includes(lang))
    return json(400, { lang: [{ message: 'Language is not supported. Supported are: default, de, en, fr', args: {}, value: lang }] })
  const q = (url.searchParams.get('q') ?? '').toLowerCase()
  if (q.startsWith('gedrosselt'))
    return json(429, { message: 'too many requests' })
  if (q.startsWith('kaputt'))
    return json(500, { message: 'broken' })
  if (q.startsWith('bad t'))
    return json(200, inLanguage(fixture('photon-badtoelz'), lang))
  if (q.startsWith('paris'))
    return json(200, inLanguage(fixture('photon-paris'), lang))
  return json(200, { type: 'FeatureCollection', features: [] })
})

server.listen(port, '127.0.0.1')
