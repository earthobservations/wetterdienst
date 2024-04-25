import polars as pl
import streamlit as st

from wetterdienst import Period, __version__
from wetterdienst.ui.core import _get_warming_stripes_request, _thread_safe_plot_warming_stripes


@st.cache_data
def get_stations(active: bool = True):
    df = _get_warming_stripes_request(period=Period.HISTORICAL).all().df
    if active:
        station_ids_active = _get_warming_stripes_request(period=Period.RECENT).all().df.select("station_id")
        df = df.join(station_ids_active, on="station_id")
    return df


@st.cache_data
def get_warming_stripes(
    station_id: str,
    start_year: int,
    end_year: int,
    name_threshold: int,
    show_title: bool,
    show_years: bool,
    show_data_availability: bool,
    dpi: int,
):
    return _thread_safe_plot_warming_stripes(
        request=_get_warming_stripes_request(),
        station_id=station_id,
        start_year=start_year,
        end_year=end_year,
        name_threshold=name_threshold,
        show_title=show_title,
        show_years=show_years,
        show_data_availability=show_data_availability,
        fmt="png",
        dpi=dpi,
    )


def get_rest_api_url(
    station_id: str,
    start_year: int,
    end_year: int,
    name_threshold: int,
    show_title: bool,
    show_years: bool,
    show_data_availability: bool,
    dpi: int,
):
    url = f"https://wetterdienst.eobs.org/api/warming_stripes?station={station_id}"
    url += f"&start_year={start_year}" if start_year else ""
    url += f"&end_year={end_year}" if end_year else ""
    url += f"&name_threshold={name_threshold}" if name_threshold else ""
    url += f"&show_title={show_title}" if show_title else ""
    url += f"&show_years={show_years}" if show_years else ""
    url += f"&show_data_availability={show_data_availability}" if show_data_availability else ""
    url += f"&dpi={dpi}" if dpi else ""
    return url


title = f"Warming Stripes (v{__version__})"
st.set_page_config(page_title=title)
st.title(title)

st.markdown(f"version refers to Wetterdienst  v{__version__}")

with st.sidebar:
    st.header("Settings")

    st.subheader("Data")

    start_year = st.number_input("Start year", value=None, step=1)
    end_year = st.number_input("End year", min_value=start_year + 1 if start_year else None, value=None, step=1)
    name_threshold = st.number_input("Name threshold", min_value=0.0, max_value=1.0, value=0.9, step=0.1)
    use_only_active_stations = st.checkbox("Use only active stations", value=True)

    st.subheader("Settings")

    show_title = st.checkbox("Show title", value=True)
    show_years = st.checkbox("Show years", value=True)
    show_data_availability = st.checkbox("Show data availability", value=True)
    dpi = st.number_input("DPI", min_value=100, max_value=300, value=300, step=1)

st.subheader("Introduction")
st.markdown(
    """
    This app visualizes the warming stripes for a given German temperature station. The warming stripes are a data
    visualization showing the change in temperature over time. Each stripe represents the temperature of a single year,
    ordered from the earliest available data to the most recent. The color scale represents the temperature, with blue
    stripes representing cooler years and red stripes representing warmer years. The data is being acquired with
    [wetterdienst](https://github.com/earthobservations/wetterdienst).
    """
)

df_stations = get_stations(active=use_only_active_stations)
with st.expander("Map of all stations", expanded=False):
    st.map(df_stations, latitude="latitude", longitude="longitude")

st.subheader("Station")
station = st.selectbox(
    "Select climate station",
    options=df_stations.sort("name").rows(named=True),
    format_func=lambda s: f"{s['name']} [{s['station_id']}]",
)
df = pl.DataFrame()
if station:
    station["start_date"] = station["start_date"].isoformat() if station["start_date"] else None
    station["end_date"] = station["end_date"].isoformat() if station["end_date"] else None
    with st.expander("Station JSON", expanded=False):
        st.json(station)
    with st.expander("Map of selected station", expanded=False):
        st.map(
            df_stations.filter(pl.col("station_id").eq(station["station_id"])),
            latitude="latitude",
            longitude="longitude",
        )
    buf = get_warming_stripes(
        station_id=station["station_id"],
        start_year=start_year,
        end_year=end_year,
        name_threshold=name_threshold,
        show_title=show_title,
        show_years=show_years,
        show_data_availability=show_data_availability,
        dpi=dpi,
    )
    st.subheader("Warming Stripes")
    st.image(buf, use_column_width=True)
    st.download_button("Download", buf, file_name="warming_stripes.png", mime="image/png", use_container_width=True)
    st.link_button(
        "Static URL",
        get_rest_api_url(
            station_id=station["station_id"],
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
            show_title=show_title,
            show_years=show_years,
            show_data_availability=show_data_availability,
            dpi=dpi,
        ),
        use_container_width=True,
    )

st.subheader("Credits")
st.markdown(
    """
    This app is powered by [wetterdienst](https://github.com/earthobservations/wetterdienst) from
    [earthobservations](https://github.com/earthobservations) developers.

    Credits for the data go to
    [Deutscher Wetterdienst](https://www.dwd.de) - Germany's national meteorological service - and
    [others](https://wetterdienst.readthedocs.io/en/latest/data/coverage.html) for publishing their data as
    **open data**.

    Credits also go to [streamlit](https://streamlit.io/) for hosting this
    app.

    Special credits go to [Fridays for Future Freiburg](https://www.s4f-freiburg.de/temperaturstreifen/) who had
    provided the simple but yet powerful lines of code.

    If you have any issues or ideas regarding this app, please let us know in the
    [issues](https://github.com/earthobservations/wetterdienst/issues) on Github.
    """,
)
