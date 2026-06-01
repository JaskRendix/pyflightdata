import struct

import pandas as pd

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.arinc767.frame import Arinc767Frame, Arinc767FrameParser
from pyarinc.models.parameter import Parameter


def build_frame(
    frame_id: int, frame_type: int, timestamp_ms: int, data: bytes
) -> Arinc767Frame:
    """Build an Arinc767Frame with header, data, and trailer matching type/id."""
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
        frame_index=0,
        frame_id=frame_id,
        frame_type=frame_type,
        timestamp_ms=timestamp_ms,
    )


def test_decode_frames_frame_id_filtering() -> None:
    # Parameter bound to frame_id 1 should only decode from frame 1
    p = Parameter("P1", start_bit=0, bit_length=8, data_type="BNR", frame_id_767=1)

    f1 = build_frame(1, 0x01, 0, b"\x05\x00")
    f2 = build_frame(2, 0x01, 10, b"\x07\x00")

    dec = Arinc767Decoder([p])
    df = dec.decode_frames([f1, f2])

    # Frame 1 should contain decoded value 5
    assert df.loc[df.frame_id == 1, "P1"].iloc[0] == 5
    # Frame 2 should not have the parameter (column may be missing or NaN)
    if "P1" in df.columns:
        assert pd.isna(df.loc[df.frame_id == 2, "P1"]).all()


def test_decode_rate_scheduling_and_sampling() -> None:
    # Create two parameters with different rates
    p_fast = Parameter("FAST", start_bit=0, bit_length=8, data_type="BNR", rate=2.0)
    p_slow = Parameter("SLOW", start_bit=0, bit_length=8, data_type="BNR", rate=1.0)

    # Build 4 frames with same id and simple 1-byte data
    frames: list[Arinc767Frame] = []
    for i in range(4):
        frames.append(build_frame(1, 0x01, i * 100, bytes([i, 0x00])))

    dec = Arinc767Decoder([p_fast, p_slow], frames_per_second=2.0)
    df = dec.decode(frames)

    # p_fast (rate=2) with fps=2 -> interval_frames = round(2/2)=1 -> sampled every frame
    fast_rows = df[df.parameter_name == "FAST"]
    assert len(fast_rows) == 4

    # p_slow (rate=1) with fps=2 -> interval_frames = round(2/1)=2 -> sampled every 2 frames
    slow_rows = df[df.parameter_name == "SLOW"]
    # Should have one sampled value and one invalid between samples per 2-frame period → 4 rows total for 4 frames
    assert len(slow_rows) == 4
    sampled = slow_rows[slow_rows.valid == True]
    assert len(sampled) == 2


def test_decode_frames_empty_data_section() -> None:
    # Build a frame with header+trailer but no data (raw length 12)
    sync = 0xEB90
    frame_len = 12
    header = struct.pack(
        ">H H I H",
        sync,
        frame_len,
        0,
        (0x01 << 8) | 0x01,
    )
    trailer = struct.pack(">H", (0x01 << 8) | 0x01)
    raw = header + trailer
    f = Arinc767Frame(
        raw_bytes=raw, frame_index=0, frame_id=1, frame_type=0x01, timestamp_ms=0
    )

    p = Parameter("P", start_bit=0, bit_length=8, data_type="BNR", rate=1.0)
    dec = Arinc767Decoder([p])
    df = dec.decode_frames([f])

    # Should return a row but parameter should not be present (no data)
    assert len(df) == 1
    assert df.iloc[0].frame_id == 1
    assert "P" not in df.columns or pd.isna(df.iloc[0].get("P"))


def test_frame_parser_handles_invalid_and_short_frames() -> None:
    # Valid frame with mismatched trailer (warning expected but frame yielded)
    good = build_frame(3, 0x02, 0, b"\x01\x02")
    # Corrupt trailer: change last two bytes
    bad_trailer_raw = good.raw_bytes[:-2] + b"\x00\x00"

    buf = good.raw_bytes + bad_trailer_raw

    frames = list(Arinc767FrameParser.iter_frames(buf))
    # Parser should yield the first (good) frame; second may still be parsed but will be logged
    assert any(f.frame_id == 3 for f in frames)

    # Short frame (length in header larger than buffer) should be skipped
    sync = 0xEB90
    # frame_len set to very large so it extends beyond buffer
    header = struct.pack(
        ">H H I H",
        sync,
        0xFFFF,
        0,
        (0x01 << 8) | 0x01,
    )
    short_buf = header
    frames2 = list(Arinc767FrameParser.iter_frames(short_buf))
    assert frames2 == []
