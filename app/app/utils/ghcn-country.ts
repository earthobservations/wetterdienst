import { withData } from './format'

/**
 * The country of a station of NOAA's GHCN daily (GH-4078): the first two letters of its id are the country's FIPS 10-4 code (`GM`
 * Germany, `US` the United States, `AS` Australia, `SW` Sweden: not the ISO ones), as `ghcnd-countries.txt` lists them. They are
 * taken to the ISO 3166-1 alpha-2 code, from which the browser's own `Intl.DisplayNames` names the country in the language of the page,
 * so the app carries no country names of its own.
 *
 * A territory is the ISO code it has (Puerto Rico `PR`, Greenland `GL`, Svalbard and Jan Mayen `SJ`, the small US islands `UM`, the
 * French Southern Territories `TF`), as GHCN lists it by itself and not under the country it belongs to. A prefix the table has not (one
 * GHCN adds, or a station whose id is not GHCN's) is no country: the title is written without one.
 */
const FIPS_TO_ISO: Record<string, string> = Object.fromEntries(`
AC=AG AE=AE AF=AF AG=DZ AJ=AZ AL=AL AM=AM AO=AO AQ=AS AR=AR AS=AU AU=AT AY=AQ BA=BH BB=BB BC=BW BD=BM BE=BE BF=BS
BG=BD BH=BZ BK=BA BL=BO BM=MM BN=BJ BO=BY BP=SB BR=BR BU=BG BX=BN BY=BI CA=CA CB=KH CD=TD CE=LK CF=CG CG=CD CH=CN
CI=CL CJ=KY CK=CC CM=CM CO=CO CQ=MP CS=CR CT=CF CU=CU CV=CV CW=CK CY=CY DA=DK DO=DM DR=DO EC=EC EG=EG EI=IE EK=GQ
EN=EE ER=ER ES=SV ET=ET EU=TF EZ=CZ FG=GF FI=FI FJ=FJ FK=FK FM=FM FP=PF FR=FR FS=TF GA=GM GB=GA GG=GE GH=GH GI=GI
GL=GL GM=DE GP=GP GQ=GU GR=GR GT=GT GV=GN GY=GY HO=HN HR=HR HU=HU IC=IS ID=ID IN=IN IO=IO IR=IR IS=IL IT=IT IV=CI
IZ=IQ JA=JP JM=JM JN=SJ JO=JO JQ=UM JU=TF KE=KE KG=KG KN=KP KR=KI KS=KR KT=CX KU=KW KZ=KZ LA=LA LE=LB LG=LV LH=LT
LI=LR LO=SK LQ=UM LT=LS LU=LU LY=LY MA=MG MB=MQ MC=MO MD=MD MF=YT MG=MN MI=MW MJ=ME MK=MK ML=ML MO=MA MP=MU MQ=UM
MR=MR MT=MT MU=OM MV=MV MX=MX MY=MY MZ=MZ NC=NC NE=NU NF=NF NG=NE NH=VU NI=NG NL=NL NN=SX NO=NO NP=NP NS=SR NU=NI
NZ=NZ PA=PY PC=PN PE=PE PK=PK PL=PL PM=PA PO=PT PP=PG PS=PW PU=GW QA=QA RE=RE RI=RS RM=MH RO=RO RP=PH RQ=PR RS=RU
RW=RW SA=SA SB=PM SE=SC SF=ZA SG=SN SH=SH SI=SI SL=SL SN=SG SP=ES ST=LC SU=SD SV=SJ SW=SE SX=GS SY=SY SZ=CH TD=TT
TH=TH TI=TJ TL=TK TN=TO TO=TG TE=TF TS=TN TU=TR TV=TV TX=TM TZ=TZ UC=CW UG=UG UK=GB UP=UA US=US UV=BF UY=UY UZ=UZ
VE=VE VM=VN VQ=VI WA=NA WF=WF WI=EH WQ=UM WZ=SZ ZA=ZM ZI=ZW
`.split(/\s+/).map(pair => pair.split('=') as [string, string]))

/**
 * The ISO 3166-1 alpha-2 code of the country of a station of GHCN daily, from the FIPS code its id begins with, or null where the id
 * has none the table knows.
 *
 * @example
 * ghcnCountryCode('GM000010147') // 'DE'
 * ghcnCountryCode('USW00094728') // 'US'
 * ghcnCountryCode('ZZ000000000') // null
 */
export function ghcnCountryCode(stationId: string): string | null {
  return FIPS_TO_ISO[stationId.slice(0, 2).toUpperCase()] ?? null
}

/**
 * The name of the country of a station of GHCN daily in a language of the app, as the browser has it (`Intl.DisplayNames`, from the
 * language's own data, `withData`), or null where the station has no country the table knows or the browser has no name for it.
 *
 * @example
 * ghcnCountryName('GM000010147', 'fr') // 'Allemagne'
 * ghcnCountryName('USW00094728', 'de') // 'Vereinigte Staaten'
 */
export function ghcnCountryName(stationId: string, locale: string): string | null {
  const code = ghcnCountryCode(stationId)
  if (!code)
    return null
  try {
    const name = new Intl.DisplayNames(withData(locale, Intl.DisplayNames.supportedLocalesOf), { type: 'region', fallback: 'none' }).of(code)
    return name ?? null
  }
  catch {
    return null
  }
}
