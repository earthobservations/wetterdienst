import pandas as pd


def frame_summary(frame: pd.DataFrame):
    return f"{len(frame)} records and columns={list(frame.columns)}"
