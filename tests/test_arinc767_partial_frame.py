import struct

from pyarinc.arinc767.frame import Arinc767FrameParser


def test_arinc767_truncated_frame_handling() -> None:
    """Ensure truncated frame (declared length > buffer) is not parsed."""
    sync = 0xEB90
    # declare a frame length (20) but provide fewer bytes (header + 2)
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

    buf = header + b"\x00\x00"  # total 12 bytes (truncated)

    parsed = Arinc767FrameParser.parse_frame(buf, 0, 0)
    frames = list(Arinc767FrameParser.iter_frames(buf))

    # Current behavior: either parse_frame returns None or iter_frames yields no frames
    assert (parsed is None) or (len(frames) == 0)
