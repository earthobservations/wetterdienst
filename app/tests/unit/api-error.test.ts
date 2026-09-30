import { describe, expect, it } from 'vitest'
import { describeApiError, describeFetchError } from '../../app/utils/api-error'

describe('describeApiError', () => {
  it('passes on the string detail of an error an endpoint raises itself', () => {
    expect(describeApiError({ detail: 'No data available for given constraints' }))
      .toBe('No data available for given constraints')
  })

  it('tells each entry of a validation error by the parameter it is located at', () => {
    // as /api/values answers a station and a name together
    const body = {
      detail: [
        { type: 'mutually_exclusive', loc: ['query', 'station'], msg: 'Cannot be combined with name', input: ['01048'], ctx: { conflicts_with: ['name'] } },
        { type: 'mutually_exclusive', loc: ['query', 'name'], msg: 'Cannot be combined with station', input: 'Hamburg', ctx: { conflicts_with: ['station'] } },
      ],
    }
    expect(describeApiError(body)).toBe('station: Cannot be combined with name; name: Cannot be combined with station')
  })

  it('tells a rule about no parameter in particular by its message alone', () => {
    const body = { detail: [{ type: 'missing_one_of', loc: ['query'], msg: 'Exactly one of station or (latitude and longitude) is required' }] }
    expect(describeApiError(body)).toBe('Exactly one of station or (latitude and longitude) is required')
  })

  it('keeps a key within a parameter', () => {
    const body = { detail: [{ loc: ['query', 'unit_targets', 'temperature'], msg: 'Input should be a valid string' }] }
    expect(describeApiError(body)).toBe('unit_targets.temperature: Input should be a valid string')
  })

  it('returns null for a body without detail', () => {
    expect(describeApiError(null)).toBeNull()
    expect(describeApiError('Internal Server Error')).toBeNull()
    expect(describeApiError({ detail: [] })).toBeNull()
  })
})

describe('describeFetchError', () => {
  const refusal = { detail: [{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }] }

  it('tells the detail of an error answer', () => {
    expect(describeFetchError({ data: refusal, message: '[GET] /api/values: 422' })).toBe('station: Cannot be combined with name')
  })

  it('reads a body that came as text, as it does for a request asked for as text', () => {
    expect(describeFetchError({ data: JSON.stringify(refusal), message: '[GET] /api/values: 422' })).toBe(
      'station: Cannot be combined with name',
    )
  })

  it('tells the status of an answer without a detail, not the request URL', () => {
    // the error's message spells out the whole request, query and all
    const plain = { data: 'Internal Server Error', message: '[GET] "/api/interpolate?provider=dwd&latitude=51": 500 Internal Server Error', statusCode: 500, statusMessage: 'Internal Server Error', response: {} }
    expect(describeFetchError(plain)).toBe('500 Internal Server Error')
  })

  it('tells an answer without a status text by its code alone', () => {
    // HTTP/2 sends no status text, and an empty answer no body: only its response says one came
    const http2 = { data: undefined, message: '[GET] "/api/values?station=01048": 502 ', statusCode: 502, statusMessage: '', response: {} }
    expect(describeFetchError(http2)).toBe('502')
  })

  it('tells a request that got no answer by its message, without the request ofetch puts first', () => {
    // as useFetch holds it: a status of 500 by default, and no status text, as nothing answered
    const unanswered = { data: undefined, message: '[GET] "/api/values?provider=dwd&station=01048": <no response> Failed to fetch', statusCode: 500 }
    expect(describeFetchError(unanswered)).toBe('<no response> Failed to fetch')
  })
})
