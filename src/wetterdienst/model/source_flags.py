# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The codes of a source's own quality flag that mark a value as erroneous or doubtful: the check ``source`` (GH-3677).

Many sources return a value and say in a quality flag of their own that it is wrong or in doubt: GHCN-Daily's ``QFLAG``
names the check a value failed, Frost's ``qualityCode`` is 7 for a value it calls erroneous, the Environment Agency
writes ``Suspect``. A reader hands that flag over in ``quality_flags`` as the source wrote it
(``model/quality_flags.py``) and returns the value, and the core reads it here: a reading whose flag holds one of the
codes below is judged by the check ``source``, which in the mode ``soft`` (the default) keeps the value and writes
``suspect:source``, and in the mode ``hard`` nulls it and writes ``rejected:source,raw:<text>`` (``model/judge.py``).

The rule is one for every provider: **a code is in the map where the provider's documentation words it as the verdict
that the value failed a check, is erroneous, suspect, doubtful or of poor quality**, and every code of the map is cited
beside it, with the documentation's wording and its URL. What the documentation words as a degree of uncertainty
(Frost's "slightly uncertain"), a treatment (estimated, corrected, interpolated), a missing value or no control at all
(``Unchecked``, DMI's ``qcStatus`` ``none``) is no verdict and is not in the map. Both levels of a source that has two
(GHCNh's ``Suspect`` and ``Erroneous``, CHMI's ``Suspect`` and ``Poor``) are in it, the check judges them alike, and the
wording of each code is in the page of the provider.

A code is read from the token of ``quality_flags`` that carries it: the plain first token (the source's ordinary quality
flag, ``3``, ``Suspect``) or a token of a kind (``validity:false``). A rule may be limited to the readings that have one
of several values in another token (GHCNh's quality code is read in the list of its source, ``source:335``).

A value that carries a ``raw:`` token already is a code of the source and is not judged; a network whose source marks no
value in a flag the reader returns has no entry, and the check judges nothing there.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

#: the ordinary quality flag of a source: the first token of ``quality_flags``, a code without a ``kind:`` before it
PLAIN = None
#: a regular expression for the first token of a ``quality_flags`` string that has no ``kind:``: the plain quality flag
_FIRST_FLAG = r"^([^,:]+)(?:,|$)"


@dataclass(frozen=True)
class SourceCode:
    """A code the source words as a verdict against the value, with the words it uses."""

    code: str
    #: the documentation's own wording of the code, in the language it is written in
    wording: str


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
        url: the page or file of the provider that words the codes.
        quote: what that document says about the flag, as it says it.

    """

    datasets: tuple[str, ...]
    codes: tuple[SourceCode, ...]
    url: str
    quote: str
    kind: str | None = PLAIN
    beside: tuple[str, tuple[str, ...]] | None = None

    def hit(self) -> pl.Expr:
        """Give the expression that is true for a reading whose ``quality_flags`` hold one of the codes."""
        flags = pl.col("quality_flags")
        code = flags.str.extract(_FIRST_FLAG, 1) if self.kind is None else _token_of(flags, self.kind)
        hit = code.is_in([code_.code for code_ in self.codes])
        if self.beside is not None:
            beside, values = self.beside
            hit = hit & _token_of(flags, beside).is_in(list(values))
        return hit.fill_null(value=False)


def _token_of(flags: pl.Expr, kind: str) -> pl.Expr:
    """Give the code of the token ``kind:<code>`` of a ``quality_flags`` string, null where there is none."""
    return flags.str.extract(rf"(?:^|,){kind}:([^,]*)", 1)


_GHCND = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt"
_GHCNH = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf"
_FROST = "https://frost.met.no/dataclarifications.html#quality-code"
_CHMI = "https://opendata.chmi.cz/meteorology/climate/historical_csv/metadata/meta4.csv"
_EA = "https://environment.data.gov.uk/hydrology/doc/reference#readings-section"
_DMI = "https://www.dmi.dk/friedata/dokumentation/apis/climate-data-api-1"
_MF = "https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-{name}/{stamp}/{file}"
_MF_DOUBTFUL = (
    "Pour certains paramètres, un code qualité est associé à la mesure (noté Qparamètre). Il qualifie l'état de "
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
#: ``tests/test_source_flags.py`` holds the three to one another.
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
        # documentation. The two lists of the legacy sources are the ones that have a verdict; the letters of the
        # integration's own checks and the codes of sources 345 and 382 are not wording of a verdict and are not read
        SourceFlags(
            datasets=("hourly/data",),
            codes=(
                SourceCode("2", "Suspect"),
                SourceCode("3", "Erroneous"),
                SourceCode("6", "Suspect, data originate from an NCEI data source"),
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
            codes=(SourceCode("2", "Suspect"), SourceCode("3", "Erroneous")),
            url=_GHCNH,
            quote="Legacy Codes for Sources: 220, 221, 222, 223, 347, 348 include 0 Not Checked 1 Good 2 Suspect "
            "3 Erroneous 4 Calculated 5 Removed",
            beside=("source", ("220", "221", "222", "223", "347", "348")),
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
                SourceCode("1", "Suspect/Podezřelá hodnota"),
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
