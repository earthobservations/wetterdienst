import { createError } from 'h3'
import { describe, expect, it } from 'vitest'
import { describeFetchError } from '~/utils/api-error'

// the errors as useFetch holds them: each failure wrapped by h3's createError
describe('describeFetchError with the errors useFetch holds', () => {
  it('does not report a request nothing answered as a 500', () => {
    // createError gives it a status of 500 all the same, with no status text
    const unanswered = createError(new TypeError('[GET] "/api/values?station=01048": <no response> Failed to fetch'))
    expect(unanswered.statusCode).toBe(500)
    expect(describeFetchError(unanswered)).toBe('<no response> Failed to fetch')
  })

  it('tells an error with an empty message by the error itself, never an empty text', () => {
    // h3 makes the message of an error given nothing an empty string
    const empty = createError({})
    expect(describeFetchError(empty)).not.toBe('')
  })

  it('tells an answer without a detail by its status', () => {
    const plain = createError({ statusCode: 502, statusMessage: 'Bad Gateway', message: '[GET] "/api/values?station=01048": 502 Bad Gateway', data: 'Bad Gateway' })
    expect(describeFetchError(plain)).toBe('502 Bad Gateway')
  })
})
