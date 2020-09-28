from datetime import datetime, timedelta


def round_minutes(timestamp: datetime, step: int):
    """
    Align timestamp to the given minute mark before tm.
    - https://stackoverflow.com/a/3464000

    :param timestamp:
    :param step:
    :return:
    """

    timestamp = timestamp.replace(second=0, microsecond=0)
    change = timedelta(minutes=timestamp.minute % step)
    return timestamp - change


def raster_minutes(timestamp: datetime, value: int):
    """
    Align timestamp to the most recent minute mark.

    - https://stackoverflow.com/a/55013608
    - https://stackoverflow.com/a/60709050

    :param timestamp:
    :param value:
    :return:
    """

    timestamp = timestamp.replace(second=0, microsecond=0)

    if timestamp.minute < value:
        timestamp = timestamp - timedelta(hours=1)

    timestamp = timestamp.replace(minute=value)

    return timestamp
