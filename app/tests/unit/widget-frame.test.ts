import { describe, expect, it } from 'vitest'
import { isWidgetRequest, widgetPolicy } from '../../server/utils/widgetFrame'

// What may frame `/widget`: the request line as the client wrote it is the widget or it is not, however the
// app's router would read it.

describe('isWidgetRequest', () => {
  it.each([
    '/widget',
    '/widget/',
    '/widget?station=10381',
    '/widget/?station=10381&theme=dark',
    '/widget?',
  ])('takes %s for the widget', (url) => {
    expect(isWidgetRequest(url)).toBe(true)
  })

  it.each([
    '/%77idget',
    '/widge%74',
    '/%57idget',
    '/%77idget?station=1',
    '/widget//',
    '/widget/..',
    '/widget/../',
    '/widget/./',
    '/widget%2f',
    '/widgetx',
    '/widget/x',
    '/Widget',
    '/WIDGET',
    '/x/../widget',
    '/./widget',
    '//widget',
    '/meteogram?next=/widget',
    '/meteogram#/widget',
    '/',
    '',
    undefined,
  ])('does not take %s for the widget', (url) => {
    expect(isWidgetRequest(url)).toBe(false)
  })
})

describe('widgetPolicy', () => {
  it('puts any origin in the place of the app\'s own, and leaves every other directive', () => {
    const policy = 'base-uri \'none\'; frame-ancestors \'self\'; img-src \'self\' data:; default-src \'self\''

    expect(widgetPolicy(policy)).toBe('base-uri \'none\'; img-src \'self\' data:; default-src \'self\'; frame-ancestors *')
  })

  it('adds the directive where the policy has none, and says nothing where there is no policy', () => {
    expect(widgetPolicy('default-src \'self\'')).toBe('default-src \'self\'; frame-ancestors *')
    expect(widgetPolicy(undefined)).toBeUndefined()
    expect(widgetPolicy('')).toBeUndefined()
  })
})
