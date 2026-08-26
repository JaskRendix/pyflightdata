import struct

import pytest

from pyarinc.arinc767.parser import Arinc767FrameParser


def build_raw_frame(
    frame_id: int, frame_type: int, timestamp_ms: int, data: bytes
) -> bytes:
    sync = 0xEB90
    frame_len = 10 + len(data) + 2
    header = struct.pack(
        ">H H I H", sync, frame_len, timestamp_ms, (frame_type << 8) | frame_id
    )
    trailer = struct.pack(">H", (frame_type << 8) | frame_id)
    return header + data + trailer


def test_trailer_strict_vs_lenient():
    data = b"\x01\x02"
    raw_good = build_raw_frame(1, 0x01, 0, data)
    raw_bad = raw_good[:-2] + b"\x00\x00"

    # parse_frame now returns (frame, trailer_mismatch) tuple
    frame_strict, _ = Arinc767FrameParser.parse_frame(raw_bad, 0, 0, strict=True)
    assert frame_strict is None

    frame_lenient, mismatch = Arinc767FrameParser.parse_frame(
        raw_bad, 0, 0, strict=False
    )
    assert frame_lenient is not None
    assert mismatch is True


def test_max_frames_limit():
    frame = build_raw_frame(1, 0x00, 0, b"\xAA\xBB")
    stream = frame * 1000

    frames = list(Arinc767FrameParser.iter_frames(stream, max_frames=10))

    assert len(frames) == 10


def test_timestamp_wraparound():
    ms1 = ((23 * 3600 + 59 * 60 + 59) * 1000) + 900
    ms2 = 100

    outer = build_raw_frame(1, 0x00, ms1, b"\xAA\xBB")
    inner = build_raw_frame(2, 0x00, ms2, b"\xCC\xDD")
    buf = outer + inner

    frames = list(Arinc767FrameParser.iter_frames(buf, timestamp_wrap=True))

    assert len(frames) == 2
    assert frames[0].timestamp_ms == ms1
    assert frames[1].timestamp_ms == ms2 + 24 * 3600 * 1000


def test_overlapping_frames_skip_to_inner_sync():
    inner = build_raw_frame(3, 0x00, 1, b"\x11\x22")
    outer_data = b"\xFF" * 5 + inner + b"\xEE" * 11
    outer = build_raw_frame(1, 0x00, 0, outer_data)

    frames = list(Arinc767FrameParser.iter_frames(outer))

    assert any(f.frame_id == 3 for f in frames)


@pytest.mark.parametrize(
    "declared_len, actual_extra",
    [
        (20, b""),  # no trailer
        (20, b"\x00"),  # 1 byte only
        (20, b"\x00\x00"),  # 2 bytes but missing data
    ],
)
def test_partial_frame_rejected(declared_len, actual_extra):
    sync = 0xEB90
    timestamp = 0
    type_id = (0 << 8) | 1
    header = struct.pack(">H H I H", sync, declared_len, timestamp, type_id)
    buf = header + actual_extra

    parsed = Arinc767FrameParser.parse_frame(buf, 0, 0)
    frames = list(Arinc767FrameParser.iter_frames(buf))

    assert parsed is None or len(frames) == 0


def test_payload_incidental_sync_not_split():
    payload = b"\x01\x02" + b"\xEB\x90" + b"\xFF\xFF" + b"\x03\x04"
    frame_bytes = build_raw_frame(5, 0x00, 0, payload)

    frames = list(Arinc767FrameParser.iter_frames(frame_bytes))

    assert len(frames) == 1
    assert frames[0].frame_id == 5
    assert frames[0].data == payload


def test_incidental_sync_with_oversized_length_not_split():
    payload = b"\x01\x02" + b"\xEB\x90" + b"\x7F\xFF" + b"\x03\x04"
    frame_bytes = build_raw_frame(5, 0x00, 0, payload)

    frames = list(Arinc767FrameParser.iter_frames(frame_bytes))

    assert len(frames) == 1
    assert frames[0].data == payload


def test_multiple_gaps_logged(caplog):
    frame_a = build_raw_frame(1, 0x00, 0, b"\x01\x02\x03\x04")
    frame_b = build_raw_frame(2, 0x00, 0, b"\x05\x06\x07\x08")

    gap1 = b"\x00" * 6
    gap2 = b"\x00" * 6

    stream = frame_a + gap1 + frame_b + gap2 + frame_a

    with caplog.at_level("WARNING"):
        frames = list(Arinc767FrameParser.iter_frames(stream))

    assert len(frames) == 3

    gap_warnings = [r for r in caplog.records if "gap of" in r.message]
    assert len(gap_warnings) >= 2


def test_strict_gap_rejection():
    frame_a = build_raw_frame(1, 0x00, 0, b"\xAA\xBB")
    gap = b"\x00" * 10
    frame_b = build_raw_frame(2, 0x00, 0, b"\xCC\xDD")

    stream = frame_a + gap + frame_b

    frames = list(Arinc767FrameParser.iter_frames(stream, strict=True))

    # strict mode should reject the second frame entirely
    assert len(frames) == 1
    assert frames[0].frame_id == 1


def test_max_gap_threshold(caplog):
    frame_a = build_raw_frame(1, 0x00, 0, b"\xAA\xBB")
    gap = b"\x00" * 100
    frame_b = build_raw_frame(2, 0x00, 0, b"\xCC\xDD")

    stream = frame_a + gap + frame_b

    with caplog.at_level("WARNING"):
        frames = list(Arinc767FrameParser.iter_frames(stream, max_gap=50))

    assert any("exceeds max_gap" in r.message for r in caplog.records)


def test_timestamp_regression_warning(caplog):
    f1 = build_raw_frame(1, 0x00, 1000, b"\xAA\xBB")
    f2 = build_raw_frame(2, 0x00, 900, b"\xCC\xDD")  # regression

    stream = f1 + f2

    with caplog.at_level("WARNING"):
        frames = list(Arinc767FrameParser.iter_frames(stream, timestamp_wrap=False))

    assert any("timestamp regression" in r.message for r in caplog.records)


def test_iter_frames_from_file_streaming(tmp_path):
    f1 = build_raw_frame(1, 0x00, 0, b"\xAA\xBB")
    f2 = build_raw_frame(2, 0x00, 100, b"\xCC\xDD")
    f3 = build_raw_frame(3, 0x00, 200, b"\xEE\xFF")
    stream_data = f1 + f2 + f3

    dfile = tmp_path / "test_recording.arinc767"
    dfile.write_bytes(stream_data)

    frames = list(Arinc767FrameParser.iter_frames_from_file(dfile, chunk_size=20))

    assert len(frames) == 3
    assert frames[0].frame_id == 1
    assert frames[1].frame_id == 2
    assert frames[2].frame_id == 3
    assert frames[2].timestamp_ms == 200


def test_parse_with_stats_diagnostics():
    frame_good = build_raw_frame(1, 0x00, 100, b"\x01\x02")
    frame_bad_trailer = build_raw_frame(2, 0x00, 200, b"\x03\x04")[:-2] + b"\xFF\xFF"
    gap = b"\x00" * 16

    stream = frame_good + gap + frame_bad_trailer

    stats = Arinc767FrameParser.parse_with_stats(stream)

    assert stats.valid_frames_count == 2
    assert stats.gaps_encountered == 1
    assert stats.total_gap_bytes == 16
    assert stats.trailer_mismatches == 1
    assert len(stats.frames) == 2


def test_parser_empty_and_garbage_streams():
    garbage = b"\xFF\xFE\xFA\xCE" * 20

    frames = list(Arinc767FrameParser.iter_frames(garbage))
    stats = Arinc767FrameParser.parse_with_stats(garbage)

    assert len(frames) == 0
    assert stats.valid_frames_count == 0
    assert stats.total_bytes_processed == len(garbage)
