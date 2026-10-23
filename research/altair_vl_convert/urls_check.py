"""Can a Vega-Lite spec make vl-convert fetch a URL, and does `allowed_base_urls=[]` stop it? (GH-3238).

    python research/altair_vl_convert/urls_check.py

The library's own specs hold all their data, so none of this is reachable through the prototype; it matters if a
spec or a URL in one ever comes from a request. A local HTTP server (in another process) serves a CSV whose one text
is `SECRET-ROW`; each way of naming the data is rendered to SVG with and without `allowed_base_urls=[]`, and the
answer says whether the text came out.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import vl_convert as vlc


def spec(url: str) -> dict:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"url": url, "format": {"type": "csv"}},
        "mark": {"type": "text", "fontSize": 20, "font": "Liberation Sans"},
        "encoding": {"text": {"field": "a", "type": "nominal"}},
        "width": 200,
        "height": 40,
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / "secret.csv").write_text("a,b\nSECRET-ROW,2\n", encoding="utf-8")
        # a server of its own process: vl-convert holds the GIL while it renders, so one in a thread never answers
        port = 8765
        server = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", directory],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        cases = {
            "http://127.0.0.1": f"http://127.0.0.1:{port}/secret.csv",
            "file:// URI": (Path(directory) / "secret.csv").as_uri(),
            "absolute path": str(Path(directory) / "secret.csv"),
        }
        for name, url in cases.items():
            for label, kwargs in (("default", {}), ("allowed_base_urls=[]", {"allowed_base_urls": []})):
                try:
                    svg = vlc.vegalite_to_svg(spec(url), **kwargs)
                    seen = "SECRET-ROW" in svg
                    print(f"{name:14s} {label:22s} rendered; data read: {seen}")  # noqa: T201
                except Exception as error:  # noqa: BLE001
                    print(f"{name:14s} {label:22s} error: {str(error).splitlines()[0][:100]}")  # noqa: T201
        server.terminate()


if __name__ == "__main__":
    main()
