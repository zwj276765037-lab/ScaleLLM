import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--raw', type=Path, required=True)
parser.add_argument('--analysis', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
raw = args.raw
analysis = json.loads(args.analysis.read_text())
launcher = json.loads((raw / 'main_001/receipt.json').read_text(encoding='utf-8-sig'))
workload = json.loads((raw / 'main_001/workload/workload.json').read_text())
metadata = json.loads((raw / 'main_001/telemetry.json').read_text(encoding='utf-8-sig'))
process = json.loads((raw / 'environment/main_process_receipt.json').read_text(encoding='utf-8-sig'))
freeze = json.loads((raw / 'pilot_frozen.json').read_text())
if launcher['state'] != 'CAPTURE_COMPLETE_WITH_LIMITS' or launcher['workload_exit_code'] != 0 or launcher['sampler_exit_code'] != 0 or process['exitcode'] != 0:
    raise RuntimeError('Native acquisition completion failed')
if workload['status'] != 'COMPLETE_WITH_LIMITS' or workload['completed_windows'] != 12 or not workload['handles_closed']:
    raise RuntimeError('Workload command/output/handle closure failed')
if analysis['raw_record_validation_status'] != 'PASS' or len(analysis['windows']) != 12:
    raise RuntimeError('Offline validation incomplete')
commands = []
with (raw / 'main_001/commands.jsonl').open() as stream:
    for line in stream:
        record = json.loads(line)
        if record['record'] == 'command':
            commands.append(record)
windows = []
trace_windows = analysis['command_trace']['windows']
for window, trace in zip(analysis['windows'], trace_windows):
    selected = [command for command in commands if window['start_ticks'] <= command['start_write']['before_ticks'] < window['end_ticks']]
    windows.append(dict(kind=window['kind'], repeat_id=window['repeat_id'],
                        window_start_qpc=window['start_ticks'], window_end_qpc=window['end_ticks'],
                        qpc_frequency=metadata['qpc_frequency'], window_seconds=window['window_seconds'],
                        command_count=trace['command_count'], common_coverage_fraction=window['common_coverage_fraction'],
                        common_coverage_seconds=window['common_coverage_seconds'],
                        common_missing_seconds=window['window_seconds'] - window['common_coverage_seconds'],
                        seven_rail_covered_mean_w=window['total_covered_mean_w'],
                        seven_rail_full_window_mean_w=window['total_full_window_mean_w'],
                        rail_covered_mean_w=window['rail_covered_mean_w'],
                        fpga_done_cycles=sum(command['done_cycles_read']['value'] for command in selected),
                        fpga_done_cycle_seconds=trace['fpga_cycle_seconds_80mhz'],
                        observed_busy_inner_seconds=trace['busy_inner_seconds'],
                        busy_inner_unavailable_commands=len(trace['busy_inner_unavailable_command_ids']),
                        outside_start_to_ack_seconds=window['window_seconds'] - sum(command['wall_ms'] for command in trace['commands']) / 1000,
                        busy_common_coverage_seconds=trace['busy_inner_common_telemetry_coverage_seconds'],
                        strict_physical_active_mean_w=None))
started = datetime.fromisoformat(process['started_utc'].replace('Z', '+00:00'))
finished = datetime.fromisoformat(process['finished_utc'].replace('Z', '+00:00'))
summary = dict(schema='scalellm_kv128_sevenrail_report_v1', status=analysis['status'],
               measurement_scope='Seven selected regulator output VOUT-times-IOUT telemetry',
               bitstream_sha256=launcher['bit_sha256'], active_requests=16, kv_length=128, position=127, core_hz=80000000,
               planned_window_collection='COMPLETE_12_OF_12', workload_protocol='PASS_WITH_LIMITS',
               full_window_means_established={kind: sum(row['kind'] == kind and row['seven_rail_full_window_mean_w'] is not None for row in windows)
                                               for kind in analysis['window_counts']},
               raw_launcher_state=launcher['state'], raw_launcher_reason=launcher.get('error'),
               workload_exit_code=launcher['workload_exit_code'], sampler_native_exit_code=launcher['sampler_exit_code'],
               phase_launcher_native_exit_code=process['exitcode'], native_collection_wall_seconds=(finished - started).total_seconds(),
               sampler_metadata_status=metadata['status'], sweeps=metadata['complete_sweeps'], rail_points=metadata['complete_rail_points'],
               read_transactions=7 + sum(len(rail.get('calibration', [])) for rail in metadata['configuration']) + 17 * metadata['complete_sweeps'],
               read_errors=metadata['read_errors'], commands_completed_and_acknowledged=len(commands),
               commands_no_busy_observation=[row['descriptor']['command_id'] for row in commands if row['busy_reads'] == 0],
               commands_without_two_busy_observations=[row['descriptor']['command_id'] for row in commands if row['busy_reads'] < 2],
               target_sweep_period_ms=freeze['target_period_ms'], maximum_interpolated_gap_ms=freeze['gap_threshold_ms'],
               pilot_actual_sweep_start_period_p95_ms=freeze['p95_sweep_period_ms'],
               actual_sweep_period_ms=analysis['actual_sweep_period_ms'],
               sensor_aperture_and_lag=None, strict_physical_active_mean_w=None, whole_board_input_mean_w=None,
               independent_full_model_oracle='NOT_ESTABLISHED',
               historical_kv_scope='Five captured layers byte-exact;27 layers without independent old per-layer KV hash',
               qualification=workload['qualification'], repeat_statistics=analysis['repeat_differences'], windows=windows,
               analysis_sha256=hashlib.sha256(args.analysis.read_bytes()).hexdigest())
args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print(json.dumps({key: summary[key] for key in ('status', 'full_window_means_established', 'sweeps', 'rail_points', 'commands_completed_and_acknowledged', 'sampler_native_exit_code', 'workload_exit_code')}))
for kind, record in summary['repeat_statistics'].items():
    selected = [row for row in windows if row['kind'] == kind]
    print(json.dumps(dict(kind=kind, mean_w=record['equal_repeat_covered_mean_w'], sample_sd_w=record['sample_sd_w'],
                          coverage_fractions=[row['common_coverage_fraction'] for row in selected])))
