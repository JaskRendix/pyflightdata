import struct

from pyarinc.arinc767.frame import Arinc767FrameParser


def build_raw_frame(
    frame_id: int, frame_type: int, timestamp_ms: int, data: bytes
) -> bytes:
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
    return header + data + trailer


def test_trailer_strict_vs_lenient() -> None:
    # Build a frame with mismatched trailer
    data = b"\x01\x02"
    raw_good = build_raw_frame(1, 0x01, 0, data)
    # corrupt trailer (set to 0x0000)
    raw_bad_trailer = raw_good[:-2] + b"\x00\x00"

    # strict=True should reject
    parsed_strict = Arinc767FrameParser.parse_frame(raw_bad_trailer, 0, 0, strict=True)
    assert parsed_strict is None

    # strict=False should accept (warning) and return a frame
    parsed_lenient = Arinc767FrameParser.parse_frame(
        raw_bad_trailer, 0, 0, strict=False
    )
    assert parsed_lenient is not None


def test_timestamp_wraparound() -> None:
    # timestamp near 24h: 23:59:59.900 => ms
    ms1 = ((23 * 3600 + 59 * 60 + 59) * 1000) + 900
    ms2 = 100

    outer = build_raw_frame(1, 0x00, ms1, b"\xAA\xBB")
    inner = build_raw_frame(2, 0x00, ms2, b"\xCC\xDD")

    buf = outer + inner

    frames = list(
        Arinc767FrameParser.iter_frames(buf, strict=False, timestamp_wrap=True)
    )
    # Should yield two frames
    assert len(frames) == 2
    # First timestamp unchanged
    assert frames[0].timestamp_ms == ms1
    # Second timestamp should be adjusted by +24h in ms
    assert frames[1].timestamp_ms == ms2 + 24 * 3600 * 1000


def test_overlapping_frames_skip_to_inner_sync() -> None:
    # Create an outer frame with inner sync embedded
    outer_ts = 0
    inner_ts = 1
    inner = build_raw_frame(3, 0x00, inner_ts, b"\x11\x22")
    # outer data length such that inner appears inside
    data_before = b"\xFF" * 5
    data_after = b"\xEE" * 11
    outer_data = data_before + inner + data_after
    outer = build_raw_frame(1, 0x00, outer_ts, outer_data)

    buf = outer

    frames = list(Arinc767FrameParser.iter_frames(buf, strict=False))
    # Should parse the inner frame (id 3) and yield at least one frame with that id
    assert any(f.frame_id == 3 for f in frames)


def test_partial_frame_rejected() -> None:
    sync = 0xEB90
    frame_len = 20
    timestamp = 0
    type_id = (0 << 8) | 1
    header = struct.pack(
        ">H H I H",
        sync,
        frame_len,
        timestamp,
        type_id,
    )

    buf = header + b"\x00\x00"  # truncated buffer

    parsed = Arinc767FrameParser.parse_frame(buf, 0, 0)
    frames = list(Arinc767FrameParser.iter_frames(buf))
    assert parsed is None or len(frames) == 0
