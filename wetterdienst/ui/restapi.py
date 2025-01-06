# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Literal, Union

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import ValidationError
from starlette.responses import RedirectResponse

from wetterdienst import Author, Info, Settings, Wetterdienst
from wetterdienst.core.timeseries.result import (
    _InterpolatedValuesDict,
    _InterpolatedValuesOgcFeatureCollection,
    _StationsDict,
    _StationsOgcFeatureCollection,
    _SummarizedValuesDict,
    _SummarizedValuesOgcFeatureCollection,
    _ValuesDict,
    _ValuesOgcFeatureCollection,
)
from wetterdienst.ui.core import (
    InterpolationRequest,
    InterpolationRequestRaw,
    StationsRequest,
    StationsRequestRaw,
    SummaryRequest,
    SummaryRequestRaw,
    ValuesRequest,
    ValuesRequestRaw,
    _get_stripes_stations,
    _thread_safe_plot_stripes,
    get_interpolate,
    get_stations,
    get_summarize,
    get_values,
    set_logging_level,
)
from wetterdienst.util.cli import setup_logging
from wetterdienst.util.ui import read_list

info = Info()

app = FastAPI(debug=False)

log = logging.getLogger(__name__)


REQUEST_EXAMPLES = {
    "dwd_observation_daily_climate_stations": "api/stations?provider=dwd&network=observation&parameters=daily/kl&periods=recent&all=true",  # noqa:E501
    "dwd_observation_daily_climate_values": "api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&station=00011",  # noqa:E501
    "dwd_observation_daily_climate_interpolation": "api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_summary": "api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_stripes_stations": "api/stripes/stations?kind=temperature",
    "dwd_observation_daily_climate_stripes_values": "api/stripes/values?kind=temperature&station=1048",
}


@app.get("/", response_class=HTMLResponse)
def index():
    def _create_author_entry(author: Author):
        # create author string Max Mustermann (Github href, Mailto)
        return f"{author.name} (<a href='https://github.com/{author.github_handle}' target='_blank' rel='noopener'>github</a>, <a href='mailto:{author.email}'>mail</a>)"  # noqa:E501

    title = f"{info.slogan} | {info.name}"
    sources = []

    for provider in Wetterdienst.registry.keys():
        # take the first network api
        first_network = list(Wetterdienst.registry[provider].keys())[0]
        api = Wetterdienst(provider, first_network)
        shortname = api.metadata.name_short
        name = api.metadata.name_english
        country = api.metadata.country
        copyright_ = api.metadata.copyright
        url = api.metadata.url
        sources.append(
            f"<li><a href={url} target='_blank' rel='noopener'>{shortname}</a> ({name}, {country}) - {copyright_}</li>",
        )
    sources = "\n".join(sources)
    return f"""
    <html lang="en">
        <head>
            <title>{title}</title>
            <meta name="description" content="{info.name} - {info.slogan}">
            <meta name="keywords" content="weather, climate, data, api, open, source, wetterdienst">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                }}

                header {{
                    background-color: #0074d9;
                    text-align: center;
                    padding: 20px;
                }}

                h1, h2 {{
                    color: #333;
                }}

                h2 {{
                    border-top: 1px solid #ccc;
                    padding-top: 20px;
                }}

                li {{
                    margin-bottom: 10px;
                }}

                a {{
                    text-decoration: none;
                    color: #0074d9;
                }}

                a:hover {{
                    text-decoration: underline;
                }}

                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}

                .box {{
                    margin-left: 20px;
                }}

                .list {{
                    display: flex;
                    flex-wrap: wrap;
                    list-style: none;
                    flex-direction: column;
                }}

                .list li {{
                    margin-left: 20px;
                    text-align: left;
                }}

            </style>
        </head>
        <body>
            <div class="container">
                <h1>{info.slogan}</h1>
                <h2>Endpoints</h2>
                <div class="list">
                    <li><a href="api/coverage" target="_blank" rel="noopener">coverage</a></li>
                    <li><a href="api/stations" target="_blank" rel="noopener">stations</a></li>
                    <li><a href="api/values" target="_blank" rel="noopener">values</a></li>
                    <li><a href="api/interpolate" target="_blank" rel="noopener">interpolation</a></li>
                    <li><a href="api/summarize" target="_blank" rel="noopener">summary</a></li>
                    <li><a href="api/stripes/stations" target="_blank" rel="noopener">stripes stations</a></li>
                    <li><a href="api/stripes/values" target="_blank" rel="noopener">stripes values</a></li>
                </div>
                <h2>Examples</h2>
                <div class="list">
                    <li><a href="{REQUEST_EXAMPLES['dwd_observation_daily_climate_stations']}" target="_blank" rel="noopener">DWD Observation Daily Climate Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES['dwd_observation_daily_climate_values']}" target="_blank" rel="noopener">DWD Observation Daily Climate Values</a></li>
                    <li><a href="{REQUEST_EXAMPLES['dwd_observation_daily_climate_interpolation']}" target="_blank" rel="noopener">DWD Observation Daily Climate Interpolation</a></li>
                    <li><a href="{REQUEST_EXAMPLES['dwd_observation_daily_climate_summary']}" target="_blank" rel="noopener">DWD Observation Daily Climate Summary</a></li>
                    <li><a href="{REQUEST_EXAMPLES['dwd_observation_daily_climate_stripes_stations']}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES['dwd_observation_daily_climate_stripes_values']}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Values</a></li>
                </div>
                <h2>Producer</h2>
                <div class="List">
                    <li>Version: {info.version}</li>
                    <li>Authors: {', '.join(_create_author_entry(author) for author in info.authors)}</li>
                    <li>Repository: <a href="{info.repository}" target="_blank" rel="noopener">{info.repository}</a></li>
                    <li>Documentation: <a href="{info.documentation}" target="_blank" rel="noopener">{info.documentation}</a></li>
                </div>
                <h2>Providers</h2>
                <div class="list">
                    {sources}
                </div>
            </div>
        </body>
    </html>
    """  # noqa:B950,E501


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return """
User-agent: *
Disallow: /api/
    """.strip()


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(
        url="https://raw.githubusercontent.com/earthobservations/wetterdienst/refs/heads/main/docs/assets/logo.png"
    )


@app.get("/api/coverage")
def coverage(
    provider: str | None = None,
    network: str | None = None,
    resolutions: str = None,
    datasets: str = None,
    pretty: bool = False,
    debug: bool = False,
):
    set_logging_level(debug)

    if (provider and not network) or (not provider and network):
        raise HTTPException(
            status_code=400,
            detail="Either both or none of 'provider' and 'network' must be given. If none are given, all providers "
            "and networks are returned.",
        )

    if not provider and not network:
        cov = Wetterdienst.discover()
        return Response(content=json.dumps(cov, indent=4), media_type="application/json")

    try:
        api = Wetterdienst(provider, network)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e

    if resolutions:
        resolutions = read_list(resolutions)

    if datasets:
        datasets = read_list(datasets)

    cov = api.discover(
        resolutions=resolutions,
        datasets=datasets,
    )

    return Response(content=json.dumps(cov, indent=4 if pretty else None), media_type="application/json")


# response models for the different formats are
# - _StationsDict for json
# - _StationsOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/stations", response_model=Union[_StationsDict, _StationsOgcFeatureCollection, str])
def stations(request: Annotated[StationsRequestRaw, Query()]) -> Any:
    # parse list-like parameters into lists
    try:
        request = StationsRequest.model_validate(request.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    set_logging_level(request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e

    try:
        stations_ = get_stations(
            api=api,
            request=request,
            date=None,
            settings=Settings(),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    content = stations_.to_format(fmt=request.format, with_metadata=True, indent=request.pretty)

    if request.format == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _ValuesDict for json
# - _ValuesOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/values", response_model=Union[_ValuesDict, _ValuesOgcFeatureCollection, str])
def values(
    request: Annotated[ValuesRequestRaw, Query()],
) -> Any:
    try:
        request = ValuesRequest.model_validate(request.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    set_logging_level(request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        ) from e

    settings = Settings(
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
        ts_shape=request.shape,
        ts_humanize=request.humanize,
        ts_skip_empty=request.skip_empty,
        ts_skip_criteria=request.skip_criteria,
        ts_skip_threshold=request.skip_threshold,
        ts_drop_nulls=request.drop_nulls,
    )

    try:
        values_ = get_values(
            api=api,
            request=request,
            settings=settings,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=str(e)) from e

    content = values_.to_format(fmt=request.format, with_metadata=True, indent=request.pretty)

    if request.format == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _InterpolatedValuesDict for json
# - _InterpolatedValuesOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/interpolate",
    response_model=Union[_InterpolatedValuesDict, _InterpolatedValuesOgcFeatureCollection, str],
)
def interpolate(request: Annotated[InterpolationRequestRaw, Query()]) -> Any:
    """Wrapper around get_interpolate to provide results via restapi"""
    try:
        request = InterpolationRequest.model_validate(request.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    set_logging_level(request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        ) from e

    settings = Settings(
        ts_humanize=request.humanize,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
        ts_interpolation_station_distance=request.interpolation_station_distance,
        ts_interpolation_use_nearby_station_distance=request.use_nearby_station_distance,
    )

    try:
        values_ = get_interpolate(
            api=api,
            request=request,
            settings=settings,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=404, detail=str(e)) from e

    content = values_.to_format(fmt=request.format, with_metadata=True, indent=request.pretty)

    if request.format == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _SummarizedValuesDict for json
# - _SummarizedValuesOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/summarize", response_model=Union[_SummarizedValuesDict, _SummarizedValuesOgcFeatureCollection, str])
def summarize(
    request: Annotated[SummaryRequestRaw, Query()],
) -> Any:
    """Wrapper around get_summarize to provide results via restapi"""
    try:
        request = SummaryRequest.model_validate(request.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    set_logging_level(request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        ) from e

    settings = Settings(
        ts_humanize=request.humanize,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
    )

    try:
        values_ = get_summarize(
            api=api,
            request=request,
            settings=settings,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=404, detail=str(e)) from e

    content = values_.to_format(fmt=request.format, with_metadata=True, indent=request.pretty)

    if request.format == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/stations")
def stripes_stations(
    kind: Annotated[Literal["temperature", "precipitation"], Query()],
    active: Annotated[bool, Query()] = True,
    fmt: Annotated[Literal["json", "geojson", "csv"], Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    """Wrapper around get_climate_stripes_temperature_request to provide results via restapi"""
    set_logging_level(debug)

    try:
        stations = _get_stripes_stations(kind=kind, active=active)
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    content = stations.to_format(fmt=fmt, with_metadata=True, indent=pretty)
    if fmt == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"
    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/values")
def stripes_values(
    kind: Annotated[Literal["temperature", "precipitation"], Query()],
    station: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    start_year: Annotated[int | None, Query()] = None,
    end_year: Annotated[int | None, Query()] = None,
    name_threshold: Annotated[float, Query()] = 0.9,
    show_title: Annotated[bool, Query()] = True,
    show_years: Annotated[bool, Query()] = True,
    show_data_availability: Annotated[bool, Query()] = True,
    fmt: Annotated[Literal["png", "jpg", "svg", "pdf"], Query(alias="format")] = "png",
    dpi: Annotated[int, Query(gt=0)] = 300,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    """Wrapper around get_summarize to provide results via restapi"""
    set_logging_level(debug)

    if not station and not name:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'station' or 'name' is required",
        )
    if station and name:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'station' and 'name' are mutually exclusive",
        )
    if start_year and end_year:
        if start_year >= end_year:
            raise HTTPException(
                status_code=400,
                detail="Query argument 'start_year' must be less than 'end_year'",
            )
    if name_threshold < 0 or name_threshold > 1:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'name_threshold' must be between 0.0 and 1.0",
        )

    try:
        buf = _thread_safe_plot_stripes(
            kind=kind,
            station_id=station,
            name=name,
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
            show_title=show_title,
            show_years=show_years,
            show_data_availability=show_data_availability,
            fmt=fmt,
            dpi=dpi,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    media_type = f"image/{fmt}"
    return Response(content=buf.getvalue(), media_type=media_type)


def start_service(listen_address: str | None = None, reload: bool | None = False):  # pragma: no cover
    from uvicorn.main import run

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload)
