import { describe, expect, it } from 'vitest'
import { backendFailure, describeRequestError } from '../../app/utils/request-error'

// a translation that shows which message it was asked for, with its named values
const t = (key: string, named?: Record<string, unknown>) => `${key}${named ? JSON.stringify(named) : ''}`

describe('backendFailure', () => {
  it('keeps the backend\'s reason where its body gives one', () => {
    expect(backendFailure(422, 'Unprocessable Entity', { detail: 'Unknown station' })).toEqual({ kind: 'backendDetail', status: 422, detail: 'Unknown station' })
  })

  it('keeps the status text where the body gives none, and leaves any other body out', () => {
    expect(backendFailure(502, 'Bad Gateway', null)).toEqual({ kind: 'backend', status: 502, statusText: 'Bad Gateway' })
    expect(backendFailure(502, 'Bad Gateway', '<html>proxy page</html>')).toEqual({ kind: 'backend', status: 502, statusText: 'Bad Gateway' })
  })
})

describe('describeRequestError', () => {
  it.each([
    [{ kind: 'requestFailed' }, 'common.requestFailed'],
    [{ kind: 'stationNotFound' }, 'widget.stationNotFound'],
    [{ kind: 'backend', status: 502, statusText: 'Bad Gateway' }, 'common.backendError{"status":502} Bad Gateway'],
    [{ kind: 'backend', status: 502, statusText: '' }, 'common.backendError{"status":502}'],
    [{ kind: 'backendDetail', status: 422, detail: 'Unknown station' }, 'common.backendErrorDetail{"status":422,"detail":"Unknown station"}'],
    [{ kind: 'text', text: 'Failed to fetch' }, 'Failed to fetch'],
  ] as const)('writes %j through the translation', (error, expected) => {
    expect(describeRequestError(error, t)).toBe(expected)
  })
})
