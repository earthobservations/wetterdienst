"""This example shows how to compare forecast data of the mosmix model with observation data. The mosmix model is
a numerical weather prediction model of the DWD. The observation data is provided by the DWD as well."""

import datetime as dt
from zoneinfo import ZoneInfo

from matplotlib import pyplot as plt

from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest


def find_observation_id(string: str) -> str:
    """Find the observation id for the given string."""
    query = f"SELECT * FROM station_data WHERE station_name LIKE '%{string}%'"  # noqa: S608
    observation_request = DwdObservationRequest(
        parameters=("hourly", "temperature_air", "temperature_air_mean_2m"),
        periods="recent",
        start_date=dt.datetime.now() - dt.timedelta(days=2),
        end_date=dt.datetime.now(),
    ).filter_by_sql(query)
    return input(f"Select the observation id from {observation_request.df.get_column('station_id')}")  # noqa: S608


def get_earliest_issue() -> dt.datetime:
    """Get the earliest start issue for the mosmix request."""
    issue = dt.datetime.now(ZoneInfo("UTC")) - dt.timedelta(days=2)
    if issue.hour < 3:
        issue = issue.replace(hour=3)
    elif issue.hour < 9:
        issue = issue.replace(hour=9)
    elif issue.hour < 15:
        issue = issue.replace(hour=15)
    elif issue.hour < 21:
        issue = issue.replace(hour=21)
    else:
        issue = issue.replace(hour=3) + dt.timedelta(days=1)
    return issue


def main(obs_id: str, for_id: str) -> None:
    """Compare the forecast with the observation by plotting them."""
    forecast_request = DwdMosmixRequest(
        parameters=("hourly", "large", "temperature_air_mean_2m"),
        start_date=dt.datetime.now() - dt.timedelta(days=2),
        end_date=dt.datetime.now(),
        issue=get_earliest_issue(),
    ).filter_by_station_id(station_id=for_id)
    print(forecast_request.df)
    forecast_values = forecast_request.values.all()
    print(forecast_values.df)
    observation_request = DwdObservationRequest(
        parameters=("hourly", "temperature_air", "temperature_air_mean_2m"),
        periods="recent",
        start_date=dt.datetime.now() - dt.timedelta(days=2),
        end_date=dt.datetime.now(),
    ).filter_by_station_id(station_id=obs_id)
    print(observation_request.df)
    observation_values = observation_request.values.all()
    print(observation_values.df)
    df_joined = (
        forecast_values.df.select(["date", "value"])
        .rename({"value": "forecast"})
        .join(observation_values.df.select(["date", "value"]).rename({"value": "observation"}), on="date")
    )
    df_joined.to_pandas().plot(x="date", y=["observation", "forecast"], title="Forecast validation")
    plt.show()


if __name__ == "__main__":
    observation_id = "1048"
    forecast_id = "10488"
    main(observation_id, forecast_id)
