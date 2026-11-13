/**
 * The privacy policy in English: a translation of `de.ts`, which is the legally binding text.
 *
 * Same sections in the same order (tests/nuxt/pages/privacy.test.ts holds the two to it). It is what a
 * reader sees whose language is not German.
 */

import type { PrivacyPolicy } from './de'

export const privacy: PrivacyPolicy = {
  title: 'Privacy policy',
  updated: 'Last updated: 11 November 2026',
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
      icon: 'i-ph-hard-drives',
      title: 'Hosting and processing on behalf of the controller',
      paragraphs: [
        'The service consists of two applications: the backend (REST API and MCP server, https://wetterdienst-backend.eobs.org) and this web app (https://wetterdienst.eobs.org). The web app\'s server forwards requests to /api and /mcp to the backend.',
        'Both run on servers of Hetzner Online GmbH (Industriestr. 25, 91710 Gunzenhausen) in Germany. Hetzner processes data as a processor on behalf of the controller under a data processing agreement (Art. 28 GDPR). The applications are deployed with the self-hosted software Coolify; it is not a third party.',
      ],
    },
    {
      id: 'logs',
      icon: 'i-ph-notebook',
      title: 'Log data',
      paragraphs: [
        'The backend writes one line per request to its container log. It contains the request line with the full URL including the query string, and a timestamp. The query string holds what the request asks for, such as provider, parameters, station IDs and coordinates. The client address shown there is the internal address of the reverse proxy in front of it, not the visitor\'s.',
        'The reverse proxy (Traefik) keeps no access log. The web app\'s server writes next to no logs. Logs are not exported to third parties, and there is no analytics software and no analysis of traffic.',
        'To protect against overload, the web app\'s server counts requests to the data endpoints per client address in memory only, for a short window (five minutes by default). The counters are neither stored nor logged.',
        'No fixed retention period is configured. The size of the container log is capped (at most three files of 10 MB per container); when the cap is reached, the oldest lines are overwritten. How long a line is kept therefore depends on traffic. At the latest, the log is deleted when the container is replaced at the next deployment (for example with every release).',
        'The legal basis is Art. 6(1)(f) GDPR. The legitimate interest is the operation and security of the service.',
      ],
    },
    {
      id: 'browser',
      icon: 'i-ph-cookie',
      title: 'Cookie and local storage in the browser',
      paragraphs: [
        'The web app sets one functional cookie and keeps settings in your browser\'s local storage (localStorage). There are no tracking or advertising cookies. The web app does not pass cookies on to the backend.',
        'The cookie and local storage are necessary for the web app to work (the language, colour scheme and display you choose) and are set without your consent (Section 25(2) no. 2 TDDDG). Where personal data is processed in the process, the legal basis is Art. 6(1)(f) GDPR. The entry localStorage wd-location is the exception: it is set only if you tick "Remember my position in this browser" next to "Use my location", and it is based on your consent (Section 25(1) TDDDG; see "Location").',
      ],
      items: [
        'Cookie wd_lang: stores the language of the interface. Lifetime 365 days, path /, SameSite=Lax.',
        'localStorage wd_settings: your display settings (parameter names, units, the display of the climate stripes and which tools are in the tab bar of the phone layout).',
        'localStorage meteogram.view: whether the meteogram is shown as a chart, in its compact view or as a table. A value stored earlier under meteogram.compact is taken over once and deleted.',
        'localStorage wd-station-picker: whether the station picker in the explorer, the history, the forecast and the climate stripes shows the list or the map (for each tool separately).',
        'localStorage wd-place: the weather station of "Ask the weather" (its number, name, position and region), chosen on the home page or named by a link you opened. The entry itself stays in your browser. The station\'s number and position are in the requests for the answers (see "Log data"), and its number is in the address of the page (place=) once chosen.',
        'localStorage wd-location: only if you tick "Remember my position in this browser" next to "Use my location": your position, rounded to about 1 km (latitude and longitude). Unlike the other entries it is set only with your consent (see "Location"); the entry itself stays in your browser.',
        'localStorage nuxt-color-mode: the colour scheme you chose (light, dark or system).',
      ],
    },
    {
      id: 'location',
      icon: 'i-ph-crosshair',
      title: 'Location ("Use my location")',
      paragraphs: [
        'In several places the web app offers the button "Use my location": in the station picker of the forecast, the explorer, the climate stripes and the station history, on the map, and in "Ask the weather". It is used to find the nearest station and to centre the map on your location. The location is requested only when you press the button, never when a page loads, and your browser also asks for your permission. Without a location, the search by place or station name and the choice on the map work as before.',
        'Your browser determines the position, depending on the browser for example from GPS, Wi-Fi or mobile network data and possibly through its vendor\'s location service; the operator has no influence on this, and the browser vendor\'s privacy policy applies. The web app rounds it in your browser to two decimal places (about 1 km) before it is used any further. In the station picker of the forecast, the explorer and the station history and in "Ask the weather", the rounded coordinates are sent with each press of the button, also for a remembered position, as the coordinates of the stations request, to the backend of this service (see "Log data"). For the climate stripes and on the map, the nearest station is determined in the browser from the station list that has already been loaded; the coordinates are not sent to the backend there. If the map centres on your location, however, your browser fetches the map tiles of that area from tile.openstreetmap.org, so the OpenStreetMap Foundation learns roughly where you are (see "Resources from third parties (map and images)"). Beyond that, the coordinates are not passed on to third parties. The backend does not store them beyond the usual request log and does not link them with other data.',
        'The position stays in the memory of the open page and is forgotten when the page is closed or reloaded. Only if you tick "Remember my position in this browser", which appears under the button (on the map, on the station card) once a position has been found, is the rounded position kept in your browser\'s local storage (localStorage wd-location) and used for a later press of the button without asking again, until you choose "Forget my position" under "Stored" next to the button (on the map, on the station card), or your browser reports the permission as blocked. The nearest station that "Ask the weather" takes as its place from that position is then stored under wd-place too, and deleted together with the position when you choose "Forget my position"; without the tick it applies to the visit only.',
        'The legal basis for processing the position is your consent (Art. 6(1)(a) GDPR), which you give by pressing the button and by allowing it in your browser. Storage in local storage is based on your consent by ticking the box (Section 25(1) TDDDG). You can withdraw your consent at any time with effect for the future (Art. 7(3) GDPR): "Forget my position" under "Stored" next to the button deletes the stored position and the station stored with it, and withdrawing the permission in your browser\'s settings stops your browser from determining your position again; the stored position and the station stored with it are then deleted the next time the web app uses them and your browser reports the permission as blocked (denied). Where your browser does not report this, they stay until you choose "Forget my position". The lawfulness of the processing carried out until then is not affected.',
      ],
    },
    {
      id: 'third-parties',
      icon: 'i-ph-map-trifold',
      title: 'Resources from third parties (map and images)',
      paragraphs: [
        'The web app loads fonts, icons and scripts from its own server. Only in the following cases does your browser request images directly from third parties. They receive your IP address, the time and your browser\'s details as a matter of how the web works, as well as the address of this web app (https://wetterdienst.eobs.org) as the origin of the request (Referer) and, for map tiles, the map section shown. The operator does not learn of this and has no influence on it.',
        'The legal basis is Art. 6(1)(f) GDPR (showing the map and the profile pictures).',
      ],
      items: [
        'Map tiles from tile.openstreetmap.org (OpenStreetMap Foundation), as soon as the map for choosing stations is shown.',
        'The profile pictures on the "About" page from avatars.githubusercontent.com (GitHub).',
      ],
    },
    {
      id: 'links',
      icon: 'i-ph-arrow-square-out',
      title: 'External links',
      paragraphs: [
        'The web app links to pages of third parties, such as GitHub, PyPI and the documentation. Data is transmitted to the respective provider only once you follow such a link; its own privacy policy applies there.',
      ],
    },
    {
      id: 'weather-data',
      icon: 'i-ph-cloud-sun',
      title: 'Weather data from the providers',
      paragraphs: [
        'The backend fetches the weather data from the open-data services of the respective providers (such as the German Weather Service and NOAA). Data of visitors is not passed on in doing so. The backend identifies itself with the User-Agent "wetterdienst/<version> (<operating system>)"; it contains no personal data.',
      ],
    },
    {
      id: 'mcp',
      icon: 'i-ph-robot',
      title: 'Use through Claude (MCP)',
      paragraphs: [
        'When the MCP server is used through Claude, the requests come from Anthropic\'s servers. The operator therefore sees Anthropic\'s address, not that of the end user. The content of the conversation does not reach the operator, only the arguments Claude chooses when it calls a tool (such as provider, parameters and stations). They appear in the log like any other request. Anthropic\'s processing of the conversation is outside the operator\'s influence; Anthropic\'s privacy notices apply to it.',
      ],
    },
    {
      id: 'recipients',
      icon: 'i-ph-share-network',
      title: 'Sharing with third parties',
      paragraphs: [
        'Data is not shared with third parties, except for the processor named above, Hetzner. The providers named under "Resources from third parties" receive data directly from your browser, not from the operator.',
      ],
    },
    {
      id: 'rights',
      icon: 'i-ph-scales',
      title: 'Your rights',
      paragraphs: [
        'Under the GDPR you have the right of access (Art. 15), rectification (Art. 16), erasure (Art. 17), restriction of processing (Art. 18) and objection to processing based on legitimate interests (Art. 21). To exercise them, write to the email address above.',
        'You also have the right to lodge a complaint with a supervisory authority (Art. 77 GDPR). The competent one is the Hamburg Commissioner for Data Protection and Freedom of Information (Der Hamburgische Beauftragte für Datenschutz und Informationsfreiheit, HmbBfDI).',
      ],
      link: { label: 'datenschutz-hamburg.de', href: 'https://datenschutz-hamburg.de' },
    },
  ],
}
