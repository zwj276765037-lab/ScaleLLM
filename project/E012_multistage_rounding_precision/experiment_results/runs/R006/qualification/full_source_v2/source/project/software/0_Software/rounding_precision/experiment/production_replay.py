"""CPU scalar replay of arithmetic expressions read from the active V5 kernel.

This adapter never imports torch/Triton and never imports the exact oracle.
The trusted local kernel AST supplies multiply, shift, wrap, round and clamp
expressions.  Python integers model their valid <=S54 domain exactly; out-of-
contract inputs are diagnostics and do not prove native int64 behavior.
"""
from __future__ import annotations

import ast
from functools import lru_cache
import hashlib
from pathlib import Path

SOFTWARE_ROOT = Path(__file__).resolve().parents[3]
V5_SOURCE = SOFTWARE_ROOT / "0_Software/FPtoQ/experiment/v5_fullchain.py"
PROFILES = {
    "attention": dict(shift_min=26, shift_max=47, guard_width=42,
                      accumulator_width=42, output_width=24,
                      dot_width=21, dot_abs_max=1_036_320, raw_width=37),
    "mlp_gate_up": dict(shift_min=20, shift_max=44, guard_width=37,
                        accumulator_width=44, output_width=24,
                        dot_width=17, dot_abs_max=65_280, raw_width=33),
    "mlp_down": dict(shift_min=12, shift_max=44, guard_width=45,
                     accumulator_width=54, output_width=32,
                     dot_width=17, dot_abs_max=65_280, raw_width=33),
}


class _ScalarTL:
    maximum = staticmethod(max)
    minimum = staticmethod(min)
    where = staticmethod(lambda condition, yes, no: yes if condition else no)


class _Scalarize(ast.NodeTransformer):
    def visit_UnaryOp(self, node):
        # Tensor bool ~ is logical complement; Python bool ~ is integer inversion.
        if isinstance(node.op, ast.Invert) and isinstance(node.operand, ast.Name) \
                and node.operand.id == "legal_shift":
            return ast.copy_location(ast.UnaryOp(op=ast.Not(), operand=node.operand), node)
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        # Selected expressions contain only broadcasting of these scalar loads.
        if isinstance(node.value, ast.Name) and node.value.id in {
                "act_code", "weight_code", "act_shift", "weight_shift"}:
            return ast.copy_location(ast.Name(id=node.value.id, ctx=ast.Load()), node)
        raise ValueError("unsupported production scalar subscript: " + ast.unparse(node))


def _validate_scalar_expression(expression):
    allowed = (ast.Expression, ast.Name, ast.Load, ast.Constant, ast.BinOp,
               ast.UnaryOp, ast.Compare, ast.Call, ast.Attribute,
               ast.Add, ast.Sub, ast.Mult, ast.RShift, ast.LShift, ast.BitAnd,
               ast.USub, ast.Not, ast.GtE, ast.LtE, ast.NotEq)
    names = {"tl", "correlation", "act_code", "weight_code", "act_shift", "weight_shift",
             "raw", "delta", "right", "left", "aligned", "pair_active", "legal_shift",
             "accumulator", "next_accumulator", "guard", "rounded", "SHIFT_MIN", "SHIFT_MAX",
             "COMPUTE_ACCUM_MIN", "COMPUTE_ACCUM_MASK", "OUTPUT_MIN", "OUTPUT_MAX"}
    for node in ast.walk(expression):
        if not isinstance(node, allowed):
            raise ValueError("unsupported active V5 scalar AST node: " + type(node).__name__)
        if isinstance(node, ast.Name) and node.id not in names:
            raise ValueError("unsupported active V5 scalar name: " + node.id)
        if isinstance(node, ast.Constant) and type(node.value) is not int:
            raise ValueError("active V5 scalar constants must be integers")
        if isinstance(node, ast.Attribute) and not (isinstance(node.value, ast.Name)
                and node.value.id == "tl" and node.attr in {"maximum", "minimum", "where"}):
            raise ValueError("unsupported active V5 scalar attribute")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Attribute) or node.keywords):
            raise ValueError("unsupported active V5 scalar call")


@lru_cache(maxsize=1)
def _production_expressions():
    source = V5_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(V5_SOURCE))
    kernel = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_v5_grouped_linear_kernel")
    assignments = {}
    for node in ast.walk(kernel):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            assignments.setdefault(node.targets[0].id, []).append(node)
    expected = ("raw", "delta", "right", "left", "aligned", "pair_active",
                "legal_shift", "next_accumulator", "rounded", "saturated")
    selected = {}
    for name in expected:
        values = assignments.get(name, [])
        if len(values) != 1:
            raise ValueError(f"active V5 AST no longer has one {name} assignment")
        selected[name] = values[0]
    accumulators = [node for node in assignments.get("accumulator", [])
                    if isinstance(node.value, ast.BinOp)]
    guards = [node for node in assignments.get("guard", [])
              if isinstance(node.value, ast.Call)]
    if len(accumulators) != 1 or len(guards) != 1:
        raise ValueError("active V5 AST accumulator/zero-invalid guard contract changed")
    selected["accumulator"] = accumulators[0]
    selected["guard"] = guards[0]
    compiled = {}
    expression_source = {}
    for name, assignment in selected.items():
        expression_source[name] = ast.get_source_segment(source, assignment.value)
        expression = ast.Expression(body=_Scalarize().visit(assignment.value))
        _validate_scalar_expression(expression)
        compiled[name] = compile(ast.fix_missing_locations(expression), str(V5_SOURCE), "eval")
    manifest = {
        "path": str(V5_SOURCE),
        "sha256": hashlib.sha256(source.encode()).hexdigest(),
        "kernel": kernel.name,
        "expression_lines": {name: node.lineno for name, node in selected.items()},
        "scalarization": "broadcast_loads_to_scalars_and_tensor_bool_invert_to_not",
        "allowed_ast_operations": "integer_arithmetic_compare_and_tl_min_max_where_only",
        "expression_sha256": hashlib.sha256(
            repr(sorted(expression_source.items())).encode()).hexdigest(),
        "guard_semantics": "audit_only_no_guard_wrap",
        "accumulator_semantics": "signed_wrap_after_each_group",
    }
    return compiled, manifest


def production_source_identity() -> dict:
    return dict(_production_expressions()[1])


def _limits(width: int) -> tuple[int, int]:
    return -(1 << (width - 1)), (1 << (width - 1)) - 1


def replay_linear(sample: dict) -> dict:
    """Replay fixed code/metadata; invalid active shifts are strict rejections.

    The diagnostic output always follows V5's zero-invalid-guard kernel path.
    Guard values are audited and retained, never silently wrapped.
    """
    profile = PROFILES[sample["profile"]]
    expressions, manifest = _production_expressions()
    namespace = {"tl": _ScalarTL, "accumulator": 0}
    for prefix, width in (("HARDWARE_ACCUM", profile["accumulator_width"]),
                          ("COMPUTE_ACCUM", profile["accumulator_width"]),
                          ("OUTPUT", profile["output_width"])):
        namespace[prefix + "_MIN"], namespace[prefix + "_MAX"] = _limits(width)
    namespace["COMPUTE_ACCUM_MASK"] = (1 << profile["accumulator_width"]) - 1
    namespace["SHIFT_MIN"] = profile["shift_min"]
    namespace["SHIFT_MAX"] = profile["shift_max"]
    errors = {name: 0 for name in (
        "invalid_active_shift", "dot_range", "raw_range", "guard_overflow",
        "accumulator_overflow", "output_saturation")}
    metadata_hints = {"zero_code_nonzero_shift": 0}
    guard_low, guard_high = _limits(profile["guard_width"])
    raw_low, raw_high = _limits(profile["raw_width"])
    trace = []
    g_right = g_nonzero_remainder = 0
    for index, group in enumerate(sample["groups"]):
        namespace.update(correlation=group["dot"], act_code=group["act_code"],
                         act_shift=group["act_shift"], weight_code=group["weight_code"],
                         weight_shift=group["weight_shift"])
        for name in ("raw", "delta", "right", "left", "aligned", "pair_active", "legal_shift"):
            namespace[name] = eval(expressions[name], {"__builtins__": {}}, namespace)
        active = bool(namespace["pair_active"])
        errors["dot_range"] += int(abs(group["dot"]) > profile["dot_abs_max"])
        errors["raw_range"] += int(not raw_low <= namespace["raw"] <= raw_high)
        errors["invalid_active_shift"] += int(active and not namespace["legal_shift"])
        metadata_hints["zero_code_nonzero_shift"] += int(
            (group["act_code"] == 0 and group["act_shift"] != 0)
            or (group["weight_code"] == 0 and group["weight_shift"] != 0))
        errors["guard_overflow"] += int(active and not guard_low <= namespace["aligned"] <= guard_high)
        namespace["guard"] = eval(expressions["guard"], {"__builtins__": {}}, namespace)
        namespace["next_accumulator"] = eval(
            expressions["next_accumulator"], {"__builtins__": {}}, namespace)
        overflow = not (namespace["HARDWARE_ACCUM_MIN"] <= namespace["next_accumulator"]
                        <= namespace["HARDWARE_ACCUM_MAX"])
        errors["accumulator_overflow"] += int(overflow)
        namespace["accumulator"] = eval(expressions["accumulator"], {"__builtins__": {}}, namespace)
        right = namespace["right"]
        remainder = namespace["raw"] % (1 << right) if right else 0
        g_right += int(active and right > 0)
        g_nonzero_remainder += int(active and right > 0 and remainder != 0)
        trace.append({
            "index": index, "raw": str(namespace["raw"]),
            "total_shift": group["act_shift"] + group["weight_shift"],
            "active": active, "legal_shift": bool(namespace["legal_shift"]),
            "aligned_f24_code": str(namespace["aligned"]),
            "guard_f24_code": str(namespace["guard"]),
            "right_shift_bits": right, "floor_remainder": str(remainder),
            "accumulator_f24_code": str(namespace["accumulator"]),
            "accumulator_overflow": overflow,
        })
    for name in ("rounded", "saturated"):
        namespace[name] = eval(expressions[name], {"__builtins__": {}}, namespace)
    errors["output_saturation"] = int(namespace["rounded"] != namespace["saturated"])
    accepted = errors["invalid_active_shift"] == 0
    return {
        "label": "当前实现", "accepted": accepted,
        "output_code": namespace["saturated"] if accepted else None,
        "pre_saturation_code": namespace["rounded"] if accepted else None,
        "accumulator_f24_code": str(namespace["accumulator"]),
        "diagnostic_zero_guard_raw": {
            "output_code": namespace["saturated"],
            "pre_saturation_code": namespace["rounded"],
            "interpretation": "kernel_zero_invalid_guard_diagnostic_not_strict_primary",
        } if not accepted else None,
        "fractional_bits": 16, "g_right": g_right,
        "g_nonzero_remainder": g_nonzero_remainder,
        "error_counts": errors, "metadata_hints": metadata_hints, "group_trace": trace,
        "production_source": manifest,
    }
