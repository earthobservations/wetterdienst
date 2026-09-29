import { describe, expect, it } from 'vitest'
import { describeApiError } from '../../app/utils/api-error'

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
