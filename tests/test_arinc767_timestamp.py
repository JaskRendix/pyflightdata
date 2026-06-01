import struct

import pytest

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.arinc767.frame import Arinc767Frame
from pyarinc.models.parameter import Parameter


def build_frame(
    frame_id: int, frame_type: int, timestamp_ms: int, data: bytes, frame_index: int
) -> Arinc767Frame:
    sync = 0xEB90
    frame_len = 10 + len(data) + 2
    header = struct.pack(
        ">H H I H",
        sync,
        frame_len,
        timestamp_ms,
        (frame_type << 8) | (frame_id & 0xFF),
    )
    trailer = struct.pack(
        ">H",
        (frame_type << 8) | (frame_id & 0xFF),
    )
    raw = header + data + trailer
    return Arinc767Frame(
        raw_bytes=raw,
        frame_index=frame_index,
        frame_id=frame_id,
        frame_type=frame_type,
        timestamp_ms=timestamp_ms,
    )


def _ts_to_seconds(ts: str) -> float:
    hh, mm, rest = ts.split(":")
    ss, mmm = rest.split(".")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(mmm) / 1000.0


def test_arinc767_timestamp_based_times_from_decode_frames() -> None:
    # 3 synthetic frames with timestamps 0, 100, 200 ms
    frames = [
        build_frame(1, 0x01, 0, b"\x01\x02", 0),
        build_frame(1, 0x01, 100, b"\x03\x04", 1),
        build_frame(1, 0x01, 200, b"\x05\x06", 2),
    ]

    p = Parameter(
        "P", start_bit=0, bit_length=8, data_type="DISCRETE", frame_id_767=1, rate=1.0
    )
    dec = Arinc767Decoder([p])
    df = dec.decode_frames(frames)

    # decode_frames currently exposes formatted `timestamp` (HH:MM:SS.mmm)
    assert "timestamp" in df.columns

    times = [_ts_to_seconds(ts) for ts in df["timestamp"].tolist()]
    assert times == pytest.approx([0.0, 0.1, 0.2])
