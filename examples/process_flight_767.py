import zipfile
from pathlib import Path

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.arinc767.parser import Arinc767FrameParser
from pyarinc.arinc767.vec_parser import parse_vec_file_767, vec_to_parameters_767
from pyarinc.io.csv_export import export_csv
from pyarinc.io.parquet_export import export_parquet


def process_flight_767_data(
    vec_path: Path, archive_path: Path, output_dir: Path
) -> None:
    """Read VEC config, extract and read raw ARINC 767 flight data from zip, decode, and export."""
    print(f"Loading parameters from VEC file {vec_path}...")
    mapping = parse_vec_file_767(vec_path)
    parameters = vec_to_parameters_767(mapping)

    print(f"Extracting raw ARINC 767 data from zip archive {archive_path}...")
    with zipfile.ZipFile(archive_path, "r") as z:
        inner_filename = z.namelist()[0]
        print(f"Reading inner file: {inner_filename}")
        raw_bytes = z.read(inner_filename)

    print(f"Loaded {len(raw_bytes)} bytes of raw flight data.")
    print("Analyzing stream health with Arinc767FrameParser.parse_with_stats()...")
    stats = Arinc767FrameParser.parse_with_stats(raw_bytes)
    print("--- Stream Health Diagnostics ---")
    print(f"  Total Bytes Processed : {stats.total_bytes_processed}")
    print(f"  Valid Frames Found    : {stats.valid_frames_count}")
    print(
        f"  Gaps Encountered      : {stats.gaps_encountered} (Total gap bytes: {stats.total_gap_bytes})"
    )
    print(f"  Trailer Mismatches    : {stats.trailer_mismatches}")
    print(f"  Embedded Headers      : {stats.embedded_headers_detected}")
    print("--------------------------------")

    print("Decoding ARINC 767 parameters using Arinc767Decoder...")
    decoder = Arinc767Decoder(list(parameters.values()), frames_per_second=1.0)

    df = decoder.decode_raw_bytes(raw_bytes)

    print(f"Decoded {len(df)} rows.")

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
    archive_file = Path("tests/fixtures/ags767/B-678920010203001603N.zip")
    output_directory = Path("output")

    if vec_file.exists() and archive_file.exists():
        process_flight_767_data(vec_file, archive_file, output_directory)
    else:
        print("Sample fixture files not found. Check paths to run the example.")
