from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AircraftRecord:
    tail: str
    reception_date: str
    airline: str
    ac_type: str
    ac_type_wired_no: str
    ac_ident: str
    ac_serial_number: str
    ac_in_operation: str
    qar_model: str
    qar2_model: str
    fdr_model: str
    fdr2_model: str
    qar_version: str
    qar2_version: str
    fdr_version: str
    fdr2_version: str
    qar_link: str
    qar2_link: str
    fdr_link: str
    fdr2_link: str
    qar_serial: str
    qar2_serial: str
    fdr_serial: str
    fdr2_serial: str
    eng1_serial: str
    eng2_serial: str
    eng3_serial: str
    eng4_serial: str
    eng1_install_date: str
    eng2_install_date: str
    eng3_install_date: str
    eng4_install_date: str
    eng1_type: str
    eng2_type: str
    eng3_type: str
    eng4_type: str
    # we won’t model all remaining fields; keep raw for now
    raw_fields: list[str]


def extract_vec_from_ags_bundle(path: Path) -> dict[str, bytes]:
    """
    Extract files from an AGS .vec bundle (ZIP archive).

    Returns a mapping {name: data}, typically including .add/.vec/.air.
    """
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            out[name] = zf.read(name)
    return out


def find_text_vec_file(files: dict[str, bytes]) -> tuple[str, str] | None:
    """
    Heuristic: pick the first inner file that looks like a text VEC/PRM file.
    """
    for name, data in files.items():
        # skip obvious binaries
        if data.startswith(b"PK\x03\x04"):
            continue
        text = data.decode("utf-8", errors="ignore")
        if "W" in text and "B" in text and "SF=" in text:
            return name, text
    return None


def parse_aircraft_air(path: Path) -> list[AircraftRecord]:
    """
    Parse an AGS aircraft.air file (UTF-16LE, tab-separated, with // comments).
    """
    raw = path.read_bytes()
    text = raw.decode("utf-16-le", errors="ignore")

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("//")
    ]
    if not lines:
        return []

    header = lines[0].split("\t")
    records: list[AircraftRecord] = []

    for row in lines[1:]:
        cols = row.split("\t")
        # pad to header length
        if len(cols) < len(header):
            cols += [""] * (len(header) - len(cols))

        # map the first N fields we care about
        rec = AircraftRecord(
            tail=cols[0],
            reception_date=cols[1],
            airline=cols[2],
            ac_type=cols[3],
            ac_type_wired_no=cols[4],
            ac_ident=cols[5],
            ac_serial_number=cols[6],
            ac_in_operation=cols[7],
            qar_model=cols[8],
            qar2_model=cols[9],
            fdr_model=cols[10],
            fdr2_model=cols[11],
            qar_version=cols[12],
            qar2_version=cols[13],
            fdr_version=cols[14],
            fdr2_version=cols[15],
            qar_link=cols[16],
            qar2_link=cols[17],
            fdr_link=cols[18],
            fdr2_link=cols[19],
            qar_serial=cols[20],
            qar2_serial=cols[21],
            fdr_serial=cols[22],
            fdr2_serial=cols[23],
            eng1_serial=cols[24],
            eng2_serial=cols[25],
            eng3_serial=cols[26],
            eng4_serial=cols[27],
            eng1_install_date=cols[28],
            eng2_install_date=cols[29],
            eng3_install_date=cols[30],
            eng4_install_date=cols[31],
            eng1_type=cols[32],
            eng2_type=cols[33],
            eng3_type=cols[34],
            eng4_type=cols[35],
            raw_fields=cols,
        )
        records.append(rec)

    return records
