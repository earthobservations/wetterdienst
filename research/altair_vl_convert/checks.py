"""The open points of GH-3238, each a small check that prints what it found.

    python research/altair_vl_convert/checks.py <check>

`polars` and `rowlimit` need only `altair`, `vl-convert-python` and `polars` (run them in an environment without
pandas, pyarrow and numpy to see what Altair needs); the others use the prototype and so the library. Checks:

- `polars`: a polars frame goes into Altair, to a spec and to a PNG, and which of pandas, pyarrow and numpy got
  imported on the way;
- `rowlimit`: the 5,000 rows of Altair's default data transformer, and four ways round it;
- `html`: the size of the HTML of the same chart from Plotly and from Altair, at three row counts;
- `fonts`: which fonts vl-convert draws with, and whether the PNG depends on the system's; the lines that print the
  same digest as `NoSuchFontXYZ` are families that are not there, which vl-convert draws as no text at all, and
  `NoSuch, sans-serif` (a list) as `sans-serif`;
- `urls`: see `urls_check.py`, which needs a server of its own process;
- `determinism`: the same chart rendered twice, in two processes and with another time zone, byte for byte;
- `fork`: a render in a child process forked after one in the parent;
- `gil`: whether another Python thread runs while vl-convert renders (the longest gap of a thread that wakes every
  10 ms, against the duration of the render);
- `gil_matplotlib`: the same while matplotlib draws the values chart of 10 years;
- `profile`: where the time of an Altair image of 10 years of values goes, as records and as CSV text;
- `huge`: the time and memory of an image of many pixels, which the REST API caps (`_MAX_IMAGE_SIDE`).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()[:12]


def _frame(n: int):  # noqa: ANN202
    import datetime as dt  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    start = dt.datetime(2016, 1, 1, tzinfo=dt.UTC)
    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(start, start + dt.timedelta(hours=n - 1), "1h", eager=True),
            "value": [float(i % 17) for i in range(n)],
        }
    )


def check_polars() -> None:
    import altair as alt  # noqa: PLC0415
    import polars as pl  # noqa: PLC0415
    import vl_convert as vlc  # noqa: PLC0415

    df = _frame(500).with_columns(pl.lit("00433").alias("station_id"))
    chart = alt.Chart(df).mark_line().encode(x="timestamp:T", y="value:Q", color="station_id:N")
    spec = chart.to_dict()
    png = vlc.vegalite_to_png(spec)
    print(
        json.dumps(
            {
                "altair": alt.__version__,
                "polars": pl.__version__,
                "spec_rows": len(spec["datasets"][spec["data"]["name"]]),
                "png_bytes": len(png),
                "first_row": spec["datasets"][spec["data"]["name"]][0],
            }
        )
    )  # noqa: T201
    print(json.dumps({m: m in sys.modules for m in ("pandas", "pyarrow", "numpy", "narwhals")}))  # noqa: T201


def check_rowlimit() -> None:
    import altair as alt  # noqa: PLC0415
    import polars as pl  # noqa: PLC0415
    import vl_convert as vlc  # noqa: PLC0415

    def attempt(label: str, make) -> None:  # noqa: ANN001
        t = time.perf_counter()
        try:
            spec = make()
            png = vlc.vegalite_to_png(spec)
            print(f"{label:58s} ok   {time.perf_counter() - t:6.2f} s  {len(png) // 1024} KiB png")  # noqa: T201
        except Exception as error:  # noqa: BLE001
            print(f"{label:58s} {type(error).__name__}: {str(error).splitlines()[0][:90]}")  # noqa: T201

    for n in (5000, 5001, 87_600):
        df = _frame(n)
        enc = {"x": alt.X("timestamp:T", scale=alt.Scale(type="utc")), "y": "value:Q"}
        print(f"--- {n} rows")  # noqa: T201
        attempt("alt.Chart(polars_frame).to_dict()", lambda: alt.Chart(df).mark_line().encode(**enc).to_dict())

        def disable() -> dict:
            with alt.data_transformers.disable_max_rows():
                return alt.Chart(df).mark_line().encode(**enc).to_dict()

        attempt("with alt.data_transformers.disable_max_rows(): ...", disable)

        def records() -> dict:
            rows = df.with_columns(pl.col("timestamp").dt.strftime("%Y-%m-%dT%H:%M:%SZ")).to_dicts()
            return alt.Chart(alt.Data(values=rows)).mark_line().encode(**enc).to_dict()

        attempt("alt.Data(values=list of records)", records)

        def text() -> dict:
            csv = df.with_columns(pl.col("timestamp").dt.strftime("%Y-%m-%dT%H:%M:%SZ")).write_csv()
            data = alt.InlineData(
                values=csv, format=alt.CsvDataFormat(type="csv", parse={"timestamp": "date", "value": "number"})
            )
            return alt.Chart(data).mark_line().encode(**enc).to_dict()

        attempt("alt.InlineData(values=csv text)", text)
    print("data_transformers after all of it:", alt.data_transformers.active)  # noqa: T201


def check_html() -> None:
    import altair as alt  # noqa: PLC0415
    import plotly.express as px  # noqa: PLC0415
    import polars as pl  # noqa: PLC0415

    for n in (744, 8_760, 87_600):
        df = _frame(n)
        fig = px.line(df, x="timestamp", y="value")
        csv = df.with_columns(pl.col("timestamp").dt.strftime("%Y-%m-%dT%H:%M:%SZ")).write_csv()
        data = alt.InlineData(
            values=csv, format=alt.CsvDataFormat(type="csv", parse={"timestamp": "date", "value": "number"})
        )
        chart = alt.Chart(data).mark_line().encode(x=alt.X("timestamp:T", scale=alt.Scale(type="utc")), y="value:Q")
        print(  # noqa: T201
            json.dumps(
                {
                    "rows": n,
                    "plotly_default_bytes": len(fig.to_html()),
                    "plotly_cdn_bytes": len(fig.to_html(include_plotlyjs="cdn")),
                    "altair_default_bytes": len(chart.to_html()),
                    "altair_inline_bytes": len(chart.to_html(inline=True)),
                }
            )
        )


def check_fonts() -> None:
    import vl_convert as vlc  # noqa: PLC0415

    def png(font: str) -> bytes:
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": [{"a": 1}]},
            "mark": {"type": "text", "text": "Hamburg Fuhlsbüttel 1781 gjpqy", "fontSize": 24, "font": font},
            "encoding": {"x": {"datum": 1, "type": "quantitative", "axis": None}},
            "width": 420,
            "height": 40,
        }
        return vlc.vegalite_to_png(spec)

    base = png("sans-serif")
    print("sans-serif       ", digest(base))  # noqa: T201
    for font in (
        "Liberation Sans",
        "Arial",
        "Helvetica",
        "DejaVu Sans",
        "Open Sans",
        "Menlo",
        "SF Pro Text",
        "NoSuchFontXYZ",
        "NoSuchFontXYZ, sans-serif",
        "NoSuchFontXYZ, Liberation Sans",
    ):
        same = "= sans-serif" if digest(png(font)) == digest(base) else ""
        print(f"{font:31s}", digest(png(font)), same)  # noqa: T201


def _render_subject() -> dict[str, str]:
    sys.path.insert(0, str(ROOT))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import to_image  # noqa: PLC0415

    stripes = data.stripes()
    values = data.values(start="2025-12-01", end="2025-12-31", station_ids=("00433", "00403"), parameters=2)
    return {
        "stripes.png": digest(to_image(stripes, engine="altair", fmt="png")),
        "stripes.svg": digest(to_image(stripes, engine="altair", fmt="svg")),
        "stripes.pdf": digest(to_image(stripes, engine="altair", fmt="pdf")),
        "values.png": digest(to_image(values, engine="altair", fmt="png")),
        "values.svg": digest(to_image(values, engine="altair", fmt="svg")),
    }


def check_determinism() -> None:
    first = _render_subject()
    second = _render_subject()
    print(
        "same process, twice: ",
        "identical" if first == second else {k: (first[k], second[k]) for k in first if first[k] != second[k]},
    )  # noqa: T201
    results = {"this process": first}
    for tz in ("UTC", "America/Los_Angeles", "Asia/Kolkata"):
        out = subprocess.run(  # noqa: S603
            [sys.executable, __file__, "determinism-child"],
            env={**os.environ, "TZ": tz},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        results[f"new process, TZ={tz}"] = json.loads(out.strip().splitlines()[-1])
    for label, digests in results.items():
        print(
            f"{label:34s} {'identical to the first' if digests == first else {k: v for k, v in digests.items() if v != first[k]}}"
        )  # noqa: T201


def check_fork() -> None:
    import vl_convert as vlc  # noqa: PLC0415

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": [{"a": 1, "b": 2}]},
        "mark": "point",
        "encoding": {"x": {"field": "a", "type": "quantitative"}, "y": {"field": "b", "type": "quantitative"}},
    }
    vlc.vegalite_to_png(spec)
    # a pool of workers that is forked after the parent rendered (gunicorn `--preload`, multiprocessing's fork)
    pid = os.fork()
    if pid == 0:
        try:
            vlc.vegalite_to_png(spec)
            os._exit(0)
        except BaseException as error:  # noqa: BLE001
            print("child:", type(error).__name__, str(error).replace("\n", " ")[:200], flush=True)  # noqa: T201
            os._exit(1)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            print("child after fork: exit status", os.waitstatus_to_exitcode(status))  # noqa: T201
            return
        time.sleep(0.2)
    os.kill(pid, 9)
    print("child after fork: no answer in 60 s (killed)")  # noqa: T201


def check_profile() -> None:
    """Where the time of an Altair image of 10 years of hourly values goes: building the spec, or drawing it."""
    import altair as alt  # noqa: PLC0415
    import vl_convert as vlc  # noqa: PLC0415

    sys.path.insert(0, str(ROOT))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import _iso, values_chart_altair, values_frame  # noqa: PLC0415

    values = data.values(start="2016-01-01", end="2025-12-31")

    def timed(label: str, fn):  # noqa: ANN001, ANN202
        t = time.perf_counter()
        result = fn()
        print(f"{label:52s}{time.perf_counter() - t:7.2f} s")  # noqa: T201
        return result

    # the records: a list of 87,000 dicts in `alt.Data`
    def records():  # noqa: ANN202
        frame, _ = values_frame(values)
        data_ = alt.Data(values=_iso(frame).to_dicts())
        base = alt.Chart(data_).mark_line(point=True).encode(x="timestamp:T", y="value:Q", color="station_id:N")
        return base.properties(width=560, height=260).facet(row="facet:N").resolve_scale(y="independent")

    chart = timed("records: build (to_dicts + Altair objects)", records)
    spec = timed("records: chart.to_dict() validated", chart.to_dict)
    timed("records: chart.to_dict(validate=False)", lambda: chart.to_dict(validate=False))
    timed("records: vegalite_to_png of the spec", lambda: vlc.vegalite_to_png(spec))
    chart = timed("CSV text (the prototype): build", lambda: values_chart_altair(values))
    spec = timed("CSV text: chart.to_dict() validated", chart.to_dict)
    timed("CSV text: vegalite_to_png of the spec", lambda: vlc.vegalite_to_png(spec))


def check_gil() -> None:
    import threading  # noqa: PLC0415

    import vl_convert as vlc  # noqa: PLC0415

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"sequence": {"start": 0, "stop": 60000, "as": "x"}},
        "transform": [{"calculate": "sin(datum.x / 300) * 50 + random() * 5", "as": "y"}],
        "mark": {"type": "point", "size": 4},
        "encoding": {"x": {"field": "x", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}},
        "width": 800,
        "height": 400,
    }
    vlc.vegalite_to_png(spec)
    gaps: list[float] = []
    stop = threading.Event()

    def beat() -> None:
        last = time.perf_counter()
        while not stop.is_set():
            time.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    thread = threading.Thread(target=beat)
    thread.start()
    t = time.perf_counter()
    vlc.vegalite_to_png(spec)
    took = time.perf_counter() - t
    stop.set()
    thread.join()
    print(f"render {took:.2f} s; the other thread woke {len(gaps)} times, longest gap {max(gaps):.2f} s")  # noqa: T201


def check_gil_matplotlib() -> None:
    """The same heartbeat as `gil`, while matplotlib draws the values chart of 10 years."""
    import threading  # noqa: PLC0415

    sys.path.insert(0, str(ROOT))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import render_matplotlib, values_figure_mpl  # noqa: PLC0415

    values = data.values(start="2016-01-01", end="2025-12-31")
    gaps: list[float] = []
    stop = threading.Event()

    def beat() -> None:
        last = time.perf_counter()
        while not stop.is_set():
            time.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    figure = values_figure_mpl(values)
    render_matplotlib(figure, "png")
    thread = threading.Thread(target=beat)
    thread.start()
    t = time.perf_counter()
    render_matplotlib(figure, "png")
    took = time.perf_counter() - t
    stop.set()
    thread.join()
    print(f"render {took:.2f} s; the other thread woke {len(gaps)} times, longest gap {max(gaps):.2f} s")  # noqa: T201


def check_huge() -> None:
    import psutil  # noqa: PLC0415

    sys.path.insert(0, str(ROOT))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import render_altair, stripes_chart_altair  # noqa: PLC0415

    chart = stripes_chart_altair(data.stripes())
    process = psutil.Process()
    # 11.7 is the largest scale the REST API lets through for 700 px: 8,190 px
    for scale in (1, 3, 8, 11.7):
        t = time.perf_counter()
        before = process.memory_info().rss
        png = render_altair(chart, "png", scale)
        after = process.memory_info().rss
        print(
            f"scale {scale:6.2f} ({700 * scale:6.0f} x {500 * scale:6.0f} px): {time.perf_counter() - t:6.2f} s, {len(png) // 1024} KiB, rss {before // 2**20} -> {after // 2**20} MiB"
        )  # noqa: T201


if __name__ == "__main__":
    name = sys.argv[1]
    if name == "determinism-child":
        print(json.dumps(_render_subject()))  # noqa: T201
    else:
        globals()[f"check_{name}"]()
