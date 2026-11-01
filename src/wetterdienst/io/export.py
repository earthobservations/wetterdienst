# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Export data to various formats."""

from __future__ import annotations

import inspect
import logging
import os
from abc import abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal, Self

import polars as pl

from wetterdienst.exceptions import ImageTooLargeError
from wetterdienst.io.file_metadata import write_sidecar
from wetterdienst.io.formats import find_format, refuse_unknown_arguments
from wetterdienst.io.sinks import join_list_columns, write_to_target
from wetterdienst.io.sql_filter import filter_by_sql
from wetterdienst.metadata.renamed import RefusesRenamedMembers
from wetterdienst.util.datetime import timestamps_to_string
from wetterdienst.util.extras import import_optional
from wetterdienst.util.json_util import dumps_json
from wetterdienst.util.url import ConnectionString, redact_password

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import plotly.graph_objs as go

log = logging.getLogger(__name__)


#: how a chart written as html carries plotly.js: inline (`True`, about 4.8 MB, and the page works offline) or from the
#: CDN (`"cdn"`, a few kilobytes). Inline unless the request is an MCP tool's, whose answer an assistant reads (GH-3464)
HTML_PLOTLYJS: ContextVar[bool | str] = ContextVar("wetterdienst_html_plotlyjs", default=True)


def figure_to_html(fig: go.Figure) -> str:
    """Write a figure as an html page, with plotly.js as `HTML_PLOTLYJS` says."""
    return fig.to_html(include_plotlyjs=HTML_PLOTLYJS.get())


#: the size plotly renders a figure at when neither the figure nor the caller names one
_DEFAULT_IMAGE_WIDTH, _DEFAULT_IMAGE_HEIGHT = 700, 500


def check_image_size(
    fig: go.Figure, width: int | None, height: int | None, scale: float | None, max_side: int | None
) -> None:
    """Raise `ImageTooLargeError` when the image of `fig` would have a side over `max_side` pixels.

    Measured as the browser will paint it: a size the caller gives wins over the figure's own, which
    wins over plotly's default, and `scale` multiplies the result. Nothing is checked without
    `max_side`, which is what the library and the CLI do.
    """
    if max_side is None:
        return
    factor = 1 if scale is None else scale
    rendered_width = (width or fig.layout.width or _DEFAULT_IMAGE_WIDTH) * factor
    rendered_height = (height or fig.layout.height or _DEFAULT_IMAGE_HEIGHT) * factor
    if max(rendered_width, rendered_height) > max_side:
        raise ImageTooLargeError(rendered_width, rendered_height, max_side)


def require_kaleido() -> None:
    """Say what to install where Kaleido, which renders a plotly figure as an image, is not.

    Plotly raises a `RuntimeError` with its own advice from `Figure.to_image`, which the command
    line prints as a traceback and the REST API answers with a 500. Asked for first, its absence is
    a `MissingDependencyError`, as that of every other package an extra installs.
    """
    import_optional("kaleido", "Rendering an image", extra="plotting")


def _taken_by(method: Callable[..., object], kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Pick the arguments `method` takes by name out of `kwargs`, all of them for one that takes any."""
    parameters = inspect.signature(method).parameters
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return dict(kwargs)
    return {name: value for name, value in kwargs.items() if name in parameters}


@dataclass(frozen=True, kw_only=True)
class ExportMixin(RefusesRenamedMembers):
    """Postprocessing data.

    This aids in collecting, filtering, formatting and emitting data acquired through the core machinery.

    A result is frozen: nothing assigns to it once it is built, and a filter hands back a new result
    (`filtered_by_sql`) instead of changing the one it was asked on.
    """

    df: pl.DataFrame

    def filtered_by_sql(self, sql: str) -> Self:
        """Filter the frame with the WHERE clause of an SQL query and return a new result of it.

        This result is left as it is.
        """
        return replace(self, df=filter_by_sql(self.df, sql))

    # The three formatters below are declared as narrowly as every subclass keeps them: each takes
    # `with_metadata` (and may take more, keyword-only with a default) and returns a mapping, which a
    # TypedDict is and a `dict` is not. A wider declaration made every subclass an invalid override.
    # None of the formatters takes an argument it does not know: an unknown keyword is a `TypeError`
    # (GH-3043), and `to_format` is what picks the arguments of the one it calls.
    @abstractmethod
    def to_dict(self, *, with_metadata: bool = False) -> Mapping[str, object]:
        """Convert station information into dictionary format."""

    @abstractmethod
    def to_json(self, *, with_metadata: bool = False, indent: int | bool | None = 4) -> str:
        """Convert station information into JSON format."""

    @abstractmethod
    def to_ogc_feature_collection(self, *, with_metadata: bool = False) -> Mapping[str, object]:
        """Convert station information into OGC Feature Collection format.

        Abstract method implementation.
        """

    def to_geojson(self, *, with_metadata: bool = False, indent: int | bool | None = 4) -> str:
        """Convert station information into GeoJSON format.

        Args:
            with_metadata: Include metadata in GeoJSON
            indent: Indentation level for JSON output

        Returns:
            GeoJSON string

        """
        if indent is True:
            indent = 4
        elif indent is False:
            indent = None
        return dumps_json(
            self.to_ogc_feature_collection(with_metadata=with_metadata), indent=indent, ensure_ascii=False
        )

    def _flatten(self) -> pl.DataFrame:
        """Render the frame in the shape the flat formats take it.

        Timestamps as ISO strings and list columns joined, which is what a format without a notion
        of either needs. `to_csv` did this for itself while the CSV file target did not, so
        `--target=file://out.csv` failed on an interpolation with `CSV format does not support
        nested data` where `--format=csv` wrote the same data out fine.
        """
        return join_list_columns(self._iso_datetimes())

    def _iso_datetimes(self) -> pl.DataFrame:
        """Render every timestamp the frame carries as an ISO string."""
        return timestamps_to_string(self.df)

    def to_csv(self, *, with_metadata: bool = False, **kwargs: Any) -> str:  # noqa: ANN401
        """Convert DataFrame to CSV format.

        The CSV is bare: a CSV has no place for the licence, the credit line and the date of its data. `with_metadata`
        writes them beside the file, as `<file>.metadata.json`, holding the `metadata` block of the REST API.

        Args:
            with_metadata: Write `<file>.metadata.json` beside the file `file` names. It needs `file`: a string has no
                file to write the sidecar beside.
            **kwargs: Additional arguments passed to the CSV writer

        Returns:
            CSV string

        Raises:
            ValueError: `with_metadata` without `file` being the path of a file.
            ExportRefusedError: `with_metadata` for a result that has no provider to describe.

        """
        if with_metadata and not isinstance(kwargs.get("file"), str | os.PathLike):
            msg = "with_metadata writes the metadata beside the CSV file: give the path of the file as `file`"
            raise ValueError(msg)
        csv = self._flatten().write_csv(**kwargs)
        if with_metadata:
            write_sidecar(self, kwargs["file"])
        return csv

    def to_ndjson(self) -> str:
        """Convert the rows to NDJSON: one JSON object per line, the records of the frame and no envelope.

        What the `.jsonl` and `.ndjson` file targets hold, and the records of the lines the REST API and the command
        line send between their `metadata` and `end` lines. The records are the same; the text of a number need not
        be, as polars writes `0.00005` where `json.dumps` writes `5e-05`. Timestamps are ISO strings and a list stays
        a list.

        Returns:
            NDJSON string, a line of every row and none for a frame without rows

        """
        return self._iso_datetimes().write_ndjson()

    @abstractmethod
    def to_plot(self) -> go.Figure:
        """Create a plotly figure from the DataFrame."""

    @abstractmethod
    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        max_side: int | None = None,
    ) -> bytes | str:
        """Create an image from the plotly figure."""

    def to_image(self, **kwargs: Any) -> bytes | str:  # noqa: ANN401
        """Create an image from the plotly figure.

        Args:
            **kwargs: The arguments of the image creation method: `fmt`, `width`, `height`, `scale`
                and `max_side`. Any other is a `TypeError`.

        Returns:
            Image data as bytes or string

        """
        return self._to_image(**kwargs)

    def to_format(self, fmt: str, **kwargs: Any) -> str | bytes:  # noqa: ANN401
        """Format data according to the specified format.

        The formatting is done by one of the following methods:
        - `to_json`
        - `to_csv`
        - `to_geojson`
        - `to_ndjson`
        - `to_image`

        The one set of arguments a caller builds for every format (`with_metadata`, `indent`,
        `width`, ...) is given, and each formatter is passed those it takes: `indent` is not passed
        to a chart, `width` not to JSON, and CSV is given none. An argument that no format takes is refused with a
        `TypeError` listing the ones that are, so a typo is no more silent here than in the method that is called
        (GH-3043).

        Args:
            fmt: Output format, in any case: one of the formats of `wetterdienst.io.formats.FORMATS`
            **kwargs: Arguments for the formatting method, of which it is given those it takes

        Returns:
            Formatted data

        Raises:
            UnknownFormatError: Nothing renders `fmt`. It is a `KeyError` and a `ValueError`.
            TypeError: An argument that is the name of none of the arguments any format takes.

        """
        format_ = find_format(fmt)
        refuse_unknown_arguments(kwargs)

        if format_.kind == "chart":
            return self.to_image(fmt=format_.name, **_taken_by(self._to_image, kwargs))
        formatter = getattr(self, format_.method)
        # `to_csv` passes its keywords to polars, so it is given none
        return formatter(**_taken_by(formatter, kwargs)) if format_.takes else formatter()

    def to_target(
        self,
        target: str,
        if_exists: Literal["replace", "append", "fail", "skip"] = "replace",
        *,
        with_metadata: bool = False,
    ) -> None:
        """Emit data to a target.

        The target is identified by a connection string.

        Examples:
        - duckdb:///dwd.duckdb?table=weather
        - influxdb://localhost/?database=dwd&table=weather
        - crate://localhost/?database=dwd&table=weather

        Dispatch data to different data sinks. Currently, SQLite, DuckDB,
        InfluxDB and CrateDB are implemented. However, through the SQLAlchemy
        layer, it should actually work with any supported SQL database.

        - https://docs.sqlalchemy.org/en/13/dialects/

        Args:
            target: Connection string
            if_exists: Behavior when the target already exists. Options: 'replace', 'append', 'fail', 'skip'.
                Default is 'replace', as a result is one frame written as a whole; `TimeseriesValues.to_target`
                defaults to 'fail', as it fills one table station by station.
                - 'replace': Drop and recreate the target (default, backward compatible)
                - 'append': Append data to the target
                - 'fail': Raise error if target exists
                - 'skip': Do not write if target exists (only for supported backends)
            with_metadata: Write the `metadata` block of the REST API beside a file target, as `<file>.metadata.json`,
                with the unit of every parameter and what `quality_flags` holds. A Parquet file, a NetCDF file and a
                Zarr group carry the licence, the credit line and the date of the data themselves, always, in their
                key-value metadata and attributes (`with_metadata` adds those heavy parts to them); the other files
                are bare without it. Only a file target has a file to write it beside.

        Raises:
            ExportRefusedError: The sink will not perform this export -- a mode it does not
                do, a target already holding data under ``if_exists='fail'``, a format or
                protocol nothing here writes, a target that cannot be read, such as one whose
                password holds an unencoded ``@``, or ``with_metadata`` for a target that is not
                a file, or for a result that has no provider to describe.

        Returns:
            None (data is emitted to the target)

        """
        # read once, and before anything is logged: a target its sink cannot read is refused
        # here, with a message that names no part of it
        connspec = ConnectionString(target)

        log.info(f"Exporting records to {redact_password(target)}\n{self.df.select(pl.len())}")

        write_to_target(self, target, connspec, if_exists, with_metadata=with_metadata)
