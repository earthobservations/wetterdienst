""" entrypoints ro tun scripts via Docker or command line """
import fire

from wetterdienst.data_collection import collect_climate_observations_data


if __name__ == "__main__":
    fire.Fire({"collect_climate_observations_data": collect_climate_observations_data})
