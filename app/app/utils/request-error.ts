import { describeApiError } from './api-error'

/**
 * Why a request of a page failed, kept as data and not as the message: a message is written in the
 * language of the moment it was made, and a language switch while it is shown would leave it in the
 * old one. The page translates it when it renders (see {@link describeRequestError}).
 *
 * `text` is words that are not the app's to translate: the REST API's own reason, or a browser's
 * message for a request nothing answered.
 */
export type RequestError
  = | { kind: 'requestFailed' }
    | { kind: 'stationNotFound' }
    | { kind: 'backend', status: number, statusText: string }
    | { kind: 'backendDetail', status: number, detail: string }
    | { kind: 'text', text: string }

/**
 * The failure of a request the backend answered with an error: its reason when its body gives one,
 * its status text when not; any other body, such as a proxy's error page, is left out.
 */
export function backendFailure(status: number, statusText: string, body: unknown): RequestError {
  const detail = describeApiError(body)
  return detail ? { kind: 'backendDetail', status, detail } : { kind: 'backend', status, statusText }
}

/** Write the failure in the language `t` translates to. */
export function describeRequestError(error: RequestError, t: (key: string, named?: Record<string, unknown>) => string): string {
  switch (error.kind) {
    case 'requestFailed':
      return t('common.requestFailed')
    case 'stationNotFound':
      return t('widget.stationNotFound')
    case 'backend':
      // the status text is the server's own, in English, and is not translated
      return [t('common.backendError', { status: error.status }), error.statusText].filter(Boolean).join(' ')
    case 'backendDetail':
      return t('common.backendErrorDetail', { status: error.status, detail: error.detail })
    case 'text':
      return error.text
  }
}
