#!/usr/bin/env python3
"""Portable entry point for final 80 MHz, 16-slot incremental Llama inference."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
from final.common import (ROOT, bootstrap, check_bit, profile_identity, read_config,
                          current_host_identity, read_program_receipt, read_requests, sha, source_check)
from final.execution import BENCHMARK_KV128, DECODE, benchmark_requests, policy_description

# Kept as the exporter's source-identity API.
vendor_check = source_check
config = read_config


def main(argv=None, *, hooks=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(HERE / 'config.example.json'),
                        help='paths are relative to this configuration file')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('dry-run', help='validate sources/config/requests without dependencies or a device')
    command = commands.add_parser('prepare', help='encode text conversations with the model chat template')
    command.add_argument('--messages')
    command.add_argument('--result', required=True)
    command = commands.add_parser('preflight', help='read-only source/dependency checks')
    command.add_argument('--models', action='store_true', help='hash every exported hardware and CPU asset')
    command.add_argument('--device', action='store_true', help='read installed driver and final board ABI; no CSR writes')
    command.add_argument('--requests')
    command = commands.add_parser('run', help='run 1..16 requests, each with up to 32 new tokens')
    command.add_argument('--requests')
    command.add_argument('--result', help='new output directory; default is a unique directory under output_dir')
    command.add_argument('--power-log', action='append', default=[],
                         help='external sampler log to reference in run.json; repeat for multiple instruments')
    command.add_argument('--program-receipt', help='prior successful SRAM programming receipt')
    command = commands.add_parser('benchmark-kv128', help='run the published 16 prompts for exactly 128 positions')
    command.add_argument('--result', help='new output directory; default is a unique directory under output_dir')
    command.add_argument('--program-receipt', help='prior successful all-DSP SRAM programming receipt')
    command.add_argument('--power-log', action='append', default=[])
    command.add_argument('--dry-run', action='store_true', help='inspect fixed-position policy without dependencies or a device')
    command = commands.add_parser('program', help='verify the released bitstream and program volatile FPGA SRAM')
    command.add_argument('--vivado', required=True)
    command.add_argument('--server', required=True)
    command.add_argument('--target', required=True)
    command.add_argument('--device', required=True)
    command.add_argument('--dry-run', action='store_true')
    command.add_argument('--receipt', help='write a new JSON programming receipt, including native tool exit and output')
    args = parser.parse_args(argv)
    current = read_config(args.config)
    verified = source_check()
    profile = profile_identity(current['deployment_profile'])
    benchmark = args.command == 'benchmark-kv128'
    if benchmark and profile['name'] != 'all-dsp':
        raise ValueError('The public KV128 benchmark requires the all-dsp deployment profile')
    if args.command == 'dry-run' or (benchmark and args.dry_run):
        requests = benchmark_requests() if benchmark else read_requests(current['requests'])
        if benchmark and args.program_receipt is not None:
            read_program_receipt(args.program_receipt, profile['name'])
        bit_check = 'MISSING'
        if Path(current['bitstream']).is_file():
            check_bit(current['bitstream'], profile['name'])
            bit_check = 'SIZE_SHA256_PASS'
        print(json.dumps(dict(verdict='PLAN_VALID', core_hz=80000000, request_count=len(requests),
                              deployment_profile=profile, bitstream_file=bit_check,
                              execution_policy=policy_description(BENCHMARK_KV128 if benchmark else DECODE),
                              requests=requests if benchmark else None,
                              missing_prerequisites=(['successful all-dsp --program-receipt for live benchmark']
                                                     if benchmark and args.program_receipt is None else []),
                              device_opened=False, source_files_verified=verified,
                              resolved_config=current,
                              missing_paths=[current[key] for key in ('artifacts', 'host_assets', 'bitstream')
                                             if not Path(current[key]).is_file()]), indent=2))
        return
    if benchmark and args.program_receipt is None:
        raise ValueError('Live KV128 requires a successful all-dsp --program-receipt')
    bootstrap()
    if args.command == 'prepare':
        from final.prepare_chat_requests import prepare
        print(json.dumps(prepare(current['host_assets'], args.messages or current['messages'], args.result), indent=2))
        return
    if args.command == 'preflight':
        from final.preflight import preflight
        print(json.dumps(preflight(current, models=args.models, device=args.device,
                                   requests_path=args.requests), indent=2))
        return
    if args.command == 'program':
        bit = check_bit(current['bitstream'], profile['name'])
        command = [args.vivado, '-mode', 'batch', '-source', str(HERE / 'final/program_sram.tcl'),
                   '-tclargs', args.server, args.target, args.device, str(bit), profile['name']]
        if args.dry_run:
            print(json.dumps(dict(device_opened=False, command=command, deployment_profile=profile,
                                  bit_sha256=profile['bit_sha256']), indent=2))
            return
        receipt_path = None if args.receipt is None else Path(args.receipt).resolve()
        if receipt_path is not None:
            if receipt_path.exists():
                raise FileExistsError('Use a new programming receipt path: ' + str(receipt_path))
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
        tool_path = Path(shutil.which(args.vivado) or args.vivado)
        receipt = dict(schema='scalellm_sram_program_receipt_v1', execution='RUNNING',
                       deployment_profile=profile, bitstream=str(bit), volatile_sram=True,
                       host_identity=current_host_identity(),
                       server=args.server, target=args.target, device=args.device, command=command,
                       source_manifest_sha256=sha(HERE / 'vendor_manifest.json'),
                       tool=dict(requested=args.vivado,
                                 path=str(tool_path.resolve()) if tool_path.is_file() else args.vivado,
                                 sha256=sha(tool_path) if tool_path.is_file() else None),
                       started_unix=time.time(), returncode=None)
        if receipt_path is not None:
            with receipt_path.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(receipt, indent=2) + '\n')
        begin = time.monotonic()
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            receipt.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                           execution='COMPLETE' if result.returncode == 0 else 'FAIL')
            receipt['tool']['version_output'] = [line for line in (result.stdout + result.stderr).splitlines()
                                                   if 'Vivado v' in line]
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)
        except BaseException as error:
            receipt.update(execution='FAIL', error=repr(error))
            raise
        finally:
            receipt.update(finished_unix=time.time(), elapsed_seconds=time.monotonic() - begin)
            if receipt_path is not None:
                temporary = receipt_path.with_name(receipt_path.name + '.tmp')
                with temporary.open('x', encoding='utf-8') as stream:
                    stream.write(json.dumps(receipt, indent=2) + '\n')
                temporary.replace(receipt_path)
            print(json.dumps(receipt, indent=2))
        return
    from final.preflight import preflight, driver_identity
    requests_path = str(ROOT / 'examples/requests16.json') if benchmark else args.requests or current['requests']
    preflight(current, requests_path=requests_path)
    driver_identity(current.get('expected_driver_sha256'))
    check_bit(current['bitstream'], profile['name'])
    if args.program_receipt is not None:
        read_program_receipt(args.program_receipt, profile['name'])
    from final.run import main as run_main
    suffix = '_kv128' if benchmark else '_decode16'
    output = args.result or str(Path(current['output_dir']) /
                               ('AT_' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + suffix))
    output = str(Path(output).resolve())
    command = ['--artifacts', current['artifacts'], '--assets', current['host_assets'],
               '--requests', str(Path(requests_path).resolve()),
               '--result', output, '--command-timeout-seconds', str(current['command_timeout_seconds'])]
    if current['wall_seconds'] is not None:
        command.extend(['--wall-seconds', str(current['wall_seconds'])])
    if args.program_receipt is not None:
        command.extend(['--program-receipt', str(Path(args.program_receipt).resolve())])
    for path in args.power_log:
        command.extend(['--power-log', str(Path(path).resolve())])
    if benchmark and hooks is None:
        from resource_optimization.deployment.benchmark_capture import create_hooks
        hooks = create_hooks(output)
    return run_main(command, config=current,
                    execution_policy=BENCHMARK_KV128 if benchmark else DECODE, hooks=hooks)


if __name__ == '__main__':
    main()
