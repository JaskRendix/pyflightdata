import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pyarinc.config.fred_parser import (
    FredDocument,
    FredParameter,
    FredXmlParser,
    StrictMode,
)


def write_temp_xml(tmp_path, xml: str) -> Path:
    p = tmp_path / "test.xml"
    p.write_text(xml)
    return p


def test_basic_parameter_parsing(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Altitude" BitLength="16" StartBit="0" DataType="BNR" Units="FT"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)

    assert len(doc.parameters) == 1
    fp = doc.parameters[0]
    assert fp.parameter.name == "Altitude"
    assert fp.parameter.bit_length == 16
    assert fp.parameter.start_bit == 0
    assert fp.units == "FT"


@pytest.mark.parametrize(
    "ns_decl",
    [
        'xmlns="http://www.arinc.com/FRED"',
        'xmlns:fred="http://www.arinc.com/FRED"',
    ],
)
def test_namespace_variants(tmp_path, ns_decl):
    xml = f"""
    <FRED {ns_decl}>
        <Parameter Name="Speed" BitLength="8" StartBit="4"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)
    assert doc.parameters[0].parameter.name == "Speed"


def test_parent_fallback_metadata(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <ParameterDefinition Units="KTS" Description="Airspeed">
            <Parameter Name="IAS" BitLength="16" StartBit="0"/>
        </ParameterDefinition>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)

    fp = doc.parameters[0]
    assert fp.units == "KTS"
    assert fp.description == "Airspeed"


def test_subparameter_parsing(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Flags" BitLength="8" StartBit="0">
            <SubParameter Name="FlagA" StartBit="0" BitLength="1"/>
            <SubParameter Name="FlagB" StartBit="1" BitLength="1"/>
        </Parameter>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)

    names = [fp.parameter.name for fp in doc.parameters]
    assert "Flags_FlagA" in names
    assert "Flags_FlagB" in names


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1/2", 0.5),
        ("3/4", 0.75),
        ("10", 10.0),
    ],
)
def test_fraction_parsing(tmp_path, value, expected):
    xml = f"""
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Test" BitLength="8" StartBit="0" Scale="{value}"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)
    assert doc.parameters[0].parameter.scale == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("BitLength", "abc"),
        ("StartBit", "xyz"),
        ("Scale", "not_a_number"),
    ],
)
def test_invalid_numeric_fields(tmp_path, field, value):
    xml = f"""
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Test" {field}="{value}"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)
    fp = doc.parameters[0]
    # BitLength defaults to 16, StartBit becomes None, Scale defaults to 1.0
    assert fp.parameter.bit_length == 16


def test_strict_mode_fail_missing_fields(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Broken"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    with pytest.raises(ValueError):
        FredXmlParser.parse_file(path, strict_mode=StrictMode.FAIL)


def test_strict_mode_warn(tmp_path, caplog):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Broken"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    FredXmlParser.parse_file(path, strict_mode=StrictMode.WARN)
    assert any("missing or invalid structural fields" in m for m in caplog.messages)


def test_resolution_validation(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Test" BitLength="8" StartBit="0" Resolution="-1"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    with pytest.raises(ValueError):
        FredXmlParser.parse_file(path, strict_mode=StrictMode.FAIL)


def test_sample_rate_validation(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Test" BitLength="8" StartBit="0" SampleRate="-5"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    with pytest.raises(ValueError):
        FredXmlParser.parse_file(path, strict_mode=StrictMode.FAIL)


@pytest.mark.parametrize("frame_id", [-1, 3000])
def test_frameid_bounds_warn(tmp_path, frame_id, caplog):
    xml = f"""
    <FRED xmlns="http://www.arinc.com/FRED">
        <Parameter Name="Test" BitLength="8" StartBit="0" FrameId="{frame_id}"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    FredXmlParser.parse_file(path, strict_mode=StrictMode.WARN)
    assert any("FrameId out of standard bounds" in m for m in caplog.messages)


def test_metadata_extraction(tmp_path):
    xml = """
    <FRED xmlns="http://www.arinc.com/FRED">
        <AircraftType>A320</AircraftType>
        <Parameter Name="Test" BitLength="8" StartBit="0"/>
    </FRED>
    """
    path = write_temp_xml(tmp_path, xml)
    doc = FredXmlParser.parse_file(path)
    assert doc.metadata["aircraft_type"] == "A320"
