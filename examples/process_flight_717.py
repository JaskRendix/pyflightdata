from pathlib import Path

from pyarinc.arinc717.aligned import AlignedStream
from pyarinc.arinc717.decoder import Arinc717Decoder
from pyarinc.io.csv_export import export_csv
from pyarinc.io.datafile import read_binary
from pyarinc.io.parquet_export import export_parquet
from pyarinc.models.parameter import Parameter


def process_flight_data(file_path: Path, output_dir: Path) -> None:
    """Read a raw flight data file and decode it."""
    print(f"Reading raw data from {file_path}...")
    raw_bytes = read_binary(file_path)

    # 1. Build the AlignedStream using the bitstream scanner & sync pattern
    print("Parsing bitstream and finding sync positions...")
    aligned_stream = AlignedStream.from_bitstream(
        data=raw_bytes,
        sync_pattern=0x247,  # Standard ARINC 717 bipolar sync word example
        sync_length=12,
        word_bits=12,
        words_per_subframe=64,
        subframes_per_frame=4,
    )

    # Define sample parameters for demonstration (expanded with HDG and VS)
    sample_params = [
        Parameter("ALT", start_bit=0, bit_length=12, data_type="BNR", rate=16),
        Parameter("CAS", start_bit=12, bit_length=12, data_type="BNR", rate=16),
        Parameter("HDG", start_bit=24, bit_length=12, data_type="BNR", rate=16),
        Parameter("VS", start_bit=36, bit_length=12, data_type="BNR", rate=16),
    ]

    print("Decoding parameters using Arinc717Decoder...")
    decoder = Arinc717Decoder(sample_params)
    df = decoder.decode(aligned_stream, frames_per_second=16)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "decoded_flight.csv"
    parquet_path = out_dir / "decoded_flight.parquet"

    print(f"Exporting CSV to {csv_path}...")
    export_csv(df, csv_path)

    print(f"Exporting Parquet to {parquet_path}...")
    export_parquet(df, parquet_path)
    print("Done!")


if __name__ == "__main__":
    sample_file = Path("tests/fixtures/ags717/B-8888_20010102171005-10888.wgl.zip")
    output_directory = Path("output")

    if sample_file.exists():
        process_flight_data(sample_file, output_directory)
    else:
        print("Sample fixture not found. Provide a valid path to run.")
