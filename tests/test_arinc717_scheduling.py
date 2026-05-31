from pyarinc.arinc717.decoder import Arinc717Decoder
from pyarinc.arinc717.frame import Frame, Subframe
from pyarinc.models.parameter import Parameter


def make_frames(n: int, byte_per_frame: int = 1) -> list[Frame]:
    frames: list[Frame] = []
    for i in range(n):
        # each frame contains one subframe with one byte equal to frame index
        b = bytes([i % 256]) * byte_per_frame
        sf = Subframe(raw_bits=b, subframe_index=0)
        frames.append(
            Frame(
                frame_index=i, frame_bit_offset=i * byte_per_frame * 8, subframes=[sf]
            )
        )
    return frames


class FakeAlignedStream:
    def __init__(
        self, frames: list[Frame], words_per_subframe: int = 1, word_bits: int = 8
    ):
        self.frames = frames
        self.words_per_subframe = words_per_subframe
        self.word_bits = word_bits
        self.subframes_per_frame = 1

    def iter_frames(self):
        for f in self.frames:
            yield f


def test_rate_expansion_counts():
    frames = make_frames(16)
    stream = FakeAlignedStream(frames)
    # create parameters with rates 1,2,4,8,16 Hz
    rates = [1, 2, 4, 8, 16]
    params = [
        Parameter(
            name=f"P{r}", start_bit=0, bit_length=8, data_type="DISCRETE", rate=float(r)
        )
        for r in rates
    ]
    dec = Arinc717Decoder(params)
    df = dec.decode(stream, frames_per_second=16)
    # number of valid samples per parameter in one second should equal rate
    for r in rates:
        valid_count = df[(df.parameter_name == f"P{r}") & (df.valid == True)].shape[0]
        assert valid_count == r


def test_superframe_only_parameter():
    frames = make_frames(8)
    stream = FakeAlignedStream(frames)
    p = Parameter(
        name="SF",
        start_bit=0,
        bit_length=8,
        data_type="DISCRETE",
        rate=4.0,
        superframe=1,
        superframe_group_count=4,
    )
    dec = Arinc717Decoder([p])
    df = dec.decode(stream, frames_per_second=4)
    # valid samples should occur on frames where index % 4 == 1
    valid_frames = list(
        df[(df.parameter_name == "SF") & (df.valid == True)]["frame_index"]
    )
    assert valid_frames == [1, 5]


def test_timestamp_reconstruction():
    frames = make_frames(4)
    stream = FakeAlignedStream(frames)
    p = Parameter(name="TST", start_bit=0, bit_length=8, data_type="DISCRETE", rate=1.0)
    dec = Arinc717Decoder([p])
    df = dec.decode(stream, frames_per_second=4)
    # valid samples at frames 0 only (every 4 frames)
    row = df[(df.parameter_name == "TST") & (df.valid == True)].iloc[0]
    assert row["time"] == 0.0


def test_missing_frame_behavior():
    # create frames where one frame is too short
    frames = make_frames(4)
    # make frame 2 missing data
    frames[2] = Frame(
        frame_index=2,
        frame_bit_offset=2 * 8,
        subframes=[Subframe(raw_bits=b"", subframe_index=0)],
    )
    stream = FakeAlignedStream(frames)
    p = Parameter(name="M", start_bit=0, bit_length=8, data_type="DISCRETE", rate=4.0)
    dec = Arinc717Decoder([p])
    df = dec.decode(stream, frames_per_second=4)
    # Frame 2 sample should be invalid
    row = df[(df.parameter_name == "M") & (df.frame_index == 2)].iloc[0]
    assert row["valid"] == False
