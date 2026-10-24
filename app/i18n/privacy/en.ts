/**
 * The privacy policy in English: a translation of `de.ts`, which is the legally binding text.
 *
 * Same sections in the same order (tests/nuxt/pages/privacy.test.ts holds the two to it). It is what a
 * reader sees whose language is not German.
 */

import type { PrivacyPolicy } from './de'

export const privacy: PrivacyPolicy = {
  title: 'Privacy policy',
  updated: 'Last updated: 24 October 2026',
  binding: 'This is a translation. The German version (Datenschutzerklärung) is the legally binding one.',
  intro: 'This policy describes which personal data is processed when you visit wetterdienst.eobs.org and when you use the REST API and the MCP server of Wetterdienst. There are no user accounts, no registration, no analytics or tracking services and no advertising.',
  controller: {
    title: 'Controller',
    text: 'The controller within the meaning of the General Data Protection Regulation (GDPR) is the operator named in the legal notice (Impressum):',
    addressLabel: 'Address',
    emailLabel: 'Email',
  },
  sections: [
    {
      id: 'hosting',
      icon: 'i-lucide-server',
      title: 'Hosting and processing on behalf of the controller',
      paragraphs: [
        'The service consists of two applications: the backend (REST API and MCP server, https://wetterdienst-backend.eobs.org) and this web app (https://wetterdienst.eobs.org). The web app\'s server forwards requests to /api and /mcp to the backend.',
        'Both run on servers of Hetzner in Germany. Hetzner processes data as a processor on behalf of the controller under a data processing agreement (Art. 28 GDPR). The applications are deployed with the self-hosted software Coolify; it is not a third party.',
      ],
    },
    {
      id: 'logs',
      icon: 'i-lucide-file-clock',
      title: 'Log data',
      paragraphs: [
        'The backend writes one line per request to its container log. It contains the request line with the full URL including the query string, and a timestamp. The query string holds what the request asks for, such as provider, parameters, station IDs and coordinates. The client address shown there is the internal address of the reverse proxy in front of it, not the visitor\'s.',
        'The reverse proxy (Traefik) keeps no access log. The web app\'s server writes next to no logs. Logs are not exported to third parties, and there is no analytics software and no analysis of traffic.',
        'To protect against overload, the web app\'s server counts requests to the data endpoints per client address in memory only, for a short window (five minutes by default). The counters are neither stored nor logged.',
        'No fixed retention period is configured. The container log lasts until the container is replaced at the next deployment (for example with every release). A size cap on the log set by Docker may apply in addition.',
        'The legal basis is Art. 6(1)(f) GDPR. The legitimate interest is the operation and security of the service.',
      ],
    },
    {
      id: 'browser',
      icon: 'i-lucide-cookie',
      title: 'Cookie and local storage in the browser',
      paragraphs: [
        'The web app sets one functional cookie and keeps settings in your browser\'s local storage (localStorage). There are no tracking or advertising cookies. The web app does not pass cookies on to the backend.',
      ],
      items: [
        'Cookie wd_lang: stores the language of the interface. Lifetime 365 days, path /, SameSite=Lax.',
        'localStorage wd_settings: your display settings (parameter names, units and the display of the climate stripes).',
        'localStorage meteogram.compact: whether the meteogram is shown in its compact view.',
        'localStorage nuxt-color-mode: the colour scheme you chose (light, dark or system).',
      ],
    },
    {
      id: 'third-parties',
      icon: 'i-lucide-map',
      title: 'Resources from third parties (map and images)',
      paragraphs: [
        'The web app loads fonts, icons and scripts from its own server. Only in the following cases does your browser request images directly from third parties. They receive your IP address, the time and your browser\'s details as a matter of how the web works, as well as the address of this web app (https://wetterdienst.eobs.org) as the origin of the request (Referer) and, for map tiles, the map section shown. The operator does not learn of this and has no influence on it.',
        'The legal basis is Art. 6(1)(f) GDPR (showing the map and its markers).',
      ],
      items: [
        'Map tiles from tile.openstreetmap.org (OpenStreetMap Foundation), as soon as the map for choosing stations is shown.',
        'The marker icons of the map from cdnjs.cloudflare.com (Cloudflare) and, for selected stations, from raw.githubusercontent.com (GitHub).',
        'The profile pictures on the "About" page from avatars.githubusercontent.com (GitHub).',
      ],
    },
    {
      id: 'links',
      icon: 'i-lucide-external-link',
      title: 'External links',
      paragraphs: [
        'The web app links to pages of third parties, such as GitHub, PyPI and the documentation. Data is transmitted to the respective provider only once you follow such a link; its own privacy policy applies there.',
      ],
    },
    {
      id: 'weather-data',
      icon: 'i-lucide-cloud-sun',
      title: 'Weather data from the providers',
      paragraphs: [
        'The backend fetches the weather data from the open-data services of the respective providers (such as the German Weather Service and NOAA). Data of visitors is not passed on in doing so. The backend identifies itself with the User-Agent "wetterdienst/<version> (<operating system>)"; it contains no personal data.',
      ],
    },
    {
      id: 'mcp',
      icon: 'i-lucide-bot',
      title: 'Use through Claude (MCP)',
      paragraphs: [
        'When the MCP server is used through Claude, the requests come from Anthropic\'s servers. The operator therefore sees Anthropic\'s address, not that of the end user. The content of the conversation does not reach the operator, only the arguments Claude chooses when it calls a tool (such as provider, parameters and stations). They appear in the log like any other request. Anthropic\'s processing of the conversation is outside the operator\'s influence; Anthropic\'s privacy notices apply to it.',
      ],
    },
    {
      id: 'recipients',
      icon: 'i-lucide-share-2',
      title: 'Sharing with third parties',
      paragraphs: [
        'Data is not shared with third parties, except for the processor named above, Hetzner. The providers named under "Resources from third parties" receive data directly from your browser, not from the operator.',
      ],
    },
    {
      id: 'rights',
      icon: 'i-lucide-scale',
      title: 'Your rights',
      paragraphs: [
        'Under the GDPR you have the right of access (Art. 15), rectification (Art. 16), erasure (Art. 17), restriction of processing (Art. 18) and objection to processing based on legitimate interests (Art. 21). To exercise them, write to the email address above.',
        'You also have the right to lodge a complaint with a supervisory authority (Art. 77 GDPR). The competent one is the Hamburg Commissioner for Data Protection and Freedom of Information (Der Hamburgische Beauftragte für Datenschutz und Informationsfreiheit, HmbBfDI).',
      ],
      link: { label: 'datenschutz-hamburg.de', href: 'https://datenschutz-hamburg.de' },
    },
  ],
}
