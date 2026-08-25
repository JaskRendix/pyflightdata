import zipfile
from pathlib import Path

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.io.csv_export import export_csv
from pyarinc.io.datafile import read_binary
from pyarinc.io.parquet_export import export_parquet
from pyarinc.models.parameter import Parameter


def process_zip_archive(zip_path: Path, output_dir: Path) -> None:
    """Extract and process only the valid flight data files inside an ARINC 767 ZIP archive."""
    print(f"\nProcessing archive: {zip_path.name}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        print(f"Contents: {namelist}")

        # Filter out schemas, specifications, and directories—keep only payload files
        data_files = [
            f for f in namelist if not f.lower().endswith((".xml", ".xsd", "/"))
        ]

        if not data_files:
            print(f"-> Skipping: No binary flight data files found in {zip_path.name}")
            return

        extract_dir = output_dir / "extracted" / zip_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Target only the right files directly
        for file_name in data_files:
            zf.extract(file_name, extract_dir)
            extracted_file = extract_dir / file_name

            print(f"-> Found target flight data file: {extracted_file.name}")
            try:
                raw_bytes = read_binary(extracted_file)

                # Define parameters matching a 767 dataset
                sample_params = [
                    Parameter(
                        "ALTITUDE",
                        start_bit=0,
                        bit_length=16,
                        data_type="BNR",
                        rate=1.0,
                    ),
                    Parameter(
                        "AIRSPEED",
                        start_bit=16,
                        bit_length=16,
                        data_type="BNR",
                        rate=1.0,
                    ),
                ]

                decoder = Arinc767Decoder(sample_params, frames_per_second=1.0)
                df = decoder.decode_raw_bytes(raw_bytes, strict=False)

                out_name = f"{zip_path.stem}_{extracted_file.stem}"
                csv_path = output_dir / f"{out_name}_decoded.csv"
                parquet_path = output_dir / f"{out_name}_decoded.parquet"

                export_csv(df, csv_path)
                export_parquet(df, parquet_path)
                print(
                    f"   Successfully decoded and exported {len(df)} rows to {csv_path.name}"
                )

            except Exception as e:
                print(f"   Could not decode {extracted_file.name}: {e}")


if __name__ == "__main__":
    fixtures_dir = Path("tests/fixtures/ags767")
    output_directory = Path("output")
    output_directory.mkdir(parents=True, exist_ok=True)

    zip_files = list(fixtures_dir.glob("*.zip"))

    if zip_files:
        for z_file in zip_files:
            process_zip_archive(z_file, output_directory)
        print("\nAll batch archives processed successfully!")
    else:
        print("No ZIP fixtures found in tests/fixtures/ags767/")
