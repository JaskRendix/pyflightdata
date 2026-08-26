from __future__ import annotations

import logging
import zipfile
from pathlib import Path

from pyarinc.arinc717.decoder import Arinc717Decoder
from pyarinc.arinc717.prm_parser import parse_prm_file, prm_to_parameters
from pyarinc.config.fred_parser import FredXmlParser, StrictMode
from pyarinc.io.csv_export import export_csv
from pyarinc.io.datafile import read_binary
from pyarinc.io.parquet_export import export_parquet
from pyarinc.models.parameter import Parameter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def process_zip_archive(zip_path: Path, output_dir: Path) -> None:
    """Extract, dynamically parse configuration (XML or PRM/JSON), and decode ARINC 717 data inside a ZIP archive."""
    print(f"\nProcessing archive: {zip_path.name}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        print(f"Contents: {namelist}")

        extract_dir = output_dir / "extracted" / zip_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Extract all contents so configuration files and raw.dat are accessible together
        zf.extractall(extract_dir)

        # 1. Locate raw.dat for binary flight data
        raw_dat_path = extract_dir / "raw.dat"
        if not raw_dat_path.exists():
            print(
                f"-> Skipping: No 'raw.dat' binary flight data found in {zip_path.name}"
            )
            return

        parameters = []

        # 2. Try loading configuration XML file if available
        xml_files = list(extract_dir.glob("*.xml"))
        if xml_files:
            target_xml = xml_files[0]
            print(
                f"-> Found XML configuration file: {target_xml.name}. Parsing parameters..."
            )
            try:
                fred_doc = FredXmlParser.parse_file(
                    file_path=target_xml, strict_mode=StrictMode.WARN
                )
                parameters = [
                    fp.parameter
                    for fp in fred_doc.parameters
                    if fp.parameter is not None
                ]
                if parameters:
                    print(
                        f"   Successfully loaded {len(parameters)} parameters from XML configuration."
                    )
            except Exception as e:
                print(f"   Warning: Failed to parse XML configuration ({e}).")

        # 3. Try loading PRM or JSON configuration files if no XML parameters were found
        if not parameters:
            prm_files = list(extract_dir.glob("*.prm")) + list(extract_dir.glob("*.json"))
            if prm_files:
                target_prm = prm_files[0]
                print(
                    f"-> Found PRM/JSON configuration file: {target_prm.name}. Parsing mapping..."
                )
                try:
                    prm_mapping = parse_prm_file(target_prm)
                    param_dict = prm_to_parameters(prm_mapping)
                    parameters = list(param_dict.values())
                    if parameters:
                        print(
                            f"   Successfully loaded {len(parameters)} parameters from PRM configuration."
                        )
                except Exception as e:
                    print(f"   Warning: Failed to parse PRM configuration ({e}).")

        # 4. Fallback to default hardcoded flight parameters if no config files found
        if not parameters:
            print("-> Using expanded default flight parameters mapping (Fallback).")
            parameters = [
                Parameter.from_717(
                    name="ALTITUDE",
                    bit_length=12,
                    data_type="BNR",
                    subframe=0,
                    word=2,
                    bit_offset=4,
                ),
                Parameter.from_717(
                    name="AIRSPEED",
                    bit_length=12,
                    data_type="BNR",
                    subframe=0,
                    word=4,
                    bit_offset=0,
                ),
                Parameter.from_717(
                    name="HEADING",
                    bit_length=12,
                    data_type="BNR",
                    subframe=0,
                    word=6,
                    bit_offset=0,
                ),
                Parameter.from_717(
                    name="VERTICAL_SPEED",
                    bit_length=12,
                    data_type="BNR",
                    subframe=1,
                    word=10,
                    bit_offset=0,
                ),
                Parameter.from_717(
                    name="PITCH",
                    bit_length=10,
                    data_type="BNR",
                    subframe=1,
                    word=14,
                    bit_offset=0,
                ),
                Parameter.from_717(
                    name="ROLL",
                    bit_length=10,
                    data_type="BNR",
                    subframe=2,
                    word=18,
                    bit_offset=0,
                ),
            ]

        # 5. Decode binary stream using parameters
        print(f"-> Decoding raw.dat...")
        try:
            raw_bytes = read_binary(raw_dat_path)

            decoder = Arinc717Decoder(parameters)
            df = decoder.decode_raw_bytes(raw_bytes)

            out_name = f"{zip_path.stem}_raw"
            csv_path = output_dir / f"{out_name}_decoded.csv"
            parquet_path = output_dir / f"{out_name}_decoded.parquet"

            export_csv(df, csv_path)
            export_parquet(df, parquet_path)
            print(
                f"   Successfully decoded {len(parameters)} parameters across {len(df)} rows to {csv_path.name}"
            )

        except Exception as e:
            print(f"   Could not decode raw.dat: {e}")


if __name__ == "__main__":
    fixtures_dir = Path("tests/fixtures/ags717")
    output_directory = Path("output")
    output_directory.mkdir(parents=True, exist_ok=True)

    zip_files = list(fixtures_dir.glob("*.zip"))

    if zip_files:
        for z_file in zip_files:
            process_zip_archive(z_file, output_directory)
        print("\nAll batch archives processed successfully!")
    else:
        print(f"No ZIP fixtures found in {fixtures_dir}/")
