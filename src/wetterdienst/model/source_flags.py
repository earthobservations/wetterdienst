# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The codes of a source's own quality flag that mark a value as erroneous or doubtful: the check ``source`` (GH-3677).

Many sources return a value and say in a quality flag of their own that it is wrong or in doubt: GHCN-Daily's ``QFLAG``
names the check a value failed, Frost's ``qualityCode`` is 7 for a value it calls erroneous, the Environment Agency
writes ``Suspect``. A reader hands that flag over in ``quality_flags`` as the source wrote it
(``model/quality_flags.py``) and returns the value, and the core reads it here: a reading whose flag holds one of the
codes below is judged by the check ``source``, which in the mode ``soft`` (the default) keeps the value and writes
``suspect:source``, and in the mode ``hard`` nulls it and writes ``rejected:source,raw:<text>`` (``model/judge.py``),
unless the code is of the milder level of its source (below).

The rule is one for every provider: **a code is in the map where the provider's documentation words it as the verdict
that the value failed a check, is erroneous, suspect, doubtful or of poor quality**, and every code of the map is cited
beside it, with the documentation's wording and its URL. What the documentation words as a degree of uncertainty
(Frost's "slightly uncertain"), a treatment (estimated, corrected, interpolated), a missing value or no control at all
(``Unchecked``, DMI's ``qcStatus`` ``none``) is no verdict and is not in the map.

A source with two levels of verdict (GHCNh's ``Suspect`` and ``Erroneous``, and source 382's ``R`` and its failed
checks; CHMI's ``Suspect`` and ``Poor``; MADIS's ``Questioned`` and ``Rejected/erroneous``) has both in the map, each
code with its ``level``. In the mode ``soft`` both write ``suspect:source``. In the mode ``hard`` only
the ``erroneous`` level (the code the source words as erroneous, failed or poor) nulls the value; the ``suspect`` level
stays ``suspect:source``, and is never nulled. A source with one level only (GHCN-Daily's ``QFLAG``, Frost's 7, the
Environment Agency's ``Suspect``, Météo-France's 2, DMI's ``validity:false``, Hub'Eau's 12, DWD road's 1, MIDAS's
status 1) has it as ``erroneous``.

A code is read from the token of ``quality_flags`` that carries it: the plain first token (the source's ordinary quality
flag, ``3``, ``Suspect``) or a token of a kind (``validity:false``). A rule may be limited to the readings that have one
of several values in another token (GHCNh's quality code is read in the list of its source, ``source:335``), to the
parameters the documentation words the code for (GHCNh's list of source 345 is "for relative humidity and wind speed
only"), and may read one digit of a compound code (MIDAS's ``MESQL``, five digits of which the third from the right is
the status of the value).

A value that carries a ``raw:`` token already is a code of the source and is not judged; a network whose source marks no
value in a flag the reader returns has no entry, and the check judges nothing there.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: the ordinary quality flag of a source: the first token of ``quality_flags``, a code without a ``kind:`` before it
PLAIN = None
Level = Literal["suspect", "erroneous"]
#: what a rule reads a code in: the kind of token (``PLAIN`` for the plain flag) and the digit of it, or ``None``
Reading = tuple[str | None, int | None]
#: a regular expression for the first token of a ``quality_flags`` string that has no ``kind:``: the plain quality flag
_FIRST_FLAG = r"^([^,:]+)(?:,|$)"


@dataclass(frozen=True)
class SourceCode:
    """A code the source words as a verdict against the value, with the words it uses and how bad it says it is."""

    code: str
    #: the documentation's own wording of the code, in the language it is written in
    wording: str
    #: ``erroneous``: the documentation words the value as wrong, failed or poor (and any code of a source that has
    #: one level only); ``suspect``: the milder level of a source that has two (GHCNh's "Suspect", source 382's
    #: "R" and the "f" of a derived humidity, CHMI's "Suspect", MADIS's "Questioned").
    #: The check in the mode ``hard`` nulls the first and only flags the second
    level: Level = "erroneous"


@dataclass(frozen=True)
class SourceFlags:
    """The codes of one flag of a source, in the datasets that carry it, and where the documentation says so.

    Attributes:
        datasets: the datasets (``resolution/dataset``) of the network whose rows carry the flag.
        codes: the codes that count, each with the documentation's wording.
        kind: the kind of the token of ``quality_flags`` that holds the code (``validity``), or ``PLAIN`` for the
            plain quality flag.
        beside: ``(kind, values)``: the rule applies only to the readings whose token of that kind holds one of the
            values (the sources of GHCNh's Table 3), where the meaning of a code depends on another token.
        parameters: the canonical names of the parameters the documentation words the codes for; the rule applies to
            no other (GHCNh's ``o`` and ``f`` of a derived humidity, which are the integration's own checks on six
            other elements). Resolved against the dataset's parameters where the core judges (``hits``).
        digit: the place, counted from the right and from 1 (the ones are 1, the hundreds 3), of the digit of a
            compound code that the codes are digits of: the status of MIDAS's ``MESQL`` is the third. The code is read
            in the token without padding, as the file writes it (``2576`` is ``02576``), and a code with fewer digits
            has none there.
        url: the page or file of the provider that words the codes.
        quote: what that document says about the flag, as it says it.

    """

    datasets: tuple[str, ...]
    codes: tuple[SourceCode, ...]
    url: str
    quote: str
    kind: str | None = PLAIN
    beside: tuple[str, tuple[str, ...]] | None = None
    parameters: tuple[str, ...] | None = None
    digit: int | None = None

    def hit(
        self,
        columns: Mapping[Reading, pl.Expr] | None = None,
        level: Level | None = None,
        names: Mapping[str, str] | None = None,
    ) -> pl.Expr:
        """Give the expression that is true for a reading whose ``quality_flags`` hold one of the codes.

        ``level`` limits it to the codes of that level; without it every code counts.

        ``columns`` maps a reading (``reading()``: the kind of token and the digit read in it) to the expression of
        its code, where ``hits`` has extracted them once for several rules; without it the codes are extracted from
        ``quality_flags`` here.

        ``names`` maps the canonical name of a parameter to the name its ``parameter`` column holds, for a rule that
        names ``parameters``; a name it lacks is taken as it is.
        """
        columns = columns or {}
        reading = self.reading()
        code = columns[reading] if reading in columns else _code_of(*reading)
        hit = code.is_in([code_.code for code_ in self.codes if level in (None, code_.level)])
        if self.beside is not None:
            beside, values = self.beside
            key = (beside, None)
            hit = hit & (columns[key] if key in columns else _code_of(beside)).is_in(list(values))
        if self.parameters is not None:
            names = names or {}
            hit = hit & pl.col("parameter").is_in([names.get(name, name) for name in self.parameters])
        return hit.fill_null(value=False)

    def reading(self) -> Reading:
        """Name what the codes of this rule are read in: the kind of token and the digit of it."""
        return (self.kind, self.digit)

    def readings(self) -> set[Reading]:
        """Name the tokens (and digits) this rule reads a code in (``PLAIN`` for the plain flag)."""
        return {self.reading()} | ({(self.beside[0], None)} if self.beside is not None else set())


def _code_of(kind: str | None, digit: int | None = None) -> pl.Expr:
    """Give the code of the plain flag (``PLAIN``) or of the token ``kind:<code>`` of ``quality_flags``, or null.

    With a ``digit``, give that digit of the code (counted from the right, from 1), or null where the code has no such
    digit or is no whole number.
    """
    flags = pl.col("quality_flags")
    code = flags.str.extract(_FIRST_FLAG if kind is None else rf"(?:^|,){kind}:([^,]*)", 1)
    if digit is None:
        return code
    return code.str.extract(rf"^-?\d*(\d)\d{{{digit - 1}}}$", 1)


def hits(
    df: pl.DataFrame, rules: Sequence[SourceFlags], names: Mapping[str, str] | None = None
) -> tuple[pl.Series, pl.Series]:
    """Mark the readings of a frame whose ``quality_flags`` hold a code of any of the rules: erroneous, and suspect.

    The code of each kind of token is extracted from the flags once, however many rules read it: the lists of GHCNh
    are several rules over two kinds, and the extraction is the cost of the check. ``names`` resolves the parameters a
    rule is limited to (``SourceFlags.hit``).
    """
    readings = sorted({reading for rule in rules for reading in rule.readings()}, key=str)
    codes = df.select(*(_code_of(*reading).alias(f"__code_{index}") for index, reading in enumerate(readings)))
    columns = {reading: pl.col(f"__code_{index}") for index, reading in enumerate(readings)}
    # the parameter beside the codes, which a rule limited to some parameters reads
    codes = codes.with_columns(df.get_column("parameter")) if "parameter" in df.columns else codes
    marked = codes.select(
        pl.any_horizontal(rule.hit(columns, "erroneous", names) for rule in rules).alias("erroneous"),
        pl.any_horizontal(rule.hit(columns, "suspect", names) for rule in rules).alias("suspect"),
    )
    return marked.get_column("erroneous"), marked.get_column("suspect")


_GHCND = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt"
_GHCNH = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf"
_FROST = "https://frost.met.no/dataclarifications.html#quality-code"
_CHMI = "https://opendata.chmi.cz/meteorology/climate/historical_csv/metadata/meta4.csv"
_EA = "https://environment.data.gov.uk/hydrology/doc/reference#readings-section"
_DMI = "https://www.dmi.dk/friedata/dokumentation/apis/climate-data-api-1"
_MADIS = "https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml"
_HUBEAU = "https://hubeau.eaufrance.fr/api/v2/hydrometrie/api-docs"
_WMO_0_33_005 = "https://github.com/wmo-im/BUFR4/blob/master/BUFRCREX_CodeFlag_en_33.csv"
_MIDAS = "https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html"
#: the sources of GHCNh whose relative humidity and wet bulb temperature are derived from other measurements
_GHCNH_DERIVED = ("220", "221", "222", "223", "313", "314", "315", "322", "335", "343", "344", "346", "347", "348")
_MF = "https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-{name}/{stamp}/{file}"
_MF_DOUBTFUL = (
    "Pour certains paramètres, un code qualité est associé à la mesure (noté Qparamètre). Il qualifie l’état de "  # noqa: RUF001
    "validation de la donnée : 9 : donnée filtrée (la donnée a passé les filtres/contrôles de premiers niveaux) ; "
    "0 : donnée protégée (la donnée a été validée définitivement par le climatologue) ; 1 : donnée validée (la donnée "
    "a été validée par contrôle automatique ou par le climatologue) ; 2 : donnée douteuse en cours de vérification "
    "(la donnée a été mise en doute par contrôle automatique)."
)
_MF_CODE = (
    SourceCode(
        "2", "donnée douteuse en cours de vérification (la donnée a été mise en doute par contrôle automatique)"
    ),
)

#: by network, the flags whose codes the check ``source`` reads. Every code is the provider's own, cited with the
#: wording of its documentation; the pages of the providers and ``docs/data/plausibility.md`` give them again, and
#: ``tests/model/test_source_flags.py`` holds the three to one another.
SOURCE_FLAGS: dict[str, tuple[SourceFlags, ...]] = {
    # GHCN-Daily: the quality flag of a value (`QFLAG`) is blank for a value that failed no check, and any letter says
    # the value failed one; the daily CSV returns the value with the flag
    "noaa/ghcn": (
        SourceFlags(
            datasets=("daily/data",),
            codes=(
                SourceCode("D", "failed duplicate check"),
                SourceCode("G", "failed gap check"),
                SourceCode("I", "failed internal consistency check"),
                SourceCode("K", "failed streak/frequent-value check"),
                SourceCode("L", "failed check on length of multiday period"),
                SourceCode("M", "failed megaconsistency check"),
                SourceCode("N", "failed naught check"),
                SourceCode("O", "failed climatological outlier check"),
                SourceCode("R", "failed lagged range check"),
                SourceCode("S", "failed spatial consistency check"),
                SourceCode("T", "failed temporal consistency check"),
                SourceCode("W", "temperature too warm for snow"),
                SourceCode("X", "failed bounds check"),
                SourceCode("Z", "flagged as a result of an official Datzilla investigation"),
            ),
            url=_GHCND,
            quote="QFLAG1 is the quality flag for the first day of the month. There are fourteen possible values: "
            "Blank = did not fail any quality assurance check",
        ),
        # GHCNh: the quality code is read in the list of the source of the element (`source:` token), Table 3 of the
        # documentation: the two lists of the legacy sources, the list of source 382 (the precipitation of C-HPD,
        # worded as GHCN-Daily's QFLAG) and the list of source 345, which the documentation gives "for relative
        # humidity and wind speed only", so that rule is limited to those parameters. The letters of the integration's
        # own checks (`c`, `s`, `f`, ... for six elements) are not read: they name the check of this dataset's
        # processing that flagged a value ("Spike check", "Frequent value"). The `o` and `f` of a derived humidity and
        # wet bulb are worded as verdicts, and are read for those two parameters alone, where the documentation gives
        # them: the same letters are the integration's own on the six other elements
        SourceFlags(
            datasets=("hourly/data",),
            codes=(
                SourceCode("2", "Suspect", "suspect"),
                SourceCode("3", "Erroneous"),
                SourceCode("6", "Suspect, data originate from an NCEI data source", "suspect"),
                SourceCode("7", "Erroneous, data originate from an NCEI data source"),
            ),
            url=_GHCNH,
            quote="Legacy Codes for Sources 313, 314, 315, 322, 335, 343, 344, 346 include: 0 = Passed gross limits "
            "check 1 = Passed all quality control checks 2 = Suspect 3 = Erroneous 4 = Passed gross limits check, "
            "data originate from an NCEI data source 5 = Passed all quality control checks, data originate from an "
            "NCEI data source 6 = Suspect, data originate from an NCEI data source 7 = Erroneous, data originate "
            "from an NCEI data source 9 = Passed gross limits check if element is present",
            beside=("source", ("313", "314", "315", "322", "335", "343", "344", "346")),
        ),
        SourceFlags(
            datasets=("hourly/data",),
            codes=(SourceCode("2", "Suspect", "suspect"), SourceCode("3", "Erroneous")),
            url=_GHCNH,
            quote="Legacy Codes for Sources: 220, 221, 222, 223, 347, 348 include 0 Not Checked 1 Good 2 Suspect "
            "3 Erroneous 4 Calculated 5 Removed",
            beside=("source", ("220", "221", "222", "223", "347", "348")),
        ),
        SourceFlags(
            datasets=("hourly/data",),
            codes=(
                SourceCode("X", "failed global extreme exceedance check"),
                SourceCode("N", "failed negative precipitation check"),
                SourceCode("Y", "failed state extreme exceedance check (performed on daily totals)"),
                SourceCode("K", "failed streak/frequent-value check"),
                SourceCode("G", "failed gap check"),
                SourceCode("O", "failed climatological outlier check"),
                SourceCode("Z", "flagged as a result of an official Datzilla investigation"),
                SourceCode("Q", "Indicates value failed an extreme value test (value will be present)"),
                SourceCode(
                    "R",
                    "Indicates data values are suspect with regard to the times or period of occurrence",
                    "suspect",
                ),
            ),
            url=_GHCNH,
            quote="Legacy Codes for Source 382 for precipitation (as given in C-HPD documentation) Blank = did not "
            "fail any quality assurance check X = failed global extreme exceedance check N = failed negative "
            "precipitation check Y = failed state extreme exceedance check (performed on daily totals) K = failed "
            "streak/frequent-value check G = failed gap check O = failed climatological outlier check Z = flagged as "
            "a result of an official Datzilla investigation ... Q = a carry-over quality flag the legacy DSI-3240 data "
            "source. Prior to 1996: Indicates value failed an extreme value test (value will be present) ... R = a "
            "carry-over quality flag the legacy DSI-3240 data source. Used since January 1996. Indicates data values "
            "are suspect with regard to the times or period of occurrence",
            beside=("source", ("382",)),
        ),
        SourceFlags(
            datasets=("hourly/data",),
            codes=(SourceCode("3", "Error (erroneous data)"),),
            url=_GHCNH,
            quote="Legacy Codes for Source 345 (for relative humidity and wind speed only): 0 = Good 1 = Issue "
            "(field-length overflow) 3 = Error (erroneous data)",
            beside=("source", ("345",)),
            parameters=("humidity_relative", "wind_speed"),
        ),
        SourceFlags(
            datasets=("hourly/data",),
            codes=(
                SourceCode("o", "Out of range (relative humidity only - with values < 1 or > 100)"),
                SourceCode("f", "Suspect or Error flags for 1 or more of the input measurements", "suspect"),
            ),
            url=_GHCNH,
            quote="Sources: 220, 221, 222, 223, 313, 314, 315, 322, 335, 343, 344, 346, 347, 348 For these sources, "
            "relative humidity and wet-bulb temperature are not directly measured, but rather derived from other "
            "measured variables. These can have the following QC flags: o - Out of range (relative humidity only - "
            "with values < 1 or > 100) f - Suspect or Error flags for 1 or more of the input measurements",
            beside=("source", _GHCNH_DERIVED),
            parameters=("humidity_relative",),
        ),
        SourceFlags(
            datasets=("hourly/data",),
            codes=(SourceCode("f", "Suspect or Error flags for 1 or more of the input measurements", "suspect"),),
            url=_GHCNH,
            quote="Sources: 220, 221, 222, 223, 313, 314, 315, 322, 335, 343, 344, 346, 347, 348 For these sources, "
            "relative humidity and wet-bulb temperature are not directly measured, but rather derived from other "
            "measured variables. These can have the following QC flags: o - Out of range (relative humidity only - "
            "with values < 1 or > 100) f - Suspect or Error flags for 1 or more of the input measurements",
            beside=("source", _GHCNH_DERIVED),
            parameters=("temperature_wet_2m",),
        ),
    ),
    # Frost: `qualityCode` aggregates the flags of MET Norway's quality control into one value, and 7 is its erroneous
    "metno/frost": (
        SourceFlags(
            datasets=(
                "10_minutes/data",
                "hourly/data",
                "6_hours/data",
                "daily/data",
                "monthly/data",
                "annual/data",
            ),
            codes=(SourceCode("7", "Erroneous, value is not corrected"),),
            url=_FROST,
            quote="Frost tries to give the user a single value to represent the general quality of the observation. "
            "This value is set in the field qualityCode. 0 OK, value is controlled and found O.K. 1 OK, value is "
            "controlled and corrected, or value is missing and interpolated 2 Slightly uncertain, value is not "
            "controlled 4 Slightly uncertain, value is not corrected 5 Very uncertain, value is not corrected "
            "6 Very uncertain, model data. Value is controlled and corrected, or value is missing and is "
            "interpolated - automatic 7 Erroneous, value is not corrected",
        ),
    ),
    # CHMI: `meta4.csv` explains the QUALITY of the daily, hourly and 10 minute files; the monthly and annual have none
    "chmi/observation": (
        SourceFlags(
            datasets=("10_minutes/data", "hourly/data", "daily/data"),
            codes=(
                SourceCode("1", "Suspect/Podezřelá hodnota", "suspect"),
                SourceCode("2", "Poor/Hodnota s nízkou kvalitou, podezřelá, zatím nepoužívat"),
            ),
            url=_CHMI,
            quote="FLAG2,DESCRIPTION 0,Good/Kvalitní hodnota 1,Suspect/Podezřelá hodnota 2,Poor/Hodnota s nízkou "
            "kvalitou, podezřelá, zatím nepoužívat 3,Estimated/Odhadnutá hodnota 4,Missing/Chybějící hodnota "
            "5,Unknown/Kvalita neznámá",
        ),
    ),
    # Environment Agency: the `quality` of a reading
    "ea/hydrology": (
        SourceFlags(
            datasets=("15_minutes/data", "daily/data"),
            codes=(SourceCode("Suspect", "Suspect"),),
            url=_EA,
            quote="quality: The quality of this reading: Good, Estimated, Suspect, Unchecked, Missing",
        ),
    ),
    # Météo-France: the validation code of a parameter, `Q<parameter>`, of the four descriptions of the base
    # climatological data; the synop network has none
    "meteofrance/observation": (
        SourceFlags(
            datasets=("daily/core", "daily/others"),
            codes=_MF_CODE,
            url=_MF.format(
                name="quotidiennes",
                stamp="20260603-085232",
                file="climatologie-donnees-quotidiennes-descriptif-20260603.pdf",
            ),
            quote=_MF_DOUBTFUL,
        ),
        SourceFlags(
            datasets=("hourly/core", "hourly/others"),
            codes=_MF_CODE,
            url=_MF.format(
                name="horaires", stamp="20260603-085646", file="climatologie-donnees-horaires-descriptif-20260603.pdf"
            ),
            quote=_MF_DOUBTFUL,
        ),
        SourceFlags(
            datasets=("monthly/data",),
            codes=_MF_CODE,
            url=_MF.format(
                name="mensuelles",
                stamp="20260603-085345",
                file="climatologie-donnees-mensuelles-descriptif-20260603.pdf",
            ),
            quote=_MF_DOUBTFUL,
        ),
        SourceFlags(
            datasets=("6_minutes/data",),
            codes=_MF_CODE,
            url=_MF.format(
                name="6-minutes", stamp="20260401-151040", file="climatologie-donnees-6-minutes-descriptif-20250604.pdf"
            ),
            quote=_MF_DOUBTFUL,
        ),
    ),
    # DMI: `validity` says whether the climatologists consider the value valid; `qcStatus` (manual or none) says
    # whether it was controlled, which is no verdict and is not read
    "dmi/observation": (
        SourceFlags(
            datasets=("hourly/data", "daily/data", "monthly/data", "annual/data"),
            codes=(
                SourceCode(
                    "false",
                    "Whether or not the value is considered valid by the climatologists. Invalid data is generally "
                    "not correct",
                ),
            ),
            url=_DMI,
            quote="properties.validity: Boolean. Whether or not the value is considered valid by the climatologists. "
            "Invalid data is generally not correct",
            kind="validity",
        ),
    ),
    # NWS: `qualityControl` of every quantity is MADIS's QC data descriptor, which the NWS API names as "the quality
    # control flag from the MADIS system", defined on MADIS's page. `X` failed the first level, `Q` failed the second
    # or third, `B` is a person's verdict; the codes `Z C S V` say how far a value got, and `G` that a person found it
    # good (`T` says a temperature was returned for a virtual temperature)
    "nws/observation": (
        SourceFlags(
            datasets=("hourly/data",),
            codes=(
                SourceCode("Q", "Questioned, passed level 1, failed 2 or 3", "suspect"),
                SourceCode("X", "Rejected/erroneous, failed level 1"),
                SourceCode("B", "Subjective bad"),
            ),
            url=_MADIS,
            quote="NWS API, QuantitativeValue.qualityControl: For values in observation records, the quality control "
            "flag from the MADIS system. The definitions of these flags can be found at "
            "https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml. MADIS, QC Data Descriptor Values: Z - Preliminary, "
            "no QC; C - Coarse pass, passed level 1; S - Screened, passed levels 1 and 2; V - Verified, passed levels "
            "1, 2, and 3; X - Rejected/erroneous, failed level 1; Q - Questioned, passed level 1, failed 2 or 3 "
            "where level 1 = validity, level 2 = internal consistency, temporal consistency, statistical spatial "
            "consistency checks, level 3 = spatial consistency check; G - Subjective good; B - Subjective bad; "
            "T - Virtual temperature could not be calculated, air temperature passing all QC checks has been returned",
        ),
    ),
    # Hub'Eau: `code_qualification_obs`, the Sandre nomenclature 515 of the qualification of an observation
    "eaufrance/hubeau": (
        SourceFlags(
            datasets=("5_minutes/data", "6_minutes/data", "10_minutes/data", "15_minutes/data", "hourly/data"),
            codes=(SourceCode("12", "Douteuse"),),
            url=_HUBEAU,
            quote="code_qualification_obs: Qualification de la donnée d'observation hydrométrique. 7 valeurs "
            "possibles : 0, 4, 8, 12, 16, 20, 30 (Neutre, Faible, Forte, Douteuse, Non qualifiée, Bonne, Estimée). "
            "Sandre, nomenclature 515, 12 Douteuse: Valeur douteuse",
        ),
    ),
    # DWD road: the flag of the station (`qualityInformationAwsData`, BUFR 0 33 005) says, for each quantity, whether
    # the station reports it as suspect; the reader hands over `1` where it does, `0` where it checked and did not
    "dwd/road": (
        SourceFlags(
            datasets=("15_minutes/data",),
            codes=(
                SourceCode(
                    "1",
                    "Wind data suspect, Air temperature data suspect, Humidity data suspect, Ground temperature data "
                    "suspect, Visibility data suspect, Precipitation data suspect",
                ),
            ),
            url=_WMO_0_33_005,
            # the quantities the table names; the road surface (bit 7, "Ground temperature") and the dew point (the
            # humidity's bit) are the reader's reading of the table, which the documentation does not state
            parameters=(
                "wind_speed",
                "wind_direction",
                "wind_gust_max",
                "wind_direction_gust_max",
                "temperature_air",
                "humidity_relative",
                "visibility",
                "precipitation_amount",
                "precipitation_intensity",
                "precipitation_type_flags",
            ),
            quote="0 33 005 Quality information (AWS data): 1 No automated meteorological data checks performed; "
            "2 Pressure data suspect; 3 Wind data suspect; 4 Air temperature data suspect; 5 Wet-bulb temperature "
            "data suspect; 6 Humidity data suspect; 7 Ground temperature data suspect; 14 Visibility data suspect; "
            "18 Precipitation data suspect",
        ),
    ),
    # Met Office MIDAS: the `_q` of an element is `MESQL`, five digits each of which says one thing; the status (S)
    # is the third digit from the right, and 1 is "Observed and suspect"
    "metoffice/observation": (
        SourceFlags(
            datasets=(
                "daily/rain",
                "daily/temperature",
                "daily/weather",
                "hourly/rain",
                "hourly/weather",
                "hourly/wind",
                "hourly/radiation",
                "hourly/soil_temperature",
            ),
            codes=(
                SourceCode(
                    "1",
                    "Observed and suspect (i.e. has failed the latest QC check), or there are strong grounds for "
                    "suspecting the accuracy of the observation",
                ),
            ),
            url=_MIDAS,
            quote="This _q attribute is a five digit number (of the form MESQL), where each digit describes one aspect "
            "of the quality of a meteorological element. S qc_status Indicates 1 of up to 8 possible descriptions of "
            "the value of the element (e.g. reason for suspecting a value). qc_status (code_id 8023) indicates the "
            "status of the data value. 0 Observed and not suspect 1 Observed and suspect (i.e. has failed the latest "
            "QC check), or there are strong grounds for suspecting the accuracy of the observation",
            digit=3,
        ),
    ),
}


def source_coverage() -> dict[str, tuple[str, ...]]:
    """Give, by network (in alphabetical order), the datasets the check ``source`` reads a flag in."""
    return {
        network: tuple(dict.fromkeys(dataset for flags in SOURCE_FLAGS[network] for dataset in flags.datasets))
        for network in sorted(SOURCE_FLAGS)
    }


def flags_of(network: str, dataset: str) -> tuple[SourceFlags, ...]:
    """Give the flags of a network that its dataset (``resolution/dataset``) carries; none for most."""
    return tuple(flags for flags in SOURCE_FLAGS.get(network, ()) if dataset in flags.datasets)
