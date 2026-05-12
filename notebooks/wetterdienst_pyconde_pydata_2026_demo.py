# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "marimo>=0.10.0",
#   "duckdb",
#   "polars",
#   "pyarrow",
#   "altair>=5.1.0",
# ]
# ///

import marimo

__generated_with = "0.12.0"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        r"""
        # DWD Daily Climate Summary — Germany

        A Marimo notebook exploring weather stations from the [DWD (Deutscher Wetterdienst)](https://www.dwd.de/) 
        `climate_summary` dataset.

        | | |
        |---|---|
        | **Data** | Entire `climate_summary` dataset (daily resolution) |
        | **Format** | DuckDB file (~1 GB) |
        | **Download** | [Proton Drive](https://drive.proton.me/urls/V4Z9EQP53W#Cyt7m3nAlxFU) |

        ## ▶ How to run

        ```bash
        # Interactive edit mode
        uv run marimo edit notebooks/wetterdienst_pyconde_pydata_2026_demo.py

        # Read-only presentation mode
        uv run marimo run notebooks/wetterdienst_pyconde_pydata_2026_demo.py
        ```
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## How the database was created

        The DuckDB file was built using **wetterdienst** — fetching all stations for the
        `climate_summary` dataset and exporting each result directly to DuckDB:

        ```python
        from wetterdienst.provider.dwd.observation import DwdObservationRequest
        from wetterdienst import Settings

        request = DwdObservationRequest(
            parameters=[("daily", "climate_summary")],
        ).all()

        # export station metadata
        request.to_target(
            "duckdb://wetterdienst_pyconde_pydata_2026_demo.duckdb?table=stations",
            if_exists="replace",
        )

        # export all daily values station by station
        for result in request.values.query():
            result.to_target(
                "duckdb://wetterdienst_pyconde_pydata_2026_demo.duckdb?table=values",
                if_exists="append",
            )
        ```
        """
    )
    return


@app.cell
def _():
    import altair as alt
    import duckdb
    import marimo as mo
    import polars as pl

    return alt, duckdb, mo, pl


@app.cell
def _(duckdb):
    DB_PATH = "/Users/benjamin/Library/Application Support/JetBrains/PyCharm2026.1/scratches/wetterdienst_pyconde_pydata_2026_demo.duckdb"
    con = duckdb.connect(DB_PATH, read_only=True)
    return DB_PATH, con


@app.cell
def _(mo):
    mo.md("# 🗼 Station Network")
    return


@app.cell
def _(con, mo):
    _total = con.execute("SELECT count(*) FROM stations").fetchone()[0]
    _start_min, _start_max = con.execute("SELECT min(start_date)::date, max(start_date)::date FROM stations").fetchone()
    _active = con.execute("""
        SELECT count(DISTINCT station_id) FROM "values"
        WHERE year(date) = 2024
    """).fetchone()[0]

    mo.hstack(
        [
            mo.stat(value=f"{_total:,}", label="Total Stations"),
            mo.stat(value=f"{_active:,}", label="Currently Active"),
            mo.stat(value=f"{_start_min} – {_start_max}", label="First–Latest Station"),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    mo.md("### Network Growth Over Time")
    return


@app.cell
def _(alt, con):
    def _make_map(df, title):
        return (
            alt.Chart(df)
            .mark_circle(size=10, opacity=0.75)
            .encode(
                x=alt.X(
                    "longitude:Q",
                    scale=alt.Scale(domain=[5.5, 15.5]),
                    axis=alt.Axis(title=None, labels=False, ticks=False, grid=False),
                ),
                y=alt.Y(
                    "latitude:Q",
                    scale=alt.Scale(domain=[47.0, 55.5]),
                    axis=alt.Axis(title=None, labels=False, ticks=False, grid=False),
                ),
                color=alt.Color(
                    "active:N",
                    scale=alt.Scale(domain=["active", "inactive"], range=["#2ca02c", "#aec7e8"]),
                    legend=alt.Legend(title="Status"),
                ),
                order=alt.Order("active:N", sort="descending"),
                tooltip=[
                    "name:N",
                    "state:N",
                    alt.Tooltip("start_date:T", title="Since", format="%Y"),
                    "active:N",
                ],
            )
            .properties(title=title, width=430, height=520)
        )

    _active_ids = {
        r[0] for r in con.execute('SELECT DISTINCT station_id FROM "values" WHERE year(date) = 2024').fetchall()
    }

    def _with_active(query):
        df = con.execute(query).pl()
        return df.with_columns(
            active=df["station_id"].map_elements(
                lambda sid: "active" if sid in _active_ids else "inactive",
                return_dtype=__import__("polars").String,
            )
        )

    _df_1900 = _with_active(
        "SELECT station_id, name, state, latitude, longitude, start_date FROM stations WHERE start_date <= '1900-12-31'"
    )
    _df_1950 = _with_active(
        "SELECT station_id, name, state, latitude, longitude, start_date FROM stations WHERE start_date <= '1950-12-31'"
    )
    _df_1980 = _with_active(
        "SELECT station_id, name, state, latitude, longitude, start_date FROM stations WHERE start_date <= '1980-12-31'"
    )
    _df_all = _with_active("SELECT station_id, name, state, latitude, longitude, start_date FROM stations")

    _active_1900 = (_df_1900["active"] == "active").sum()
    _active_1950 = (_df_1950["active"] == "active").sum()
    _active_1980 = (_df_1980["active"] == "active").sum()
    _active_all = (_df_all["active"] == "active").sum()

    alt.vconcat(
        alt.hconcat(
            _make_map(_df_1900, f"By 1900 · {len(_df_1900)} stations · {_active_1900} still active"),
            _make_map(_df_1950, f"By 1950 · {len(_df_1950)} stations · {_active_1950} still active"),
        ),
        alt.hconcat(
            _make_map(_df_1980, f"By 1980 · {len(_df_1980)} stations · {_active_1980} still active"),
            _make_map(_df_all, f"Today · {len(_df_all)} stations · {_active_all} active in 2024"),
        ),
    ).resolve_scale(x="shared", y="shared", color="shared")
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ### Impact of War on the Network

        Active stations per year (stations with at least one measurement) clearly shows both wars:
        - **WWI (1914–1918)**: modest dip from ~66 to ~59 active stations
        - **WWII (1939–1945)**: growth halted, sharp drop to 128 active stations in 1945 —
          followed by the fastest expansion in the network's history
        """
    )
    return


@app.cell
def _(alt, con):
    _df = con.execute("""
        SELECT
            date_trunc('year', date)::date AS year,
            count(DISTINCT station_id) AS active_stations
        FROM "values"
        WHERE date < '2025-01-01'
        GROUP BY year
        ORDER BY year
    """).pl()

    _wars = alt.Data(
        values=[
            {"start": "1914-07-01", "end": "1918-11-30", "war": "WWI"},
            {"start": "1939-09-01", "end": "1945-05-31", "war": "WWII"},
        ]
    )

    _decline = alt.Data(values=[{"start": "2000-01-01", "end": "2024-12-31"}])

    _bands = (
        alt.Chart(_wars)
        .mark_rect(opacity=0.15, color="red")
        .encode(
            x=alt.X("start:T"),
            x2=alt.X2("end:T"),
        )
    )

    _decline_band = (
        alt.Chart(_decline)
        .mark_rect(opacity=0.1, color="orange")
        .encode(
            x=alt.X("start:T"),
            x2=alt.X2("end:T"),
        )
    )

    _labels = (
        alt.Chart(_wars)
        .mark_text(align="left", dx=4, dy=-8, color="red", fontSize=11, fontWeight="bold")
        .encode(
            x=alt.X("start:T"),
            y=alt.value(0),
            text=alt.Text("war:N"),
        )
    )

    _decline_label = (
        alt.Chart(_decline)
        .mark_text(align="left", dx=4, dy=-8, color="orange", fontSize=11, fontWeight="bold", angle=270)
        .encode(
            x=alt.X("start:T"),
            y=alt.value(300),
            text=alt.value(["Decline of voluntary observers", "& takeover of automatic measurements"]),
        )
    )

    _line = (
        alt.Chart(_df)
        .mark_area(line={"color": "#1f77b4"}, opacity=0.3, color="#1f77b4")
        .encode(
            x=alt.X("year:T", title="Year"),
            y=alt.Y("active_stations:Q", title="Active Stations"),
            tooltip=[
                alt.Tooltip("year:T", title="Year", format="%Y"),
                alt.Tooltip("active_stations:Q", title="Active stations", format=","),
            ],
        )
    )

    (_bands + _decline_band + _labels + _decline_label + _line).properties(
        title="Active Stations per Year", width=700, height=320
    )
    return


@app.cell
def _(con, mo):
    _total_rows = con.execute('SELECT count(*) FROM "values"').fetchone()[0]
    _total_stations = con.execute('SELECT count(DISTINCT station_id) FROM "values"').fetchone()[0]
    _date_min, _date_max = con.execute('SELECT min(date)::date, max(date)::date FROM "values"').fetchone()
    _total_params = con.execute('SELECT count(DISTINCT parameter) FROM "values"').fetchone()[0]

    mo.hstack(
        [
            mo.stat(value=f"{_total_stations:,}", label="Stations"),
            mo.stat(value=f"{_total_params}", label="Parameters"),
            mo.stat(value=f"{_total_rows:,}", label="Total Records"),
            mo.stat(value=f"{_date_min} – {_date_max}", label="Date Range"),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    mo.md("# 📊 Values")
    return


@app.cell
def _(mo):
    mo.md("## Date Coverage per Parameter")
    return


@app.cell
def _(alt, con):
    _df = con.execute("""
        SELECT
            parameter,
            min(date)::date AS first_date,
            max(date)::date AS last_date,
            count(DISTINCT station_id) AS stations,
            datediff('year', min(date)::date, max(date)::date) AS years_covered
        FROM "values"
        GROUP BY parameter
        ORDER BY first_date
    """).pl()

    alt.Chart(_df).mark_bar(height=20).encode(
        y=alt.Y(
            "parameter:N",
            sort=alt.EncodingSortField(field="first_date", order="ascending"),
            title=None,
            axis=alt.Axis(labelLimit=200),
        ),
        x=alt.X("first_date:T", title="Date"),
        x2=alt.X2("last_date:T"),
        color=alt.Color(
            "years_covered:Q",
            scale=alt.Scale(scheme="blues"),
            legend=alt.Legend(title="Years covered"),
        ),
        tooltip=[
            "parameter:N",
            alt.Tooltip("first_date:T", title="From"),
            alt.Tooltip("last_date:T", title="To"),
            alt.Tooltip("years_covered:Q", title="Years covered"),
            alt.Tooltip("stations:Q", title="Stations", format=","),
        ],
    ).properties(title="Date Coverage per Parameter", width=700, height=340)
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Temperature Change Over Germany

        Daily anomalies relative to each station's **1961–1990 climatological baseline**
        (mean temperature per calendar day per station). Two quality filters are applied:

        - **Baseline**: a station's day-of-year baseline is only used if it has ≥ 24 of the
          30 reference years available (WMO-No. 1203 ≥ 80 % completeness threshold)
        - **Yearly coverage**: a station only contributes to a given year if it reported
          values for ≥ 90 % of that year's days

        Anomalies from all qualifying stations are then averaged per year.
        The orange line is a 10-year centred rolling mean.
        """
    )
    return


@app.cell
def _(alt, con):
    _df = con.execute("""
        WITH baseline AS (
            -- mean temperature per station per calendar day over 1961-1990
            -- only use station+doy combos with at least 20 of the 30 reference years
            SELECT
                station_id,
                dayofyear(date) AS doy,
                avg(value)      AS baseline_mean
            FROM "values"
            WHERE parameter = 'temperature_air_mean_2m'
              AND date BETWEEN '1961-01-01' AND '1990-12-31'
            GROUP BY station_id, doy
            HAVING count(DISTINCT year(date)) >= 24
        ),
        station_year_coverage AS (
            -- keep only station+year combos with >= 90% day coverage
            SELECT
                station_id,
                year(date)  AS yr,
                count(*)    AS days_present,
                CASE WHEN year(date) % 4 = 0 AND (year(date) % 100 != 0 OR year(date) % 400 = 0)
                     THEN 366 ELSE 365 END AS days_in_year
            FROM "values"
            WHERE parameter = 'temperature_air_mean_2m'
              AND date < '2025-01-01'
            GROUP BY station_id, yr
            HAVING days_present >= 0.9 * days_in_year
        ),
        anomalies AS (
            SELECT
                date_trunc('year', v.date)::date AS year,
                avg(v.value - b.baseline_mean)   AS mean_anomaly,
                count(DISTINCT v.station_id)      AS stations
            FROM "values" v
            JOIN baseline b
              ON v.station_id = b.station_id AND dayofyear(v.date) = b.doy
            JOIN station_year_coverage s
              ON v.station_id = s.station_id AND year(v.date) = s.yr
            WHERE v.parameter = 'temperature_air_mean_2m'
              AND v.date < '2025-01-01'
            GROUP BY year
        )
        SELECT
            year,
            round(mean_anomaly, 4)   AS anomaly,
            stations,
            round(avg(mean_anomaly) OVER (
                ORDER BY year
                ROWS BETWEEN 4 PRECEDING AND 5 FOLLOWING
            ), 4) AS rolling_10y
        FROM anomalies
        ORDER BY year
    """).pl()

    _zero = (
        alt.Chart(alt.Data(values=[{"y": 0}]))
        .mark_rule(color="black", opacity=0.3, strokeWidth=1)
        .encode(y=alt.Y("y:Q"))
    )

    _bars = (
        alt.Chart(_df)
        .mark_bar(width=2)
        .encode(
            x=alt.X("year:T", title="Year"),
            y=alt.Y("anomaly:Q", title="Temperature anomaly (°C)"),
            color=alt.condition(
                "datum.anomaly >= 0",
                alt.value("#d62728"),
                alt.value("#1f77b4"),
            ),
            tooltip=[
                alt.Tooltip("year:T", title="Year", format="%Y"),
                alt.Tooltip("anomaly:Q", title="Anomaly (°C)", format=".2f"),
                alt.Tooltip("stations:Q", title="Stations", format=","),
            ],
        )
    )

    _rolling = (
        alt.Chart(_df)
        .mark_line(color="#ff7f0e", strokeWidth=2.5)
        .encode(
            x=alt.X("year:T"),
            y=alt.Y("rolling_10y:Q"),
            tooltip=[alt.Tooltip("rolling_10y:Q", title="10-yr mean (°C)", format=".2f")],
        )
    )

    (_zero + _bars + _rolling).properties(
        title="Annual Mean Temperature Anomaly — Germany (baseline 1961–1990)",
        width=700,
        height=360,
    )
    return


@app.cell
def _(mo):
    mo.md("## Record Values")
    return


@app.cell
def _(con, mo):
    mo.md("### Top 10 Highest Precipitation")
    return


@app.cell
def _(con, mo):
    _df = con.execute("""
        SELECT
            v.date::date  AS date,
            v.station_id,
            s.name        AS station,
            s.state,
            v.value       AS precipitation_height_mm,
            v.quality
        FROM "values" v
        JOIN stations s USING (station_id)
        WHERE v.parameter = 'precipitation_height'
          AND v.value IS NOT NULL
        ORDER BY v.value DESC
        LIMIT 10
    """).pl()
    mo.ui.table(_df)


@app.cell
def _(mo):
    mo.md(
        """
        ## White Christmas — A Disappearing Tradition

        For each year, we count the share of active stations that recorded **snow on the ground
        on December 24th–26th** (`snow_depth > 0` on any of the three days).
        reporting stations removes the network-growth bias and leaves a clean climate signal.
        """
    )
    return


@app.cell
def _(alt, con, mo):
    _df = con.execute("""
        SELECT
            year(date)                                                          AS year,
            count(DISTINCT CASE WHEN value > 0 THEN station_id END)            AS stations_with_snow,
            count(DISTINCT station_id)                                          AS stations_reporting,
            100.0 * count(DISTINCT CASE WHEN value > 0 THEN station_id END)
                  / count(DISTINCT station_id)                                  AS pct_white_christmas
        FROM "values"
        WHERE parameter = 'snow_depth'
          AND month(date) = 12
          AND day(date) BETWEEN 24 AND 26
          AND year(date) BETWEEN 1950 AND 2024
        GROUP BY year(date)
        ORDER BY year
    """).pl()

    _bars = (
        alt.Chart(_df)
        .mark_bar(color="#aec6e8", opacity=0.7)
        .encode(
            x=alt.X("year:Q", title=None, axis=alt.Axis(format="d")),
            y=alt.Y("pct_white_christmas:Q", title="Stations with snow on any of 24–26 Dec (%)"),
            tooltip=[
                alt.Tooltip("year:Q", title="Year"),
                alt.Tooltip("pct_white_christmas:Q", title="% white", format=".1f"),
                alt.Tooltip("stations_with_snow:Q", title="Stations with snow"),
                alt.Tooltip("stations_reporting:Q", title="Stations reporting"),
            ],
        )
    )

    _trend = (
        alt.Chart(_df)
        .mark_line(color="#d62728", strokeWidth=2.5)
        .transform_regression("year", "pct_white_christmas")
        .encode(
            x="year:Q",
            y="pct_white_christmas:Q",
        )
    )

    (_bars + _trend).properties(
        title="Share of German Weather Stations Reporting a White Christmas (24–26 Dec, 1950–2024)",
        width=700,
        height=350,
    )


@app.cell
def _(mo):
    mo.md(
        """
        ## Your Birthday Weather

        Enter your birthday below to see the mean temperature recorded across Germany
        on that calendar day for every year of your life. Red bars = warmer than your
        personal birthday average, blue = cooler. The dashed trend line shows whether
        your birthdays have been warming over time.
        """
    )
    return


@app.cell
def _(mo):
    import datetime as _dt

    birthday = mo.ui.date(value=_dt.date(1990, 6, 15), label="Your birthday")
    birthday
    return (birthday,)


@app.cell
def _(alt, birthday, con, mo):
    _month = birthday.value.month
    _day = birthday.value.day
    _birth_year = birthday.value.year

    _df = con.execute(
        """
        SELECT
            year(date)  AS year,
            avg(value)  AS mean_temp
        FROM "values"
        WHERE parameter = 'temperature_air_mean_2m'
          AND month(date) = ?
          AND day(date)   = ?
          AND year(date) >= ?
          AND value IS NOT NULL
        GROUP BY year(date)
        ORDER BY year
    """,
        [_month, _day, _birth_year],
    ).pl()

    _avg = float(_df["mean_temp"].mean())
    _max_year = int(_df["year"].max())
    _n = _max_year - _birth_year + 1

    _bars = (
        alt.Chart(_df)
        .mark_bar()
        .encode(
            x=alt.X("year:Q", title=None, axis=alt.Axis(format="d")),
            y=alt.Y("mean_temp:Q", title="Mean Temperature (°C)"),
            color=alt.condition(
                alt.datum.mean_temp > _avg,
                alt.value("#d62728"),
                alt.value("#4292c6"),
            ),
            tooltip=[
                alt.Tooltip("year:Q", title="Year"),
                alt.Tooltip("mean_temp:Q", title="Temp (°C)", format=".1f"),
            ],
        )
    )

    _trend = (
        alt.Chart(_df)
        .mark_line(color="black", strokeWidth=2, strokeDash=[5, 3])
        .transform_regression("year", "mean_temp")
        .encode(
            x="year:Q",
            y="mean_temp:Q",
        )
    )

    mo.vstack(
        [
            mo.md(
                f"**{birthday.value.strftime('%B %d')}** across your {_n} birthdays — lifetime average {_avg:.1f} °C"
            ),
            (_bars + _trend).properties(
                title=f"Temperature on Your Birthday ({birthday.value.strftime('%B %d')}) — Germany",
                width=700,
                height=350,
            ),
        ]
    )


@app.cell
def _(mo):
    mo.md("# 🔍 Custom Query")
    return


@app.cell
def _(mo):
    sql_query = mo.ui.code_editor(
        value='SELECT * FROM stations LIMIT 10',
        language="sql",
        label="SQL Query",
    )
    sql_query
    return (sql_query,)


@app.cell
def _(con, mo, sql_query):
    import traceback as _tb

    try:
        _result = con.execute(sql_query.value).pl()
        _out = mo.vstack([
            mo.md(f"_{len(_result):,} rows returned_"),
            mo.ui.table(_result),
        ])
    except Exception:
        _out = mo.callout(mo.md(f"```\n{_tb.format_exc()}\n```"), kind="danger")
    _out


if __name__ == "__main__":
    app.run()
