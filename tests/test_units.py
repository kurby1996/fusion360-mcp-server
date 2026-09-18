"""Tests for millimetre-first conversion at the add-in boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ADDON_SERVER = Path(__file__).resolve().parent.parent / "addon" / "server"


def _load(path: Path, name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


units = _load(ADDON_SERVER / "units.py", "fusion_units")


class TestHelpers:
    def test_mm_to_cm(self):
        assert units.mm_to_cm(10) == 1
        assert units.mm_to_cm(25) == 2.5

    def test_cm_to_mm(self):
        assert units.cm_to_mm(1) == 10
        assert units.cm_to_mm(2.5) == 25


class TestToInternal:
    def test_extrude_height_mm_becomes_cm(self):
        out = units.to_internal("extrude", {"height": 10, "operation": "new_body"})
        assert out["height"] == 1
        assert out["operation"] == "new_body"

    def test_draw_rectangle_origins(self):
        out = units.to_internal(
            "draw_rectangle",
            {"width": 20, "height": 10, "origin_x": 5, "origin_y": 0},
        )
        assert out["width"] == 2
        assert out["height"] == 1
        assert out["origin_x"] == 0.5
        assert out["origin_y"] == 0

    def test_direction_vectors_are_not_scaled(self):
        out = units.to_internal(
            "revolve",
            {
                "angle": 90,
                "axis_origin_x": 10,
                "axis_direction_x": 1,
                "axis_direction_y": 0,
            },
        )
        assert out["axis_origin_x"] == 1
        assert out["axis_direction_x"] == 1
        assert out["axis_direction_y"] == 0
        assert out["angle"] == 90

    def test_scale_factors_are_not_scaled(self):
        out = units.to_internal("scale_body", {"scale": 2, "anchor_x": 10})
        assert out["scale"] == 2
        assert out["anchor_x"] == 1

    def test_string_expressions_pass_through(self):
        out = units.to_internal(
            "create_box_parametric",
            {"length": "boxL", "width": 20, "height": "56 mm"},
        )
        assert out["length"] == "boxL"
        assert out["width"] == 2
        assert out["height"] == "56 mm"

    def test_spline_points(self):
        out = units.to_internal(
            "draw_spline",
            {"spline_type": "fit_points", "points": [[10, 0], [20, 30, 40]]},
        )
        assert out["points"] == [[1, 0], [2, 3, 4]]

    def test_angular_dimension_is_not_converted(self):
        out = units.to_internal(
            "add_dimension", {"dimension_type": "angular", "value": 90}
        )
        assert out["value"] == 90

    def test_distance_dimension_is_converted(self):
        out = units.to_internal(
            "add_dimension", {"dimension_type": "distance", "value": 10}
        )
        assert out["value"] == 1

    def test_parameter_commands_are_skipped(self):
        out = units.to_internal(
            "create_parameter", {"name": "L", "value": 1000, "unit": "mm"}
        )
        assert out["value"] == 1000

    def test_execute_code_is_skipped(self):
        out = units.to_internal("execute_code", {"code": "x = 1"})
        assert out == {"code": "x = 1"}

    def test_measure_distance_point_string(self):
        out = units.to_internal(
            "measure_distance",
            {"entity_one": "10, 20, 30", "entity_two": "Body1"},
        )
        assert out["entity_one"] == "1.0,2.0,3.0"
        assert out["entity_two"] == "Body1"

    def test_empty_params(self):
        assert units.to_internal("extrude", None) == {}
        assert units.to_internal("extrude", {}) == {}

    def test_does_not_mutate_input(self):
        params = {"height": 10}
        units.to_internal("extrude", params)
        assert params["height"] == 10


class TestToExternal:
    def test_bbox_and_area_and_volume(self):
        out = units.to_external(
            "get_object_info",
            {
                "ok": True,
                "area": 6.0,
                "volume": 1.0,
                "bounding_box": {"min": [0.0, 0.0, 0.0], "max": [1.0, 2.0, 3.0]},
            },
        )
        assert out["area"] == 600.0
        assert out["volume"] == 1000.0
        assert out["bounding_box"]["max"] == [10.0, 20.0, 30.0]
        assert out["units"] == "mm"

    def test_normals_are_not_scaled(self):
        out = units.to_external(
            "list_faces",
            {
                "faces": [
                    {
                        "area": 1.0,
                        "radius": 0.5,
                        "normal": [0.0, 0.0, 1.0],
                        "point_on_face": [1.0, 2.0, 3.0],
                    }
                ]
            },
        )
        face = out["faces"][0]
        assert face["area"] == 100.0
        assert face["radius"] == 5.0
        assert face["normal"] == [0.0, 0.0, 1.0]
        assert face["point_on_face"] == [10.0, 20.0, 30.0]

    def test_deltas_bbox(self):
        out = units.to_external(
            "extrude",
            {
                "ok": True,
                "height": 1.0,
                "deltas": {
                    "body_count_delta": 1,
                    "mass_g_delta": 7.85,
                    "bbox_after": {"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0]},
                },
            },
        )
        assert out["height"] == 10.0
        assert out["deltas"]["mass_g_delta"] == 7.85
        assert out["deltas"]["bbox_after"]["max"] == [10.0, 10.0, 10.0]
        assert out["deltas"]["body_count_delta"] == 1

    def test_angular_dimension_output_not_scaled(self):
        out = units.to_external(
            "add_dimension", {"dimension_type": "angular", "value": 90}
        )
        assert out["value"] == 90

    def test_length_parameter_value_reported_in_mm(self):
        out = units.to_external(
            "get_parameters",
            {
                "parameters": [
                    {"name": "L", "value": 10.0, "unit": "mm", "expression": "100 mm"}
                ]
            },
        )
        assert out["parameters"][0]["value"] == 100.0
        assert out["parameters"][0]["value_unit"] == "mm"
        assert out["parameters"][0]["expression"] == "100 mm"

    def test_angle_parameter_value_not_scaled(self):
        out = units.to_external(
            "get_parameters",
            {"parameters": [{"name": "A", "value": 1.57, "unit": "deg"}]},
        )
        assert out["parameters"][0]["value"] == 1.57
        assert "value_unit" not in out["parameters"][0]

    def test_ping_has_no_units_stamp(self):
        out = units.to_external("ping", {"status": "pong"})
        assert out == {"status": "pong"}

    def test_bools_are_not_treated_as_numbers(self):
        out = units.to_external("extrude", {"ok": True, "height": 1})
        assert out["ok"] is True
        assert out["height"] == 10


class TestCallSite:
    def test_execute_command_converts_both_ways(self):
        tree = ast.parse((ADDON_SERVER / "command_handler.py").read_text())
        fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "execute_command":
                fn = node
                break
        assert fn is not None
        attrs = {
            n.func.attr
            for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        assert "to_internal" in attrs
        assert "to_external" in attrs
