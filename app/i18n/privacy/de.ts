/**
 * The privacy policy (Datenschutzerklärung), in German: the text that is legally binding.
 *
 * It is not in `locales/*.json`, whose eleven catalogs are held to the same keys and are translated by
 * the project's contributors: a legal text is written once in German and once in English by the
 * operator, who answers for both, and reaches the other nine languages as the English one. `en.ts` has
 * the same shape (it is typed by `PrivacyPolicy`), and tests/nuxt/pages/privacy.test.ts holds the two
 * to the same sections.
 *
 * Every statement is one the code or the production deployment shows. Change the text when either
 * changes: a new third party a page loads from, a log, a cookie, a processor.
 */

export interface PrivacySection {
  /** Anchor of the section, the same in both languages */
  id: string
  icon: string
  title: string
  paragraphs: string[]
  /** A list after the paragraphs */
  items?: string[]
  /** One link after the list */
  link?: { label: string, href: string }
}

export interface PrivacyPolicy {
  title: string
  /** Set under the title: the date the text was last revised */
  updated: string
  /** Set under the title in a language that is not the legally binding one */
  binding?: string
  intro: string
  /** The controller (Art. 4 (7) GDPR) is the operator of the Impressum; its details are not repeated here */
  controller: { title: string, text: string, addressLabel: string, emailLabel: string }
  sections: PrivacySection[]
}

export const privacy: PrivacyPolicy = {
  title: 'Datenschutzerklärung',
  updated: 'Stand: 25. Oktober 2026',
  intro: 'Diese Erklärung beschreibt, welche personenbezogenen Daten beim Besuch von wetterdienst.eobs.org und bei der Nutzung der REST-API und des MCP-Servers von Wetterdienst verarbeitet werden. Es gibt keine Benutzerkonten, keine Registrierung, keine Analyse- oder Tracking-Dienste und keine Werbung.',
  controller: {
    title: 'Verantwortlicher',
    text: 'Verantwortlicher im Sinne der Datenschutz-Grundverordnung (DSGVO) ist der im Impressum genannte Betreiber:',
    addressLabel: 'Anschrift',
    emailLabel: 'E-Mail',
  },
  sections: [
    {
      id: 'hosting',
      icon: 'i-lucide-server',
      title: 'Hosting und Auftragsverarbeitung',
      paragraphs: [
        'Der Dienst besteht aus zwei Anwendungen: dem Backend (REST-API und MCP-Server, https://wetterdienst-backend.eobs.org) und dieser Web-App (https://wetterdienst.eobs.org). Der Server der Web-App leitet Anfragen an /api und /mcp an das Backend weiter.',
        'Beide laufen auf Servern der Hetzner Online GmbH (Industriestr. 25, 91710 Gunzenhausen) in Deutschland. Hetzner verarbeitet Daten als Auftragsverarbeiter im Auftrag des Verantwortlichen auf Grundlage eines Vertrags zur Auftragsverarbeitung (Art. 28 DSGVO). Bereitgestellt werden die Anwendungen mit der selbst betriebenen Software Coolify; sie ist kein Dritter.',
      ],
    },
    {
      id: 'logs',
      icon: 'i-lucide-file-clock',
      title: 'Protokolldaten (Logs)',
      paragraphs: [
        'Das Backend schreibt für jede Anfrage eine Zeile in sein Container-Protokoll. Sie enthält die Anfragezeile mit der vollständigen URL einschließlich Query-String und einen Zeitstempel. Im Query-String stehen die Angaben der Abfrage, etwa Anbieter, Parameter, Stationskennungen und Koordinaten. Die dort angezeigte Client-Adresse ist die interne Adresse des vorgeschalteten Reverse-Proxys, nicht die des Besuchers.',
        'Der Reverse-Proxy (Traefik) führt kein Zugriffsprotokoll. Der Server der Web-App schreibt praktisch keine Protokolle. Es gibt keinen Log-Export an Dritte, keine Analyse-Software und keine Auswertung des Datenverkehrs.',
        'Zum Schutz vor Überlastung zählt der Server der Web-App die Anfragen an die Daten-Schnittstellen je Client-Adresse ausschließlich im Arbeitsspeicher, für ein kurzes Zeitfenster (standardmäßig fünf Minuten). Die Zähler werden nicht gespeichert und nicht protokolliert.',
        'Eine feste Speicherdauer ist nicht eingestellt. Die Größe des Container-Protokolls ist begrenzt (höchstens drei Dateien zu je 10 MB je Container); ist die Grenze erreicht, werden die ältesten Zeilen überschrieben. Wie lange eine Zeile erhalten bleibt, hängt daher vom Datenverkehr ab. Spätestens wird das Protokoll gelöscht, wenn der Container bei der nächsten Bereitstellung ersetzt wird (etwa bei jedem Release).',
        'Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO. Das berechtigte Interesse liegt im Betrieb und in der Sicherheit des Dienstes.',
      ],
    },
    {
      id: 'browser',
      icon: 'i-lucide-cookie',
      title: 'Cookie und lokaler Speicher im Browser',
      paragraphs: [
        'Die Web-App setzt ein funktionales Cookie und legt Einstellungen im lokalen Speicher (localStorage) Ihres Browsers ab. Es gibt keine Tracking- und keine Werbe-Cookies. Die Web-App leitet Cookies nicht an das Backend weiter.',
        'Cookie und lokaler Speicher sind für die Funktion der Web-App erforderlich (Sprache, Farbschema und Darstellung, die Sie wählen) und werden ohne Ihre Einwilligung gesetzt (§ 25 Abs. 2 Nr. 2 TDDDG). Soweit dabei personenbezogene Daten verarbeitet werden, ist die Rechtsgrundlage Art. 6 Abs. 1 lit. f DSGVO.',
      ],
      items: [
        'Cookie wd_lang: speichert die Sprache der Oberfläche. Laufzeit 365 Tage, Pfad /, SameSite=Lax.',
        'localStorage wd_settings: Ihre Darstellungseinstellungen (Parameterbezeichnungen, Einheiten und die Anzeige der Klimastreifen).',
        'localStorage meteogram.compact: ob das Meteogramm in der kompakten Ansicht gezeigt wird.',
        'localStorage nuxt-color-mode: das gewählte Farbschema (hell, dunkel oder System).',
      ],
    },
    {
      id: 'third-parties',
      icon: 'i-lucide-map',
      title: 'Ressourcen von Dritten (Karte und Bilder)',
      paragraphs: [
        'Die Web-App lädt Schriften, Symbole und Skripte von ihrem eigenen Server. Nur in den folgenden Fällen fordert Ihr Browser Bilder direkt bei Dritten an. Diese erhalten dabei technisch bedingt Ihre IP-Adresse, den Zeitpunkt und die Angaben Ihres Browsers; außerdem die Adresse dieser Web-App (https://wetterdienst.eobs.org) als Herkunft der Anfrage (Referer) und, bei Kartenkacheln, den angezeigten Kartenausschnitt. Der Betreiber erfährt davon nichts und hat keinen Einfluss darauf.',
        'Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO (Darstellung der Karte und der Profilbilder).',
      ],
      items: [
        'Kartenkacheln von tile.openstreetmap.org (OpenStreetMap Foundation), sobald die Karte zur Auswahl von Stationen angezeigt wird.',
        'Die Profilbilder auf der Seite „Über uns“ von avatars.githubusercontent.com (GitHub).',
      ],
    },
    {
      id: 'links',
      icon: 'i-lucide-external-link',
      title: 'Externe Links',
      paragraphs: [
        'Die Web-App verweist auf Seiten Dritter, etwa GitHub, PyPI und die Dokumentation. Erst wenn Sie einem solchen Link folgen, werden Daten an den jeweiligen Anbieter übertragen; dort gilt dessen Datenschutzerklärung.',
      ],
    },
    {
      id: 'weather-data',
      icon: 'i-lucide-cloud-sun',
      title: 'Wetterdaten der Anbieter',
      paragraphs: [
        'Das Backend ruft die Wetterdaten bei den offenen Datendiensten der jeweiligen Anbieter ab (etwa Deutscher Wetterdienst und NOAA). Daten der Besucherinnen und Besucher werden dabei nicht weitergegeben. Das Backend meldet sich mit dem User-Agent „wetterdienst/<Version> (<Betriebssystem>)“; er enthält keine personenbezogenen Angaben.',
      ],
    },
    {
      id: 'mcp',
      icon: 'i-lucide-bot',
      title: 'Nutzung über Claude (MCP)',
      paragraphs: [
        'Wird der MCP-Server über Claude genutzt, kommen die Anfragen von den Servern von Anthropic. Der Betreiber sieht daher die Adresse von Anthropic, nicht die der Endnutzerin oder des Endnutzers. Der Inhalt der Unterhaltung erreicht den Betreiber nicht, nur die Argumente, die Claude für den Aufruf eines Werkzeugs wählt (etwa Anbieter, Parameter und Stationen). Sie stehen im Protokoll wie jede andere Anfrage. Die Verarbeitung der Unterhaltung durch Anthropic liegt außerhalb des Einflusses des Betreibers; dafür gelten die Datenschutzhinweise von Anthropic.',
      ],
    },
    {
      id: 'recipients',
      icon: 'i-lucide-share-2',
      title: 'Weitergabe an Dritte',
      paragraphs: [
        'Eine Weitergabe von Daten an Dritte findet nicht statt, mit Ausnahme des oben genannten Auftragsverarbeiters Hetzner. Die im Abschnitt „Ressourcen von Dritten“ genannten Anbieter erhalten Daten unmittelbar von Ihrem Browser, nicht vom Betreiber.',
      ],
    },
    {
      id: 'rights',
      icon: 'i-lucide-scale',
      title: 'Ihre Rechte',
      paragraphs: [
        'Sie haben nach der DSGVO das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung der Verarbeitung (Art. 18) und Widerspruch gegen die Verarbeitung auf Grundlage berechtigter Interessen (Art. 21). Wenden Sie sich dazu an die oben genannte E-Mail-Adresse.',
        'Sie haben außerdem das Recht, sich bei einer Aufsichtsbehörde zu beschweren (Art. 77 DSGVO). Zuständig ist der Hamburgische Beauftragte für Datenschutz und Informationsfreiheit (HmbBfDI).',
      ],
      link: { label: 'datenschutz-hamburg.de', href: 'https://datenschutz-hamburg.de' },
    },
  ],
}
