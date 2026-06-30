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
    # Create an outer frame with a genuine, well-formed inner frame embedded
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


def test_payload_with_incidental_sync_bytes_is_not_split() -> None:
    """A frame whose payload coincidentally contains the 0xEB90 byte
    pattern, with no valid length field following it, must be parsed as a
    single intact frame rather than truncated at the coincidence."""

    # Bytes immediately following the coincidental sync (0xFF, 0xFF) do NOT
    # form a valid frame length (max is 2048), so this must NOT be treated
    # as an embedded frame boundary.
    payload = b"\x01\x02" + b"\xEB\x90" + b"\xFF\xFF" + b"\x03\x04"
    frame_bytes = build_raw_frame(5, 0x00, 0, payload)

    frames = list(Arinc767FrameParser.iter_frames(frame_bytes))

    assert len(frames) == 1, (
        f"expected exactly 1 frame, got {len(frames)} "
        "(a coincidental byte pattern in the payload was incorrectly "
        "treated as a frame boundary)"
    )
    assert frames[0].frame_id == 5
    assert frames[0].data == payload


def test_incidental_sync_with_plausible_but_oversized_length_not_split() -> None:
    """Even if the bytes after a coincidental sync happen to form a number,
    it must still fall within MIN/MAX frame size AND fit in the remaining
    buffer to be treated as a real frame boundary."""

    # 0x7FFF as a "length" is in range syntactically but the buffer is far
    # too short to actually contain a frame that long.
    payload = b"\x01\x02" + b"\xEB\x90" + b"\x7F\xFF" + b"\x03\x04"
    frame_bytes = build_raw_frame(5, 0x00, 0, payload)

    frames = list(Arinc767FrameParser.iter_frames(frame_bytes))

    assert len(frames) == 1
    assert frames[0].data == payload


def test_multiple_gaps_are_each_logged(caplog) -> None:
    """gap_logged is currently set once and never reset, so only the first
    gap between frames in a stream produces a warning. Every distinct gap
    should be reported, not just the first one encountered."""
    frame_a = build_raw_frame(1, 0x00, 0, b"\x01\x02\x03\x04")
    frame_b = build_raw_frame(2, 0x00, 0, b"\x05\x06\x07\x08")

    gap1 = b"\x00" * 6
    gap2 = b"\x00" * 6

    stream = frame_a + gap1 + frame_b + gap2 + frame_a

    with caplog.at_level("WARNING"):
        frames = list(Arinc767FrameParser.iter_frames(stream))

    assert len(frames) == 3
    gap_warnings = [r for r in caplog.records if "gap of" in r.message]
    assert len(gap_warnings) >= 2, (
        "expected a gap warning for each gap in the stream, but logging "
        "was suppressed after the first one"
    )
