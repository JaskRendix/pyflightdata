from pyarinc.arinc717.decoder import Arinc717Decoder
from pyarinc.arinc717.frame import Frame, Subframe
from pyarinc.models.parameter import Parameter


def test_arinc717_decode_simple():
    # one frame with two bytes: 0x12 0x34 -> bits
    frame = Frame(
        frame_index=0,
        frame_bit_offset=0,
        subframes=[Subframe(raw_bits=b"\x12\x34", subframe_index=0)],
    )

    params = [
        Parameter(name="P1", start_bit=0, bit_length=8, data_type="DISCRETE"),
        Parameter(name="P2", start_bit=8, bit_length=8, data_type="DISCRETE"),
    ]

    dec = Arinc717Decoder(params)
    df = dec.decode_frames([frame])

    assert "frame_index" in df.columns
    assert "P1" in df.columns and "P2" in df.columns
    assert int(df.iloc[0]["P1"]) == 0x12
    assert int(df.iloc[0]["P2"]) == 0x34
