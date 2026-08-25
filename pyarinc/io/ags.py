from __future__ import annotations

import logging
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_EXPECTED_FIELDS = 36


@dataclass
class AircraftRecord:
    tail: str = ""
    reception_date: str = ""
    airline: str = ""
    ac_type: str = ""
    ac_type_wired_no: str = ""
    ac_ident: str = ""
    ac_serial_number: str = ""
    ac_in_operation: str = ""
    qar_model: str = ""
    qar2_model: str = ""
    fdr_model: str = ""
    fdr2_model: str = ""
    qar_version: str = ""
    qar2_version: str = ""
    fdr_version: str = ""
    fdr2_version: str = ""
    qar_link: str = ""
    qar2_link: str = ""
    fdr_link: str = ""
    fdr2_link: str = ""
    qar_serial: str = ""
    qar2_serial: str = ""
    fdr_serial: str = ""
    fdr2_serial: str = ""
    eng1_serial: str = ""
    eng2_serial: str = ""
    eng3_serial: str = ""
    eng4_serial: str = ""
    eng1_install_date: str = ""
    eng2_install_date: str = ""
    eng3_install_date: str = ""
    eng4_install_date: str = ""
    eng1_type: str = ""
    eng2_type: str = ""
    eng3_type: str = ""
    eng4_type: str = ""
    raw_fields: list[str] = field(default_factory=list)
    extra_attributes: dict[str, str | int | float] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Perform per-record validation and return a list of warning/error messages."""
        issues: list[str] = []
        if not self.tail:
            issues.append("Missing aircraft tail identifier.")
        if not self.ac_type:
            issues.append(f"Aircraft {self.tail or 'UNKNOWN'}: Missing aircraft type.")
        return issues


@dataclass
class AircraftAirParseResult:
    records: list[AircraftRecord]
    source_path: Path | None = None
    error: str | None = None


def extract_vec_from_ags_bundle(path: Path) -> dict[str, bytes]:
    """Extract files from an AGS .vec bundle (ZIP archive)."""
    out: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                out[name] = zf.read(name)
    except Exception as e:
        logger.error(f"Failed to extract AGS bundle {path}: {e}")
        raise
    return out


def find_text_vec_file(files: dict[str, bytes]) -> tuple[str, str] | None:
    """Heuristic to pick the first inner file that looks like a text VEC/PRM file."""
    for name, data in files.items():
        if data.startswith(b"PK\x03\x04") or name.endswith((".air", ".zip", ".add")):
            continue
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue

        upper_text = text.upper()
        if any(k in upper_text for k in ("SF=", "TYPE=", "W=")) and "B=" in upper_text:
            return name, text
    return None


def _smart_cast(val: str) -> str | int | float:
    """Attempt to cast string values to int or float for analytics utility."""
    val_clean = val.strip()
    if not val_clean:
        return ""
    try:
        if "." in val_clean or "e" in val_clean.lower():
            return float(val_clean)
        return int(val_clean)
    except ValueError:
        return val_clean


def parse_aircraft_air(path: Path) -> AircraftAirParseResult:
    """Parse an AGS aircraft.air file (UTF-16LE, tab-separated, with // comments)."""
    try:
        raw = path.read_bytes()
        # Use 'strict' errors to catch actual encoding corruption
        text = raw.decode("utf-16-le", errors="strict")
    except Exception as e:
        err_msg = f"Failed to read/decode aircraft file {path}: {e}"
        logger.error(err_msg)
        return AircraftAirParseResult(records=[], source_path=path, error=err_msg)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("//")
    ]
    if not lines:
        return AircraftAirParseResult(
            records=[],
            source_path=path,
            error=f"Aircraft file {path} is empty or contains only comments.",
        )

    raw_header = lines[0].split("\t")
    norm_header = [
        unicodedata.normalize("NFKC", h).strip().lower().replace(" ", "_")
        for h in raw_header
    ]

    records: list[AircraftRecord] = []

    for row_idx, row in enumerate(lines[1:], start=2):
        cols = [c.strip() for c in row.split("\t")]

        if len(cols) < MIN_EXPECTED_FIELDS:
            logger.warning(
                f"Row {row_idx} in {path} is shorter than expected ({len(cols)} < {MIN_EXPECTED_FIELDS})"
            )

        if len(cols) < len(raw_header):
            cols += [""] * (len(raw_header) - len(cols))

        def get_col(idx: int) -> str:
            return cols[idx] if idx < len(cols) else ""

        rec = AircraftRecord(
            tail=get_col(0),
            reception_date=get_col(1),
            airline=get_col(2),
            ac_type=get_col(3),
            ac_type_wired_no=get_col(4),
            ac_ident=get_col(5),
            ac_serial_number=get_col(6),
            ac_in_operation=get_col(7),
            qar_model=get_col(8),
            qar2_model=get_col(9),
            fdr_model=get_col(10),
            fdr2_model=get_col(11),
            qar_version=get_col(12),
            qar2_version=get_col(13),
            fdr_version=get_col(14),
            fdr2_version=get_col(15),
            qar_link=get_col(16),
            qar2_link=get_col(17),
            fdr_link=get_col(18),
            fdr2_link=get_col(19),
            qar_serial=get_col(20),
            qar2_serial=get_col(21),
            fdr_serial=get_col(22),
            fdr2_serial=get_col(23),
            eng1_serial=get_col(24),
            eng2_serial=get_col(25),
            eng3_serial=get_col(26),
            eng4_serial=get_col(27),
            eng1_install_date=get_col(28),
            eng2_install_date=get_col(29),
            eng3_install_date=get_col(30),
            eng4_install_date=get_col(31),
            eng1_type=get_col(32),
            eng2_type=get_col(33),
            eng3_type=get_col(34),
            eng4_type=get_col(35),
            raw_fields=cols,
        )

        rec.extra_attributes = {
            norm_header[i]: _smart_cast(cols[i]) for i in range(len(norm_header))
        }

        # Optional validation logging
        if validation_issues := rec.validate():
            logger.debug(
                f"Validation notices for row {row_idx} in {path}: {validation_issues}"
            )

        records.append(rec)

    return AircraftAirParseResult(records=records, source_path=path, error=None)
