from pathlib import Path

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.arinc767.vec_parser import parse_vec_file_767, vec_to_parameters_767
from pyarinc.io.csv_export import export_csv
from pyarinc.io.datafile import read_binary
from pyarinc.io.parquet_export import export_parquet


def process_flight_767_data(vec_path: Path, data_path: Path, output_dir: Path) -> None:
    """Read a VEC config, parse raw ARINC 767 flight data, decode parameters, and export."""
    print(f"Loading parameters from VEC file {vec_path}...")
    mapping = parse_vec_file_767(vec_path)
    parameters = vec_to_parameters_767(mapping)

    print(f"Reading raw ARINC 767 data from {data_path}...")
    raw_bytes = read_binary(data_path)

    print("Decoding ARINC 767 parameters using Arinc767Decoder...")
    decoder = Arinc767Decoder(list(parameters.values()), frames_per_second=1.0)

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
    vec_file = Path("tests/fixtures/ags767/078711.vec")
    data_file = Path("tests/fixtures/ags767/B-678920010203001603N.zip")
    output_directory = Path("output")

    if vec_file.exists() and data_file.exists():
        process_flight_767_data(vec_file, data_file, output_directory)
    else:
        print("Sample fixture files not found. Check paths to run the example.")
