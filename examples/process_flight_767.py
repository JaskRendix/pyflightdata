from pathlib import Path

import pandas as pd

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.arinc767.frame import Arinc767FrameParser
from pyarinc.io.csv_export import export_csv
from pyarinc.io.datafile import read_binary
from pyarinc.io.parquet_export import export_parquet
from pyarinc.models.parameter import Parameter


def process_flight_767_data(file_path: Path, output_dir: Path) -> None:
    """Read a raw ARINC 767 flight data file, decode parameters, and export to CSV/Parquet."""
    print(f"Reading raw ARINC 767 data from {file_path}...")
    raw_bytes = read_binary(file_path)

    # Define sample parameters for ARINC 767 demonstration
    # (Adjust field names, bit lengths, and frame IDs based on your 767 spec)
    sample_params = [
        Parameter("ALTITUDE", start_bit=0, bit_length=16, data_type="BNR", rate=1.0),
        Parameter("AIRSPEED", start_bit=16, bit_length=16, data_type="BNR", rate=1.0),
    ]

    print("Decoding ARINC 767 parameters using Arinc767Decoder...")
    decoder = Arinc767Decoder(sample_params, frames_per_second=1.0)

    # decode_raw_bytes parses the raw frame stream and returns a scheduled DataFrame
    df = decoder.decode_raw_bytes(raw_bytes)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "decoded_flight_767.csv"
    parquet_path = out_dir / "decoded_flight_767.parquet"

    print(f"Exporting CSV to {csv_path}...")
    export_csv(df, csv_path)

    print(f"Exporting Parquet to {parquet_path}...")
    export_parquet(df, parquet_path)
    print("Done!")


if __name__ == "__main__":
    # Point to the actual ARINC 767 fixture in your tree
    sample_file = Path("tests/fixtures/ags767/078711.vec")
    output_directory = Path("output")

    if sample_file.exists():
        process_flight_767_data(sample_file, output_directory)
    else:
        print(
            f"Sample fixture not found at {sample_file}. Provide a valid path to run."
        )
