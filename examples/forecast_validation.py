"""This example shows how to compare forecast data of the mosmix model with observation data. The mosmix model is
a numerical weather prediction model of the DWD. The observation data is provided by the DWD as well."""
import datetime as dt

from matplotlib import pyplot as plt

from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest


def find_observation_id(string: str) -> str:
    """Find the observation id for the given string."""
    query = f"SELECT * FROM station_data WHERE station_name LIKE '%{string}%'"  # noqa: S608
    observation_request = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="hourly",
        period="recent",
        start_date=dt.datetime.now() - dt.timedelta(days=2),
        end_date=dt.datetime.now(),
    ).filter_by_sql(query)
    return input(f"Select the observation id from {observation_request.df.get_column('station_id')}")  # noqa: S608


def get_earliest_start_issue() -> dt.datetime:
    """Get the earliest start issue for the mosmix request."""
    start_issue = dt.datetime.now() - dt.timedelta(days=2)
    if start_issue.hour < 3:
        start_issue = start_issue.replace(hour=3)
    elif start_issue.hour < 9:
        start_issue = start_issue.replace(hour=9)
    elif start_issue.hour < 15:
        start_issue = start_issue.replace(hour=15)
    elif start_issue.hour < 21:
        start_issue = start_issue.replace(hour=21)
    else:
        start_issue = start_issue.replace(hour=3) + dt.timedelta(days=1)
    return start_issue + dt.timedelta(hours=1)


def main(obs_id: str, for_id: str) -> None:
    """Compare the forecast with the observation by plotting them."""
    observation_request = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="hourly",
        period="recent",
        start_date=dt.datetime.now() - dt.timedelta(days=2),
        end_date=dt.datetime.now(),
    ).filter_by_station_id(station_id=obs_id)
    observation_values = observation_request.values.all().df
    forecast_request = DwdMosmixRequest(
        parameter="temperature_air_mean_200",
        mosmix_type="large",
        start_issue=get_earliest_start_issue(),
        start_date=dt.datetime.now() - dt.timedelta(days=2),
        end_date=dt.datetime.now(),
    ).filter_by_station_id(station_id=for_id)
    forecast_values = forecast_request.values.all().df
    merged = (
        observation_values.select(["date", "value"])
        .rename({"value": "observation"})
        .join(forecast_values.select(["date", "value"]).rename({"value": "forecast"}), on="date")
    )
    merged.to_pandas().plot(x="date", y=["observation", "forecast"], title="Forecast validation")
    plt.show()


if __name__ == "__main__":
    observation_id = "1048"
    forecast_id = "10488"
    main(observation_id, forecast_id)
