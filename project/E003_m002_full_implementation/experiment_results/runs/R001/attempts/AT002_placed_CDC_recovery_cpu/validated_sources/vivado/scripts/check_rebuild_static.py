#!/usr/bin/env python3
"""Read-only structural gate for the reviewed format05 production graph.

This is a source/configuration check, not an RTL functional or timing result.
It deliberately uses the .list grammar, Python AST, an SV token stream, and
parsed clock fields rather than searching tool logs for PASS text.
"""

from __future__ import annotations

import argparse
import ast
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path("vivado/manifests/attention_mlp_production_v5_cohort16_sources.list")
REQUIRED_DEFINES = {
    "HAP_BOARD_BUILD",
    "HAP_BOARD_V5",
    "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54",
    "HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core",
}
OLD_SELECTED_MODULES = {
    "hap_mlp_down_group_major_accum_s46",
    "hap_mlp_shared_dual_slice16x12_s44_s46",
    "hap_mlp_down_v5_scheduler16_s46",
    "hap_mlp_serial_ddr_command16_v5_s46",
    "hap_mlp_full_command16_v5_s46",
}
REQUIRED_MODULES = {
    "hap_axi512_dual_engine_dedicated_read",
    "hap_axi256_dedicated_data_router",
    "hap_mlp_down_group_major_accum_s54",
    "hap_mlp_shared_dual_slice16x12_s44_s54",
    "hap_mlp_down_v5_scheduler16_s54",
    "hap_mlp_serial_ddr_command16_v5_s54",
    "hap_mlp_full_command16_s54",
    "hap_mlp_projection_repack12_to16_s32_history2",
    "hap_attention_board_cohort16_core",
    "hap_projection_core16x16_w8_reuse",
    "hap_mlp_tensor_dma_bridge",
    "hap_mlp_axil_control",
    "hap_attention_mlp_production_core",
    "hap_attention_mlp_board_core",
}
BOARD_CLOCK_MODULES = (
    "hap_attention_mlp_board_core",
    "hap_attention_board_cohort16_core",
)
BOARD_CLOCK_PORTS = {
    "core_clk": (100_000_000, "S_AXIL:M_AXI_DATA", "core_rst_n"),
    "ddr0_clk": (200_000_000, "M_AXI_WEIGHT_C0", "ddr0_rst_n"),
    "ddr1_clk": (200_000_000, "M_AXI_WEIGHT_C1", "ddr1_rst_n"),
}


class ContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def inside_root(root: Path, relative: str | Path) -> Path:
    item = Path(relative)
    require(not item.is_absolute(), f"absolute input rejected: {item}")
    require(".." not in item.parts, f"parent traversal rejected: {item}")
    candidate = root / item
    for path in (candidate, *candidate.parents):
        if path == root:
            break
        require(not path.is_symlink(), f"symlink input rejected: {path}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ContractError(f"missing or out-of-root input: {item}") from exc
    require(resolved.is_file(), f"not a regular input file: {item}")
    return resolved


def manifest_tokens(line: str, path: Path, line_number: int) -> list[str]:
    try:
        return shlex.split(line, comments=True, posix=True)
    except ValueError as exc:
        raise ContractError(f"invalid .list row {path}:{line_number}: {exc}") from exc


def expand_manifest(root: Path, manifest: Path) -> tuple[list[Path], list[Path]]:
    root = root.resolve(strict=True)
    seen_manifests: set[Path] = set()
    active: set[Path] = set()
    seen_leaves: set[Path] = set()
    manifests: list[Path] = []
    leaves: list[Path] = []

    def visit(path: Path) -> None:
        require(path not in active, f"recursive .list cycle: {path}")
        if path in seen_manifests:
            return
        active.add(path)
        seen_manifests.add(path)
        manifests.append(path)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            fields = manifest_tokens(line, path, number)
            if not fields:
                continue
            require(len(fields) == 1, f".list row needs one path: {path}:{number}")
            member = inside_root(root, fields[0])
            if member.suffix == ".list":
                visit(member)
            else:
                require(member.suffix in {".sv", ".v", ".mem"},
                        f"unsupported source type: {member}")
                require(member not in seen_leaves,
                        f"duplicate source in profile: {member}")
                seen_leaves.add(member)
                leaves.append(member)
        active.remove(path)

    visit(inside_root(root, manifest))
    require(bool(leaves), "empty production source graph")
    return manifests, leaves


TOKEN_RE = re.compile(
    r"(?P<space>\s+)|(?P<line>//[^\n]*)|(?P<block>/\*.*?\*/)|"
    r'(?P<string>"(?:\\.|[^"\\])*")|'
    r"(?P<number>\d+'[sS]?[bBdDhHoO][0-9a-fA-F_xXzZ?]+|\d[\d_]*)|"
    r"(?P<ident>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<symbol>.)",
    re.DOTALL,
)


def sv_tokens(path: Path, *, keep_strings: bool = False) -> list[str]:
    result = []
    for match in TOKEN_RE.finditer(path.read_text(encoding="utf-8")):
        ignored = {"space", "line", "block"}
        if not keep_strings:
            ignored.add("string")
        if match.lastgroup not in ignored:
            result.append(match.group())
    return result


def module_names(tokens: list[str], defines: dict[str, str]) -> list[str]:
    result = []
    for index, value in enumerate(tokens[:-2]):
        if value != "module":
            continue
        if tokens[index + 1] == "`":
            macro = tokens[index + 2]
            require(macro in defines, f"unresolved module-name macro: {macro}")
            result.append(defines[macro])
        else:
            result.append(tokens[index + 1])
    return result


def module_header(tokens: list[str], name: str) -> tuple[list[str], list[str]]:
    for index in range(len(tokens) - 2):
        if tokens[index:index + 2] != ["module", name]:
            continue
        cursor = index + 2
        parameters: list[str] = []
        if tokens[cursor] == "#":
            require(tokens[cursor + 1] == "(", f"bad parameter header: {name}")
            parameters, cursor = balanced(tokens, cursor + 1)
        require(tokens[cursor] == "(", f"bad port header: {name}")
        ports, _ = balanced(tokens, cursor)
        return parameters, ports
    raise ContractError(f"module declaration missing: {name}")


def balanced(tokens: list[str], start: int) -> tuple[list[str], int]:
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index] == "(":
            depth += 1
        elif tokens[index] == ")":
            depth -= 1
            if depth == 0:
                return tokens[start + 1:index], index + 1
    raise ContractError("unclosed SV parenthesized declaration")


def split_top_level(tokens: list[str]) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for token in tokens:
        if token in {"(", "[", "{"}:
            depth += 1
        elif token in {")", "]", "}"}:
            depth -= 1
        if token == "," and depth == 0:
            result.append(current)
            current = []
        else:
            current.append(token)
    result.append(current)
    return result


def leading_port_attributes(declaration: list[str], owner: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    cursor = 0
    while declaration[cursor:cursor + 2] == ["(", "*"]:
        start = cursor + 2
        cursor = start
        while cursor + 1 < len(declaration) and declaration[cursor:cursor + 2] != ["*", ")"]:
            cursor += 1
        require(cursor + 1 < len(declaration), f"unterminated SV attribute: {owner}")
        for spec in split_top_level(declaration[start:cursor]):
            require(len(spec) == 3 and spec[1] == "=",
                    f"malformed SV attribute: {owner}: {spec}")
            name = spec[0]
            require(name not in attributes, f"duplicate SV attribute {name}: {owner}")
            try:
                value = json.loads(spec[2])
            except json.JSONDecodeError as exc:
                raise ContractError(f"non-string SV attribute {name}: {owner}") from exc
            require(type(value) is str,
                    f"non-string SV attribute {name}: {owner}")
            attributes[name] = value
        cursor += 2
    require("input" in declaration[cursor:], f"clock port is not input: {owner}")
    return attributes


def board_clock_attributes(tokens: list[str], module: str) -> dict[str, int]:
    _, ports = module_header(tokens, module)
    declarations = split_top_level(ports)
    frequencies: dict[str, int] = {}
    for port, (expected_hz, bus, reset) in BOARD_CLOCK_PORTS.items():
        owner = f"{module}.{port}"
        matches = [item for item in declarations if item and item[-1] == port]
        require(len(matches) == 1, f"selected clock port missing/duplicate: {owner}")
        attributes = leading_port_attributes(matches[0], owner)
        try:
            info = shlex.split(attributes["X_INTERFACE_INFO"])
            clauses = next(csv.reader(
                [attributes["X_INTERFACE_PARAMETER"]], skipinitialspace=True
            ))
        except (KeyError, ValueError) as exc:
            raise ContractError(f"clock interface attribute missing/malformed: {owner}") from exc
        require(info == ["xilinx.com:signal:clock:1.0", port, "CLK"],
                f"clock X_INTERFACE_INFO mismatch: {owner}: {info}")
        parameters: dict[str, list[str]] = {}
        for clause in clauses:
            fields = shlex.split(clause.strip())
            require(len(fields) >= 2, f"clock parameter malformed: {owner}: {clause}")
            require(fields[0] not in parameters,
                    f"duplicate clock parameter {fields[0]}: {owner}")
            parameters[fields[0]] = fields[1:]
        require(parameters.get("FREQ_HZ") == [str(expected_hz)],
                f"clock FREQ_HZ mismatch: {owner}: {parameters.get('FREQ_HZ')}")
        expected_bus = bus
        if module == "hap_attention_mlp_board_core" and port == "core_clk":
            expected_bus += ":M_AXI_MLP_DATA"
        require(parameters.get("ASSOCIATED_BUSIF") == [expected_bus],
                f"clock ASSOCIATED_BUSIF mismatch: {owner}")
        require(parameters.get("ASSOCIATED_RESET") == [reset],
                f"clock ASSOCIATED_RESET mismatch: {owner}")
        frequencies[port] = expected_hz
    return frequencies


def sv_integer(tokens: list[str]) -> int:
    literal = "".join(tokens)
    match = re.fullmatch(r"(\d+)'[sS]?([bBdDhHoO])([0-9a-fA-F_]+)", literal)
    if match:
        radix = {"b": 2, "d": 10, "h": 16, "o": 8}[match.group(2).lower()]
        return int(match.group(3).replace("_", ""), radix)
    if re.fullmatch(r"\d[\d_]*", literal):
        return int(literal.replace("_", ""))
    raise ContractError(f"nonliteral SV integer: {literal}")


def localparam_value(tokens: list[str], name: str) -> int:
    for index, token in enumerate(tokens):
        if token != "localparam":
            continue
        end = tokens.index(";", index)
        statement = tokens[index + 1:end]
        if name in statement:
            position = statement.index(name)
            require(statement[position + 1] == "=", f"bad localparam {name}")
            return sv_integer(statement[position + 2:])
    raise ContractError(f"localparam missing: {name}")


def py_constant(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            require(type(value) is int, f"Python constant {name} is not integer")
            return value
    raise ContractError(f"Python constant missing: {path}:{name}")


def py_string_constant(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            require(type(value) is str, f"Python constant {name} is not string")
            return value
    raise ContractError(f"Python constant missing: {path}:{name}")


def simple_expr(tokens: list[str], variables: dict[str, int]) -> int:
    source = "".join(tokens)
    tree = ast.parse(source, mode="eval")

    def value(node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name) and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.BinOp):
            left, right = value(node.left), value(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
        raise ContractError(f"unsupported packed-width expression: {source}")

    return value(tree.body)


def port_width(tokens: list[str], module: str, port: str,
               variables: dict[str, int] | None = None) -> int:
    _, ports = module_header(tokens, module)
    for declaration in split_top_level(ports):
        if port not in declaration:
            continue
        position = declaration.index(port)
        require(position > 0 and declaration[position - 1] == "]",
                f"packed range missing for {module}.{port}")
        open_index = len(declaration[:position]) - 1 - declaration[:position][::-1].index("[")
        range_tokens = declaration[open_index + 1:position - 1]
        require(":" in range_tokens, f"packed range malformed: {module}.{port}")
        colon = range_tokens.index(":")
        env = variables or {}
        msb = simple_expr(range_tokens[:colon], env)
        lsb = simple_expr(range_tokens[colon + 1:], env)
        require(msb >= lsb, f"negative packed range: {module}.{port}")
        return msb - lsb + 1
    raise ContractError(f"port missing: {module}.{port}")


def signal_width(tokens: list[str], name: str) -> int:
    for index, token in enumerate(tokens):
        if token != name or index == 0 or tokens[index - 1] != "]":
            continue
        statement_start = len(tokens[:index]) - 1 - tokens[:index][::-1].index(";") \
            if ";" in tokens[:index] else 0
        declaration = tokens[statement_start:index]
        if not any(item in declaration for item in ("reg", "wire", "logic")):
            continue
        bracket = len(tokens[:index]) - 1 - tokens[:index][::-1].index("[")
        packed = tokens[bracket + 1:index - 1]
        require(":" in packed, f"packed declaration malformed: {name}")
        colon = packed.index(":")
        return simple_expr(packed[:colon], {}) - simple_expr(packed[colon + 1:], {}) + 1
    raise ContractError(f"packed signal missing: {name}")


def unpacked_length(tokens: list[str], name: str) -> int:
    for index, token in enumerate(tokens[:-4]):
        if token != name or tokens[index + 1] != "[":
            continue
        try:
            end = tokens.index("]", index + 2)
            colon = tokens.index(":", index + 2, end)
        except ValueError:
            continue
        low = simple_expr(tokens[index + 2:colon], {})
        high = simple_expr(tokens[colon + 1:end], {})
        require(high >= low, f"unpacked array range malformed: {name}")
        return high - low + 1
    raise ContractError(f"unpacked array missing: {name}")


def dma_command_beats(tokens: list[str]) -> tuple[int, int]:
    for index, token in enumerate(tokens[:-1]):
        if token != "dma_cmd_beats" or tokens[index + 1] != "=":
            continue
        end = tokens.index(";", index)
        expression = tokens[index + 2:end]
        require(expression.count("?") == 1 and expression.count(":") == 1,
                "DMA beat command is not a two-way conditional")
        question = expression.index("?")
        colon = expression.index(":")
        require(question < colon, "DMA beat command order malformed")
        values = {"INPUT_GROUPS": 128, "OUTPUT_TILES": 256}
        return (simple_expr(expression[question + 1:colon], values),
                simple_expr(expression[colon + 1:], values))
    raise ContractError("DMA beat command assignment missing")


def clock_periods(path: Path) -> dict[str, Decimal]:
    clocks: dict[str, Decimal] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("create_clock "):
            continue
        parts = shlex.split(line, comments=True)
        try:
            name = parts[parts.index("-name") + 1]
            period = Decimal(parts[parts.index("-period") + 1])
        except (ValueError, IndexError, InvalidOperation) as exc:
            raise ContractError(f"bad create_clock at {path}:{number}") from exc
        require(name not in clocks, f"duplicate clock: {name}")
        clocks[name] = period
    return clocks


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(root: Path, manifest: Path, xdc: Path,
          defines: set[str]) -> dict[str, object]:
    root = root.resolve(strict=True)
    require(defines == REQUIRED_DEFINES,
            f"production defines mismatch: expected={sorted(REQUIRED_DEFINES)} actual={sorted(defines)}")
    manifests, leaves = expand_manifest(root, manifest)
    names = {path.name for path in leaves}
    require(not any(name.endswith("_s46.sv") for name in names),
            "old S46 source file selected")
    define_values = dict(item.split("=", 1) for item in defines if "=" in item)
    selected_xdc = inside_root(root, xdc)
    source_tokens: dict[Path, list[str]] = {}
    owners: dict[str, Path] = {}
    for path in leaves:
        if path.suffix not in {".sv", ".v"}:
            continue
        tokens = sv_tokens(path)
        source_tokens[path] = tokens
        for module in module_names(tokens, define_values):
            require(module not in owners,
                    f"duplicate module {module}: {owners.get(module)} and {path}")
            owners[module] = path
    missing = REQUIRED_MODULES - owners.keys()
    require(not missing, f"required selected modules missing: {sorted(missing)}")
    stale = OLD_SELECTED_MODULES & owners.keys()
    require(not stale, f"stale Down modules selected: {sorted(stale)}")

    board_clock_hz = {
        module: board_clock_attributes(
            sv_tokens(owners[module], keep_strings=True), module
        ) for module in BOARD_CLOCK_MODULES
    }
    for module, prefix in (("hap_attention_mlp_board_core", "m_mlp_axi"),
                           ("hap_attention_mlp_production_core", "mlp_data_axi")):
        tokens = source_tokens[owners[module]]
        for suffix, expected in (("araddr", 32), ("awaddr", 32),
                                 ("rdata", 256), ("wdata", 256), ("wstrb", 32)):
            require(port_width(tokens, module, f"{prefix}_{suffix}") == expected,
                    f"MLP dedicated data port width mismatch: {module}.{prefix}_{suffix}")

    control = source_tokens[owners["hap_mlp_axil_control"]]
    require(localparam_value(control, "FULL_FORMAT_ID") == 0x48384605,
            "RTL MLP format ID is not 0x48384605")
    require(localparam_value(control, "ABI_VERSION") == 0x00050000,
            "RTL MLP command ABI is not 0x00050000")
    host_hw = inside_root(root, "host/scalellm_hardware.py")
    for name, expected in {
        "MLP_FORMAT_ID": 0x48384605,
        "MLP_ABI": 0x00050000,
        "MLP_TENSOR_INPUT_BEATS": 6144,
        "MLP_TENSOR_OUTPUT_BEATS": 8192,
        "MLP_TENSOR_INPUT_GROUPS": 128,
        "MLP_TENSOR_OUTPUT_TILES": 256,
    }.items():
        require(py_constant(host_hw, name) == expected,
                f"Host {name} contract mismatch")
    model = inside_root(root, "model/mlp_fixed.py")
    for name, expected in {
        "MLP_GATE_UP_TOTAL_SHIFT_MIN": 20,
        "MLP_DOWN_TOTAL_SHIFT_MIN": 12,
        "MLP_TOTAL_SHIFT_MAX": 44,
        "MLP_GATE_UP_GUARD_WIDTH": 37,
        "MLP_DOWN_GUARD_WIDTH": 45,
        "MLP_GATE_UP_ACCUM_WIDTH": 44,
        "MLP_DOWN_ACCUM_WIDTH": 54,
        "MLP_DOWN_OUTPUT_WIDTH": 32,
    }.items():
        require(py_constant(model, name) == expected,
                f"copied model {name} contract mismatch")
    memory = inside_root(root, "host/scalellm_memory.py")
    require(py_constant(memory, "ACTIVATION_INPUT_ELEMENT_BYTES") == 3,
            "Host input element byte count mismatch")
    require(py_constant(memory, "ACTIVATION_OUTPUT_ELEMENT_BYTES") == 4,
            "Host output element byte count mismatch")
    target_model = "meta-llama/Llama-3.1-8B-Instruct"
    exporter = inside_root(root, "model/export_scalellm_llama31_artifacts.py")
    artifacts = inside_root(root, "host/scalellm_artifacts.py")
    for source in (exporter, artifacts):
        require(py_string_constant(source, "MODEL_ID") == target_model,
                f"model identity mismatch in {source.relative_to(root)}")

    down = source_tokens[owners["hap_mlp_down_group_major_accum_s54"]]
    require(port_width(down, "hap_mlp_down_group_major_accum_s54",
                       "in_guard_s45", {"LANES": 128}) == 128 * 45,
            "Down accumulator guard port is not 128xS45")
    require(port_width(down, "hap_mlp_down_group_major_accum_s54",
                       "out_projection_s32", {"LANES": 128}) == 128 * 32,
            "Down accumulator output port is not 128xS32")
    dma = source_tokens[owners["hap_mlp_tensor_dma_bridge"]]
    require(port_width(dma, "hap_mlp_tensor_dma_bridge",
                       "mlp_input_s24x16x32") == 12288,
            "MLP DMA input port is not 12288 bits")
    require(port_width(dma, "hap_mlp_tensor_dma_bridge",
                       "mlp_out_s32x16x16") == 8192,
            "MLP DMA output port is not 8192 bits")
    require(signal_width(dma, "output_tile_hold_r") == 32,
            "DMA tile hold mask is not 32 bits")
    require(signal_width(dma, "output_issue_count_r") >= 6,
            "DMA issue counter cannot represent 32")
    require(signal_width(dma, "output_beat_r") >= 5,
            "DMA beat index cannot represent 31")
    require(unpacked_length(dma, "output_tile_beat_r") == 32,
            "DMA tile bank is not 32 beats")
    require(unpacked_length(dma, "output_mux_group_data_r") == 8,
            "DMA four-beat mux is not eight groups")
    require(dma_command_beats(dma) == (6144, 8192),
            "DMA command beats are not 6144/8192")
    clocks = clock_periods(selected_xdc)
    require(clocks == {
        "core_clk": Decimal("10.000"),
        "ddr0_clk": Decimal("5.000"),
        "ddr1_clk": Decimal("5.000"),
    }, f"Core100/DDR200 clock constraint mismatch: {clocks}")

    inputs = sorted(set(manifests + leaves + [selected_xdc, host_hw, model, memory,
                                            exporter, artifacts,
                                            Path(__file__).resolve()]))
    return {
        "status": "STATIC_CONTRACT_PASS",
        "scope": "source_structure_only_no_functional_or_timing_claim",
        "manifest": str(inside_root(root, manifest).relative_to(root)),
        "xdc": str(selected_xdc.relative_to(root)),
        "defines": sorted(defines),
        "clocks_ns": {name: str(period) for name, period in sorted(clocks.items())},
        "selected_board_clock_hz": board_clock_hz,
        "manifest_count": len(manifests),
        "source_count": len(leaves),
        "module_count": len(owners),
        "inputs_sha256": {str(path.relative_to(root)): sha256(path)
                          for path in inputs},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--xdc", type=Path, required=True)
    parser.add_argument("--define", action="append", default=[])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.root, args.manifest, args.xdc, set(args.define))
    except (ContractError, OSError, SyntaxError) as exc:
        print(json.dumps({"status": "STATIC_CONTRACT_FAIL", "reason": str(exc)},
                         sort_keys=True), file=sys.stderr)
        return 1
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        report_root = args.root.resolve(strict=True) / "vivado/reports/rebuild_validation"
        destination = args.report.resolve(strict=False)
        require(destination.is_relative_to(report_root),
                "report path must be within rebuild_validation")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
