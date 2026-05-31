from pathlib import Path

import pandas as pd


def export_csv(df: pd.DataFrame, path: Path) -> None:
    """Export DataFrame to CSV."""
    df.to_csv(path, index=False)
