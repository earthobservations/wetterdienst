// The works the methods of "Ask the weather" rest on (GH-3764, step 1c): each is one entry of the list of works cited at
// the end of the page of the methods (`/methods#work-wmo-1203`), and the definitions of the chips (`chips/*.ts`) cite them
// by the id given here and the place in the work (`Citation`). Only what is language-independent is here: the short name
// and the formal citation, whose titles stay in the language of the work. What the work is, who issues it and why it counts,
// in plain words, is in the texts of the page (`i18n/methods/`), in German and English.
//
// A work is cited only where the document itself was read for it: the WMO publications from the official PDFs (the
// Guide to Instruments and Methods of Observation, Volume I, 2024 edition; the Guidelines on the Calculation of Climate
// Normals, 2017, as NOAA NCEI mirrors it), the DWD pages and files on the day they were read (21 November 2026).

export interface Work {
  /** How a link names it: the issuer and the year, short */
  short: string
  /** The formal citation: issuer, year, title, publication number, edition */
  citation: string
  /** Where the work is found: the issuer's page for it */
  href: string
  /** Who issues it, to group and to say in plain words which kind of source it is */
  issuer: 'wmo' | 'dwd'
}

export const WORKS = {
  'wmo-8-i': {
    short: 'WMO-No. 8 (2024), Vol. I',
    citation: 'WMO (2024). Guide to Instruments and Methods of Observation (WMO-No. 8), Volume I – Measurement of Meteorological Variables, 2024 edition. Geneva: World Meteorological Organization.',
    href: 'https://library.wmo.int/records/item/68695-guide-to-instruments-and-methods-of-observation',
    issuer: 'wmo',
  },
  'wmo-1203': {
    short: 'WMO-No. 1203 (2017)',
    citation: 'WMO (2017). WMO Guidelines on the Calculation of Climate Normals (WMO-No. 1203), 2017 edition. Geneva: World Meteorological Organization.',
    href: 'https://library.wmo.int/records/item/55797-wmo-guidelines-on-the-calculation-of-climate-normals',
    issuer: 'wmo',
  },
  'dwd-seasons': {
    short: 'DWD Wetterlexikon: Jahreszeiten',
    citation: 'Deutscher Wetterdienst. Wetterlexikon, Glossar, entry „Jahreszeiten“. dwd.de/DE/service/lexikon, read on 21 November 2026.',
    href: 'https://www.dwd.de/DE/service/lexikon/Functions/glossar.html?lv3=101324&lv2=101304',
    issuer: 'dwd',
  },
  'dwd-summer': {
    short: 'DWD (2018): Sommerbeginn',
    citation: 'Deutscher Wetterdienst (2018). Thema des Tages, 20 June 2018: „Sommerbeginn – astronomisch, meteorologisch und phänologisch?“. Read on 21 November 2026.',
    href: 'https://www.dwd.de/DE/wetter/thema_des_tages/2018/6/20.html',
    issuer: 'dwd',
  },
  'dwd-monthly-kl': {
    short: 'DWD monthly station observations',
    citation: 'Deutscher Wetterdienst (2024). Monthly station observations (temperature, precipitation, sunshine duration, wind and cloud cover) for Germany, Version v24.03, dataset description (DESCRIPTION_obsgermany-climate-monthly-kl_en.pdf), section "Data origin".',
    href: 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/kl/DESCRIPTION_obsgermany-climate-monthly-kl_en.pdf',
    issuer: 'dwd',
  },
  'dwd-daily-kl': {
    short: 'DWD daily station observations',
    citation: 'Deutscher Wetterdienst (2024). Daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany, Version v24.3, dataset description (DESCRIPTION_obsgermany-climate-daily-kl_en.pdf), parameters FX, FM, SDK, RSK, TMK, TXK, TNK and SHK_TAG.',
    href: 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/DESCRIPTION_obsgermany-climate-daily-kl_en.pdf',
    issuer: 'dwd',
  },
  'dwd-daily-more-precip': {
    short: 'DWD daily precipitation observations',
    citation: 'Deutscher Wetterdienst (2024). Daily precipitation observations for Germany, Version v24.3, dataset description (DESCRIPTION_obsgermany-climate-daily-more_precip_en.pdf), parameters SH_TAG and NSH_TAG.',
    href: 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/DESCRIPTION_obsgermany-climate-daily-more_precip_en.pdf',
    issuer: 'dwd',
  },
  'dwd-kenntage': {
    short: 'DWD (2025): Kenntage des Sommers',
    citation: 'Deutscher Wetterdienst (2025). Thema des Tages, 13 August 2025: „Sommerlich, heiß, sehr heiß? – ‚Kenntage‘ des Sommers 2025“, which defines the Sommertag, the Heiße Tag, the Frosttag and the Eistag. Read on 22 November 2026.',
    href: 'https://www.dwd.de/DE/wetter/thema_des_tages/2025/8/13.html',
    issuer: 'dwd',
  },
  'dwd-tropennacht': {
    short: 'DWD Wetterlexikon: Tropennacht',
    citation: 'Deutscher Wetterdienst. Wetterlexikon, Glossar, entry „Tropennacht“. dwd.de/DE/service/lexikon, read on 22 November 2026.',
    href: 'https://www.dwd.de/DE/service/lexikon/Functions/glossar.html?lv2=102672&lv3=102802',
    issuer: 'dwd',
  },
  'dwd-warnings': {
    short: 'DWD Warnkriterien',
    citation: 'Deutscher Wetterdienst. Warnungen aktuell: Warnkriterien (wind criteria, in about 10 m above open ground). dwd.de/DE/wetter/warnungen_aktuell/kriterien/warnkriterien.html, read on 21 November 2026.',
    href: 'https://www.dwd.de/DE/wetter/warnungen_aktuell/kriterien/warnkriterien.html',
    issuer: 'dwd',
  },
  'dwd-mosmix': {
    short: 'DWD MOSMIX',
    citation: 'Deutscher Wetterdienst. Model Output Statistics-MIX (MOSMIX). dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html, read on 21 November 2026.',
    href: 'https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html',
    issuer: 'dwd',
  },
  'dwd-mosmix-elements': {
    short: 'DWD MOSMIX elements',
    citation: 'Deutscher Wetterdienst. MOSMIX: Aufschlüsselung der meteorologischen Elemente nach MOSMIX_L und MOSMIX_S (mosmix_elemente.xlsx, list of 2018), elements R101, RR1c, RR6c, RRhc and RRdc, read on 21 November 2026.',
    href: 'https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_xls.html',
    issuer: 'dwd',
  },
} as const satisfies Record<string, Work>

export type WorkId = keyof typeof WORKS

/** The ids of the works, in the order of the list of works cited */
export const WORK_IDS = Object.keys(WORKS) as WorkId[]

/** Whether a string is the id of a work */
export function isWork(value: unknown): value is WorkId {
  return typeof value === 'string' && Object.hasOwn(WORKS, value)
}

/** The anchor of a work on the page of the methods (`#work-wmo-1203`) */
export function workAnchor(id: WorkId): string {
  return `work-${id}`
}
