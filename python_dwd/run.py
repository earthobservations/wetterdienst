""" entrypoints ro tun scripts via Docker or command line """
import fire

from python_dwd.data_collection import collect_dwd_data


if __name__ == '__main__':
  fire.Fire({
      'collect_dwd_data': collect_dwd_data
})