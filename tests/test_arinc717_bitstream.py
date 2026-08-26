import pytest

from pyarinc.arinc717.aligned import AlignedStream
from pyarinc.arinc717.bitstream import BitstreamScanner


def bits_to_bytes(bits: str) -> bytes:
    # pad to full bytes
    bits = bits + ("0" * ((8 - (len(bits) % 8)) % 8))
    out = []
    for i in range(0, len(bits), 8):
        out.append(int(bits[i : i + 8], 2))
    return bytes(out)


def test_sync_detection_simple():
    # define sync pattern 0b1010
    sync = 0b1010
    sync_len = 4
    data_bits = "0001" + "1010" + "11110000"
    data = bits_to_bytes(data_bits)
    scanner = BitstreamScanner(sync, sync_len)
    positions = scanner.find_sync_positions(data)
    assert positions and positions[0] == 4


def test_aligned_stream_basic():
    # build a fake bitstream consisting of two frames: sync + frame bytes
    # use sync pattern 0b11110000 (8 bits) at start
    sync = 0b11110000
    sync_len = 8
    # create two frames of 32 bits each (4 bytes)
    frame1 = bytes([0xAA, 0xBB, 0xCC, 0xDD])
    frame2 = bytes([0x11, 0x22, 0x33, 0x44])
    data = bytes([sync]) + frame1 + frame2
    aligned = AlignedStream.from_bitstream(
        data,
        sync_pattern=sync,
        sync_length=sync_len,
        word_bits=8,
        words_per_subframe=1,
        subframes_per_frame=2,
    )
    frames = list(aligned.iter_frames())
    assert len(frames) >= 1
    f = frames[0]
    # calculate expected chunk from byte offset
    expected_chunk = data[0 : (8 * 1 * 2) // 8]
    assert f.bits == expected_chunk


def test_missing_frame_insertion():
    # simulate data with a gap: sync + frame1, then a gap, then frame3
    sync = 0b11110000
    sync_len = 8
    frame1 = bytes([0x01, 0x02, 0x03, 0x04])
    frame3 = bytes([0x09, 0x0A, 0x0B, 0x0C])
    # create data where second frame is missing (we just concatenate frame3 after frame1)
    data = bytes([sync]) + frame1 + frame3
    aligned = AlignedStream.from_bitstream(
        data,
        sync_pattern=sync,
        sync_length=sync_len,
        word_bits=8,
        words_per_subframe=1,
        subframes_per_frame=1,
    )
    frames = list(aligned.iter_frames())
    # we expect two frames extracted sequentially
    assert len(frames) >= 2


@pytest.mark.parametrize(
    "sync_pat, sync_len, bitstream, expected_pos",
    [
        (0b11, 2, "001100", 2),  # Simple short sync pattern
        (
            0x257,
            12,
            "000000000000" + "001001010111" + "1111",
            12,
        ),  # Standard 717 pattern
        (0xF, 4, "1111", 0),  # Sync at the very beginning
        (0xF, 4, "000000001111", 8),  # Sync at the very end
    ],
)
def test_bitstream_scanner_parametrized(sync_pat, sync_len, bitstream, expected_pos):
    data = bits_to_bytes(bitstream)
    scanner = BitstreamScanner(sync_pat, sync_len)
    positions = scanner.find_sync_positions(data)
    assert positions
    assert expected_pos in positions


def test_bitstream_scanner_edge_cases():
    # Sync length longer than data
    scanner = BitstreamScanner(0b1010, 16)
    assert scanner.find_sync_positions(b"\x0A") == []

    # Zero or negative sync length
    scanner_zero = BitstreamScanner(0b1010, 0)
    assert scanner_zero.find_sync_positions(b"\x0A\x0B") == []

    # Empty data
    scanner_empty = BitstreamScanner(0b10, 2)
    assert scanner_empty.find_sync_positions(b"") == []


def test_aligned_stream_truncated_tail():
    # Setup data where a full frame requires 4 bytes total, but we leave only 2 bytes at the end
    sync = 0b11110000
    sync_len = 8
    # Frame size configuration: 2 subframes * 1 word per subframe * 8 bits = 2 bytes per frame (+ sync)
    # Let's make frame size 4 bytes by setting words_per_subframe=2, subframes_per_frame=2
    # Total frame size = 2 * 2 * 8 bits = 32 bits = 4 bytes.
    frame1 = bytes([0xAA, 0xBB, 0xCC, 0xDD])  # Full 4-byte frame
    truncated_tail = bytes([0x11, 0x22])  # Only 2 bytes left (incomplete frame)

    data = bytes([sync]) + frame1 + truncated_tail

    aligned = AlignedStream.from_bitstream(
        data,
        sync_pattern=sync,
        sync_length=sync_len,
        word_bits=8,
        words_per_subframe=2,
        subframes_per_frame=2,  # Requires 4 bytes per frame
    )
    frames = list(aligned.iter_frames())

    # Should safely drop the truncated 2-byte tail and only return the 1 valid frame
    assert len(frames) == 1
    assert frames[0].frame_index == 0
