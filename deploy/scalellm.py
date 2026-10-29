#!/usr/bin/env python3
"""Portable entry point for final 80 MHz, 16-slot incremental Llama inference."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
from final.common import (BIT_SHA, bootstrap, check_bit, read_config,
                          read_requests, source_check)

# Kept as the exporter's source-identity API.
vendor_check = source_check
config = read_config


def main(argv=None):
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
    command = commands.add_parser('program', help='verify the released bitstream and program volatile FPGA SRAM')
    command.add_argument('--vivado', required=True)
    command.add_argument('--server', required=True)
    command.add_argument('--target', required=True)
    command.add_argument('--device', required=True)
    command.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    current = read_config(args.config)
    verified = source_check()
    if args.command == 'dry-run':
        requests = read_requests(current['requests'])
        print(json.dumps(dict(verdict='PLAN_VALID', core_hz=80000000, request_count=len(requests),
                              device_opened=False, source_files_verified=verified,
                              resolved_config=current,
                              missing_paths=[current[key] for key in ('artifacts', 'host_assets', 'bitstream')
                                             if not Path(current[key]).is_file()]), indent=2))
        return
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
        bit = check_bit(current['bitstream'])
        command = [args.vivado, '-mode', 'batch', '-source', str(HERE / 'final/program_sram.tcl'),
                   '-tclargs', args.server, args.target, args.device, str(bit)]
        if args.dry_run:
            print(json.dumps(dict(device_opened=False, command=command, bit_sha256=BIT_SHA), indent=2))
            return
        subprocess.run(command, check=True)
        return
    from final.preflight import preflight, driver_identity
    preflight(current, requests_path=args.requests)
    driver_identity(current.get('expected_driver_sha256'))
    check_bit(current['bitstream'])
    from final.run import main as run_main
    output = args.result or str(Path(current['output_dir']) /
                               ('AT_' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '_decode16'))
    command = ['--artifacts', current['artifacts'], '--assets', current['host_assets'],
               '--requests', str(Path(args.requests or current['requests']).resolve()),
               '--result', output, '--command-timeout-seconds', str(current['command_timeout_seconds']),
               '--wall-seconds', str(current['wall_seconds'])]
    for path in args.power_log:
        command.extend(['--power-log', str(Path(path).resolve())])
    run_main(command, config=current)


if __name__ == '__main__':
    main()
