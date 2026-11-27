import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OPERATOR } from '../../app/utils/operator'
import { privacy as de } from '../../i18n/privacy/de'
import { privacy as en } from '../../i18n/privacy/en'

// The privacy policy is written twice, in German (binding) and in English, outside the eleven interface
// catalogs (i18n/privacy/). These hold the two to each other, and the text to what it must not do.

const texts = { de, en }

// nuxt.config.ts relies on the `defineNuxtConfig` auto-import and imports the tailwind vite plugin: stub both
// so the raw config object can be imported in a plain node environment (as security-headers.test.ts does)
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

function allText(policy: typeof de): string {
  return JSON.stringify(policy)
}

describe('privacy policy texts', () => {
  it('have the same sections in the same order, each with the same parts', () => {
    expect(en.sections.map(s => s.id)).toEqual(de.sections.map(s => s.id))
    for (const [index, section] of de.sections.entries()) {
      const other = en.sections[index]!
      expect(other.icon, section.id).toBe(section.icon)
      expect(other.paragraphs.length, `${section.id} paragraphs`).toBe(section.paragraphs.length)
      expect(other.items?.length, `${section.id} items`).toBe(section.items?.length)
      expect(other.link, `${section.id} link`).toEqual(section.link)
      expect(other.links, `${section.id} links`).toEqual(section.links)
    }
  })

  it('say in the translation, and only there, that the German one binds', () => {
    expect(de.binding).toBeUndefined()
    expect(en.binding).toContain('legally binding')
  })

  it.each(Object.keys(texts))('have no empty string in %s', (code) => {
    const policy = texts[code as keyof typeof texts]
    const strings = [
      policy.title,
      policy.updated,
      policy.intro,
      ...Object.values(policy.controller),
      ...policy.sections.flatMap(s => [s.title, ...s.paragraphs, ...(s.items ?? [])]),
    ]
    expect(strings.filter(s => !s.trim())).toEqual([])
  })

  it.each(Object.keys(texts))('do not repeat the operator\'s address in %s: the page reads it from one place', (code) => {
    const text = allText(texts[code as keyof typeof texts])
    for (const value of [OPERATOR.street, OPERATOR.city, OPERATOR.email, OPERATOR.name])
      expect(text).not.toContain(value)
  })

  it.each(Object.keys(texts))('name every third party that the map and the About page load images from in %s', (code) => {
    const text = allText(texts[code as keyof typeof texts])
    for (const host of ['tile.openstreetmap.org', 'avatars.githubusercontent.com'])
      expect(text, host).toContain(host)
  })

  it.each(Object.keys(texts))('name the cookie and the localStorage keys the app writes in %s', (code) => {
    const text = allText(texts[code as keyof typeof texts])
    for (const key of ['wd_lang', 'wd_settings', 'meteogram.view', 'wd-station-picker', 'wd-place', 'wd-location', 'nuxt-color-mode'])
      expect(text, key).toContain(key)
  })

  it.each(Object.keys(texts))('have a section on the location in %s: purpose, rounding, the legal basis of consent, and storage only on "remember"', (code) => {
    const section = texts[code as keyof typeof texts].sections.find(s => s.id === 'location')!
    const text = section.paragraphs.join(' ')
    expect(section.icon).toBe('i-ph-crosshair')
    expect(text).toContain('1 km')
    expect(text).toContain('wd-location')
    // consent as the legal basis (Art. 6(1)(a) GDPR), and its withdrawal (Art. 7(3) GDPR), in the way each text cites it
    expect(text).toMatch(code === 'de' ? /Art\. 6 Abs\. 1 lit\. a DSGVO/ : /Art\. 6\(1\)\(a\) GDPR/)
    expect(text).toMatch(code === 'de' ? /Art\. 7 Abs\. 3 DSGVO/ : /Art\. 7\(3\) GDPR/)
    // the position is sent with each press, not once; the map's tiles tell OpenStreetMap roughly where the reader is; the
    // browser may use its vendor's service
    expect(text).toMatch(code === 'de' ? /bei jedem Druck/ : /with each press/)
    // (the English text says "once a position has been found" of the box, which is not a claim about how often it is
    // sent: that phrase is taken out, and no other "once" may be left)
    expect(text.replace('once a position has been found', '')).not.toMatch(code === 'de' ? /\beinmal\b/ : /\bonce\b/)
    expect(text).toContain('tile.openstreetmap.org')
    expect(text).toMatch(code === 'de' ? /Standortdienst seines Herstellers/ : /its vendor's location service/)
    // the storage that is set with consent is excepted where the section says the rest is set without it
    const browser = texts[code as keyof typeof texts].sections.find(s => s.id === 'browser')!
    expect(browser.paragraphs[1]).toContain('wd-location')
    expect(browser.paragraphs[1]).toMatch(code === 'de' ? /§ 25 Abs\. 1 TDDDG/ : /Section 25\(1\) TDDDG/)
  })

  it.each(Object.keys(texts))('name the radar in the section on the location in %s: the position is only shown there, not sent to the backend (GH-4287)', (code) => {
    const section = texts[code as keyof typeof texts].sections.find(s => s.id === 'location')!
    const [places, sending, storing] = section.paragraphs
    expect(places).toMatch(code === 'de' ? /auf dem Radar/ : /on the radar/)
    expect(sending).toMatch(code === 'de' ? /Auf dem Radar wird Ihr Standort nur als Markierung angezeigt und die Karte auf ihn zentriert; auch dort werden die Koordinaten nicht an das Backend gesendet/ : /On the radar your position is only shown as a marker and the map centred on it; the coordinates are not sent to the backend there either/)
    // the map's tiles of that section are asked from OpenStreetMap on the radar as on the map
    expect(sending).toMatch(code === 'de' ? /auf der Karte, auf dem Radar oder auf der Starkregen-Seite, lädt Ihr Browser jedoch die Kartenkacheln dieses Ausschnitts von tile\.openstreetmap\.org/ : /on the map, on the radar or on the heavy-rainfall page, however, your browser fetches the map tiles of that area from tile\.openstreetmap\.org/)
    // the section on the third parties says the map's tiles are asked for on the radar too, which the sentence above points to
    const tiles = texts[code as keyof typeof texts].sections.find(s => s.id === 'third-parties')!.items!.find(item => /tile\.openstreetmap\.org/.test(item))!
    expect(tiles).toMatch(code === 'de' ? /die Karte des Radars oder die Karte der Starkregen-Seite/ : /the radar's map or the map of the heavy-rainfall page/)
    // the tick and "Forget" are there as on the map
    expect(storing!.match(code === 'de' ? /auf dem Radar/g : /on the radar/g)).toHaveLength(2)
  })

  it.each(Object.keys(texts))('have a section on the place search in %s: Photon of komoot GmbH, asked by the server from three letters on, not the reader\'s browser or address, 24 hours, and the legal basis (GH-3791)', (code) => {
    const policy = texts[code as keyof typeof texts]
    const section = policy.sections.find(s => s.id === 'places')!
    const text = section.paragraphs.join(' ')
    expect(section.icon).toBe('i-ph-map-pin')
    expect(section.link).toEqual({ label: 'photon.komoot.io', href: 'https://photon.komoot.io' })
    // and komoot's own privacy policy, which says what it does with a request
    expect(section.links).toEqual([{ label: 'komoot.com/privacy', href: 'https://www.komoot.com/privacy' }])
    expect(text).toContain('Photon')
    expect(text).toContain('komoot GmbH')
    expect(text).toContain('OpenStreetMap')
    expect(text).toMatch(code === 'de' ? /Ab drei Buchstaben/ : /From three letters on/)
    // sent each time the reader pauses (0.4 s, the palette's `PLACES_DEBOUNCE_MS`), so that the states on the way to a name are sent too, which it says
    expect(text).toMatch(code === 'de' ? /jedes Mal, wenn Sie beim Tippen kurz innehalten \(0,4 Sekunden\)/ : /each time you pause typing \(0\.4 seconds\)/)
    expect(text).toMatch(code === 'de' ? /Zwischenstände Ihrer Eingabe/ : /Intermediate states of what you type are therefore sent too/)
    // what is never sent: under three letters, and what looks like a position, as `looksLikePosition` has it
    expect(text).toMatch(code === 'de' ? /weniger als drei Buchstaben hat oder wie eine Position aussieht: wenn er eine Dezimalzahl, ein Grad- oder Minutenzeichen, zwei Zahlen, einen einzelnen Buchstaben neben einer Zahl oder ein Wort für Breite oder Länge mit einer Zahl enthält/ : /has fewer than three letters or looks like a position: if it contains a decimal number, a degree or minute sign, two numbers, a single letter next to a number, or a word for latitude or longitude with a number/)
    expect(text).toMatch(code === 'de' ? /vom Server der Web-App – nicht von Ihrem Browser –/ : /by the web app's server, not by your browser/)
    expect(text).toMatch(code === 'de' ? /nicht aber Ihre IP-Adresse/ : /but not your IP address/)
    expect(text).toMatch(code === 'de' ? /keine Cookies, keine Angaben Ihres Browsers, keinen Referer/ : /no cookies, no browser details, no Referer/)
    expect(text).toMatch(code === 'de' ? /24 Stunden/ : /24 hours/)
    expect(text).toMatch(code === 'de' ? /kein Protokoll darüber, wer wonach gefragt hat/ : /keeps no record of who asked for what/)
    expect(text).toMatch(code === 'de' ? /Art\. 6 Abs\. 1 lit\. f DSGVO/ : /Art\. 6\(1\)\(f\) GDPR/)
    // what is typed in the three more fields goes the same way (GH-3791, approved wording): the scope names them
    expect(text).toContain(code === 'de'
      ? 'in die Suche (Strg/⌘ K), in die Stationssuche der Vorhersage, in die Ortssuche von „Frag das Wetter“ und in das Feld „Ort suchen“ des Explorers (Interpolation und Zusammenfassung) eingeben'
      : 'what you type in the search (Ctrl/⌘ K), in the station search of the forecast, in the place search of "Ask the weather" and in the field "Find a place" of the explorer (interpolation and summary) is sent')
    // a place chosen is not sent to Photon again: its position goes to the backend and is in the address of the page
    expect(text).toContain(code === 'de'
      ? 'Ein Ort, den Sie wählen, wird nicht erneut an Photon gesendet: Seine Position (auf vier Nachkommastellen) wird als Koordinaten der Stationsanfrage, die die nächstgelegenen Stationen findet, an das Backend dieses Dienstes gesendet (siehe „Protokolldaten“), und in der Vorhersage, in „Frag das Wetter“ und im Explorer steht sie in der Adresse der Seite (lat, lon, placeName, placeRegion), damit ein Link, den Sie weitergeben, den Ort ohne neue Suche zeigt.'
      : 'A place you choose is not sent to Photon again: its position (to four decimal places) is sent to the backend of this service as the coordinates of the stations request that finds the stations nearest to it (see "Log data"), and in the forecast, in "Ask the weather" and in the explorer it is part of the address of the page (lat, lon, placeName, placeRegion), so that a link you share shows the place without a new search.')
    // the entry of the browser's storage that can hold a town
    const storage = JSON.stringify(policy.sections)
    expect(storage).toContain(code === 'de' ? 'oder ein über seinen Namen gefundener Ort (Name, Position und Region, mit Nummer, Name, Position und Entfernung der nächsten Station)' : 'or a town found by its name (its name, position and region, with the number, name, position and distance of the station nearest to it)')
    expect(storage).toContain('lat, lon, placeName, placeRegion')
    // the sentence about sharing names komoot, which receives the text from the operator's server and not from the reader's browser
    const recipients = policy.sections.find(s => s.id === 'recipients')!.paragraphs.join(' ')
    expect(recipients).toContain('komoot')
    // and says that komoot is no processor of the operator's: the processor is Hetzner
    expect(recipients).toMatch(code === 'de' ? /das kein Auftragsverarbeiter des Betreibers ist, sondern den eingegebenen Text selbst erhält/ : /which is not a processor of the operator but receives the typed text itself/)
    // Photon is asked by the server, so it is no host of the Content Security Policy, and the section on the third parties that the browser asks does not list it
    expect(JSON.stringify(policy.sections.find(s => s.id === 'third-parties'))).not.toContain('komoot')
  })

  it.each(Object.keys(texts))('state no retention period in days in %s: none is configured, only the cookie has a lifetime', (code) => {
    expect(allText(texts[code as keyof typeof texts])).not.toMatch(/\b(?!365\b)\d+\s*(days|Tage)\b/)
  })

  describe('and the hosts the Content Security Policy allows', () => {
    beforeEach(() => {
      vi.stubGlobal('defineNuxtConfig', (config: any) => config)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
      vi.resetModules()
    })

    /** The hosts a policy's sources name: `https://host` and `https://*.host`, without scheme and wildcard */
    function cspHosts(policy: Record<string, string[]>): string[] {
      return [...new Set(Object.values(policy).flat().flatMap((source) => {
        const match = /^https:\/\/(?:\*\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)$/i.exec(source)
        return match ? [match[1]!] : []
      }))].sort()
    }

    /** The hosts the items of the third-parties section write */
    function namedHosts(policy: typeof de): string[] {
      const items = policy.sections.find(section => section.id === 'third-parties')!.items ?? []
      return [...new Set(items.flatMap(item => item.match(/\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b/gi) ?? []))].sort()
    }

    it.each(Object.keys(texts))('are exactly the hosts the third-parties section of %s names, none more, none fewer', async (code) => {
      vi.resetModules()
      const config = (await import('../../nuxt.config')).default as any
      const allowed = cspHosts(config.security.headers.contentSecurityPolicy)

      expect(allowed.length).toBeGreaterThan(0)
      // the text names the host as the policy writes it (a `*.tile.openstreetmap.org` is written `tile.openstreetmap.org`)
      expect(namedHosts(texts[code as keyof typeof texts])).toEqual(allowed)
    })
  })
})
