import { describe, expect, it } from 'vitest'
import { ghcnCountryCode, ghcnCountryName } from '../../app/utils/ghcn-country'

// The country a station of NOAA's GHCN daily is in, from the FIPS 10-4 code its id begins with (GH-4078): the title of its stripes names it.

// the 219 codes of `ghcnd-countries.txt` (NOAA NCEI, 2026-11-19)
const FIPS_CODES = `AC AE AF AG AJ AL AM AO AQ AR AS AU AY BA BB BC BD BE BF BG BH BK BL BM BN BO BP BR BU BX BY CA CB CD CE CF
CG CH CI CJ CK CM CO CQ CS CT CU CV CW CY DA DO DR EC EG EI EK EN ER ES ET EU EZ FG FI FJ FK FM FP FR FS GA
GB GG GH GI GL GM GP GQ GR GT GV GY HO HR HU IC ID IN IO IR IS IT IV IZ JA JM JN JO JQ JU KE KG KN KR KS KT
KU KZ LA LE LG LH LI LO LQ LT LU LY MA MB MC MD MF MG MI MJ MK ML MO MP MQ MR MT MU MV MX MY MZ NC NE NF NG
NH NI NL NN NO NP NS NU NZ PA PC PE PK PL PM PO PP PS PU QA RE RI RM RO RP RQ RS RW SA SB SE SF SG SH SI SL
SN SP ST SU SV SW SX SY SZ TD TE TH TI TL TN TO TS TU TV TX TZ UC UG UK UP US UV UY UZ VE VM VQ WA WF WI WQ
WZ ZA ZI`.split(/\s+/)

describe('the country of a station of GHCN daily', () => {
  it('is the ISO code of the FIPS code the id begins with: not the same letters (Australia is AS, Germany GM, Sweden SW)', () => {
    expect(ghcnCountryCode('GM000010147')).toBe('DE')
    expect(ghcnCountryCode('GME00122482')).toBe('DE')
    expect(ghcnCountryCode('USW00094728')).toBe('US')
    expect(ghcnCountryCode('ASN00086282')).toBe('AU')
    expect(ghcnCountryCode('SWE00138000')).toBe('SE')
    expect(ghcnCountryCode('CA001012475')).toBe('CA')
    expect(ghcnCountryCode('BF1BI000002')).toBe('BS')
    expect(ghcnCountryCode('gm000010147')).toBe('DE')
  })

  it('has a country for every code GHCN lists, and each is one the browser names', () => {
    const names = new Intl.DisplayNames('en', { type: 'region', fallback: 'none' })
    expect(FIPS_CODES).toHaveLength(219)
    const without = FIPS_CODES.filter(code => !ghcnCountryCode(`${code}000000000`) || !names.of(ghcnCountryCode(`${code}000000000`)!))
    expect(without).toEqual([])
  })

  it('is no country for a prefix the table has not, or an id that has none', () => {
    expect(ghcnCountryCode('ZZ000000000')).toBeNull()
    expect(ghcnCountryCode('00011')).toBeNull()
    expect(ghcnCountryCode('')).toBeNull()
    expect(ghcnCountryName('ZZ000000000', 'en')).toBeNull()
    expect(ghcnCountryName('', 'en')).toBeNull()
  })

  it('is named in the language asked for, as the browser has the name', () => {
    expect(ghcnCountryName('GM000010147', 'en')).toBe('Germany')
    expect(ghcnCountryName('GM000010147', 'de')).toBe('Deutschland')
    expect(ghcnCountryName('USW00094728', 'de')).toBe('Vereinigte Staaten')
    expect(ghcnCountryName('USW00094728', 'fr')).toBe('États-Unis')
    expect(ghcnCountryName('ASN00086282', 'es')).toBe('Australia')
    expect(ghcnCountryName('SWE00138000', 'pl')).toBe('Szwecja')
    expect(ghcnCountryName('USW00094728', 'cs')).toBe('Spojené státy')
    // Low German takes German's data, Luxembourgish its own or its stand-in
    expect(ghcnCountryName('GM000010147', 'de-hh')).toBe('Deutschland')
    expect(ghcnCountryName('GM000010147', 'lb')).toMatch(/\S/)
  })
})
