"""Independent BF16-input collection. GPU execution requires explicit Root admission.

The BF16 trajectory is only a source of local inputs. This does not attach V5
modules, score tokens, or claim to reproduce a V5 model trajectory.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

from prepare_replay_data import real_capture_plan
from run_local_experiment import identity, memory_available_bytes, write_new

SOFTWARE = Path(__file__).resolve().parents[3]
V5_SOURCE = SOFTWARE / "0_Software/FPtoQ/experiment/v5_fullchain.py"
EXPORTER_SOURCE = SOFTWARE / "model/export_scalellm_llama31_artifacts.py"
LAYERS = (0, 15, 31)
OPS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
GIB = 1 << 30
GPU0_UUID = "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_prompt(path: Path, index: int) -> tuple[str, dict]:
    if not 0 <= index < 64 or path.stat().st_size > 64 << 20:
        raise ValueError("prompt source exceeds bounded selection")
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream):
            if len(line.encode()) > 1 << 20:
                raise ValueError("prompt JSONL line exceeds 1 MiB")
            if line_number == index:
                row = json.loads(line)
                text = row.get("text") if isinstance(row, dict) else None
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("selected line has no nonempty text")
                return text, {"source": identity(path), "line_index_zero_based": index,
                              "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                              "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    raise ValueError("selected prompt line does not exist")


def selected_module_name(layer: int, op: str) -> str:
    # AutoModel returns LlamaModel, whose module names begin with layers.
    return f"layers.{layer}.{'self_attn' if op.endswith('_proj') and op in OPS[:4] else 'mlp'}.{op}"


def validate_geometry(layer: int, op: str, shape: tuple, tokens: int) -> None:
    width = 14336 if op == "down_proj" else 4096
    if layer not in LAYERS or op not in OPS or shape != (1, tokens, width):
        raise ValueError(f"unexpected capture geometry for layer={layer}, op={op}: {shape}")


def static_check(model: Path, prompt_jsonl: Path, prompt_index: int) -> dict:
    plan = real_capture_plan(model)
    if not plan["geometry_matches"]:
        raise ValueError(f"checkpoint metadata mismatch: {plan['errors']}")
    _, prompt = read_prompt(prompt_jsonl, prompt_index)
    required = {V5_SOURCE: {"fp_to_fixed_raw", "prepare_fixed_activation"},
                EXPORTER_SOURCE: {"quantize_folded_rows"}}
    apis = []
    for path, names in required.items():
        tree = ast.parse(path.read_text())
        found = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        if not names <= found:
            raise ValueError(f"production API missing in {path}: {names - found}")
        apis.append({**identity(path), "functions": sorted(names)})
    return {"schema": "m005_capture_static_check_v1", "checked_at": now(),
            "execution_kind": "metadata_and_ast_only", "gpu_initialized": False,
            "plan": plan, "prompt": prompt, "production_apis": apis,
            "tokenizer_files": [identity(model / name) for name in
                                ["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"]
                                if (model / name).is_file()],
            "model_loading": {"class": "transformers.AutoModel (LlamaModel)",
                              "dtype": "bfloat16", "low_cpu_mem_usage": True,
                              "device_map": {"": "cuda:0"}, "local_files_only": True,
                              "trust_remote_code": False, "attn_implementation": "eager",
                              "HF_DEACTIVATE_ASYNC_LOAD": "1",
                              "low_cpu_mem_usage_parameter": "compatibility flag; Transformers5.3 removes it; actual meta/shard path checked in installed loader",
                              "mechanism": "accelerate.init_empty_weights; one safe_open context per tensor; blocking copy directly to GPU0; delete host tensor and close mapping before next parameter",
                              "bulk_from_pretrained_loader": "not used after R002/AT001 RSS failure",
                              "lm_head": "not loaded or evaluated; selected base-model Linear inputs only"}}


def import_numerics():
    sys.path.insert(0, str(SOFTWARE))
    sys.path.insert(0, str(V5_SOURCE.parent))
    import numpy as np
    import torch
    import v5_fullchain as v5
    from model.export_scalellm_llama31_artifacts import LlamaCheckpoint, quantize_folded_rows
    return np, torch, v5, LlamaCheckpoint, quantize_folded_rows


def stage(directory: Path, name: str, **details) -> None:
    with (directory / "stages.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now(), "stage": name, **details}, ensure_ascii=False) + "\n")


def capture_code_identities() -> list[dict]:
    files = [Path(__file__).resolve(), Path(__file__).with_name("prepare_replay_data.py"),
             Path(__file__).with_name("run_local_experiment.py"), V5_SOURCE, EXPORTER_SOURCE,
             SOFTWARE / "model/fixbit_v2.py"]
    try:
        dist = importlib.metadata.distribution("transformers")
        files += [Path(dist.locate_file(f"transformers/{name}"))
                  for name in ["modeling_utils.py", "core_model_loading.py", "models/llama/modeling_llama.py"]]
    except importlib.metadata.PackageNotFoundError:
        pass
    return [identity(path) for path in files if path.is_file()]


def load_streamed_bf16_model(model_dir: Path, device: str, directory: Path):
    """Materialize one BF16 tensor at a time, closing its mapping immediately."""
    import torch
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    from safetensors import safe_open
    from transformers import AutoConfig, AutoModel
    config = AutoConfig.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
    with init_empty_weights(include_buffers=False):
        model = AutoModel.from_config(config, dtype=torch.bfloat16, attn_implementation="eager")
    parameters = dict(model.named_parameters())
    index = json.loads((model_dir / "model.safetensors.index.json").read_text())
    weight_map = index["weight_map"]
    needed = {"model." + name for name in parameters}
    source_model_keys = {key for key in weight_map if key.startswith("model.")}
    if needed != source_model_keys:
        raise ValueError(f"checkpoint/base-model key mismatch: missing={sorted(needed-source_model_keys)}, unexpected={sorted(source_model_keys-needed)}")
    if set(weight_map) - needed - {"lm_head.weight"}:
        raise ValueError("unexpected non-base-model checkpoint tensors; only lm_head.weight may be omitted")
    checks = []
    consumed_bytes = 0
    for name, parameter in parameters.items():
        key = "model." + name
        shard = (model_dir / weight_map[key]).resolve()
        shard.relative_to(model_dir.resolve())
        with safe_open(str(shard), framework="pt", device="cpu") as reader:
            value = reader.get_tensor(key)
            if tuple(value.shape) != tuple(parameter.shape) or value.dtype != torch.bfloat16:
                raise ValueError(f"parameter shape/dtype mismatch: {key}")
            if not value.is_contiguous():
                raise ValueError(f"noncontiguous source tensor: {key}")
            # A view over this one tensor, not an additional model-sized copy.
            tensor_bytes = value.numel() * value.element_size()
            source_tensor_sha = hashlib.sha256(memoryview(value.view(torch.uint8).numpy()).cast("B")).hexdigest()
            consumed_bytes += tensor_bytes
            flat = value.reshape(-1)
            expected_slice = torch.cat([flat[:16], flat[-16:]]).clone()
            set_module_tensor_to_device(model, name, device, value=value, dtype=torch.bfloat16,
                                        non_blocking=False, clear_cache=False)
            if str(device).startswith("cuda"):
                torch.cuda.synchronize(device)
            actual_flat = model.get_parameter(name).detach().reshape(-1)
            actual_slice = torch.cat([actual_flat[:16], actual_flat[-16:]]).to("cpu")
            if not torch.equal(actual_slice.view(torch.uint8), expected_slice.view(torch.uint8)):
                raise AssertionError(f"loaded selected bytes differ: {key}")
            checks.append({"key": key, "shape": list(value.shape), "dtype": str(value.dtype),
                           "bytes": tensor_bytes, "source_tensor_sha256": source_tensor_sha,
                           "selected_first_last_bytes_equal": True,
                           "selected_bytes_sha256": hashlib.sha256(expected_slice.view(torch.uint8).numpy().tobytes()).hexdigest()})
            del actual_slice, actual_flat, expected_slice, flat, value
        # The CPU tensor and safe_open handle both end here, so old shard pages
        # are not retained by a model-wide merged_state_dict or pointer set.
        del reader
        stage(directory, "stream_tensor_loaded", key=key, count=len(checks), total=len(parameters))
    for name, buffer in list(model.named_buffers()):
        if buffer.device.type == "meta":
            raise ValueError(f"uninitialized meta buffer: {name}")
        set_module_tensor_to_device(model, name, device, value=buffer, dtype=buffer.dtype,
                                    non_blocking=False, clear_cache=False)
    if any(parameter.device != torch.device(device) or parameter.dtype != torch.bfloat16
           for parameter in model.parameters()):
        raise RuntimeError("streamed model has wrong-device/dtype or meta parameters")
    if any(buffer.device != torch.device(device) for buffer in model.buffers()):
        raise RuntimeError("streamed model has wrong-device buffers")
    model.eval()
    write_new(directory / "stream_loader_validation.json", {"schema": "m005_stream_loader_validation_v1",
              "model_class": type(model).__name__, "device": device, "parameter_count": len(checks),
              "all_keys_loaded": True, "all_parameters_bf16": True, "no_meta_parameters_or_buffers": True,
              "parameter_dtypes": sorted({str(p.dtype) for p in model.parameters()}),
              "buffer_dtypes": {name: str(buffer.dtype) for name, buffer in model.named_buffers()},
              "consumed_parameter_bytes": consumed_bytes,
              "consumed_base_model_identity_sha256": hashlib.sha256(json.dumps(checks, sort_keys=True).encode()).hexdigest(),
              "source_model_keys_match_exactly": True, "parameters": checks,
              "omitted_non_base_model_keys": sorted(set(weight_map) - needed),
              "comparison_scope": "all parameter names/dtypes/shapes and first/last16 elements; selected Linear full weight rows checked separately",
              "loader": "one CPU safetensors tensor per context, blocking copy, host tensor+mapping released before next"})
    return model


def prepare_tokens(args, tokenizer, directory: Path) -> tuple[dict, dict]:
    text, source = read_prompt(args.prompt_jsonl, args.prompt_index)
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=args.tokens,
                        add_special_tokens=True, padding=False)
    if tuple(encoded["input_ids"].shape) != (1, args.tokens):
        raise ValueError(f"fixed prompt has fewer than {args.tokens} tokens; no padding/repetition is allowed")
    record = {"schema": "m005_bf16_input_identity_v1", **source,
              "input_ids": encoded["input_ids"][0].tolist(),
              "attention_mask": encoded.get("attention_mask")[0].tolist(),
              "tokens": args.tokens, "token_rows": [0, args.tokens - 1],
              "trajectory": "bf16", "scoring_or_generation": False}
    write_new(directory / "input_identity.json", record)
    return encoded, record


def cpu_check(args) -> int:
    # This is set before importing torch, transformers, or triton.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    np, torch, v5, _, quantize = import_numerics()
    import accelerate
    import transformers
    from transformers import AutoTokenizer
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    initialized_before = torch.cuda.is_initialized()
    if initialized_before:
        raise RuntimeError("CPU check unexpectedly initialized CUDA")
    tokenizer = AutoTokenizer.from_pretrained(str(args.model), local_files_only=True, trust_remote_code=False)
    _, token_record = prepare_tokens(args, tokenizer, args.output_dir)
    checks = []
    for width, hwidth in [(24, 27), (32, 35)]:
        probe = torch.arange(-64, 64, dtype=torch.float32).reshape(2, 64) / 64
        raw = v5.fp_to_fixed_raw(probe, width)
        prepared = v5.prepare_fixed_activation(raw, input_width=width, hadamard_width=hwidth)
        checks.append({"input_width": width, "hadamard_width": hwidth,
                       "shape": list(prepared.values_u8.shape), "all_cpu": prepared.values_u8.device.type == "cpu"})
    weight = np.arange(256, dtype=np.float32).reshape(4, 64) / 256 - .5
    for bits in [4, 8]:
        full = quantize(weight, bits)
        chosen = quantize(weight[[0, 3]], bits)
        if not all(np.array_equal(left[[0, 3]], right) for left, right in zip(full, chosen)):
            raise AssertionError("output-row slicing changed production quantization")
    initialized_after = torch.cuda.is_initialized()
    if initialized_after:
        raise RuntimeError("CPU check unexpectedly initialized CUDA")
    packages = {name: importlib.metadata.version(name) for name in
                ["torch", "numpy", "transformers", "accelerate", "safetensors", "triton"]}
    write_new(args.output_dir / "cpu_check.json", {"schema": "m005_capture_cpu_check_v1",
              "execution_kind": "synthetic CPU API checks + tokenizer only; not real capture",
              "python": sys.version, "executable": sys.executable, "packages": packages,
              "cuda_initialized_before": initialized_before, "cuda_initialized_after": initialized_after,
              "frontend_checks": checks, "quantizer_row_slice_equal": True,
              "token_count": token_record["tokens"], "model_loaded": False})
    return 0


def collect(args) -> int:
    if not args.gpu0_qualified:
        raise RuntimeError("Root GPU0 resource admission is required for collect mode")
    np, torch, v5, Checkpoint, quantize = import_numerics()
    from transformers import AutoTokenizer
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(20261019)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tokenizer = AutoTokenizer.from_pretrained(str(args.model), local_files_only=True, trust_remote_code=False)
    encoded, _ = prepare_tokens(args, tokenizer, args.output_dir)
    stage(args.output_dir, "tokenizer_complete", tokens=args.tokens)
    torch.cuda.set_device(0)
    total = torch.cuda.get_device_properties(0).total_memory
    # Keep 1 GiB for context/non-allocator use under the 24 GiB total budget.
    torch.cuda.set_per_process_memory_fraction(min(1., 23 * GIB / total), 0)
    torch.cuda.reset_peak_memory_stats(0)
    stage(args.output_dir, "loading_model", mechanism="explicit meta + per-tensor safe_open/close/blocking GPU copy")
    model = load_streamed_bf16_model(args.model, "cuda:0", args.output_dir)
    model.eval()
    if any(parameter.device.type != "cuda" or parameter.device.index != 0 for parameter in model.parameters()):
        raise RuntimeError("model loading did not place every parameter directly on GPU0")
    stage(args.output_dir, "model_loaded", model_class=type(model).__name__,
          allocated_bytes=torch.cuda.memory_allocated(0), reserved_bytes=torch.cuda.memory_reserved(0))
    captured = {}
    captured_weight_rows = {}
    captured_metadata = {}
    handles = []
    modules = dict(model.named_modules())
    for layer in LAYERS:
        for op in OPS:
            name = selected_module_name(layer, op)
            if name not in modules:
                raise ValueError(f"expected LlamaModel module missing: {name}")
            def hook(_module, inputs, *, layer=layer, op=op, name=name):
                if name in captured:
                    raise RuntimeError(f"selected module called more than once: {name}")
                tensor = inputs[0]
                validate_geometry(layer, op, tuple(tensor.shape), args.tokens)
                chosen = tensor.detach()[0, [0, args.tokens - 1], :].to(device="cpu", dtype=torch.float32)
                if not torch.isfinite(chosen).all().item():
                    raise ValueError(f"nonfinite real activation at {name}")
                captured[name] = chosen.contiguous()
                captured_metadata[name] = {"module": name, "source_dtype": str(tensor.dtype),
                                           "source_device": str(tensor.device), "source_shape": list(tensor.shape)}
                out_features = int(_module.weight.shape[0])
                channels = [0, 1, 63, out_features - 1]
                captured_weight_rows[name] = _module.weight.detach()[channels].to(device="cpu", dtype=torch.float32).contiguous()
                stage(args.output_dir, "module_captured", **captured_metadata[name],
                      allocated_bytes=torch.cuda.memory_allocated(0), reserved_bytes=torch.cuda.memory_reserved(0))
            handles.append(modules[name].register_forward_pre_hook(hook))
    try:
        with torch.inference_mode():
            result = model(**{key: value.to("cuda:0") for key, value in encoded.items()},
                           use_cache=False, output_attentions=False, output_hidden_states=False, return_dict=True)
        del result
        torch.cuda.synchronize(0)
    finally:
        for handle in handles:
            handle.remove()
    if len(captured) != len(LAYERS) * len(OPS):
        raise RuntimeError("incomplete selected module coverage")
    gpu_peaks = {"max_allocated_bytes": torch.cuda.max_memory_allocated(0),
                 "max_reserved_bytes": torch.cuda.max_memory_reserved(0)}
    del modules, model
    gc.collect()
    torch.cuda.empty_cache()
    stage(args.output_dir, "forward_complete_gpu_weights_released", **gpu_peaks)
    checkpoint = Checkpoint(args.model)
    artifact_dir = args.output_dir / "integer_artifacts"
    artifact_dir.mkdir()
    records = []
    source_code = [identity(V5_SOURCE), identity(EXPORTER_SOURCE)]
    common_sources = [identity(args.output_dir / "input_identity.json"), *source_code]
    audits = {}
    with (args.output_dir / "captured_input.jsonl").open("x", encoding="utf-8") as output:
        for layer in LAYERS:
            for op in OPS:
                name = selected_module_name(layer, op)
                tensor_name = "model." + name + ".weight"
                source_input = captured.pop(name)
                out_features = int(checkpoint._reader(tensor_name).info(tensor_name)["shape"][0])
                columns = [0, 1, 63, out_features - 1]
                source_weight = checkpoint.float32(tensor_name, rows=columns)
                actual_weight = captured_weight_rows.pop(name).numpy()
                if not np.array_equal(actual_weight, source_weight):
                    raise AssertionError(f"captured GPU weight rows differ from original BF16 slices: {name}")
                bits = 8 if op in OPS[:4] else 4
                weight, wc, ws = quantize(source_weight, bits)
                width, hwidth = (32, 35) if op == "down_proj" else (24, 27)
                audit = v5.V5Audit(torch.device("cpu"))
                raw = v5.fp_to_fixed_raw(source_input, width, audit)
                activation = v5.prepare_fixed_activation(raw, input_width=width, hadamard_width=hwidth, audit=audit)
                qa = activation.values_u8.numpy()
                zp = activation.zero_points_u8.numpy()
                ac = activation.codes_u8.numpy()
                ash = activation.shifts_u8.numpy()
                expected_groups = 448 if op == "down_proj" else 128
                if qa.shape != (2, expected_groups, 32) or weight.shape != (4, expected_groups, 32):
                    raise ValueError("prepared integer geometry mismatch")
                artifact = artifact_dir / f"layer{layer:02d}_{op}.npz"
                with artifact.open("xb") as stream:
                    np.savez_compressed(stream, source_input_float32=source_input.numpy(),
                                        source_weight_float32=source_weight, loaded_weight_rows_float32=actual_weight,
                                        source_fixed_raw=raw.numpy(),
                                        q_a=qa, zero_point=zp, act_code=ac, act_shift=ash,
                                        q_w=weight, weight_code=wc, weight_shift=ws,
                                        token_rows=np.array([0, args.tokens - 1]), output_channels=np.array(columns))
                artifact_id = identity(artifact)
                audits[name] = audit.collect()
                profile = "attention" if op in OPS[:4] else ("mlp_down" if op == "down_proj" else "mlp_gate_up")
                for row_index, token in enumerate([0, args.tokens - 1]):
                    for column_index, column in enumerate(columns):
                        dot = ((qa[row_index].astype(np.int64) - zp[row_index, :, None].astype(np.int64))
                               * weight[column_index].astype(np.int64)).sum(axis=-1)
                        groups = [{"dot": int(dot[g]), "act_code": int(ac[row_index, g]),
                                   "act_shift": int(ash[row_index, g]), "weight_code": int(wc[column_index, g]),
                                   "weight_shift": int(ws[column_index, g]),
                                   "lane_evidence": {"q_a": qa[row_index, g].tolist(),
                                                     "q_w": weight[column_index, g].tolist(),
                                                     "zero_point": int(zp[row_index, g])}} for g in range(expected_groups)]
                        item = {"schema_version": 1, "sample_id": f"bf16:l{layer}:{op}:t{token}:c{column}",
                                "kernel": "linear_recovery", "profile": profile, "groups": groups,
                                "provenance": {"kind": "real_trace", "model": "Llama-3.1-8B-Instruct",
                                    "layer": layer, "op": op, "source_format_id": None,
                                    "trajectory": "bf16", "token": token, "column": column,
                                    "adapter_target_format_id": "0x48384103" if profile == "attention" else "0x48384605",
                                    "input_width": width, "hadamard_width": hwidth,
                                    "captured_activation": captured_metadata[name],
                                    "group_selection": "all input groups in natural order",
                                    "source_files": [{"path": source["path"], "sha256": source["sha256"]}
                                                     for source in [artifact_id, *common_sources]],
                                    "limitation": "BF16 trajectory input passed through production local frontend; not full V5 trajectory"}}
                        output.write(json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
                        records.append(item["sample_id"])
                output.flush()
                stage(args.output_dir, "integer_artifact_frozen", module=name, artifact=artifact_id,
                      frontend_audit=audits[name])
    write_new(args.output_dir / "capture_summary.json", {"schema": "m005_bf16_capture_summary_v1",
              "trajectory": "bf16", "local_replay_only": True, "tokens": args.tokens,
              "selected_layers": list(LAYERS), "selected_ops": list(OPS), "outputs": len(records),
              "ordered_group_records": 29184, "lane_evidence_present_for_all_groups": True,
              "captured_input": identity(args.output_dir / "captured_input.jsonl"),
              "frontend_audits": audits, "gpu_peaks": gpu_peaks,
              "checkpoint_content_identity": "metadata and consumed selected weight slices only; full checkpoint hash not recomputed",
              "ppl_evaluated": False, "acc_evaluated": False, "v5_trajectory_evaluated": False})
    return 0


def rss_bytes(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def own_gpu_bytes(pid: int) -> int | None:
    try:
        probe = subprocess.run(["nvidia-smi", "-i", GPU0_UUID, "--query-compute-apps=pid,used_gpu_memory",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
        if probe.returncode:
            return None
        values = [int(parts[1].strip()) << 20 for line in probe.stdout.splitlines()
                  if len(parts := line.split(",")) == 2 and parts[0].strip() == str(pid)]
        return sum(values)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def gpu_snapshot() -> dict:
    query = subprocess.run(["nvidia-smi", "-i", GPU0_UUID,
                            "--query-gpu=uuid,memory.free,memory.total,name", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3, check=True)
    parts = [part.strip() for part in query.stdout.strip().split(",")]
    if len(parts) != 4 or parts[0] != GPU0_UUID:
        raise ValueError("GPU0 UUID query did not return the frozen device identity")
    return {"observed_at": now(), "uuid": parts[0], "free_bytes": int(parts[1]) << 20,
            "total_bytes": int(parts[2]) << 20, "name": parts[3]}


def terminate_owned_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def supervise(args) -> int:
    if args.mode == "collect" and not args.gpu0_qualified:
        raise RuntimeError("collect mode requires the already-qualified GPU0 flag from Root")
    if args.tokens not in (32, 128) or not 1 <= args.wall_seconds <= 300:
        raise ValueError("capture requires 32/128 tokens and <=300 seconds")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if (args.output_dir / "capture_manifest.json").exists():
        raise FileExistsError("capture attempt already has evidence; use a new AT")
    checked = static_check(args.model, args.prompt_jsonl, args.prompt_index)
    write_new(args.output_dir / "static_check.json", checked)
    code = capture_code_identities()
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", "--mode", args.mode,
               "--model", str(args.model), "--prompt-jsonl", str(args.prompt_jsonl),
               "--prompt-index", str(args.prompt_index), "--tokens", str(args.tokens),
               "--output-dir", str(args.output_dir), "--wall-seconds", str(args.wall_seconds)]
    if args.gpu0_qualified:
        command.append("--gpu0-qualified")
    manifest = {"schema": "m005_capture_manifest_v1", "started_at": now(), "mode": args.mode,
                "command": command, "parent_command": [sys.executable, *sys.argv], "code": code,
                "input": checked["prompt"], "model_metadata": checked["plan"]["metadata_identities"],
                "tokenizer_files": checked["tokenizer_files"],
                "resources": {"threads": 2, "cpu_rss_bytes": 8 * GIB, "gpu_process_bytes": 24 * GIB,
                              "torch_reserved_cap_bytes": 23 * GIB, "wall_seconds": args.wall_seconds},
                "gpu0_admission_supplied": args.gpu0_qualified,
                "checkpoint_weight_content_fully_hashed": False}
    write_new(args.output_dir / "capture_manifest.json", manifest)
    if args.mode == "static-check":
        write_new(args.output_dir / "capture_receipt.json", {"execution_state": "completed", "exit_code": 0,
                  "started_at": manifest["started_at"], "ended_at": now(), "kind": "metadata_only", "worker_launched": False})
        return 0
    available = memory_available_bytes()
    if available is None or available < 32 * GIB:
        write_new(args.output_dir / "capture_receipt.json", {"execution_state": "blocked", "exit_code": 75,
                  "started_at": manifest["started_at"], "ended_at": now(), "reason": "available RAM below32GiB/unknown"})
        return 75
    if args.mode == "collect":
        admission = gpu_snapshot()
        apps = subprocess.run(["nvidia-smi", "-i", GPU0_UUID,
                               "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory",
                               "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3, check=True)
        write_new(args.output_dir / "resource_preflight.json", {**admission,
                  "available_ram_bytes": available, "existing_compute_apps": apps.stdout,
                  "minimum_free_at_launch_bytes": 30 * GIB, "minimum_free_runtime_bytes": 8 * GIB})
        if admission["free_bytes"] < 30 * GIB:
            write_new(args.output_dir / "capture_receipt.json", {"execution_state": "blocked", "exit_code": 75,
                      "started_at": manifest["started_at"], "ended_at": now(), "reason": "GPU0 free memory below30GiB; no worker launched"})
            return 75
    env = os.environ.copy()
    for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        env[key] = "2"
    env["TOKENIZERS_PARALLELISM"] = "false"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HF_DEACTIVATE_ASYNC_LOAD"] = "1"
    if args.mode == "cpu-check":
        env["CUDA_VISIBLE_DEVICES"] = ""
    else:
        env["CUDA_VISIBLE_DEVICES"] = GPU0_UUID
    stop = None
    max_rss = 0
    max_gpu = 0
    start = time.monotonic()
    with (args.output_dir / "capture_stdout.log").open("x") as stdout, \
         (args.output_dir / "capture_stderr.log").open("x") as stderr, \
         (args.output_dir / "resource_samples.jsonl").open("x") as samples:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
        write_new(args.output_dir / "capture_launch.json", {"worker_pid": process.pid, "launched_at": now()})
        try:
            while process.poll() is None:
                rss = rss_bytes(process.pid)
                gpu = own_gpu_bytes(process.pid) if args.mode == "collect" else 0
                try:
                    device = gpu_snapshot() if args.mode == "collect" else None
                except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    device = None
                max_rss = max(max_rss, rss or 0)
                max_gpu = max(max_gpu, gpu or 0)
                samples.write(json.dumps({"at": now(), "elapsed": time.monotonic() - start,
                                         "worker_pid": process.pid, "rss_bytes": rss, "own_gpu_bytes": gpu,
                                         "gpu0_free_bytes": device["free_bytes"] if device else None}) + "\n")
                samples.flush()
                if rss is not None and rss > 8 * GIB:
                    stop = "assigned worker 8 GiB RSS budget"
                elif gpu is not None and gpu > 24 * GIB:
                    stop = "assigned worker 24 GiB GPU budget"
                elif args.mode == "collect" and (device is None or gpu is None):
                    stop = "GPU memory telemetry unavailable; cannot enforce resource contract"
                elif device is not None and device["free_bytes"] < 8 * GIB:
                    stop = "shared GPU0 free memory below 8 GiB; stop own worker only"
                elif time.monotonic() - start > max(1, args.wall_seconds - 5):
                    stop = "assigned capture wall-time budget"
                elif sum(p.stat().st_size for p in args.output_dir.rglob("*") if p.is_file()) > 256 << 20:
                    stop = "assigned 256 MiB evidence budget"
                if stop:
                    terminate_owned_group(process)
                    break
                time.sleep(.5)
        finally:
            terminate_owned_group(process)
        native = process.wait()
    unchanged = code == capture_code_identities()
    exit_code = 124 if stop else native
    if exit_code == 0 and not unchanged:
        exit_code = 76
        stop = "collector/production source changed during execution"
    receipt = {"schema": "m005_capture_receipt_v1", "execution_state": "completed" if exit_code == 0 else "failed",
               "started_at": manifest["started_at"], "ended_at": now(), "wall_seconds": time.monotonic() - start,
               "exit_code": exit_code, "worker_returncode": native, "stop_reason": stop,
               "worker_pid": process.pid, "worker_reaped": True, "source_unchanged": unchanged,
               "max_observed_rss_bytes": max_rss, "max_observed_own_gpu_bytes": max_gpu,
               "available_ram_at_start_bytes": available, "monitor_interval_seconds": .5}
    write_new(args.output_dir / "capture_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["static-check", "cpu-check", "collect"], default="static-check")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--prompt-jsonl", required=True, type=Path)
    parser.add_argument("--prompt-index", type=int, default=0)
    parser.add_argument("--tokens", type=int, choices=[32, 128], default=32)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--wall-seconds", type=int, default=300)
    parser.add_argument("--gpu0-qualified", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.model = args.model.resolve()
    args.prompt_jsonl = args.prompt_jsonl.resolve()
    args.output_dir = args.output_dir.resolve()
    try:
        if args.worker:
            result = cpu_check(args) if args.mode == "cpu-check" else collect(args)
        else:
            result = supervise(args)
    except Exception:
        traceback.print_exc()
        result = 1
    raise SystemExit(result)


if __name__ == "__main__":
    main()
