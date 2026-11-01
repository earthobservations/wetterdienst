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

from pydantic import BaseModel, ConfigDict, Field


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
    "reading of another parameter of the same file contradicts) and `floor` (a model value a little below the floor of "
    "its quantity)"
)

#: the token of a value a plausibility check found implausible and left as it was, in the mode `soft` (GH-3676)
SUSPECT = QualityKind(
    kind="suspect",
    written="suspect:<check>",
    meaning="The value is kept, and a plausibility check in the mode `soft` (always, on a forecast network) finds it "
    "implausible: one of "
    + _CHECKS
    + ", several joined with `+` (`suspect:range+stuck`). The checks and their modes are the `plausibility` option "
    "of the request; the default of `stuck` is soft. No `raw` token: the value is the number the source wrote. "
    "Interpolation and summary leave such a value out.",
)

#: the token of a value a plausibility check rejected, in the mode `hard`, written before `raw` (GH-3676)
REJECTED = QualityKind(
    kind="rejected",
    written="rejected:<check>",
    meaning="The value is null (the floor of its quantity for `floor`), because a plausibility check in the mode "
    "`hard` rejected the number the source wrote, which `raw` holds: one of "
    + _CHECKS
    + ", several joined with `+`. It tells a number rejected by the library from a missing-value code of the "
    "source, which has `raw` alone. A forecast network (`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`) never has one but for "
    "`floor`: its checks are soft whatever the mode, so a value is flagged `suspect:<check>` and not nulled.",
)

#: the last token of any network that maps a missing-value marker or an impossible number to null
RAW = QualityKind(
    kind="raw",
    written="raw:<text>",
    meaning="The value is null, or the value the source documents the marker to mean (no snow as 0), because the "
    "source wrote a missing-value marker or a number no sensor can have produced; this is what the source wrote in "
    "its place, as it wrote it ('-999', '99.9', '---', '4021'). Also the floor of the quantity (0.0) where a model "
    "wrote a little below it (DWD DMO precipitation and radiation), the number as short as it goes ('-0.1' for "
    "'-0.10'). Always the last token.",
)


def _plain(meaning: str, *, codes: list[QualityCode] | None = None, documentation: str | None = None) -> QualityKind:
    """Describe the source's own quality flag, the first token and the only one without a prefix."""
    return QualityKind(kind=None, written="<code>", meaning=meaning, codes=codes, documentation=documentation)


def _kind(kind: str, code: str, meaning: str, *, codes: list[QualityCode] | None = None) -> QualityKind:
    return QualityKind(kind=kind, written=f"{kind}:{code}", meaning=meaning, codes=codes)


_DWD_QN = _plain(
    "The quality level (QN) of the dataset the reading belongs to, as DWD writes it ('3'). The levels in use and "
    "what they mean are DWD's and depend on the dataset's QN column, which `metadata.quality.source_flags` names; "
    "readings of a dataset without one have no such token.",
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
            "'generally not correct' by DMI's own words, mostly for Greenland and rarely for Denmark; the value is "
            "returned as published, so a caller can drop it by this token.",
            codes=_codes(true="Considered valid", false="Considered not valid"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "dwd/observation": [
        _DWD_QN,
        _kind(
            "zone",
            "<mez|woz>",
            "The time zone the source stamped the row in, where it is not UTC. `mez`: the stamp was MEZ (UTC+1, the "
            "eMD archive of East German stations up to 1991) and is shifted to UTC. `woz`: the stamp is the hour of "
            "the station's local true solar time, which is no whole hour from UTC, and is returned as written. Rows "
            "stamped in UTC carry no token.",
            codes=_codes(mez="Stamp shifted from MEZ (UTC+1) to UTC", woz="Stamp in local true solar time, unshifted"),
        ),
        SUSPECT,
        REJECTED,
        RAW,
    ],
    "dwd/derived": [_DWD_QN, SUSPECT, REJECTED, RAW],
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
    "dwd/poi": [SUSPECT, REJECTED, RAW],
    "dwd/phenology": [
        _plain(
            "DWD's Qualitaetsniveau of the phase report, as DWD writes it.",
            codes=_codes(
                c_1="Formal check only",
                c_7="Checked in routine, uncorrected",
                c_10="Checked and corrected",
            ),
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
            "('12'). The codes are Hub'Eau's and told in its API documentation.",
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
    "geosphere/observation": [SUSPECT, REJECTED, RAW],
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
        _plain("The qualityCode of the observation in Frost, as the service writes it, a whole number."),
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
            "as the file gives it, suspect or erroneous too.",
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


def quality_legend(provider: str, network: str) -> list[QualityKind]:
    """Give the kinds of token the `quality_flags` of a network holds, in the order of the column.

    Raises:
        KeyError: the network has no legend, which `tests/model/test_quality_legend.py` keeps a registered one from.

    """
    return list(LEGENDS[f"{provider.lower()}/{network.lower()}"])
