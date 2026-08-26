from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum, auto
from math import isfinite
from pathlib import Path

from ..models.parameter import Parameter

logger = logging.getLogger(__name__)

DEFAULT_NS = {
    "fred": "http://www.arinc.com/FRED",
}


class StrictMode(Enum):
    LENIENT = auto()
    WARN = auto()
    FAIL = auto()


@dataclass
class FredParameter:
    """Encapsulates a core Parameter model alongside ARINC 647A metadata."""

    parameter: Parameter
    units: str | None = None
    description: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    resolution: float = 1.0
    word_number: int | None = None
    sample_offset: int | None = None
    sample_rate: float | None = None


@dataclass
class FredDocument:
    """Structured container for parsed ARINC 647A metadata and parameters."""

    parameters: list[FredParameter] = field(default_factory=list)
    metadata: dict[str, str | None] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate parsed document integrity for avionics safety."""
        for fp in self.parameters:
            p = fp.parameter
            if p.bit_length <= 0:
                raise ValueError(
                    f"Invalid bit length for parameter '{p.name}': {p.bit_length}"
                )
            if p.start_bit is not None and p.start_bit < 0:
                raise ValueError(
                    f"Negative start bit for parameter '{p.name}': {p.start_bit}"
                )
            if hasattr(p, "scale") and p.scale is not None and not isfinite(p.scale):
                raise ValueError(
                    f"Non-finite scale factor for parameter '{p.name}': {p.scale}"
                )
            if (
                fp.min_value is not None
                and fp.max_value is not None
                and fp.min_value > fp.max_value
            ):
                raise ValueError(
                    f"MinValue > MaxValue for parameter '{p.name}' ({fp.min_value} > {fp.max_value})"
                )
            if fp.resolution <= 0:
                raise ValueError(
                    f"Invalid non-positive resolution for parameter '{p.name}': {fp.resolution}"
                )
            if fp.sample_rate is not None and fp.sample_rate <= 0:
                raise ValueError(
                    f"Invalid non-positive sample rate for parameter '{p.name}': {fp.sample_rate}"
                )
        logger.info(
            f"FredDocument validated successfully with {len(self.parameters)} parameters."
        )


class FredXmlParser:
    """Robust, production-grade parser for ARINC 647A Flight Recorder Electronic Documentation XML files."""

    @staticmethod
    def _resolve_namespace(
        root: ET.Element, provided_ns: dict[str, str] | None
    ) -> dict[str, str]:
        active_ns = provided_ns.copy() if provided_ns is not None else DEFAULT_NS.copy()
        if root.tag.startswith("{"):
            uri = root.tag.split("}")[0][1:]
            active_ns["fred"] = uri
        return active_ns

    @classmethod
    def _get_field(
        cls,
        elem: ET.Element,
        *keys: str,
        ns: dict[str, str],
        default: str | None = None,
    ) -> str | None:
        for k in keys:
            if k in elem.attrib:
                return elem.attrib[k]
            for child in list(elem):
                tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag_local.lower() == k.lower() and child.text:
                    return child.text.strip()
        return default

    @classmethod
    def _get_field_with_parent_fallback(
        cls,
        elem: ET.Element,
        parent_map: dict[ET.Element, ET.Element],
        *keys: str,
        ns: dict[str, str],
        default: str | None = None,
    ) -> str | None:
        val = cls._get_field(elem, *keys, ns=ns, default=None)
        if val is not None:
            return val
        parent = parent_map.get(elem)
        if parent is not None:
            return cls._get_field(parent, *keys, ns=ns, default=default)
        return default

    @staticmethod
    def _parse_int(
        value: str | None, field_name: str, parameter_name: str
    ) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid {field_name} for parameter '{parameter_name}': {value!r}"
            )
            return None

    @staticmethod
    def _parse_float(
        value: str | None, field_name: str, parameter_name: str
    ) -> float | None:
        if value is None:
            return None
        try:
            if "/" in value:
                num, denom = value.split("/", 1)
                return float(num) / float(denom)
            return float(value)
        except (TypeError, ValueError, ZeroDivisionError):
            logger.warning(
                f"Invalid {field_name} for parameter '{parameter_name}': {value!r}"
            )
            return None

    @staticmethod
    def _find_parameter_elements(root: ET.Element) -> list[ET.Element]:
        """Finds elements that represent parameters across diverse ARINC 647A/767 schema structures."""
        results = []
        for elem in root.iter():
            tag_local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            # Match elements containing 'parameter' in their local tag name (case-insensitive)
            if "parameter" in tag_local.lower():
                results.append(elem)
        return results

    @classmethod
    def parse_file(
        cls,
        file_path: str | Path,
        ns: dict[str, str] | None = None,
        strict_mode: StrictMode = StrictMode.LENIENT,
    ) -> FredDocument:
        path = Path(file_path)
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            logger.error(f"Failed to parse XML structure in {path.name}: {exc}")
            raise

        root = tree.getroot()
        active_ns = cls._resolve_namespace(root, ns)

        parent_map: dict[ET.Element, ET.Element] = {}
        for parent in root.iter():
            for child in parent:
                parent_map[child] = parent

        metadata: dict[str, str | None] = {
            "aircraft_type": cls._get_field(
                root, "AircraftType", "Aircraft", ns=active_ns
            ),
            "file_version": cls._get_field(
                root, "Version", "FileVersion", ns=active_ns
            ),
            "recorder_model": cls._get_field(
                root, "RecorderModel", "Model", ns=active_ns
            ),
            "tail_number": cls._get_field(root, "TailNumber", ns=active_ns),
            "serial_number": cls._get_field(root, "SerialNumber", ns=active_ns),
            "part_number": cls._get_field(root, "PartNumber", ns=active_ns),
            "software_version": cls._get_field(
                root, "RecorderSoftwareVersion", ns=active_ns
            ),
            "config_id": cls._get_field(root, "ConfigurationId", ns=active_ns),
        }

        fred_parameters: list[FredParameter] = []
        seen_element_ids: set[int] = set()
        param_elements: list[ET.Element] = []

        for p in cls._find_parameter_elements(root):
            tag_local = p.tag.split("}")[-1] if "}" in p.tag else p.tag
            # Exclude container or subparameter nodes from being treated as standalone root parameters
            if "sub" in tag_local.lower():
                continue
            if id(p) not in seen_element_ids:
                seen_element_ids.add(id(p))
                param_elements.append(p)

        for elem in param_elements:
            name = cls._get_field_with_parent_fallback(
                elem, parent_map, "Name", "ParameterName", ns=active_ns
            )
            if not name:
                continue  # Skip container definitions or headers lacking a real parameter name

            try:
                bit_length_str = cls._get_field_with_parent_fallback(
                    elem, parent_map, "BitLength", "Length", ns=active_ns
                )
                start_bit_str = cls._get_field_with_parent_fallback(
                    elem, parent_map, "StartBit", "Offset", ns=active_ns
                )
                frame_id_str = cls._get_field_with_parent_fallback(
                    elem, parent_map, "FrameId", "SubframeId", ns=active_ns
                )

                bit_length = cls._parse_int(bit_length_str, "bitLength", name)
                start_bit = cls._parse_int(start_bit_str, "startBit", name)

                if bit_length is None or start_bit is None:
                    if strict_mode == StrictMode.FAIL:
                        raise ValueError(
                            f"Missing required fields (BitLength or StartBit) for parameter '{name}'"
                        )
                    elif strict_mode == StrictMode.WARN:
                        logger.warning(
                            f"Parameter '{name}' has missing or invalid structural fields."
                        )

                resolved_bit_length = bit_length or 16
                frame_id = cls._parse_int(frame_id_str, "frameId", name)

                if frame_id is not None:
                    if frame_id < 0 or frame_id > 2047:
                        if strict_mode == StrictMode.WARN:
                            logger.warning(
                                f"FrameId out of standard bounds ({frame_id}) for parameter '{name}'"
                            )

                resolved_bit_length = bit_length or 16
                data_type = (
                    cls._get_field_with_parent_fallback(
                        elem, parent_map, "DataType", "Type", ns=active_ns
                    )
                    or "BNR"
                )

                scale_str = cls._get_field_with_parent_fallback(
                    elem, parent_map, "Scale", "Gain", ns=active_ns
                )
                offset_str = cls._get_field_with_parent_fallback(
                    elem, parent_map, "Offset", ns=active_ns
                )
                scale = cls._parse_float(scale_str, "scale", name) or 1.0
                offset = cls._parse_float(offset_str, "offset", name) or 0.0

                units = cls._get_field_with_parent_fallback(
                    elem, parent_map, "Units", ns=active_ns
                )
                description = cls._get_field_with_parent_fallback(
                    elem, parent_map, "Description", ns=active_ns
                )
                min_val = cls._parse_float(
                    cls._get_field_with_parent_fallback(
                        elem, parent_map, "MinValue", "Min", ns=active_ns
                    ),
                    "minValue",
                    name,
                )
                max_val = cls._parse_float(
                    cls._get_field_with_parent_fallback(
                        elem, parent_map, "MaxValue", "Max", ns=active_ns
                    ),
                    "maxValue",
                    name,
                )

                resolution = (
                    cls._parse_float(
                        cls._get_field_with_parent_fallback(
                            elem, parent_map, "Resolution", ns=active_ns
                        ),
                        "resolution",
                        name,
                    )
                    or 1.0
                )
                if resolution <= 0 and strict_mode == StrictMode.WARN:
                    logger.warning(
                        f"Non-positive resolution ({resolution}) for parameter '{name}'"
                    )

                word_number = cls._parse_int(
                    cls._get_field_with_parent_fallback(
                        elem, parent_map, "WordNumber", ns=active_ns
                    ),
                    "wordNumber",
                    name,
                )
                sample_offset = cls._parse_int(
                    cls._get_field_with_parent_fallback(
                        elem, parent_map, "SampleOffset", ns=active_ns
                    ),
                    "sampleOffset",
                    name,
                )
                sample_rate = cls._parse_float(
                    cls._get_field_with_parent_fallback(
                        elem, parent_map, "SampleRate", ns=active_ns
                    ),
                    "sampleRate",
                    name,
                )

                if (
                    sample_rate is not None
                    and sample_rate <= 0
                    and strict_mode == StrictMode.WARN
                ):
                    logger.warning(
                        f"Non-positive sampleRate ({sample_rate}) for parameter '{name}'"
                    )

                if min_val is not None and max_val is not None and min_val > max_val:
                    if strict_mode == StrictMode.FAIL:
                        raise ValueError(f"MinValue > MaxValue for parameter '{name}'")
                    elif strict_mode == StrictMode.WARN:
                        logger.warning(
                            f"MinValue > MaxValue for parameter '{name}' ({min_val} > {max_val})"
                        )

                if start_bit is not None:
                    param = Parameter.from_767(
                        name=name,
                        bit_length=resolved_bit_length,
                        data_type=data_type,
                        start_bit=start_bit,
                        frame_id_767=frame_id,
                        scale=scale,
                        offset=offset,
                    )
                else:
                    param = Parameter(
                        name=name,
                        bit_length=resolved_bit_length,
                        data_type=data_type,
                        scale=scale,
                        offset=offset,
                    )

                fred_parameters.append(
                    FredParameter(
                        parameter=param,
                        units=units,
                        description=description,
                        min_value=min_val,
                        max_value=max_val,
                        resolution=resolution,
                        word_number=word_number,
                        sample_offset=sample_offset,
                        sample_rate=sample_rate,
                    )
                )

                subparams = [
                    child
                    for child in elem.iter()
                    if "subparameter"
                    in (
                        child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    ).lower()
                    and child != elem
                ]

                for sub in subparams:
                    sub_name = cls._get_field_with_parent_fallback(
                        sub, parent_map, "Name", ns=active_ns
                    )
                    sub_start_str = cls._get_field_with_parent_fallback(
                        sub, parent_map, "StartBit", ns=active_ns
                    )
                    sub_len_str = cls._get_field_with_parent_fallback(
                        sub, parent_map, "BitLength", ns=active_ns
                    )

                    sub_start = cls._parse_int(
                        sub_start_str, "startBit", f"{name}.{sub_name}"
                    )
                    sub_len = cls._parse_int(
                        sub_len_str, "bitLength", f"{name}.{sub_name}"
                    )

                    if not sub_name or sub_start is None or sub_len is None:
                        if strict_mode == StrictMode.WARN:
                            logger.warning(
                                f"SubParameter under '{name}' has missing or invalid fields."
                            )
                        continue

                    if start_bit is not None and 0 <= sub_start < resolved_bit_length:
                        absolute_start = start_bit + sub_start
                    else:
                        absolute_start = sub_start

                    sub_units = (
                        cls._get_field_with_parent_fallback(
                            sub, parent_map, "Units", ns=active_ns
                        )
                        or units
                    )
                    sub_desc = f"{description}: {sub_name}" if description else sub_name

                    sub_param = Parameter.from_767(
                        name=f"{name}_{sub_name}",
                        bit_length=sub_len,
                        data_type="DISCRETE" if sub_len == 1 else "BNR",
                        start_bit=absolute_start,
                        frame_id_767=frame_id,
                    )
                    fred_parameters.append(
                        FredParameter(
                            parameter=sub_param,
                            units=sub_units,
                            description=sub_desc,
                            resolution=resolution,
                            min_value=min_val,
                            max_value=max_val,
                            word_number=word_number,
                            sample_offset=sample_offset,
                            sample_rate=sample_rate,
                        )
                    )

            except Exception as exc:
                if strict_mode == StrictMode.FAIL:
                    raise
                elif strict_mode == StrictMode.WARN:
                    logger.warning(
                        f"Warning during parsing parameter '{name}' in {path.name}: {exc}"
                    )
                else:
                    logger.error(
                        f"Failed parsing parameter '{name}' in {path.name}: {exc}",
                        exc_info=True,
                    )

        doc = FredDocument(parameters=fred_parameters, metadata=metadata)
        if strict_mode == StrictMode.FAIL:
            doc.validate()

        logger.info(
            f"Successfully parsed {len(fred_parameters)} parameter configurations from FRED document: {path.name}"
        )
        return doc
