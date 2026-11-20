# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The answer of `/api/radar/frames`: the loop of DWD's precipitation radar, with what an image of it needs (GH-3788).

The list says which frames there are (`time`, the `run` they are read from, `observation` or `forecast`), where the
image of a frame lies (its bounds in WGS84, which a Leaflet `ImageOverlay` takes as they are, and the projection the
image is in) and the legend of its colours: the numbers, so that a page can write them out and not only show them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from typing_extensions import TypedDict

from wetterdienst.provider.dwd.radar.frames import format_instant
from wetterdienst.provider.dwd.radar.rv import RAIN_CLASSES, RATE_UNIT, STEP_MINUTES
from wetterdienst.ui.response_metadata import ResponseMetadata, metadata_to_dict, radar_metadata
from wetterdienst.util.json_util import dumps_json

if TYPE_CHECKING:
    from wetterdienst.provider.dwd.radar.frames import RadarFrameList


class RadarBounds(TypedDict):
    """The bounds of an image in WGS84 degrees: its outer edges."""

    west: float
    south: float
    east: float
    north: float


class RadarImageInfo(TypedDict):
    """Where the image of a frame lies and how it is made."""

    #: the projection the image is in: pixels are square in it, and `bounds` are its edges
    crs: Literal["EPSG:3857"]
    bounds: RadarBounds
    width: int
    height: int
    media_type: Literal["image/png"]


class RadarLegendClass(TypedDict):
    """A class of the legend: a colour and the rates it stands for."""

    #: the rate in mm/h from which the class holds, and under which the one above it begins (null for the highest)
    lower: float
    upper: float | None
    color: str
    label: str


class RadarLegend(TypedDict):
    """The legend of the colours of the frames, lightest (lowest rate) first."""

    unit: str
    #: what is left transparent: a rate under it, and no data
    transparent_below: float
    classes: list[RadarLegendClass]


class RadarProduct(TypedDict):
    """The product the frames are of."""

    id: str
    name: str
    #: the minutes between two frames
    step_minutes: int
    unit: str


class RadarFrameEntry(TypedDict):
    """A frame: when it is valid, which run it is read from, and whether it is observed or forecast."""

    #: the UTC time the precipitation of the frame ends at
    time: str
    #: the UTC time of the run of DWD the frame is read from: the `run` of the request for its image
    run: str
    #: the minutes between the run and the time: 0 for the radar analysis
    lead_minutes: int
    kind: Literal["observation", "forecast"]


class RadarFramesWithMetadataDict(TypedDict):
    """The list of the frames of DWD's precipitation radar."""

    metadata: ResponseMetadata
    product: RadarProduct
    #: the UTC time of the newest run, the last of the observed frames and the one the forecast is from
    run: str
    image: RadarImageInfo
    legend: RadarLegend
    #: the frames, the oldest first: the analysis, then the forecast
    frames: list[RadarFrameEntry]


def legend() -> RadarLegend:
    """Give the legend of the frames: the classes of `RAIN_CLASSES`, in mm/h."""
    return {
        "unit": RATE_UNIT,
        "transparent_below": RAIN_CLASSES[0].lower,
        "classes": [{"lower": c.lower, "upper": c.upper, "color": c.color, "label": c.label} for c in RAIN_CLASSES],
    }


def render_radar_frames(listing: RadarFrameList, *, pretty: bool = False) -> tuple[str, ResponseMetadata]:
    """Write the list of the frames as JSON with the `metadata` block."""
    metadata = radar_metadata(len(listing.frames), image=False)
    image = listing.image
    answer = {
        "metadata": metadata_to_dict(metadata),
        "product": {"id": "rv", "name": "RV composite", "step_minutes": STEP_MINUTES, "unit": RATE_UNIT},
        "run": format_instant(listing.run),
        "image": {
            "crs": "EPSG:3857",
            "bounds": {"west": image.west, "south": image.south, "east": image.east, "north": image.north},
            "width": image.width,
            "height": image.height,
            "media_type": "image/png",
        },
        "legend": legend(),
        "frames": [
            {
                "time": format_instant(frame.time),
                "run": format_instant(frame.run),
                "lead_minutes": frame.lead_minutes,
                "kind": frame.kind,
            }
            for frame in listing.frames
        ],
    }
    return dumps_json(answer, indent=4 if pretty else None, ensure_ascii=False), metadata
