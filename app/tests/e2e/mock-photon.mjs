// A stand-in for Photon (photon.komoot.io) for the end-to-end tests (GH-3790, GH-3791): the app's server asks it for places
// (`NUXT_PLACES_PHOTON_BASE`, which `playwright.config.ts` points here), so that no automated test ever calls komoot's public server.
//
//   GET /api/?q=&lang=&limit=   GeoJSON as Photon answers, for a few texts; an unsupported `lang` is a 400, as on komoot's server
//   GET /__requests             what was asked, with the headers that came with it: the tests read them to see what the app's server sends
//   DELETE /__requests          forgets them
//   GET /__health               for Playwright's wait
//
// The texts: "bad tölz" and "paris" answer places (and, among them, the streets and shops that the app's server leaves out, and the
// same town twice); "gedrosselt" answers a 429, "kaputt" a 500, "nichts" no hit. Run by hand: `node tests/e2e/mock-photon.mjs 4100`.
import { createServer } from 'node:http'
import process from 'node:process'

const port = Number(process.argv[2] || process.env.E2E_PHOTON_PORT || 4100)
/** @type {Array<{ url: string, headers: Record<string, string | string[] | undefined> }>} */
let requests = []

const feature = (lon, lat, properties) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties })

function BAD_TOELZ(lang) {
  return [
    feature(11.5583, 47.7614, { osm_id: 240109189, osm_type: 'N', osm_key: 'place', osm_value: 'town', type: 'city', name: 'Bad Tölz', state: 'Bayern', county: 'Landkreis Bad Tölz-Wolfratshausen', country: lang === 'en' ? 'Germany' : 'Deutschland', countrycode: 'DE' }),
    feature(11.5584, 47.7615, { osm_id: 2145289, osm_type: 'R', osm_key: 'boundary', osm_value: 'administrative', type: 'city', name: 'Bad Tölz', state: 'Bayern', country: lang === 'en' ? 'Germany' : 'Deutschland', countrycode: 'DE' }),
    feature(11.55, 47.77, { osm_id: 51, osm_type: 'W', osm_key: 'highway', osm_value: 'residential', type: 'street', name: 'Bad Tölzer Straße', city: 'München', state: 'Bayern', country: 'Deutschland', countrycode: 'DE' }),
    feature(11.5, 47.78, { osm_id: 2145290, osm_type: 'R', osm_key: 'boundary', osm_value: 'administrative', type: 'county', name: 'Landkreis Bad Tölz-Wolfratshausen', state: 'Bayern', country: lang === 'en' ? 'Germany' : 'Deutschland', countrycode: 'DE' }),
    feature(11.57, 47.75, { osm_id: 77, osm_type: 'N', osm_key: 'amenity', osm_value: 'cafe', type: 'house', name: 'Café Bad Tölz', city: 'Bad Tölz', country: 'Deutschland', countrycode: 'DE' }),
  ]
}
function PARIS(lang) {
  return [
    feature(2.3200, 48.8588, { osm_id: 7444, osm_type: 'R', osm_key: 'boundary', osm_value: 'administrative', type: 'city', name: 'Paris', state: 'Île-de-France', country: lang === 'de' ? 'Frankreich' : lang === 'fr' ? 'France' : 'France', countrycode: 'FR' }),
    feature(2.3522, 48.8566, { osm_id: 17807753, osm_type: 'N', osm_key: 'place', osm_value: 'city', type: 'city', name: 'Paris', state: 'Île-de-France', country: lang === 'de' ? 'Frankreich' : 'France', countrycode: 'FR' }),
    feature(-95.5555, 33.6609, { osm_id: 118, osm_type: 'N', osm_key: 'place', osm_value: 'city', type: 'city', name: 'Paris', state: 'Texas', country: lang === 'de' ? 'Vereinigte Staaten' : 'United States', countrycode: 'US' }),
    feature(-82.4, 36.5, { osm_id: 119, osm_type: 'N', osm_key: 'place', osm_value: 'village', type: 'city', name: 'Paris', county: 'Henry County', state: 'Tennessee', country: 'United States', countrycode: 'US' }),
    feature(2.35, 48.85, { osm_id: 120, osm_type: 'W', osm_key: 'railway', osm_value: 'station', type: 'other', name: 'Paris Gare de Lyon', city: 'Paris', country: 'France', countrycode: 'FR' }),
    feature(2.55, 49.0, { osm_id: 121, osm_type: 'W', osm_key: 'aeroway', osm_value: 'aerodrome', type: 'other', name: 'Paris-Charles-de-Gaulle', state: 'Île-de-France', country: 'France', countrycode: 'FR' }),
  ]
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
  const features = q.startsWith('bad t') ? BAD_TOELZ(lang) : q.startsWith('paris') ? PARIS(lang) : []
  return json(200, { type: 'FeatureCollection', features })
})

server.listen(port, '127.0.0.1')
