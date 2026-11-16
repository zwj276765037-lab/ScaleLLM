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
from final.common import (ROOT, DEFAULT_PROFILE, bootstrap, check_bit, cpu_budget,
                          profile_identity, read_program_receipt, read_requests,
                          sha as file_sha, source_check, validate_timeouts)
from final.execution import (BENCHMARK_KV128, DECODE, ORIGINAL_REQUESTS_SHA, RunHooks,
                             allocate_requests, benchmark_requests, create_runtime,
                             policy_description, validate_benchmark_report)
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


def main(argv=None, config=None, *, execution_policy=DECODE, hooks=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--requests", required=True,
                        help="JSON list of {slot,prompt_token_ids,max_new_tokens}")
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-timeout-seconds", type=float, default=120)
    parser.add_argument("--wall-seconds", type=float, default=None,
                        help="optional cumulative run limit; disabled by default")
    parser.add_argument("--program-receipt", help="successful prior SRAM programming receipt")
    parser.add_argument("--power-log", action="append", default=[],
                        help="external sampler log reference; sampler lifecycle is external")
    args = parser.parse_args(argv)
    source_check()
    policy = policy_description(execution_policy)
    hooks = hooks or RunHooks()
    if not isinstance(hooks, RunHooks):
        raise TypeError('hooks must be a RunHooks instance')
    requests = (benchmark_requests(args.requests) if execution_policy == BENCHMARK_KV128
                else read_requests(args.requests))
    validate_timeouts(args.command_timeout_seconds, args.wall_seconds)
    profile = profile_identity((config or {}).get('deployment_profile', DEFAULT_PROFILE))
    if execution_policy == BENCHMARK_KV128 and profile['name'] != 'all-dsp':
        raise ValueError('The public KV128 benchmark requires the all-dsp deployment profile')
    if execution_policy == BENCHMARK_KV128 and args.program_receipt is None:
        raise ValueError('Live KV128 requires a successful all-dsp --program-receipt')
    bit = check_bit((config or {}).get('bitstream',
                    ROOT / 'resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit'),
                    profile['name'])
    programming = None if args.program_receipt is None else read_program_receipt(args.program_receipt, profile['name'])
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
    from host.scalellm_final_runtime import FinalBoardBackend, HostModelAdapter
    from host.scalellm_final_abi import IDS, CSR
    from resource_guard import ResourceGuard
    out = Path(args.result).resolve(); out.mkdir(parents=True, exist_ok=False)
    requests_path = Path(args.requests).resolve()
    if execution_policy == BENCHMARK_KV128:
        requests_path = out / 'requests.json'
        requests_path.write_text(json.dumps(requests, indent=2) + '\n', encoding='utf-8')
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
                  result=str(out), execution_policy=policy, deployment_profile=profile,
                  bitstream_file=dict(path=str(bit), sha256=profile['bit_sha256'], bytes=profile['bit_bytes']),
                  programming_receipt=programming,
                  image_provenance='PROGRAM_RECEIPT_RECORDED' if programming else 'UNVERIFIED',
                  resident_image_identity='ABI checked; caller-supplied programming receipt is the image provenance record',
                  deployment_config=config, driver=driver, cpu_affinity=cpu_affinity,
                  source_manifest_sha256=file_sha(ROOT / "deploy/vendor_manifest.json"),
                  artifact_manifest_sha256=file_sha(args.artifacts),
                  host_manifest_sha256=file_sha(args.assets),
                  requests_sha256=file_sha(requests_path),
                  cache_integrity="full startup hashes; FPGA and Down assets also hashed on each actual read",
                  external_power_logs=[dict(path=str(Path(path).resolve()), status="REFERENCED")
                                       for path in args.power_log],
                  power_analysis="NOT_RUN; externally sampled logs are references only",
                  decoding_strategy=("existing greedy top1; original EOS IDs retained" if policy['eos_retirement']
                                     else "existing greedy top1; EOS observed through fixed position127"),
                  instrumentation="command/step hooks and capture reads contribute to elapsed time; DONE cycles retain the FPGA command definition",
                  wall_limit_seconds=args.wall_seconds)
    if execution_policy == BENCHMARK_KV128:
        benchmark_source = dict(schema='scalellm_portable_kv128_source_v1',
                                deployment_profile=profile, execution_policy=policy,
                                original_requests_sha256=ORIGINAL_REQUESTS_SHA,
                                benchmark_requests_sha256=report['requests_sha256'],
                                source_manifest_sha256=report['source_manifest_sha256'],
                                artifact_manifest_sha256=report['artifact_manifest_sha256'],
                                host_manifest_sha256=report['host_manifest_sha256'])
        (out / 'benchmark_source.json').write_text(json.dumps(benchmark_source, indent=2) + '\n', encoding='utf-8')
    def save():
        report["resources"] = guard.summary()
        temporary = out / "run.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(out / "run.json")
    def event(kind, **fields):
        resources = guard()
        elapsed = time.monotonic() - started
        if args.wall_seconds is not None and elapsed >= args.wall_seconds:
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
            if hooks.before_command is not None:
                hooks.before_command(self, descriptor, payload)
            output = super().run(descriptor, payload, validate_output)
            if hooks.after_command is not None:
                hooks.after_command(self, descriptor, payload, output)
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
            runtime = create_runtime(backend, model, store, stops, execution_policy=execution_policy)
            allocate_requests(runtime, requests, execution_policy=execution_policy)
            event("resident_load_begin")
            begin = time.monotonic()
            store.load_resident()
            event("resident_load_complete", seconds=time.monotonic()-begin)
            checkpoint_generation = 0
            while any(not slot.finished for slot in runtime.slots):
                step_index = len(report['steps'])
                active_mask = sum(int(not slot.finished) << index for index, slot in enumerate(runtime.slots))
                positions_before = [slot.position for slot in runtime.slots]
                if hooks.before_step is not None:
                    hooks.before_step(runtime, step_index)
                receipt_start = len(backend.receipts)
                begin = time.monotonic()
                emitted = runtime.step()
                seconds = time.monotonic()-begin
                report["steps"].append(dict(index=step_index, seconds=seconds,
                                             active_mask=active_mask, positions_before=positions_before,
                                             emitted=emitted,
                                             fpga_cycles=sum(value['cycles'] for value in backend.receipts[receipt_start:]),
                                             phase='generation' if emitted else 'prefill',
                                             slots=[dataclasses.asdict(s) for s in runtime.slots]))
                report.update(slots=[dataclasses.asdict(slot) for slot in runtime.slots],
                              receipts=backend.receipts, asset_receipts=store.receipts)
                if hooks.after_step is not None:
                    hooks.after_step(runtime, step_index, emitted)
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
                    if args.wall_seconds is not None and estimate > args.wall_seconds:
                        raise TimeoutError("measured pilot exceeds stage budget; committed first round preserved")
            report.update(execution="COMPLETE", seconds=time.time() - report["started_unix"],
                          outputs={str(slot): state.generated for slot, state in enumerate(runtime.slots)
                                   if state.prompt})
            if execution_policy == BENCHMARK_KV128:
                report['benchmark_acceptance'] = validate_benchmark_report(report, stops)
            report["decoded"] = {str(slot): dict(stop_reason=("fixed_positions" if execution_policy == BENCHMARK_KV128
                                                            else "eos" if state.generated and state.generated[-1] in stops else "length_limit"),
                                                 prompt=tokenizer.decode(list(state.prompt), skip_special_tokens=False),
                                                 generated=tokenizer.decode(state.generated, skip_special_tokens=False),
                                                 eos=bool(state.generated and state.generated[-1] in stops))
                                 for slot, state in enumerate(runtime.slots) if state.prompt}
            backend.require_quiescent()
            report["final_quiescent"] = True
            report["final_status"] = {name: session.read32(CSR[name])
                                      for name in ("STATUS", "ADMISSION_ERROR", "DONE_ERROR")}
            if any(report['final_status'].values()):
                raise RuntimeError('Final board status/error registers must be idle and clear')
    except BaseException as error:
        report.update(execution="FAIL", error=repr(error),
                      slots=[] if runtime is None else [dataclasses.asdict(s) for s in runtime.slots],
                      pending_descriptor=None if runtime is None or runtime.backend.pending is None
                          else runtime.backend.pending.words())
        raise
    finally:
        report["handles_closed"] = (session is not None and not session.handles and not session.quarantine)
        closure_error = None
        if report['execution'] == 'COMPLETE' and not report['handles_closed']:
            closure_error = RuntimeError('Native device handles or quarantined I/O remain after session close')
            report.update(execution='FAIL', error=repr(closure_error))
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
        try:
            if report['execution'] == 'COMPLETE':
                if execution_policy == BENCHMARK_KV128:
                    (out / 'benchmark_summary.json').write_text(json.dumps(report['benchmark_acceptance'], indent=2) + '\n', encoding='utf-8')
                    (out / 'outputs.json').write_text(json.dumps(report['outputs'], indent=2) + '\n', encoding='utf-8')
                lines = ["slot %s (%s)\n%s" % (slot, value['stop_reason'], value['generated'])
                         for slot, value in report['decoded'].items()]
                (out / 'outputs.txt').write_text('\n\n'.join(lines) + '\n', encoding='utf-8')
            if hooks.finalize is not None:
                hooks.finalize(report)
            if closure_error is not None:
                raise closure_error
        except BaseException as error:
            report.update(execution='FAIL', error=repr(error), finalization_failed=True)
            raise
        finally:
            report['deployment_acceptance'] = ('PASS' if report['execution'] == 'COMPLETE'
                and report.get('handles_closed') and report.get('final_quiescent') and programming
                else 'FAIL' if report['execution'] != 'COMPLETE' else 'IMAGE_PROVENANCE_UNVERIFIED')
            save()
    print(json.dumps({"execution": report["execution"], "numerical_verification": report["numerical_verification"],
                      "result": str(out), "decoded": report["decoded"],
                      "image_provenance": report['image_provenance'],
                      "deployment_acceptance": report['deployment_acceptance']}, ensure_ascii=False))
    return report


if __name__ == "__main__": main()
