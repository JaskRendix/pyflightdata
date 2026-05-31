from pathlib import Path

import pandas as pd


def export_parquet(df: pd.DataFrame, path: Path) -> None:
    """Export DataFrame to Parquet. Requires pyarrow or fastparquet."""
    df.to_parquet(path, index=False)
