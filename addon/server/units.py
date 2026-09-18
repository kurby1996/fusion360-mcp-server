"""Millimetre-first units for the MCP surface.

Fusion's API is centimetres. Callers pass and receive millimetres. This
module converts at the command boundary so handlers can keep talking to
Fusion in internal units. Free of ``adsk`` so it can be unit-tested.
"""

from __future__ import annotations

from typing import Any

MM_PER_CM = 10.0
MM2_PER_CM2 = 100.0
MM3_PER_CM3 = 1000.0

# Commands whose numbers are not millimetre lengths (pixels, parameters,
# raw Fusion Python, etc.).
_SKIP_COMMANDS = frozenset(
    {
        "ping",
        "execute_code",
        "create_parameter",
        "set_parameter",
        "delete_parameter",
        "get_parameters",
        "render_view",
        "export_view_sheet",
        "set_color",
        "set_appearance",
        "get_design_type",
        "set_design_type",
        "cam_post_process",
        "new_document",
        "open_document",
        "save_document",
        "export_stl",
        "export_step",
        "export_f3d",
        "export",
        "rename_body",
    }
)

# Length / position fields (mm externally, cm internally).
_LENGTH_KEYS = frozenset(
    {
        "height",
        "width",
        "length",
        "radius",
        "diameter",
        "actual_diameter",
        "depth",
        "thickness",
        "distance",
        "offset",
        "z_offset",
        "offset_distance",
        "origin_x",
        "origin_y",
        "origin_z",
        "center_x",
        "center_y",
        "center_z",
        "start_x",
        "start_y",
        "start_z",
        "end_x",
        "end_y",
        "end_z",
        "axis_origin_x",
        "axis_origin_y",
        "axis_origin_z",
        "base_x",
        "base_y",
        "base_z",
        "anchor_x",
        "anchor_y",
        "anchor_z",
        "point_x",
        "point_y",
        "x",
        "y",
        "z",
        "x_spacing",
        "y_spacing",
        "thread_length",
        "bend_radius",
        "tolerance",
        "stepdown",
        "stepover",
        "feed_rate",
        "tool_diameter",
        "stock_offset_sides",
        "stock_offset_top",
        "stock_offset_bottom",
        "major_radius",
        "minor_radius",
        "direction_x",
        "direction_y",
        "min_deviation",
        "max_deviation",
        "mean_abs_deviation",
        "rms_deviation",
        "max_abs_deviation",
        "value",  # add_dimension distances; skipped for parameter commands
    }
)

# Coordinate triples / point lists.
_POINT_KEYS = frozenset(
    {
        "points",
        "point_one",
        "point_two",
        "point_three",
        "min",
        "max",
        "size",
        "center",
        "origin",
        "start",
        "end",
        "centroid",
        "center_of_mass",
        "translation",
        "resolved_center",
        "point_on_face",
        "point_on_edge",
        "eye",
        "target",
        "angles_deg",  # not a point — excluded below via skip of non-length
    }
)

_AREA_KEYS = frozenset({"area"})
_VOLUME_KEYS = frozenset({"volume"})

# Unitless directions — never scale.
_DIRECTION_KEYS = frozenset(
    {
        "normal",
        "axis",
        "up_vector",
        "axis_direction_x",
        "axis_direction_y",
        "axis_direction_z",
    }
)

_LENGTH_UNITS = frozenset({"mm", "cm", "m", "in", "ft", "micron", "nm", "mil"})

# ``angles_deg`` is a list of numbers but not a point.
_POINT_KEYS = _POINT_KEYS - {"angles_deg"}


def mm_to_cm(value: float) -> float:
    return value / MM_PER_CM


def cm_to_mm(value: float) -> float:
    return value * MM_PER_CM


def to_internal(command: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Convert caller millimetres to Fusion centimetres."""
    if not params:
        return {}
    if command in _SKIP_COMMANDS:
        return dict(params)
    if command == "add_dimension" and params.get("dimension_type") == "angular":
        return dict(params)
    converted = _walk(params, "in")
    if command == "measure_distance":
        for key in ("entity_one", "entity_two"):
            if key in converted:
                converted[key] = _convert_point_string(converted[key], mm_to_cm)
    return converted


def to_external(command: str, result: Any) -> Any:
    """Convert Fusion centimetres to millimetres on the way out."""
    if command in _SKIP_COMMANDS:
        if isinstance(result, dict) and command == "get_parameters":
            out = dict(result)
            params = out.get("parameters")
            if isinstance(params, list):
                out["parameters"] = [_parameter_value_to_mm(p) for p in params]
            out.setdefault("units", "mm")
            return out
        if isinstance(result, dict) and command not in {"ping", "execute_code"}:
            out = dict(result)
            if "deltas" in out:
                out["deltas"] = _walk(out["deltas"], "out")
            out.setdefault("units", "mm")
            return out
        return result
    if not isinstance(result, dict):
        return result
    if command == "add_dimension" and result.get("dimension_type") == "angular":
        out = dict(result)
        out.setdefault("units", "mm")
        return out
    out = _walk(result, "out")
    out.setdefault("units", "mm")
    return out


def _parameter_value_to_mm(param: Any) -> Any:
    """Parameter.value is Fusion-internal (cm for lengths). Report mm."""
    if not isinstance(param, dict):
        return param
    out = dict(param)
    unit = (out.get("unit") or "").strip().lower()
    value = out.get("value")
    if unit in _LENGTH_UNITS and _is_number(value):
        out["value"] = cm_to_mm(value)
        out["value_unit"] = "mm"
    return out


def _convert_point_string(raw: Any, fn) -> Any:
    if not isinstance(raw, str) or "," not in raw:
        return raw
    parts = [p.strip() for p in raw.split(",")]
    try:
        nums = [fn(float(p)) for p in parts]
    except ValueError:
        return raw
    return ",".join(str(n) for n in nums)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _walk(obj: Any, direction: str, key: str | None = None) -> Any:
    if key in _DIRECTION_KEYS:
        return obj
    if isinstance(obj, dict):
        return {k: _walk(v, direction, k) for k, v in obj.items()}
    if isinstance(obj, list):
        if key in _POINT_KEYS or key in _LENGTH_KEYS:
            return [_scale_numeric(item, direction, key) for item in obj]
        return [_walk(item, direction, key) for item in obj]
    return _scale_numeric(obj, direction, key)


def _scale_numeric(value: Any, direction: str, key: str | None) -> Any:
    if isinstance(value, list):
        # Nested point e.g. points: [[x,y,z], ...]
        return [_scale_numeric(item, direction, key) for item in value]
    if isinstance(value, dict):
        return _walk(value, direction, key)
    if not _is_number(value):
        return value
    if key in _DIRECTION_KEYS:
        return value
    if direction == "in":
        if key in _LENGTH_KEYS or key in _POINT_KEYS:
            return mm_to_cm(value)
        return value
    if key in _LENGTH_KEYS or key in _POINT_KEYS:
        return cm_to_mm(value)
    if key in _AREA_KEYS:
        return value * MM2_PER_CM2
    if key in _VOLUME_KEYS:
        return value * MM3_PER_CM3
    return value
