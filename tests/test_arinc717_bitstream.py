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
