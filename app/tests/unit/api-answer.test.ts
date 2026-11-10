import { describe, expect, it } from 'vitest'
import { API_ANSWER, readJsonAnswer, rejectUnexpectedAnswer, UNEXPECTED_ANSWER_TYPE, UnexpectedAnswerError, unexpectedAnswerReason } from '../../app/utils/api-answer'
import { describeFetchError } from '../../app/utils/api-error'

// What the app takes for an answer of the REST API (GH-3841): a page of HTML, or JSON that is not what the endpoint
// gives, is a failure, never a list with no entries.

const HTML = 'text/html; charset=utf-8'

describe('unexpectedAnswerReason', () => {
  it('rejects a page of HTML for any endpoint, whatever its status of success', () => {
    for (const path of ['/api/stations', '/api/values', '/api/version', '/api/anything-else'])
      expect(unexpectedAnswerReason(path, { status: 200, contentType: HTML, data: '<html></html>' })).toContain('a web page')
    expect(unexpectedAnswerReason('/api/stations', { status: 200, contentType: 'application/xhtml+xml' })).toContain('a web page')
  })

  it('does not look at an error status, which is the failure of its own, or at an answer with no body', () => {
    expect(unexpectedAnswerReason('/api/stations', { status: 502, contentType: HTML })).toBeNull()
    expect(unexpectedAnswerReason('/api/stations', { status: 204, contentType: null })).toBeNull()
  })

  it('lets the output format html through where it was asked for by name', () => {
    expect(unexpectedAnswerReason('/api/values?format=html', { status: 200, contentType: HTML })).toBeNull()
    expect(unexpectedAnswerReason('/api/values', { status: 200, contentType: HTML }, { format: 'html' })).toBeNull()
  })

  it('accepts the answers the endpoints give, an empty list included', () => {
    const json = 'application/json'
    expect(unexpectedAnswerReason('/api/stations', { status: 200, contentType: json, data: { stations: [] } })).toBeNull()
    expect(unexpectedAnswerReason('/api/stripes/values', { status: 200, contentType: json, data: { values: [] } })).toBeNull()
    expect(unexpectedAnswerReason('/api/providers', { status: 200, contentType: json, data: { providers: [] } })).toBeNull()
    expect(unexpectedAnswerReason('/api/glossary', { status: 200, contentType: json, data: [] })).toBeNull()
    expect(unexpectedAnswerReason('/api/coverage', { status: 200, contentType: json, data: {} })).toBeNull()
    // the same under the versioned address
    expect(unexpectedAnswerReason('/api/v1/stations', { status: 200, contentType: json, data: { stations: [] } })).toBeNull()
  })

  it('rejects JSON that is not the list of the endpoint, and a text where JSON was to be', () => {
    const json = 'application/json'
    expect(unexpectedAnswerReason('/api/stations', { status: 200, contentType: json, data: {} })).toContain('no list of `stations`')
    expect(unexpectedAnswerReason('/api/stations', { status: 200, contentType: json, data: { stations: {} } })).toContain('no list of `stations`')
    expect(unexpectedAnswerReason('/api/stations', { status: 200, contentType: json, data: null })).toContain('no list of `stations`')
    expect(unexpectedAnswerReason('/api/values', { status: 200, contentType: json, data: [] })).toContain('no list of `values`')
    expect(unexpectedAnswerReason('/api/glossary', { status: 200, contentType: json, data: { entries: [] } })).toContain('no list')
    expect(unexpectedAnswerReason('/api/coverage', { status: 200, contentType: json, data: [] })).toContain('no object')
    expect(unexpectedAnswerReason('/api/stations', { status: 200, contentType: 'text/plain', data: 'nope' })).toContain('text/plain, not JSON')
  })

  it('leaves what the app asked for as a text or in another format alone', () => {
    expect(unexpectedAnswerReason('/api/values', { status: 200, contentType: 'text/csv', data: 'a,b' }, { format: 'csv' })).toBeNull()
    expect(unexpectedAnswerReason('/api/values', { status: 200, contentType: 'application/geo+json', data: { type: 'FeatureCollection' } }, { format: 'geojson' })).toBeNull()
    expect(unexpectedAnswerReason('/api/values', { status: 200, contentType: 'application/json', data: '{}' }, { responseType: 'text' })).toBeNull()
  })
})

describe('the onResponse hook', () => {
  const response = (body: string, contentType: string, data?: unknown) => ({ status: 200, headers: new Headers({ 'content-type': contentType }), _data: data ?? body })

  it('throws a 502 problem of its own kind for a page of HTML, which describeFetchError tells by its detail', () => {
    let thrown: unknown
    try {
      API_ANSWER.onResponse({ request: '/api/stations', response: response('<html></html>', HTML), options: {} })
    }
    catch (error) {
      thrown = error
    }
    expect(thrown).toBeInstanceOf(UnexpectedAnswerError)
    expect((thrown as UnexpectedAnswerError).data).toMatchObject({ type: UNEXPECTED_ANSWER_TYPE, status: 502 })
    expect(describeFetchError(thrown)).toContain('The API answered with a web page, not data')
  })

  it('reads the format of the query the caller gave', () => {
    expect(() => rejectUnexpectedAnswer({ request: '/api/values', response: response('<table></table>', HTML), options: { query: { format: 'html' } } })).not.toThrow()
  })

  it('returns for a JSON answer of the right shape', () => {
    expect(() => rejectUnexpectedAnswer({ request: '/api/stations', response: response('', 'application/json', { stations: [] }), options: {} })).not.toThrow()
  })
})

describe('readJsonAnswer', () => {
  const answer = (body: string, contentType: string, status = 200) => new Response(body, { status, headers: { 'content-type': contentType } })

  it('parses the JSON of an answer', async () => {
    expect(await readJsonAnswer('/api/values', answer('{"values":[]}', 'application/json'))).toEqual({ values: [] })
  })

  it('fails for a page, before its body is read, and for a body that is no JSON', async () => {
    await expect(readJsonAnswer('/api/values', answer('<html></html>', HTML))).rejects.toThrow(/a web page/)
    await expect(readJsonAnswer('/api/values', answer('<html></html>', 'text/plain'))).rejects.toThrow(/text\/plain, not JSON/)
  })

  it('fails for JSON that is not the list of the endpoint', async () => {
    await expect(readJsonAnswer('/api/values', answer('{}', 'application/json'))).rejects.toThrow(/no list of `values`/)
  })
})
