#!/usr/bin/env python3
"""Run 1..16 independent token-ID requests on the new final FPGA image."""
import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sys
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from final.common import (ROOT, CHECKPOINT_SHA, bootstrap, cpu_budget,
                          read_requests, sha as file_sha, source_check)
bootstrap()


def remaining_full_rounds(slots):
    """Maximum remaining full-layer steps, with final prompt step yielding token1."""
    rounds = []
    for slot in slots:
        if slot.finished:
            rounds.append(0)
            continue
        prompt_left = max(0, len(slot.prompt) - slot.position)
        generation_left = max(0, slot.max_new_tokens - len(slot.generated))
        rounds.append(prompt_left + generation_left - int(prompt_left > 0 and generation_left > 0))
    return max(rounds, default=0)


def main(argv=None, config=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--requests", required=True,
                        help="JSON list of {slot,prompt_token_ids,max_new_tokens}")
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-timeout-seconds", type=float, default=120)
    parser.add_argument("--wall-seconds", type=float, default=7200)
    parser.add_argument("--power-log", action="append", default=[],
                        help="external sampler log reference; sampler lifecycle is external")
    args = parser.parse_args(argv)
    source_check()
    requests = read_requests(args.requests)
    if not 0 < args.command_timeout_seconds <= 600 or not 0 < args.wall_seconds <= 86400:
        raise ValueError("positive finite bounded command/wall timeouts required")
    if os.name != "nt":
        raise RuntimeError("actual deployment requires a local Windows XDMA device")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(key) != "1":
            raise RuntimeError("set CPU numerical worker count to one before deployment")
    cpu_affinity = cpu_budget(8)
    from final.preflight import driver_identity
    driver = driver_identity((config or {}).get("expected_driver_sha256"))
    from host_math import HostAssets
    from scalellm_windows_xdma import WindowsXdmaSession
    from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
    from host.scalellm_final_assets import FinalAssetStore, FinalHostAssetsModel
    from host.scalellm_final_runtime import FinalBoardBackend, FinalDecodeRuntime, HostModelAdapter
    from host.scalellm_final_abi import IDS, CSR
    from resource_guard import ResourceGuard
    out = Path(args.result).resolve(); out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    started_unix = time.time()
    guard = ResourceGuard(rss_limit=8 << 30, available_floor=2 << 30)
    assets = HostAssets(args.assets, verify=True)
    artifacts = GuOnlyArtifactManifest.load(args.artifacts, verify_hashes=True)
    if artifacts.original.checkpoint_sha256 != assets.manifest["checkpoint_sha256"]:
        raise ValueError("CPU/FPGA checkpoint identity mismatch")
    stops = set()
    for metadata in (assets.config, assets.generation_config):
        values = metadata.get("eos_token_id", [])
        stops.update(values if isinstance(values, list) else [values])
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(assets.file("tokenizer")))
    report = dict(schema="scalellm_final_decode16_execution_v1", abi=IDS,
                  execution="RUNNING", numerical_verification="NOT_RUN",
                  checkpoint_sha256=artifacts.original.checkpoint_sha256,
                  requests=requests, started_unix=started_unix, receipts=[], steps=[],
                  deployment_config=config, driver=driver, cpu_affinity=cpu_affinity,
                  source_manifest_sha256=file_sha(ROOT / "deploy/vendor_manifest.json"),
                  artifact_manifest_sha256=file_sha(args.artifacts),
                  host_manifest_sha256=file_sha(args.assets),
                  requests_sha256=file_sha(args.requests),
                  cache_integrity="full startup hashes; FPGA and Down assets also hashed on each actual read",
                  external_power_logs=[dict(path=str(Path(path).resolve()), status="REFERENCED")
                                       for path in args.power_log],
                  power_analysis="NOT_RUN; externally sampled logs are references only",
                  decoding_strategy="existing greedy top1; original EOS IDs retained",
                  wall_limit_seconds=args.wall_seconds)
    def save():
        report["resources"] = guard.summary()
        temporary = out / "run.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(out / "run.json")
    def event(kind, **fields):
        resources = guard()
        elapsed = time.monotonic() - started
        if elapsed >= args.wall_seconds:
            raise TimeoutError("model stage wall limit; no automatic reset/retry")
        record = dict(event=kind, elapsed_seconds=elapsed, utc=time.time(),
                      resources=resources, **fields)
        with (out / "progress.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        save()
    class ObservedBackend(FinalBoardBackend):
        def run(self, descriptor, payload, validate_output=None):
            event("command_begin", command_id=descriptor.command_id,
                  layer=descriptor.layer, opcode=descriptor.opcode,
                  descriptor_words=descriptor.words(), input_sha256=hashlib.sha256(payload).hexdigest())
            output = super().run(descriptor, payload, validate_output)
            event("command_complete", **self.receipts[-1],
                  output_sha256=hashlib.sha256(output).hexdigest())
            return output
    class ObservedStore(FinalAssetStore):
        def prepare_layer(self, layer, rows):
            event("layer_prepare_begin", layer=layer)
            begin = time.monotonic()
            generation = super().prepare_layer(layer, rows)
            event("layer_prepared", layer=layer, seconds=time.monotonic()-begin)
            return generation
        def run(self, layer, down_input):
            begin = time.monotonic()
            result = super().run(layer, down_input)
            event("host_down_complete", layer=layer, seconds=time.monotonic()-begin)
            return result
    class ObservedModel(HostModelAdapter):
        def predict(self, hidden, mask):
            begin = time.monotonic()
            result = super().predict(hidden, mask)
            event("lm_head_complete", seconds=time.monotonic()-begin, predictions=result)
            return result
    save()
    runtime = None
    session = None
    try:
        with WindowsXdmaSession(timeout_ms=5000, log_path=str(out / "xdma.jsonl")) as session:
            backend = ObservedBackend(session, args.command_timeout_seconds)
            store = ObservedStore(backend, artifacts, assets)
            model = ObservedModel(FinalHostAssetsModel(assets), store)
            report["receipts"], report["asset_receipts"] = backend.receipts, store.receipts
            runtime = FinalDecodeRuntime(backend, model, store, stops)
            seen = set()
            for request in requests:
                if set(request) != {"slot", "prompt_token_ids", "max_new_tokens"} or request["slot"] in seen:
                    raise ValueError("exact unique request slot fields required")
                seen.add(request["slot"])
                runtime.allocate(request["slot"], request["prompt_token_ids"], request["max_new_tokens"])
            event("resident_load_begin")
            begin = time.monotonic()
            store.load_resident()
            event("resident_load_complete", seconds=time.monotonic()-begin)
            checkpoint_generation = 0
            while any(not slot.finished for slot in runtime.slots):
                receipt_start = len(backend.receipts)
                begin = time.monotonic()
                emitted = runtime.step()
                seconds = time.monotonic()-begin
                report["steps"].append(dict(index=len(report["steps"]), seconds=seconds,
                                             emitted=emitted,
                                             fpga_cycles=sum(value['cycles'] for value in backend.receipts[receipt_start:]),
                                             phase='generation' if emitted else 'prefill',
                                             slots=[dataclasses.asdict(s) for s in runtime.slots]))
                report.update(slots=[dataclasses.asdict(slot) for slot in runtime.slots],
                              receipts=backend.receipts, asset_receipts=store.receipts)
                remaining = remaining_full_rounds(runtime.slots)
                recent = [step['seconds'] for step in report['steps'][-4:]]
                conservative_round = max(recent)
                report['eta'] = dict(remaining_full_rounds=remaining,
                                    recent_max_round_seconds=conservative_round,
                                    estimated_remaining_seconds=remaining*conservative_round,
                                    projected_total_seconds=time.monotonic()-started+remaining*conservative_round)
                event("position_committed", emitted=emitted, seconds=seconds,
                      phase=report['steps'][-1]['phase'],
                      fpga_cycles=report['steps'][-1]['fpga_cycles'],
                      generated_each_slot=[len(slot.generated) for slot in runtime.slots],
                      positions=[slot.position for slot in runtime.slots],
                      eos_slots=[index for index, slot in enumerate(runtime.slots)
                                 if slot.generated and slot.generated[-1] in stops],
                      **report['eta'])
                generated = max(len(slot.generated) for slot in runtime.slots)
                if generated and (checkpoint_generation == 0 or generated//4 > checkpoint_generation//4
                                  or not remaining):
                    decoded = {str(index): dict(generated_ids=slot.generated,
                                               text=tokenizer.decode(slot.generated, skip_special_tokens=False),
                                               position=slot.position, finished=slot.finished,
                                               eos=bool(slot.generated and slot.generated[-1] in stops))
                               for index, slot in enumerate(runtime.slots) if slot.prompt}
                    name = 'decode_checkpoint_%03d.json' % len(report['steps'])
                    (out/name).write_text(json.dumps(decoded, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
                    checkpoint_generation = generated
                    event('generation_checkpoint', file=name, generated_max=generated, decoded=decoded)
                if len(report["steps"]) == 1:
                    # This real first 32-layer round is the pilot; its KV remains
                    # live for the next round, with no repeat or reference KV.
                    estimate = time.monotonic()-started + remaining*seconds
                    report["pilot"] = dict(first_full_round_seconds=seconds,
                                           remaining_full_rounds=remaining,
                                           projected_total_seconds=estimate,
                                           same_session_KV_preserved=True)
                    event("pilot_complete", **report["pilot"])
                    if estimate > args.wall_seconds:
                        raise TimeoutError("measured pilot exceeds stage budget; committed first round preserved")
            report.update(execution="COMPLETE", seconds=time.time() - report["started_unix"],
                          outputs={str(slot): state.generated for slot, state in enumerate(runtime.slots)
                                   if state.prompt})
            report["decoded"] = {str(slot): dict(stop_reason="eos" if state.generated and state.generated[-1] in stops else "length_limit",
                                                 prompt=tokenizer.decode(list(state.prompt), skip_special_tokens=False),
                                                 generated=tokenizer.decode(state.generated, skip_special_tokens=False),
                                                 eos=bool(state.generated and state.generated[-1] in stops))
                                 for slot, state in enumerate(runtime.slots) if state.prompt}
            backend.require_quiescent()
            report["final_quiescent"] = True
            report["final_status"] = {name: session.read32(CSR[name])
                                      for name in ("STATUS", "ADMISSION_ERROR", "DONE_ERROR")}
    except BaseException as error:
        report.update(execution="FAIL", error=repr(error),
                      slots=[] if runtime is None else [dataclasses.asdict(s) for s in runtime.slots],
                      pending_descriptor=None if runtime is None or runtime.backend.pending is None
                          else runtime.backend.pending.words())
        raise
    finally:
        report["handles_closed"] = (session is not None and not session.handles and not session.quarantine)
        for record in report["external_power_logs"]:
            path = Path(record["path"])
            try:
                if path.is_file():
                    record.update(status="SNAPSHOT_AT_RUN_END", bytes=path.stat().st_size,
                                  sha256=file_sha(path), captured_unix=time.time())
                else:
                    record["status"] = "NOT_PRESENT_AT_RUN_END"
            except OSError as error:
                record.update(status="UNREADABLE_AT_RUN_END", error=repr(error))
        save()
    lines = ["slot %s (%s)\n%s" % (slot, value["stop_reason"], value["generated"])
             for slot, value in report["decoded"].items()]
    (out / "outputs.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"execution": report["execution"], "numerical_verification": report["numerical_verification"],
                      "result": str(out), "decoded": report["decoded"]}, ensure_ascii=False))


if __name__ == "__main__": main()
