# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every number a reader rejects is kept and flagged when its check is soft, and nothing else changes (GH-3676).

`test_value_stubs.py` runs each stubbed source with the defaults and names the numbers its reader rejects as
`verdicts`. This runs the same stubs with every check soft: the numbers named are all still there, as `suspect:` of the
same checks, and not one is nulled by a judgement. The missing-value codes of the source are no judgement, so they are
null, with `raw:` alone, in both modes.
"""

from __future__ import annotations

import polars as pl
import pytest

from tests.provider.value_stubs import STUBS, ValueStub
from wetterdienst.model.plausibility import CHECKS

JUDGING = [stub for stub in STUBS if stub.verdicts and not stub.plausibility]


def test_the_stubs_cover_every_check_a_reader_judges_with() -> None:
    """The five checks are each in some stub, so that each is held to its mode against a real reader."""
    covered = {check for stub in STUBS for _, _, checks in stub.verdicts for check in checks.split("+")}
    assert covered == set(CHECKS)


@pytest.mark.parametrize("stub", JUDGING, ids=lambda stub: stub.provider)
def test_a_reader_with_every_check_soft_keeps_what_it_rejects(stub: ValueStub, monkeypatch: pytest.MonkeyPatch) -> None:
    """The numbers the stub names as rejected are kept, flagged `suspect:` with the same checks; none is rejected."""
    for check in CHECKS:
        monkeypatch.setenv(f"WD_TS_PLAUSIBILITY__{check.upper()}", "soft")
    df = stub.build(monkeypatch, drop_nulls=False)
    flags = pl.col("quality_flags")
    assert df.filter(flags.str.contains(r"(^|,)rejected:")).is_empty(), (
        f"{stub.provider}: a check rejected in soft mode"
    )
    suspect = df.filter(flags.str.contains(r"(^|,)suspect:")).select(
        "parameter",
        pl.col("value"),
        flags.str.extract(r"suspect:([a-z+]+)$", 1).alias("checks"),
        flags.str.contains("raw:").alias("has_raw"),
    )
    assert suspect.get_column("value").is_not_null().all(), f"{stub.provider}: a suspect value was nulled"
    assert not suspect.get_column("has_raw").any(), f"{stub.provider}: a kept value has a `raw:` token"
    # a reader that judges in several steps does not show a value an earlier step rejected to the next, so the checks of
    # a kept value are at least those that rejected it: `rejected:range` and `suspect:elevation+range`
    kept = [(str(row["parameter"]), set(row["checks"].split("+"))) for row in suspect.to_dicts()]
    for parameter, text, checks in stub.verdicts:
        assert any(name == parameter and set(checks.split("+")) <= found for name, found in kept), (
            f"{stub.provider}: {parameter} {text} is not kept as `suspect:{checks}`"
        )
