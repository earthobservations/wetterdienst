// Google Search Console proves that a site is ours with a file at its root, `/google<hex>.html`, whose one line is
// `google-site-verification: google<hex>.html` (GH-4108). The name is the token of the person who verifies, so it is
// a setting of the instance (`NUXT_GOOGLE_SITE_VERIFICATION`, the private runtime config key `googleSiteVerification`)
// and not a file of `public/`, which every build and every self-hosted instance would serve as its own.

export const GOOGLE_SITE_VERIFICATION_ENV = 'NUXT_GOOGLE_SITE_VERIFICATION'

const NAME = /^google[0-9a-f]+$/

/**
 * The name to answer for, from the setting: `google` and lower-case hex, as Google gives it, with or without the
 * `.html` it ends in. Empty for a setting that is not set, and for one that is not a name, which is never answered
 * for (the path would be whatever an operator typed).
 */
export function verificationName(configured: unknown): string {
  const value = typeof configured === 'string' ? configured.trim().replace(/\.html$/, '') : ''
  return NAME.test(value) ? value : ''
}

/** The line to log at server start if the setting is set and is no name, otherwise `undefined`. It never names the value. */
export function verificationWarning(configured: unknown): string | undefined {
  if (typeof configured !== 'string' || !configured.trim() || verificationName(configured))
    return undefined
  return `${GOOGLE_SITE_VERIFICATION_ENV} is ignored: it is not a name of the form google<hex> that Google Search Console gives, such as google54ae9a07758f51bd.`
}

/** The path of the file, and its one line (Google's own download has no line break after it). */
export function verificationFile(name: string): { path: string, body: string } {
  return { path: `/${name}.html`, body: `google-site-verification: ${name}.html` }
}
