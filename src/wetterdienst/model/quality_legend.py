# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the tokens of `quality_flags` mean for each network (GH-3060).

`quality_flags` is built the same way for every provider (`model/quality_flags.py`): the source's own flag first as
the source writes it, then `kind:code` tokens, and `raw:` last. The format is shared, the codes are not: `3` is a
DWD quality level, `G` a GHCN check that failed, `validity:false` a DMI verdict. This module declares, for every
network, which kinds its `quality_flags` holds and what each means, so that a client reads the legend of the answer
it holds from the answer (`metadata.quality.legend` with `with_metadata`) and the docs do not have to be searched.

A network is listed under `provider/network`, and `LEGENDS` is held to the readers by
`tests/model/test_quality_legend.py`: the kinds a reader passes to `join_quality_flags` are the kinds declared here,
so a reader that writes a further kind fails that test until the kind is told. A network whose values never carry a
flag is listed with an empty legend, which says so rather than leaving the question out.

The codes of a flag are listed only where the repository or the source's own page documents a closed set (`codes`);
for the rest the meaning says what the source calls the flag and whose codes they are, because a code list copied from
memory is a claim nothing checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from wetterdienst.model.dwd_qn_levels import DOCUMENTS, NOTE_1980, qn_levels
from wetterdienst.model.dwd_qn_levels import LEVELS as _DWD_QN_LEVELS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wetterdienst.model.dwd_qn_levels import QnLevels


class QualityCode(BaseModel):
    """One code of a flag, as the source writes it, and what the source says it means."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    meaning: str


class QualityKind(BaseModel):
    """One kind of token in the `quality_flags` of a network."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str | None = Field(
        description="The prefix of the token, `zone` for `zone:mez`; null for the source's own quality flag, "
        "which has none and comes first.",
    )
    written: str = Field(description="How a token of this kind reads in the column, `raw:<text>`.")
    meaning: str
    codes: list[QualityCode] | None = Field(
        default=None,
        description="The codes of the flag, where they are a closed set the source documents; null for a flag "
        "whose codes the source tells itself, which `meaning` names, or are not a set (the text a value was written "
        "with).",
    )
    documentation: str | None = Field(default=None, description="Where the source documents the flag, if it does.")


def _codes(**codes: str) -> list[QualityCode]:
    return [QualityCode(code=code.removeprefix("c_"), meaning=meaning) for code, meaning in codes.items()]


_MESQL = "https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html"

_CHECKS = (
    "`range` (a number outside the physical range of its parameter), `elevation` (a station pressure the elevation "
    "does not allow), `stuck` (a sensor that held one value, or was dead, over a period), `consistency` (a reading the "
    "reading of another parameter of the same file contradicts), `floor` (a model value a little below the floor of "
    "its quantity), `limits` (a number outside the bounds the caller set for its parameter), `source` (a value the "
    "source itself marks as erroneous or doubtful in its own quality flag), `step` (a change between two "
    "consecutive readings, or a jump away and back, beyond what the weather does) and `relations` (two readings of "
    "one file that contradict each other, a maximum below the mean or a dew point above the air temperature, both "
    "flagged, or a day of sunshine longer than the day)"
)

#: the token of a value a plausibility check found implausible and left as it was, in the mode `soft` (GH-3676)
SUSPECT = QualityKind(
    kind="suspect",
    written="suspect:<check>",
    meaning="The value is kept, and a plausibility check in the mode `soft` (on a forecast network every check but "
    "`floor` and `limits` is; the suspect level of a source's own verdict, GHCNh `Suspect` and 382 `R`, CHMI "
    "`Suspect`, MADIS `Questioned`, GHCNh `f`, is flagged `source` in the mode `hard` too) finds it implausible: "
    "one of "
    + _CHECKS
    + ", several joined with `+` (`suspect:range+stuck`). The checks and their modes are the `plausibility` option "
    "of the request; the defaults of `stuck`, `step`, `source` and `relations` are soft. No `raw` token of its own: "
    "the value is "
    "the number the source wrote (beside `rejected:floor` it is the floor, 0.0). Interpolation and summary leave such "
    "a value out.",
)

#: the token of a value a plausibility check rejected, in the mode `hard`, written before `raw` (GH-3676)
REJECTED = QualityKind(
    kind="rejected",
    written="rejected:<check>",
    meaning="The value is null (the floor of its quantity for `floor`), because a plausibility check in the mode "
    "`hard` rejected the number the source wrote, which `raw` holds: one of "
    + _CHECKS
    + ", several joined with `+`. It tells a number rejected by the library from a missing-value code of the "
    "source, which has `raw` alone. A forecast network (`kind` `forecast`: `dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`, "
    "`dwd/pollen`, `dwd/uvi`) never has one but for `floor` and `limits`: its other checks are soft whatever the mode, "
    "so a value is flagged `suspect:<check>` and not nulled.",
)

#: the last token of any network that maps a missing-value marker or an impossible number to null
RAW = QualityKind(
    kind="raw",
    written="raw:<text>",
    meaning="The value is null, or the value the source documents the marker to mean (no snow as 0), because the "
    "source wrote a missing-value marker or a number no sensor can have produced; this is what the source wrote in "
    "its place, as it wrote it ('-999', '99.9', '---', '4021'). Also the floor of the quantity (0.0) where a model "
    "wrote a little below it (DWD DMO precipitation and radiation), the number as short as it goes ('-0.1' for "
    "'-0.10'). After `rejected:<check>` it is the number a check in the mode `hard` rejected, the bounds you set "
    "(`limits`) included. Always the last token.",
)


def _plain(meaning: str, *, codes: list[QualityCode] | None = None, documentation: str | None = None) -> QualityKind:
    """Describe the source's own quality flag, the first token and the only one without a prefix."""
    return QualityKind(kind=None, written="<code>", meaning=meaning, codes=codes, documentation=documentation)


def _kind(kind: str, code: str, meaning: str, *, codes: list[QualityCode] | None = None) -> QualityKind:
    return QualityKind(kind=kind, written=f"{kind}:{code}", meaning=meaning, codes=codes)


_DWD_QN = _plain(
    "The quality level (QN) of the dataset the reading belongs to, as DWD writes it ('3'): the quality control the "
    "values went through. What the levels mean is DWD's and depends on the dataset; `with_metadata` lists the levels "
    "of the datasets read, and `metadata.quality.source_flags` names the QN column. Readings of a dataset without "
    "one have no such token.",
)

_DWD_DOCUMENTS = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
#: how many datasets or documents a legend names; for more it counts them, or names the directory they are in
_MOST_NAMED = 3

#: DWD's description of the annual reporters' crops (read 2026-11-26), which lists the levels 1, 7 and 10
_DWD_PHENOLOGY = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/phenology/annual_reporters/crops/recent/"
    "DESCRIPTION_obsgermany-phenology-annual_reporters-crops-recent_en.pdf"
)
#: DWD's description of the hourly DUETT products, which lists the levels of `QN_952`
_DWD_DUETT = (
    "https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/"
    "DESCRIPTION_derived_germany-climate-hourly-duett_en.pdf"
)

#: the metadata of GeoSphere's klima-v2-1d dataset, whose `code_lists` has q21, the list of the codes of every
#: `<parameter>_flag`; the metadata of klima-v2-10min, -1h and -1m holds the same list (read 2026-11-26)
_GEOSPHERE_METADATA = "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-1d/metadata"

_GEOSPHERE_FLAG = _plain(
    "GeoSphere's quality flag of the value, the `<parameter>_flag` of the klima-v2 datasets (code list q21): whether "
    "the value was checked, by a program or by a person, and whether the check changed it. The library writes the "
    "code as a whole number ('12'), also where the source writes a column that has gaps with a decimal ('20.0'). "
    "The words are GeoSphere's, German. A flag the source leaves empty ('undefiniert' in the list) is left out, so "
    "that a reading without one has no such token. The flag of the reduced air pressure (`pred`) of the hourly "
    "dataset is not documented with a code list in the metadata; its value is written as the source gives it.",
    codes=_codes(
        c_0="ungeprüfte Daten",
        c_10="automatisch geprüft",
        c_11="automatisch geprüft (verändert)",
        c_12="automatisch geprüft (original)",
        c_20="manuell geprüft (unbekannt)",
        c_21="manuell geprüft (verändert)",
        c_22="manuell geprüft (original)",
    ),
    documentation=_GEOSPHERE_METADATA,
)

_DWD_DERIVED_QN = _plain(
    "The quality level (QN_952) of the hourly DUETT datasets (`radiation_global`, `sunshine_duration`), as DWD writes "
    "it: the scope of the input data used for merging, DWD's words. The other derived datasets have none.",
    codes=_codes(
        c_500="DUETT data without station and satellite data",
        c_501="DUETT data based on station data only",
        c_502="DUETT data based on satellite data only",
        c_503="DUETT data based on (max 42) station and satellite data",
    ),
    documentation=_DWD_DUETT,
)


def _levels_told(levels: Iterable[str]) -> str:
    """Write levels as DWD's lists do: `1, 2, 3` (the list is short and a range would hide the gaps)."""
    return ", ".join(levels)


def _datasets_told(datasets: list[str]) -> str:
    """Name up to three datasets, and count the rest."""
    named = ", ".join(datasets[:_MOST_NAMED])
    return named if len(datasets) <= _MOST_NAMED else f"{named} and {len(datasets) - _MOST_NAMED} more"


def _per_dataset(found: QnLevels) -> str:
    """Say which datasets list which levels, and the 1980 sentence for the ones that list 5 and 10."""
    told = []
    for group in found.groups:
        text = f"{_datasets_told(group.datasets)} list {_levels_told(group.levels)}"
        if {"5", "10"} & set(group.levels):
            text += " (data up to and including 1980 reach 5 at best, later data 10)"
        if group.carried:
            text += (
                f"; their data carry {_levels_told(group.carried)} as well, which the description does not list "
                "(its wording is that of the station network's descriptions)"
            )
        told.append(text)
    return " " + "; ".join(told) + "."


def _documents_of(found: QnLevels) -> tuple[str | None, str]:
    """Give the `documentation` URL of an answer's levels and what the meaning adds about the documents.

    One description is the URL; two or three are named in the meaning (`documentation` is one URL or null); for more
    the directory of the descriptions is the URL.
    """
    if len(found.urls) == 1:
        return found.urls[0], ""
    if 1 < len(found.urls) <= _MOST_NAMED:
        named = "; ".join(f"{dataset} {DOCUMENTS[dataset].url}" for group in found.groups for dataset in group.datasets)
        return None, f" Descriptions: {named}."
    if found.urls:
        return _DWD_DOCUMENTS, " Each dataset's description is the DESCRIPTION_*_en.pdf of its directory there."
    return None, ""


def dwd_observation_qn(datasets: Iterable[str]) -> QualityKind:
    """Describe the QN of the datasets read (`resolution/dataset`): the levels DWD lists for them, and where.

    Each level is told for the datasets whose description lists it: where the datasets differ, the meaning says which
    dataset lists which. Where DWD lists no level for a dataset (it publishes no description of it) the kind says so;
    the levels of another product are never told for it. `documentation` is the one description of an answer that reads
    one product, else null (the URLs are in the meaning), or the directory of the descriptions for many.
    """
    found = qn_levels(datasets)
    if not (found.groups or found.undocumented):
        return _DWD_QN
    meaning = "DWD's quality level (QN) of the row, as DWD writes it ('3'): the quality control the values went through"
    # an answer of undescribed datasets only tells no wording, so it does not say whose wording it is
    meaning += ", worded as in the product's English description." if found.groups else "."
    if len(found.groups) == 1 and not found.groups[0].carried:
        meaning += " " + NOTE_1980 if {"5", "10"} & set(found.levels) else ""
    elif found.groups:
        meaning += _per_dataset(found)
    if found.undocumented:
        meaning += " DWD publishes no description of the levels of " + ", ".join(found.undocumented) + "."
    documentation, about_documents = _documents_of(found)
    listed = {level for group in found.groups for level in group.levels}
    codes = [
        QualityCode(
            code=level,
            meaning=_DWD_QN_LEVELS[level]
            + ("" if level in listed else " (the station network's wording; the description lists no such level)"),
        )
        for level in found.levels
    ]
    return QualityKind(
        kind=None,
        written="<code>",
        meaning=meaning + about_documents,
        codes=codes or None,
        documentation=documentation,
    )


#: every network by `provider/network`; the order is that of the column
LEGENDS: dict[str, list[QualityKind]] = {
    "aemet/observation": [SUSPECT, REJECTED, RAW],
    "chmi/observation": [
        _plain(
            "The QUALITY code of the daily and sub-daily files, as CHMI's metadata/meta4.csv lists it, written as the "
            "whole number. The aggregate files (monthly, yearly) have none.",
            codes=_codes(
                c_0="Good",
                c_1="Suspect",
                c_2="Poor",
                c_3="Estimated",
                c_4="Missing",
                c_5="Unknown",
            ),
        ),
        _kind(
            "element",
            "<letter>",
            "The FLAG letter of the row, whose meaning is that of its element and listed per element in CHMI's "
            "metadata/meta3.csv (for the precipitation total SRA, `T` is an unmeasurable amount). Blank for "
            "most rows, and then left out.",
        ),
        _kind(
            "repeat",
            "*",
            "The FLAG_REPEAT of an aggregate file: the extreme of the month was reached more than once. CHMI "
            "documents neither this flag nor the next; the meaning is read off comparing the files with their daily "
            "files.",
        ),
        _kind(
            "interrupted",
            "I",
            "The FLAG_INTERRUPTED of an aggregate file: the value is computed although daily values of the period "
            "are missing, so the series was interrupted. Read off the files, as `repeat`.",
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "dmi/observation": [
        _plain(
            "DMI's qcStatus of the record.",
            codes=_codes(manual="Quality controlled by DMI's climatologists", none="Not controlled"),
        ),
        _kind(
            "validity",
            "<true|false>",
            "DMI's validity of the record: whether the climatologists consider the value valid. `false` is "
            "'generally not correct' by DMI's own words, mostly for Greenland and rarely for Denmark; the check "
            "`source` flags the value `suspect:source` (soft, the default) or nulls it as `rejected:source` (hard).",
            codes=_codes(true="Considered valid", false="Considered not valid"),
        ),
        _kind(
            "n",
            "<count>",
            "DMI's `noValuesInCalculation`: the number of readings the value was computed from (hourly values for a "
            "day, daily values for a month or a year). DMI computes the values of Greenland and the Faroe Islands "
            "from however many exist, even one; a daily value from fewer than 4 readings (half of the 8 three-hourly "
            "synoptic observations that older Greenland days have; modern days have 24 hourly), a monthly from fewer "
            "than 14 and a yearly from fewer than 183 is judged by the check `source` like `validity:false`, unless "
            "the period had not ended (`completeness:Incomplete`), whose count is the readings so far.",
        ),
        _kind(
            "completeness",
            "Incomplete",
            "The monthly or annual value of a period that had not ended when the request was served (the current "
            "month or year, which DMI serves from the readings so far, `validity:true` and not yet controlled): it is "
            "partial and may still change. DMI marks no such value, so this library does, by the `to` of the record "
            "against the time of the request. A value of a period that has ended has no token, which is no claim that "
            "it is final. A daily value of a day that had not ended is not returned at all (`window-not-closed`), and "
            "an hourly one is not judged: DMI publishes an hour when it is over.",
            codes=_codes(Incomplete="Based on a period that had not ended"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "dwd/observation": [
        _DWD_QN,
        _kind(
            "zone",
            "<mez|mez-1973-75|mez-local-mean-time|woz>",
            "The time zone the source stamped the row in, where it is not UTC. `mez`: the stamp was MEZ (UTC+1, the "
            "eMD archive of East German stations up to 1991, and the months of the plain MEZ periods that comparisons "
            "with NOAA ISD and a diurnal-phase test find in MEZ) and is shifted to UTC. `mez-1973-75`: the same "
            "shift for the batch of 1973-01 to 1975-12 at 13 stations, of which 8 are about 0.4 h later than "
            "the clock explains (the analog recorder's lag, which stays as in every other analog year). "
            "`mez-local-mean-time`: the stamp of an East German `MEZ (MD)` period was in mean local time (UTC plus the "
            "longitude over 15, 0.6 to 0.9 h, in 1952 to 1961 and at Potsdam 1973-01 to 1975-05); it is shifted by "
            "the same hour as `mez` and so is still 0.2 to 0.5 h early, which an hourly grid cannot correct. `woz`: "
            "the stamp is the hour of the station's local true solar time, which is no whole hour from UTC, and is "
            "returned as written. Rows stamped in UTC carry no token.",
            codes=[
                *_codes(mez="Stamp shifted from MEZ (UTC+1) to UTC"),
                QualityCode(
                    code="mez-1973-75",
                    meaning="Stamp shifted from MEZ (UTC+1) to UTC; the analog recorder's lag of about 0.4 h "
                    "remains at 8 stations",
                ),
                QualityCode(
                    code="mez-local-mean-time",
                    meaning="Stamp shifted by 1 h from mean local time (UTC + 0.6 to 0.9 h): still 0.2 to 0.5 h early",
                ),
                *_codes(woz="Stamp in local true solar time, unshifted"),
            ],
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "dwd/derived": [_DWD_DERIVED_QN, SUSPECT, REJECTED, RAW],
    "dwd/mosmix": [SUSPECT, RAW],
    "dwd/dmo": [SUSPECT, REJECTED, RAW],
    "dwd/road": [
        _plain(
            "The verdict on the reading, derived by the library from the station's quality flag word: `1` suspect, "
            "`0` checked and not suspect. No token where it is unknown (an unchecked or missing flag); that is told "
            "apart from a reading found sound. A sensor that has stopped is no part of it: the 198.15 K it writes for "
            "days is null with `raw:198.15`, and a sensor that holds any other value is the check `stuck`, "
            "`suspect:stuck`.",
            codes=_codes(c_0="Checked, not suspect", c_1="Suspect"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "dwd/swsmos": [SUSPECT, RAW],
    "dwd/uvi": [SUSPECT, RAW],
    "dwd/poi": [SUSPECT, REJECTED, RAW],
    "dwd/pollen": [SUSPECT, RAW],
    "dwd/phenology": [
        _plain(
            "DWD's Qualitaetsniveau of the phase report, as DWD writes it: the quality control procedure applied, in "
            "the words of DWD's English description. The German description words 7 as 'geprüft, nicht korrigiert' "
            "(checked, not corrected).",
            codes=_codes(
                c_1=_DWD_QN_LEVELS["1"],
                c_7=_DWD_QN_LEVELS["7"],
                c_10=_DWD_QN_LEVELS["10"],
            ),
            documentation=_DWD_PHENOLOGY,
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "ea/hydrology": [
        _plain(
            "The Environment Agency's quality word of the reading, as the endpoint writes it: Good, Estimated, "
            "Suspect, Unchecked or Missing.",
            codes=_codes(
                Good="Good", Estimated="Estimated", Suspect="Suspect", Unchecked="Unchecked", Missing="Missing"
            ),
        ),
        _kind(
            "completeness",
            "<Complete|Incomplete>",
            "Whether the value is based on complete data, which says how much of the day a daily value covers; "
            "where the endpoint gives one.",
            codes=_codes(Complete="Based on complete data", Incomplete="Based on incomplete data"),
        ),
    ],
    "eaufrance/hubeau": [
        _plain(
            "Hub'Eau's code_qualification_obs of the observation, as the service writes it, a whole number "
            "('12'); the seven values its API documentation lists, with the French words it gives them.",
            codes=_codes(
                c_0="Neutre",
                c_4="Faible",
                c_8="Forte",
                c_12="Douteuse",
                c_16="Non qualifiée",
                c_20="Bonne",
                c_30="Estimée",
            ),
            documentation="https://hubeau.eaufrance.fr/api/v2/hydrometrie/api-docs",
        ),
    ],
    "eccc/observation": [
        _plain(
            "ECCC's own flag letter of the value in the hourly and daily files (`M` missing, `E` estimated, `T` "
            "trace, ...), verbatim. The monthly files have none: the `I` of a monthly value is not ECCC's letter "
            "but wetterdienst's, derived from the collection's counts of valid days by the rule of ECCC's Notes 25 "
            "and 26 (incomplete month).",
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "fmi/observation": [SUSPECT, REJECTED, RAW],
    "geosphere/observation": [_GEOSPHERE_FLAG, SUSPECT, REJECTED, RAW],
    "imgw/hydrology": [SUSPECT, REJECTED, RAW],
    "imgw/meteorology": [
        _plain(
            "IMGW's status column of the value, from the file's *_format.txt, verbatim; blank (null) where the value "
            "is a measurement. `11` is the one code the library assigns itself.",
            codes=_codes(
                c_8="brak pomiaru: no measurement (the value is null)",
                c_9="brak zjawiska: the phenomenon did not occur (the value is 0)",
                Z="opad zbiorczy: a collective total over preceding days that were not measured (daily precipitation)",
                c_11="A day absent from a month that is present, which the format says is a day without the "
                "phenomenon: returned as 0 mm (daily precipitation); assigned by the library",
            ),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "ipma/observation": [SUSPECT, REJECTED, RAW],
    "knmi/observation": [SUSPECT, REJECTED, RAW],
    "lhmt/observation": [SUSPECT, REJECTED, RAW],
    "meteofrance/observation": [
        _plain(
            "Météo-France's validation code of the value, verbatim; null where the source leaves it blank.",
            codes=_codes(c_9="Filtered", c_0="Protected", c_1="Validated", c_2="Doubtful"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "meteofrance/synop": [SUSPECT, REJECTED, RAW],
    "meteoswiss/observation": [SUSPECT, REJECTED, RAW],
    "metno/frost": [
        _plain(
            "The qualityCode of the observation in Frost, as the service writes it, a whole number: Frost's single "
            "value for the quality of the observation, as its table words it.",
            codes=_codes(
                c_0="OK, value is controlled and found O.K.",
                c_1="OK, value is controlled and corrected, or value is missing and interpolated",
                c_2="Slightly uncertain, value is not controlled",
                c_4="Slightly uncertain, value is not corrected",
                c_5="Very uncertain, value is not corrected",
                c_6="Very uncertain, model data. Value is controlled and corrected, or value is missing and is "
                "interpolated - automatic",
                c_7="Erroneous, value is not corrected",
            ),
            documentation="https://frost.met.no/dataclarifications.html#quality-code",
        ),
        _kind(
            "completeness",
            "Incomplete",
            "The monthly or annual value of a window that had not closed when the request was served (the "
            "current month or year: the calendar one closes at its end, the `PT6H` sum at 06 UTC and the `PT18H` "
            "extremes at 18 UTC of its last day): it is the period so far, partial, and may still change. Frost "
            "marks no such value, so this library does. A value of a closed window has no token, which is no claim "
            "that it is final; a daily value of an open window is not returned at all (`window-not-closed`).",
            codes=_codes(Incomplete="Based on a window that had not closed"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "metoffice/observation": [
        _plain(
            "MIDAS's MESQL quality-control flag of the value, a five-digit code that the file writes as an integer and "
            "the library returns as the string the file writes (`02576` reads `2576`). Each digit encodes a different "
            "aspect of the quality, so a larger number is not worse.",
            documentation=_MESQL,
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "noaa/ghcn": [
        _plain(
            "The quality flag of the source: for the daily data a letter naming the check the value failed, blank "
            "(left out) where it failed none; for the hourly data the quality code of the element, which is read in "
            "the list of the element's source (`source:`), as the codes differ by source. The value is returned "
            "as the file gives it, suspect or erroneous too; the check `source` judges the codes that the readme and "
            "Table 3 word as a verdict (`suspect:source`, or `rejected:source` in the mode `hard` for the erroneous "
            "level).",
        ),
        _kind(
            "measurement",
            "<code>",
            "The measurement flag: how the value was made, for the daily data NOAA's MFLAG, for the hourly data the "
            "element's measurement code (`C` a calm wind, `D` a derived humidity, `T` a trace of precipitation, ...).",
        ),
        _kind(
            "source",
            "<code>",
            "The source flag: which source or network the value comes from, for the daily data NOAA's SFLAG, for the "
            "hourly data the source code that says which list the quality code is read in.",
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "nws/observation": [
        _plain(
            "The MADIS quality-control flag of the quantity, verbatim: the checks the value passed. Level 1 is "
            "validity, level 2 internal, temporal and statistical spatial consistency, level 3 spatial consistency.",
            codes=_codes(
                Z="Preliminary, no QC",
                C="Coarse pass, passed level 1",
                S="Screened, passed levels 1 and 2",
                V="Verified, passed levels 1, 2 and 3",
                X="Rejected/erroneous, failed level 1",
                Q="Questioned, passed level 1, failed 2 or 3",
                G="Subjective good",
                B="Subjective bad",
                T="Virtual temperature could not be calculated, air temperature passing all QC",
            ),
            documentation="https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml",
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "rmi/observation": [
        _plain(
            "Whether the source validated the parameter, derived from RMI's qc_flags map.",
            codes=_codes(c_1="Validated", c_0="Not validated"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "smhi/observation": [
        _plain(
            "SMHI's quality code of the value (the Kvalitet column), verbatim, as the file's legend words the two "
            "it has met: `G` Grön, `Y` Gul.",
            codes=_codes(
                G="Kontrollerade och godkända värden: controlled and approved values",
                Y="Misstänkta eller aggregerade värden: suspect or aggregated values",
            ),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "wsv/pegel": [SUSPECT, REJECTED, RAW],
}


def _with_the_tokens_of_limits(legend: list[QualityKind]) -> list[QualityKind]:
    """Add the kinds `suspect`, `rejected` and `raw` where a network's legend has not, as the last ones, `raw` the last.

    The bounds a caller sets (`Options.limits`) judge any network, so any network can write them (GH-3687).
    """
    kept = [kind for kind in legend if kind not in (SUSPECT, REJECTED, RAW)]
    return [*kept, SUSPECT, REJECTED, RAW]


LEGENDS = {network: _with_the_tokens_of_limits(legend) for network, legend in LEGENDS.items()}


def quality_legend(provider: str, network: str, datasets: Iterable[str] | None = None) -> list[QualityKind]:
    """Give the kinds of token the `quality_flags` of a network holds, in the order of the column.

    `datasets` (`resolution/dataset`, the ones an answer reads) lets `dwd/observation` tell the quality levels DWD
    lists for those products (`dwd_observation_qn`); without it the legend of that network names no level, as the
    levels differ by product.

    Raises:
        KeyError: the network has no legend, which `tests/model/test_quality_legend.py` keeps a registered one from.

    """
    key = f"{provider.lower()}/{network.lower()}"
    legend = list(LEGENDS[key])
    if key == "dwd/observation" and datasets is not None:
        legend = [dwd_observation_qn(datasets) if kind is _DWD_QN else kind for kind in legend]
    return legend


#: what a network with no flag of the source in its legend says in `metadata.quality.source_flag_note`: a fact about
#: this library, which the source may or may not contradict (`SOURCE_FLAG_NOTES`)
NO_SOURCE_FLAG = (
    "This library carries no quality flag of the source for these readings: `quality_flags` holds only its own "
    "tokens (`suspect`, `rejected`, `raw`)."
)

#: the networks whose source does publish a flag that the library does not read, and what to say of it: none now
#: (GeoSphere's `<parameter>_flag` is read, GH-4480), and the table is kept for the next one
SOURCE_FLAG_NOTES: dict[str, str] = {}


def source_flag_codes(provider: str, network: str, dataset: str) -> list[QualityCode] | None:
    """Give the codes of the source's own flag of one dataset (`resolution/dataset`), or None where none are told.

    `dwd/observation` tells the levels DWD's description of that product lists, with the levels its data carry
    besides (`dwd_observation_qn` of this dataset alone, so the urban products' undescribed level 3 included); None
    for a product DWD publishes no description of. Any other network tells the codes of its own flag (the plain kind
    of its legend), which is one set for every dataset that has the flag; None where it lists none. A dataset has
    codes here only if the answer's `legend` has them: the legend of a network is the union of these.
    """
    key = f"{provider.lower()}/{network.lower()}"
    if key == "dwd/observation":
        return dwd_observation_qn([dataset]).codes
    return next((kind.codes for kind in LEGENDS[key] if kind.kind is None), None)


def source_flag_note(provider: str, network: str) -> str | None:
    """Say so where the library carries no flag of the network's source: its legend has no plain kind.

    This is a fact about the library, not about the source: a source that publishes a flag the library does not read
    yet says so (`SOURCE_FLAG_NOTES`), and a test keeps those two apart.
    """
    key = f"{provider.lower()}/{network.lower()}"
    if any(kind.kind is None for kind in LEGENDS[key]):
        return None
    return SOURCE_FLAG_NOTES.get(key, NO_SOURCE_FLAG)
