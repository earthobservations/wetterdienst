import pandas as pd


def chunker(seq: pd.DataFrame, chunksize: int):
    """
    Chunks generator function for iterating pandas Dataframes and Series.

    https://stackoverflow.com/a/61798585
    :return:
    """
    for pos in range(0, len(seq), chunksize):
        yield seq.iloc[pos : pos + chunksize]
