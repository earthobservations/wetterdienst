# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the DWD phenology descriptions state what DWD's phase definitions state (GH-3136).

The source is the ``PH_Beschreibung_Phasendefinition_*.txt`` files beside the data (read 2026-10-31): for each plant
and phase the sentence that says when the phase is reached. DWD's English phase name alone, which was the whole
description, leaves out the share of the plants the date depends on, and that the flowering of a wind-pollinated tree
is the release of pollen. Each pin is a fact of those files; the files themselves are not fetched here.
"""

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.provider.dwd.phenology import metadata as phenology
from wetterdienst.provider.dwd.phenology.metadata import DwdPhenologyMetadata


def _description(dataset: str, phase: int) -> str:
    """Return the description of the phase in the dataset."""
    for parameter in DwdPhenologyMetadata["annual"][dataset].parameters:
        if parameter.name_original == str(phase):
            return parameter.description or ""
    msg = f"phase {phase} is not in {dataset}"
    raise KeyError(msg)


def test_the_share_of_the_plants_is_the_one_dwd_defines() -> None:
    """Rapeseed flowers at 5 % of its flowers, grassland greens at 25 %, rye heads at half of its stems."""
    assert "about 5% of the yellow flowers" in _description("annual_winter_oilseed_rape", 5)
    assert "about 25% of the selected permanent grassland" in _description("annual_permanent_grassland", 1)
    assert "about 50% of the stems" in _description("annual_winter_rye", 18)
    assert "about 25% of the grapes" in _description("annual_grapevine", 42)
    assert "about 95% of the flowers have shed their petals" in _description("annual_apple", 7)


def test_the_flowering_of_a_wind_pollinated_tree_is_the_release_of_pollen() -> None:
    """DWD defines the flowering of hazel, birch, alder, beech, oak, spruce and pine by their pollen."""
    for dataset in ("annual_common_hazel", "annual_silver_birch", "annual_black_alder", "annual_european_beech"):
        assert "pollen" in _description(dataset, 5), dataset
    for dataset in ("annual_pedunculate_oak", "annual_norway_spruce", "annual_scots_pine"):
        assert "pollen" in _description(dataset, 5), dataset


def test_wrong_claims_are_gone() -> None:
    """The ears are not the first ones, nothing is harvested by hand, and the seedlings are not the first."""
    assert "first" not in PARAMETERS["phenology_heading_beginning"].description
    assert "flag leaf" not in PARAMETERS["phenology_heading_beginning"].description
    assert "by hand" not in PARAMETERS["phenology_harvest_by_hand"].description
    assert "scythe" in PARAMETERS["phenology_harvest_by_hand"].description
    assert "first seedlings" not in PARAMETERS["phenology_emergence_beginning"].description
    assert "a quarter of the grassland" in PARAMETERS["phenology_turning_green_beginning"].description


def test_a_row_dwd_defines_for_no_one_keeps_its_name_alone() -> None:
    """The beet of the current year, immediate grapevine and immediate hazel's end of flowering have none."""
    assert _description("annual_beet", 10) == "Beginning of tilling sowing drilling (Bestellung Beginn)."
    assert _description("immediate_grapevine_early_ripening", 5) == "Beginning of flowering (Blüte Beginn)."
    assert _description("immediate_common_hazel", 41) == (
        "End of flowering in the observation area (Blüte Ende im Beobachtungsgebiet)."
    )


def test_every_definition_is_used_and_reads_as_a_sentence() -> None:
    """No override is left that applies to no row, and a description has no table pipe or double full stop.

    A key counts as used only if a row gets its sentence from it: a row in `_NO_DEFINITION`, or one of the
    immediate vine that DWD publishes no definition file for, applies none.
    """
    applied = set()
    for reporter, group, _stem, _plant, object_id, _periods, phases in phenology._PLANTS:  # noqa: SLF001
        for phase in phases:
            definition = phenology._definition(reporter, group, object_id, phase)  # noqa: SLF001
            assert definition is None or not definition.endswith("."), (object_id, phase)
            if definition is None:
                continue
            key = reporter[0]
            if (key, object_id, phase) in phenology._PLANT_DEFINITIONS:  # noqa: SLF001
                applied.add((key, object_id, phase))
            else:
                applied.add((object_id, phase))
    assert set(phenology._PLANT_DEFINITIONS) <= applied  # noqa: SLF001
    for dataset in DwdPhenologyMetadata["annual"].datasets:
        for parameter in dataset.parameters:
            assert "|" not in parameter.description
            assert ".." not in parameter.description


def test_winter_rye_full_ripeness_keeps_the_name_alone() -> None:
    """DWD's annual winter rye text for phase 22 is a weaker stage than rye's own yellow ripeness (phase 21)."""
    assert _description("annual_winter_rye", 22) == "Beginning of full ripeness (Vollreife Beginn)."
    assert "about half of the ears" in _description("annual_winter_rye", 21)


def test_the_immediate_reporters_have_their_own_alder_text_and_the_rule_on_the_places() -> None:
    """The immediate alder text is the bracts', not the annual catkins'; 17 immediate rows hold in 3 places only.

    "(an mind. 3 Stellen des Beobachtungsobjektes)" ends the immediate reporters' definition of these 17 rows and
    no annual one.
    """
    annual = DwdPhenologyMetadata["annual"]
    assert "bracts" in _description("immediate_black_alder", 5)
    assert "bracts" not in _description("annual_black_alder", 5)
    rows = {
        ("apple", 3),
        ("apple", 5),
        ("sweet_cherry", 5),
        ("alder_all_species", 5),
        ("ash", 5),
        ("birch_all_species", 5),
        ("black_alder", 5),
        ("black_locust", 5),
        ("blackthorn", 5),
        ("common_hazel", 5),
        ("european_beech", 4),
        ("european_beech", 5),
        ("forsythia", 5),
        ("goat_willow", 5),
        ("large_leaved_lime", 5),
        ("silver_birch", 4),
        ("silver_birch", 5),
    }
    places = "in at least 3 places of the observed plant"
    for dataset in annual.datasets:
        reporter, _, plant = dataset.name.partition("_")
        for parameter in dataset.parameters:
            held = (plant, int(parameter.name_original)) in rows
            assert (places in parameter.description) == (held and reporter == "immediate"), dataset.name


def test_a_first_picking_is_said_only_of_the_fruits_whose_text_says_it() -> None:
    """DWD names colour and ease for apple, ease for pear and gooseberry, the worth of a picking for plum."""
    assert "worthwhile" not in _description("annual_apple", 29)
    assert "colour" not in _description("annual_pear", 29)
    assert "colour" not in _description("annual_gooseberry", 29)
    assert "worthwhile" in _description("annual_plum_early_ripening", 29)
    assert "first maize kernels are yellowish" in _description("annual_maize", 20)
