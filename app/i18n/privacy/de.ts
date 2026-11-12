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
  updated: 'Stand: 11. November 2026',
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
      icon: 'i-ph-hard-drives',
      title: 'Hosting und Auftragsverarbeitung',
      paragraphs: [
        'Der Dienst besteht aus zwei Anwendungen: dem Backend (REST-API und MCP-Server, https://wetterdienst-backend.eobs.org) und dieser Web-App (https://wetterdienst.eobs.org). Der Server der Web-App leitet Anfragen an /api und /mcp an das Backend weiter.',
        'Beide laufen auf Servern der Hetzner Online GmbH (Industriestr. 25, 91710 Gunzenhausen) in Deutschland. Hetzner verarbeitet Daten als Auftragsverarbeiter im Auftrag des Verantwortlichen auf Grundlage eines Vertrags zur Auftragsverarbeitung (Art. 28 DSGVO). Bereitgestellt werden die Anwendungen mit der selbst betriebenen Software Coolify; sie ist kein Dritter.',
      ],
    },
    {
      id: 'logs',
      icon: 'i-ph-notebook',
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
      icon: 'i-ph-cookie',
      title: 'Cookie und lokaler Speicher im Browser',
      paragraphs: [
        'Die Web-App setzt ein funktionales Cookie und legt Einstellungen im lokalen Speicher (localStorage) Ihres Browsers ab. Es gibt keine Tracking- und keine Werbe-Cookies. Die Web-App leitet Cookies nicht an das Backend weiter.',
        'Cookie und lokaler Speicher sind für die Funktion der Web-App erforderlich (Sprache, Farbschema und Darstellung, die Sie wählen) und werden ohne Ihre Einwilligung gesetzt (§ 25 Abs. 2 Nr. 2 TDDDG). Soweit dabei personenbezogene Daten verarbeitet werden, ist die Rechtsgrundlage Art. 6 Abs. 1 lit. f DSGVO. Ausgenommen ist der Eintrag localStorage wd-location: Er wird nur gesetzt, wenn Sie bei „Meinen Standort verwenden“ das Häkchen „Meinen Standort in diesem Browser merken“ setzen, und beruht auf Ihrer Einwilligung (§ 25 Abs. 1 TDDDG; siehe „Standort“).',
      ],
      items: [
        'Cookie wd_lang: speichert die Sprache der Oberfläche. Laufzeit 365 Tage, Pfad /, SameSite=Lax.',
        'localStorage wd_settings: Ihre Darstellungseinstellungen (Parameterbezeichnungen, Einheiten, die Anzeige der Klimastreifen und welche Werkzeuge in der Leiste der Smartphone-Ansicht stehen).',
        'localStorage meteogram.view: ob das Meteogramm als Diagramm, in der kompakten Ansicht oder als Tabelle gezeigt wird. Ein früher gespeicherter Wert von meteogram.compact wird einmalig übernommen und gelöscht.',
        'localStorage wd-station-picker: ob die Stationsauswahl im Explorer, im Verlauf, in der Vorhersage und bei den Klimastreifen die Liste oder die Karte zeigt (für jedes Werkzeug einzeln).',
        'localStorage wd-place: die Wetterstation von „Frag das Wetter“ (Nummer, Name, Position und Region), auf der Startseite gewählt oder von einem Link genannt, den Sie geöffnet haben. Der Eintrag selbst bleibt in Ihrem Browser. Die Nummer und die Position der Station stehen in den Anfragen für die Antworten (siehe „Protokolldaten“), und ihre Nummer steht, einmal gewählt, in der Adresse der Seite (place=).',
        'localStorage wd-location: nur wenn Sie bei „Meinen Standort verwenden“ das Häkchen „Meinen Standort in diesem Browser merken“ setzen: Ihre auf etwa 1 km gerundete Position (Breiten- und Längengrad). Anders als die übrigen Einträge wird er nur mit Ihrer Einwilligung gesetzt (siehe „Standort“); der Eintrag selbst bleibt in Ihrem Browser.',
        'localStorage nuxt-color-mode: das gewählte Farbschema (hell, dunkel oder System).',
      ],
    },
    {
      id: 'location',
      icon: 'i-ph-crosshair',
      title: 'Standort („Meinen Standort verwenden“)',
      paragraphs: [
        'An mehreren Stellen bietet die Web-App die Schaltfläche „Meinen Standort verwenden“ an: in der Stationsauswahl von Vorhersage, Explorer, Klimastreifen und Stationsverlauf, auf der Karte und bei „Frag das Wetter“. Sie dient dazu, die nächstgelegene Station zu finden und die Karte auf Ihren Standort zu zentrieren. Der Standort wird nur abgefragt, wenn Sie die Schaltfläche drücken, nie beim Laden einer Seite, und Ihr Browser fragt zusätzlich nach Ihrer Erlaubnis. Ohne Standort funktionieren die Suche nach Ort oder Stationsname und die Auswahl auf der Karte wie bisher.',
        'Ihr Browser ermittelt die Position, je nach Browser etwa über GPS, WLAN- oder Mobilfunkdaten und gegebenenfalls über den Standortdienst seines Herstellers; darauf hat der Betreiber keinen Einfluss, und es gilt die Datenschutzerklärung des Browser-Herstellers. Die Web-App rundet sie in Ihrem Browser auf zwei Nachkommastellen (etwa 1 km), bevor sie weiterverwendet wird. In der Stationsauswahl von Vorhersage, Explorer und Stationsverlauf und bei „Frag das Wetter“ werden die gerundeten Koordinaten bei jedem Druck auf die Schaltfläche, auch bei einem gemerkten Standort, als Koordinaten der Stationsabfrage an das Backend dieses Dienstes gesendet (siehe „Protokolldaten“). Bei den Klimastreifen und auf der Karte wird die nächste Station im Browser aus der bereits geladenen Stationsliste bestimmt; die Koordinaten werden dort nicht an das Backend gesendet. Zentriert die Karte auf Ihren Standort, lädt Ihr Browser jedoch die Kartenkacheln dieses Ausschnitts von tile.openstreetmap.org; die OpenStreetMap Foundation erfährt dadurch ungefähr, wo Sie sich befinden (siehe „Ressourcen von Dritten (Karte und Bilder)“). Darüber hinaus werden die Koordinaten nicht an Dritte weitergegeben. Das Backend speichert sie nicht über das übliche Anfrageprotokoll hinaus und verknüpft sie nicht mit anderen Daten.',
        'Die Position bleibt im Arbeitsspeicher der geöffneten Seite und ist nach dem Schließen oder Neuladen der Seite vergessen. Nur wenn Sie das Kästchen „Meinen Standort in diesem Browser merken“ ankreuzen, das unter der Schaltfläche (auf der Karte auf der Stationskarte) erscheint, sobald ein Standort ermittelt wurde, wird die gerundete Position im lokalen Speicher Ihres Browsers abgelegt (localStorage wd-location) und bei einem späteren Druck auf die Schaltfläche ohne erneute Abfrage verwendet, bis Sie unter „Gespeichert“ neben der Schaltfläche (auf der Karte auf der Stationskarte) „Meinen Standort vergessen“ wählen. Die nächste Station, die „Frag das Wetter“ aus dieser Position als Ort wählt, wird dann ebenfalls unter wd-place gespeichert und zusammen mit der Position gelöscht, wenn Sie „Meinen Standort vergessen“ wählen; ohne das Häkchen gilt sie nur für den Besuch.',
        'Rechtsgrundlage der Verarbeitung der Position ist Ihre Einwilligung (Art. 6 Abs. 1 lit. a DSGVO), die Sie durch das Drücken der Schaltfläche und die Freigabe in Ihrem Browser erteilen. Die Speicherung im lokalen Speicher beruht auf Ihrer Einwilligung durch das Setzen des Häkchens (§ 25 Abs. 1 TDDDG). Sie können die Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen (Art. 7 Abs. 3 DSGVO): „Meinen Standort vergessen“ unter „Gespeichert“ neben der Schaltfläche löscht die gespeicherte Position und die mit ihr gespeicherte Station, und wenn Sie die Freigabe in den Einstellungen Ihres Browsers zurücknehmen, ermittelt Ihr Browser Ihren Standort nicht mehr. Die Rechtmäßigkeit der bis dahin erfolgten Verarbeitung bleibt unberührt.',
      ],
    },
    {
      id: 'third-parties',
      icon: 'i-ph-map-trifold',
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
      icon: 'i-ph-arrow-square-out',
      title: 'Externe Links',
      paragraphs: [
        'Die Web-App verweist auf Seiten Dritter, etwa GitHub, PyPI und die Dokumentation. Erst wenn Sie einem solchen Link folgen, werden Daten an den jeweiligen Anbieter übertragen; dort gilt dessen Datenschutzerklärung.',
      ],
    },
    {
      id: 'weather-data',
      icon: 'i-ph-cloud-sun',
      title: 'Wetterdaten der Anbieter',
      paragraphs: [
        'Das Backend ruft die Wetterdaten bei den offenen Datendiensten der jeweiligen Anbieter ab (etwa Deutscher Wetterdienst und NOAA). Daten der Besucherinnen und Besucher werden dabei nicht weitergegeben. Das Backend meldet sich mit dem User-Agent „wetterdienst/<Version> (<Betriebssystem>)“; er enthält keine personenbezogenen Angaben.',
      ],
    },
    {
      id: 'mcp',
      icon: 'i-ph-robot',
      title: 'Nutzung über Claude (MCP)',
      paragraphs: [
        'Wird der MCP-Server über Claude genutzt, kommen die Anfragen von den Servern von Anthropic. Der Betreiber sieht daher die Adresse von Anthropic, nicht die der Endnutzerin oder des Endnutzers. Der Inhalt der Unterhaltung erreicht den Betreiber nicht, nur die Argumente, die Claude für den Aufruf eines Werkzeugs wählt (etwa Anbieter, Parameter und Stationen). Sie stehen im Protokoll wie jede andere Anfrage. Die Verarbeitung der Unterhaltung durch Anthropic liegt außerhalb des Einflusses des Betreibers; dafür gelten die Datenschutzhinweise von Anthropic.',
      ],
    },
    {
      id: 'recipients',
      icon: 'i-ph-share-network',
      title: 'Weitergabe an Dritte',
      paragraphs: [
        'Eine Weitergabe von Daten an Dritte findet nicht statt, mit Ausnahme des oben genannten Auftragsverarbeiters Hetzner. Die im Abschnitt „Ressourcen von Dritten“ genannten Anbieter erhalten Daten unmittelbar von Ihrem Browser, nicht vom Betreiber.',
      ],
    },
    {
      id: 'rights',
      icon: 'i-ph-scales',
      title: 'Ihre Rechte',
      paragraphs: [
        'Sie haben nach der DSGVO das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung der Verarbeitung (Art. 18) und Widerspruch gegen die Verarbeitung auf Grundlage berechtigter Interessen (Art. 21). Wenden Sie sich dazu an die oben genannte E-Mail-Adresse.',
        'Sie haben außerdem das Recht, sich bei einer Aufsichtsbehörde zu beschweren (Art. 77 DSGVO). Zuständig ist der Hamburgische Beauftragte für Datenschutz und Informationsfreiheit (HmbBfDI).',
      ],
      link: { label: 'datenschutz-hamburg.de', href: 'https://datenschutz-hamburg.de' },
    },
  ],
}
