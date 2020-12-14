import pandas as pd
from io import BytesIO
from requests_ftp.ftp import FTPSession
from wetterdienst.util.cache import payload_cache_twelve_hours


class ECCCAdapter:
    """
    Download weather data from Environment and Climate Change Canada (ECCC).
    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    def get_stations(self):
        """
        Retrieve all ECCC stations as sane Pandas data frame.
        Column names are lowercase, without any spaces and special characters.

        :return:
        """

        # Define columns to be interpreted as integer values.
        integer_columns = [
            "WMO ID",
            "Latitude",
            "Longitude",
            "First Year",
            "Last Year",
            "HLY First Year",
            "HLY Last Year",
            "DLY First Year",
            "DLY Last Year",
            "MLY First Year",
            "MLY Last Year",
        ]

        # Build column -> type mapping.
        integer_types = ["Int64"] * len(integer_columns)
        types = dict(zip(integer_columns, integer_types))

        # Acquire raw CSV payload.
        csv_payload = self.download_stations()

        # Read into Pandas data frame.
        df = pd.read_csv(
            BytesIO(csv_payload), header=2, index_col="Station ID", dtype=types
        )

        def column_renamer(column_name):
            return (
                # No spaces.
                column_name.replace(" ", "_")
                #
                # No braces.
                .translate(str.maketrans("", "", "()"))
                #
                # Lowercase FTW.
                .lower()
            )

        # Rename all labels to lower case.
        df = df.reindex(df.index.rename("station_id"))
        df = df.rename(columns=column_renamer)

        return df

    @staticmethod
    @payload_cache_twelve_hours.cache_on_arguments()
    def download_stations() -> str:
        """
        Download station list from ECCC FTP server.

        :return: CSV payload
        """
        session = FTPSession()
        response = session.retr(
            "ftp://client_climate:foobar@ftp.tor.ec.gc.ca"
            "/Pub/Get_More_Data_Plus_de_donnees/Station Inventory EN.csv"
        )
        return response.content


if __name__ == "__main__":

    eccc = ECCCAdapter()
    stations = eccc.get_stations()

    print("-" * 42)
    print("  List of stations")
    print("-" * 42)
    print("Columns:")
    print(list(stations.columns))
    print(stations)
    print()

    print("-" * 42)
    print("  Hourly data")
    print("-" * 42)
