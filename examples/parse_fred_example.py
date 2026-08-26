import logging
import tempfile
import zipfile
from pathlib import Path

from pyarinc.arinc647a.fred_parser import FredXmlParser, StrictMode

# Configure logging to see parser warnings and debug details
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def main():
    # Path to your ARINC 647A FRED ZIP fixture
    zip_path = Path("tests/fixtures/ags767/647a-1.zip")

    if not zip_path.exists():
        print(f"Error: Fixture not found at {zip_path.absolute()}")
        return

    # Alternatively, you can use StrictMode.FAIL or StrictMode.LENIENT
    strict_setting = StrictMode.WARN

    print(f"Opening archive fixture: {zip_path.name}...")

    try:
        # Extract the inner XML file from the ZIP archive safely
        with zipfile.ZipFile(zip_path, "r") as zf:
            xml_files = [f for f in zf.namelist() if f.lower().endswith(".xml")]
            if not xml_files:
                print("Error: No XML files found inside the zip archive.")
                return

            target_xml = xml_files[0]
            print(f"Extracting inner XML file: {target_xml}")
            xml_content = zf.read(target_xml)

        # Parse via a temporary file so FredXmlParser can read it smoothly
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_xml_path = Path(tmpdir) / target_xml
            temp_xml_path.write_bytes(xml_content)

            print(f"Parsing FRED configuration from {target_xml}...")
            fred_doc = FredXmlParser.parse_file(
                file_path=temp_xml_path, strict_mode=strict_setting
            )

        # Print extracted aircraft/recorder metadata
        print("\n--- Document Metadata ---")
        for key, value in fred_doc.metadata.items():
            print(f"  {key}: {value}")

        print(
            f"\nSuccessfully extracted {len(fred_doc.parameters)} total parameters (including subparameters)."
        )

        # Inspect the first few parameters
        print("\n--- Sample Parameters ---")
        for fp in fred_doc.parameters[:5]:
            p = fp.parameter
            print(f"  - Name: {p.name}")
            print(
                f"    DataType: {p.data_type} | BitLength: {p.bit_length} | StartBit: {p.start_bit}"
            )
            print(
                f"    Units: {fp.units} | Resolution: {fp.resolution} | SampleRate: {fp.sample_rate}"
            )
            if fp.description:
                print(f"    Description: {fp.description}")
            print("-" * 40)

        # Optional: Run manual validation if using LENIENT or WARN mode
        fred_doc.validate()
        print("\nValidation check passed successfully!")

    except Exception as exc:
        print(f"\nFailed to parse FRED file due to error: {exc}")


if __name__ == "__main__":
    main()
