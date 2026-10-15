import { describe, expect, it } from 'vitest'
import { describeApiError, describeFetchError } from '../../app/utils/api-error'

describe('describeApiError', () => {
  // the problem the backend answers every error with: type, title, status and a detail that is text
  const problem = { type: 'about:blank', title: 'Bad Request', status: 400 }

  it('passes on the string detail of an error an endpoint raises itself', () => {
    expect(describeApiError({ ...problem, detail: 'No data available for given constraints' }))
      .toBe('No data available for given constraints')
  })

  it('tells each entry of a validation error by the parameter it is located at', () => {
    // as /api/values answers a station and a name together
    const body = {
      ...problem,
      status: 422,
      detail: 'station: Cannot be combined with name\nname: Cannot be combined with station',
      errors: [
        { type: 'mutually_exclusive', loc: ['query', 'station'], msg: 'Cannot be combined with name', input: ['01048'], ctx: { conflicts_with: ['name'] } },
        { type: 'mutually_exclusive', loc: ['query', 'name'], msg: 'Cannot be combined with station', input: 'Hamburg', ctx: { conflicts_with: ['station'] } },
      ],
    }
    expect(describeApiError(body)).toBe('station: Cannot be combined with name; name: Cannot be combined with station')
  })

  it('tells a rule about no parameter in particular by its message alone', () => {
    const body = { ...problem, status: 422, detail: 'Exactly one of station or (latitude and longitude) is required', errors: [{ type: 'missing_one_of', loc: ['query'], msg: 'Exactly one of station or (latitude and longitude) is required' }] }
    expect(describeApiError(body)).toBe('Exactly one of station or (latitude and longitude) is required')
  })

  it('keeps a key within a parameter', () => {
    const body = { ...problem, status: 422, detail: 'unit_targets.temperature: Input should be a valid string', errors: [{ loc: ['query', 'unit_targets', 'temperature'], msg: 'Input should be a valid string' }] }
    expect(describeApiError(body)).toBe('unit_targets.temperature: Input should be a valid string')
  })

  it('falls back to the text of detail when the entries are empty', () => {
    expect(describeApiError({ ...problem, status: 422, detail: 'Invalid request', errors: [] })).toBe('Invalid request')
  })

  it('still reads the entries of a backend that answered them as detail, before the problem', () => {
    const body = { detail: [{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }] }
    expect(describeApiError(body)).toBe('station: Cannot be combined with name')
  })

  it('returns null for a body without detail', () => {
    expect(describeApiError(null)).toBeNull()
    expect(describeApiError('Internal Server Error')).toBeNull()
    expect(describeApiError({ detail: [] })).toBeNull()
    expect(describeApiError({ errors: [] })).toBeNull()
  })
})

describe('describeFetchError', () => {
  const refusal = {
    type: 'about:blank',
    title: 'Unprocessable Content',
    status: 422,
    detail: 'station: Cannot be combined with name',
    errors: [{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }],
  }

  it('tells the detail of an error answer', () => {
    expect(describeFetchError({ data: refusal, message: '[GET] /api/values: 422' })).toBe('station: Cannot be combined with name')
  })

  it('reads a body that came as text, as it does for a request asked for as text', () => {
    expect(describeFetchError({ data: JSON.stringify(refusal), message: '[GET] /api/values: 422' })).toBe(
      'station: Cannot be combined with name',
    )
  })

  // the status and a request nothing answered are tested with errors as useFetch holds them, built
  // by h3's createError: tests/nuxt/utils/api-error.test.ts
})
