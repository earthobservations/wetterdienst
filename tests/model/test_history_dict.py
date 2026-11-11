# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The OpenAPI document describes a history by the TypedDicts of `model/result.py`, as `History` dumps one (GH-3908).

A route's `response_model` only describes the answer (it is sent as `history_to_dict` makes it), so what keeps the
document true is these tests: each record of the document has the fields of the pydantic record it stands for, and a
history dumped as the routes send it reads back through the document's model.
"""

import datetime as dt
import types
import typing

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from tests.model.test_history_result import KLOTZSCHE, _stations
from wetterdienst.model.history import (
    History,
    _DeviceHistory,
    _GeographyHistory,
    _MissingDataHistory,
    _MissingPeriod,
    _MissingSummary,
    _NameHistory,
    _OperatorName,
    _ParameterHistory,
    _StationName,
)
from wetterdienst.model.result import (
    _HistoryDevice,
    _HistoryDict,
    _HistoryEntry,
    _HistoryGeography,
    _HistoryMissing,
    _HistoryMissingData,
    _HistoryNames,
    _HistoryOperatorName,
    _HistoryParameter,
    _HistoryStationName,
    history_to_dict,
)

#: the record of the document and the pydantic record it describes, which the document spells with text for a stamp
PAIRS: list[tuple[type, type[BaseModel]]] = [
    (_HistoryStationName, _StationName),
    (_HistoryOperatorName, _OperatorName),
    (_HistoryNames, _NameHistory),
    (_HistoryParameter, _ParameterHistory),
    (_HistoryDevice, _DeviceHistory),
    (_HistoryGeography, _GeographyHistory),
    (_HistoryMissing, _MissingSummary),
    (_HistoryMissing, _MissingPeriod),
    (_HistoryMissingData, _MissingDataHistory),
    (_HistoryEntry, History),
]


@pytest.mark.parametrize(("document", "model"), PAIRS, ids=lambda pair: pair.__name__)
def test_a_record_of_the_document_has_the_fields_of_its_model(document: type, model: type[BaseModel]) -> None:
    """Every field of a `History` record is in the document's record and the other way round, with its null."""
    described = typing.get_type_hints(document, include_extras=True)
    assert list(described) == list(model.model_fields)
    for name, field in model.model_fields.items():
        # the sections of a history are the ones a request can leave out, so they are not required in the document
        if typing.get_origin(described[name]) is typing.NotRequired:
            continue
        # null in the one is null in the other, a stamp being text in the document
        assert _is_nullable(described[name]) == _is_nullable(field.annotation), name
        # and the same base type: `int` against `float` passes a read back with `==`, so it is compared here
        assert _base_type(described[name]) == _base_type(field.annotation), name


def _is_nullable(annotation: object) -> bool:
    return type(None) in typing.get_args(annotation)


def _base_type(annotation: object) -> object:
    """Give the type a field holds without its null, as the document spells it.

    A stamp (`datetime`) is text there, and a record is the TypedDict that stands for the model (`PAIRS`).
    """
    if typing.get_origin(annotation) is typing.NotRequired:
        (annotation,) = typing.get_args(annotation)
    if typing.get_origin(annotation) in {typing.Union, types.UnionType}:
        (annotation,) = (arg for arg in typing.get_args(annotation) if arg is not type(None))
    if typing.get_origin(annotation) is list:
        (item,) = typing.get_args(annotation)
        return (list, _base_type(item))
    if annotation is dt.datetime:
        return str
    return {model: document for document, model in PAIRS}.get(annotation, annotation)


def _full_history() -> History:
    """Make a history with a record in every section, the optional fields once set and once null."""
    start = dt.datetime(1926, 5, 1, tzinfo=dt.UTC)
    end = dt.datetime(1934, 1, 1, tzinfo=dt.UTC)
    return History(
        station_id=KLOTZSCHE,
        resolution="daily",
        dataset="climate_summary",
        name=_NameHistory(
            station=[_StationName(station_id=KLOTZSCHE, station_name="A", valid_from=start, valid_to=None)],
            operator=[_OperatorName(station_id=KLOTZSCHE, operator_name="B", valid_from=start, valid_to=end)],
        ),
        parameter=[
            _ParameterHistory(station_id=KLOTZSCHE, valid_from=start, valid_to=end, station_name="A", parameter="TMK"),
            _ParameterHistory(
                station_id=KLOTZSCHE,
                valid_from=start,
                valid_to=end,
                station_name="A",
                parameter="TMK",
                description="d",
                unit="u",
                data_source="s",
                extra_info="e",
                special="x",
                literature="l",
            ),
        ],
        device=[
            _DeviceHistory(station_id=KLOTZSCHE, valid_from=start, valid_to=end),
            _DeviceHistory(
                device_type="Thermometer",
                station_id=KLOTZSCHE,
                station_name="A",
                longitude=13.7,
                latitude=51.1,
                station_elevation=228.0,
                device_height=2.0,
                valid_from=start,
                valid_to=end,
                method="m",
            ),
        ],
        geography=[
            _GeographyHistory(station_id=KLOTZSCHE, valid_from=start),
            _GeographyHistory(
                station_id=KLOTZSCHE,
                station_elevation=228.0,
                latitude=51.1,
                longitude=13.7,
                valid_from=start,
                valid_to=end,
                station_name="A",
            ),
        ],
        missing_data=_MissingDataHistory(
            summary=[_MissingSummary(station_id=KLOTZSCHE, parameter="TMK", valid_from=start, valid_to=end)],
            periods=[
                _MissingPeriod(
                    station_id=KLOTZSCHE,
                    station_name="A",
                    parameter="TMK",
                    valid_from=start,
                    valid_to=end,
                    missing_count=3,
                    description="d",
                )
            ],
        ),
    )


@pytest.mark.parametrize("sections", [None, {"name"}, {"parameter", "device"}, {"geography"}, {"missing_data"}])
def test_a_dumped_history_reads_back_through_the_document_model(sections: set[str] | None) -> None:
    """The history as the routes send it, whatever the sections asked for, is what the document says of it."""
    histories = [_full_history(), _full_history().model_copy(update={"resolution": None, "dataset": None})]
    data = history_to_dict(_stations(), histories, with_metadata=False, with_stations=True, sections=sections)

    # strict, so that no field is read back as another type (`2.0` as an `int`, which `==` does not tell)
    validated = TypeAdapter(_HistoryDict).validate_python(data, strict=True)

    # reading it back changes nothing: not a value, not the order of the keys
    assert validated == data
    assert [list(history) for history in validated["histories"]] == [list(history) for history in data["histories"]]


def test_a_field_the_document_does_not_know_is_refused() -> None:
    """`extra="forbid"`: a field added to `History` and not to the document fails here and not in a client."""
    data = history_to_dict(_stations(), [_full_history()], sections={"geography"})
    data["histories"][0]["geography"][0]["new_field"] = 1  # ty: ignore[invalid-key]

    with pytest.raises(ValidationError):
        TypeAdapter(_HistoryDict).validate_python(data)
