"""Integrate synchronized seven-rail samples; export data without host identities.

The model wall window is an energy time axis, not FPGA performance. Hardware
time comes only from the sum of DONE_CYCLES / 80 MHz. Long sample gaps are left
uncovered; this tool never fills them with defaults or extrapolates full duty.
"""
import argparse
import csv
import gzip
import hashlib
from datetime import datetime
import json
import math
from pathlib import Path
import statistics

RAILS = ('0x70', '0x11', '0x12', '0x15', '0x14', '0x72', '0x73')


def finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Nonfinite/non-numeric ' + label)
    return value


def validate_model(receipt, run):
    frequency = receipt['qpc_frequency']
    if type(frequency) is not int or frequency <= 0:
        raise ValueError('QPC frequency must be a positive integer')
    if run.get('abi', {}).get('core_hz') != 80000000:
        raise ValueError('Actual model ABI is not80MHz')
    native = [entry for entry in receipt['operations'] if entry['name'] == 'inference']
    if len(native) != 1 or native[0]['exit_code'] != 0:
        raise ValueError('Native model exit was not uniquely successful')
    names = ('idle_before_begin', 'idle_before_end', 'model_begin', 'model_end',
             'idle_after_begin', 'idle_after_end')
    phases = receipt['phases']
    if tuple(phase['name'] for phase in phases) != names:
        raise ValueError('Missing, duplicate, or unordered phase windows')
    ticks = [finite(phase['ticks'], 'phase ticks') for phase in phases]
    if any(b <= a for a, b in zip(ticks, ticks[1:])):
        raise ValueError('Phase tick boundaries must be strictly ordered')
    commands, steps = run['receipts'], run['steps']
    if len(commands) != 64*len(steps):
        raise ValueError('Every model round must contain64 commands')
    total = 0
    for index, command in enumerate(commands):
        cycles = command['cycles']
        if type(cycles) is not int or not 0 < cycles < 0xffffffff:
            raise ValueError('Invalid or saturated DONE_CYCLES; no wrap inference')
        if (command['command_id'] != index+1 or command['layer'] != (index % 64)//2
                or command['opcode'] != index % 2+1):
            raise ValueError('Command order/layer/opcode changed')
        total += cycles
    for index, step in enumerate(steps):
        group = commands[64*index:64*(index+1)]
        if (type(step['fpga_cycles']) is not int
                or sum(command['cycles'] for command in group) != step['fpga_cycles']
                or len({command['active_mask'] for command in group}) != 1):
            raise ValueError('Round cycle sum or command mask mismatch')
    return frequency, total


def validate_sample(sample, expected_index):
    if (sample['index'] != expected_index
            or tuple(rail['address'] for rail in sample['rails']) != RAILS
            or not all(rail['gate_pass'] for rail in sample['rails'])):
        raise ValueError('Missing index, changed rails, or invalid complete sweep')
    start = finite(sample['sweep_started_ticks'], 'sample start ticks')
    end = finite(sample['sweep_ended_ticks'], 'sample end ticks')
    if end <= start:
        raise ValueError('Nonpositive sweep duration')
    measured = finite(sample['monitored_power_w'], 'monitored power')
    powers = []
    for rail in sample['rails']:
        powers.append(finite(rail['power_w'], 'rail power'))
        finite(rail['current_a'], 'rail current')
        if rail['voltage_v'] is not None:
            finite(rail['voltage_v'], 'rail voltage')
        a = finite(rail['read_started_ticks'], 'rail start ticks')
        b = finite(rail['read_finished_ticks'], 'rail end ticks')
        if not start <= a < b <= end:
            raise ValueError('Rail read timestamps fall outside its complete sweep')
    if not math.isclose(sum(powers), measured, rel_tol=1e-12, abs_tol=1e-8):
        raise ValueError('Monitored power does not equal the seven rail sum')


def integrate(points, start, end, gap_limit, key='power_w'):
    """Piecewise-linear midpoint integration, clipped to the observed window."""
    if end <= start:
        raise ValueError('Nonpositive measurement window')
    energy = covered = 0.0
    for left, right in zip(points, points[1:]):
        duration = right['time_s'] - left['time_s']
        if duration <= 0:
            raise ValueError('Sample timestamps must be strictly increasing')
        if duration > gap_limit:
            continue
        a, b = max(start, left['time_s']), min(end, right['time_s'])
        if a >= b:
            continue
        slope = (right[key] - left[key]) / duration
        pa = left[key] + slope * (a - left['time_s'])
        pb = left[key] + slope * (b - left['time_s'])
        energy += (pa + pb) * (b - a) / 2
        covered += b - a
    return dict(window_seconds=end-start, covered_seconds=covered,
                missing_seconds=max(0.0, end-start-covered),
                coverage_fraction=covered/(end-start),
                integrated_joules=energy,
                time_weighted_mean_w=None if not covered else energy/covered)


def qualify_completion(receipt, run, allow_timeout=False):
    if (run['execution'] != 'COMPLETE' or not run['handles_closed']
            or any(run['final_status'].values()) or receipt['survivors']
            or not receipt['lease_released']):
        raise ValueError('Native model/cleanup did not complete')
    if receipt['state'] == 'COMPLETE' and receipt['sampler'].get('native_exit') == 0:
        return False
    if (allow_timeout and receipt['state'] == 'FAIL'
            and receipt.get('error') == 'Sampler stop timeout'
            and receipt['sampler'].get('native_exit') is None):
        # Native inference success is separately required by validate_model;
        # every sweep and100% coverage of all3 windows are checked below.
        return True
    raise ValueError('Native sampler/stage failed; explicit narrowly scoped timeout flag required')


def open_telemetry(base):
    """Read an uncompressed private recording or a deterministic public gzip."""
    plain = Path(base)/'telemetry.jsonl'
    compressed = Path(base)/'telemetry.jsonl.gz'
    if plain.is_file() == compressed.is_file():
        raise ValueError('Exactly one telemetry.jsonl or telemetry.jsonl.gz required')
    return (plain.open(encoding='utf-8-sig') if plain.is_file()
            else gzip.open(compressed, 'rt', encoding='utf-8-sig'))


def write_public_telemetry(directory, lines):
    data = ('\n'.join(lines)+'\n').encode('utf-8')
    destination = Path(directory)/'telemetry.jsonl.gz'
    with destination.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            compressed.write(data)
    return dict(uncompressed_bytes=len(data),
                uncompressed_sha256=hashlib.sha256(data).hexdigest(),
                gzip_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                compression='gzip; empty filename; mtime=0; complete sweeps retained')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measurement', required=True)
    parser.add_argument('--reference-run', required=True)
    parser.add_argument('--public-dir', required=True)
    parser.add_argument('--allow-sampler-finalization-timeout', action='store_true',
                        help='only accept exact post-window Sampler stop timeout with successful model, clean release and100%% valid window coverage; preserve original FAIL')
    args = parser.parse_args()
    base, public = Path(args.measurement), Path(args.public_dir)
    public.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((base/'receipt.json').read_text(encoding='utf-8-sig'))
    run = json.loads((base/'device/run.json').read_text())
    reference = json.loads(Path(args.reference_run).read_text())
    timeout_qualified = qualify_completion(receipt, run, args.allow_sampler_finalization_timeout)
    frequency, cycles = validate_model(receipt, run)
    requested_interval = finite(receipt.get('requested_interval_ms', 1000), 'requested interval')
    if not 100 <= requested_interval <= 60000:
        raise ValueError('Requested sampler interval outside documented bounds')
    phases = {phase['name']: phase for phase in receipt['phases']}
    origin = phases['model_begin']['ticks']
    points, samples = [], []
    with open_telemetry(base) as stream:
        for line in stream:
            sample = json.loads(line)
            validate_sample(sample, len(samples))
            midpoint = (sample['sweep_started_ticks']+sample['sweep_ended_ticks'])/2
            point = dict(time_s=(midpoint-origin)/frequency,
                         power_w=sample['monitored_power_w'])
            for rail in sample['rails']:
                point[rail['address']] = rail['power_w']
            points.append(point)
            samples.append(sample)
    if len(points) < 2:
        raise ValueError('Insufficient real power samples')
    intervals = [b['time_s']-a['time_s'] for a, b in zip(points, points[1:])]
    if any(not math.isfinite(value) or value <= 0 for value in intervals):
        raise ValueError('Nonpositive/nonfinite sample midpoint interval')
    median_interval = statistics.median(intervals)
    gap_limit = max(3.0, 3*median_interval)
    windows = {}
    for name in ('idle_before', 'model', 'idle_after'):
        a = (phases[name+'_begin']['ticks']-origin)/frequency
        b = (phases[name+'_end']['ticks']-origin)/frequency
        windows[name] = integrate(points, a, b, gap_limit)
        windows[name]['coarse_read_pout_quantization_contribution_bound_j'] = 3*windows[name]['covered_seconds']
        windows[name]['per_rail'] = {
            rail: integrate(points, a, b, gap_limit, rail) for rail in RAILS}
    if timeout_qualified and any(window['coverage_fraction'] < 1-1e-12 for window in windows.values()):
        raise ValueError('Post-window timeout exception requires100% coverage of all3 windows')
    same_ids = run['outputs'] == reference['outputs']
    idle = (windows['idle_before']['time_weighted_mean_w']
            + windows['idle_after']['time_weighted_mean_w'])/2
    rail_sources = [{key: rail[key] for key in
                    ('address', 'name', 'regulator', 'power_source', 'voltage_source', 'quantization')}
                   for rail in samples[0]['rails']]
    summary = dict(schema='scalellm_full_model_seven_rail_power_v1',
                   state=('OBSERVATION_WINDOWS_VALID_SAMPLER_FINALIZATION_FAILED'
                          if timeout_qualified else 'COMPLETE'),
                   original_stage_state=receipt['state'],
                   original_stage_error=receipt.get('error'),
                   sampler_native_exit=receipt['sampler'].get('native_exit'),
                   model_native_exit=0,
                   observation_windows_valid=True,
                   bit_sha256=receipt['bit_sha256'],
                   checkpoint_sha256=run['checkpoint_sha256'],
                   measurement_scope='seven selected FPGA regulator output rails; not whole-board12V input or isolated chip total',
                   windows=windows, sample_count=len(samples), qpc_frequency_hz=frequency,
                   phase_boundaries=receipt['phases'],
                   time_origin_model_begin_ticks=origin,
                   requested_interval_ms=requested_interval,
                   requested_interval_source=('receipt' if 'requested_interval_ms' in receipt
                       else 'legacy frozen sample_power_full.ps1 configuration; IntervalMs1000'),
                   median_midpoint_interval_seconds=median_interval,
                   maximum_midpoint_interval_seconds=max(intervals),
                   gap_exclusion_threshold_seconds=gap_limit,
                   gaps_excluded=sum(value > gap_limit for value in intervals),
                   rail_sources=rail_sources, idle_baseline_mean_w=idle,
                   model_minus_idle_w=windows['model']['time_weighted_mean_w']-idle,
                   coarse_read_pout_sum_contribution_bound_w=3, coarse_read_pout_difference_contribution_bound_w=6,
                   model_rounds=len(run['steps']), commands=len(run['receipts']),
                   generated_tokens=sum(len(slot['generated']) for slot in run['slots']),
                   requested_50_round_512_token_coverage_met=(len(run['steps']) == 50
                       and len(run['receipts']) == 3200
                       and all(len(slot['generated']) == 32 for slot in run['slots'])),
                   repeated_generated_ids_match_previous_actual=same_ids,
                   fpga_cycles_python_integer=cycles, core_hz=80000000,
                   fpga_counter_seconds=cycles/80000000,
                   counter_duty_over_model_energy_window=(cycles/80000000)/windows['model']['window_seconds'],
                   numerical_verification='NOT_RUN; previous actual IDs comparison is repeatability only',
                   limitations=[
                       'Model wall timestamps are used only for energy integration, not FPGA speed.',
                       'Midpoint trapezoids interpolate adjacent sampled values; gaps above the stated threshold are excluded, never filled.',
                       'Sequential rail reads and roughly1s cadence do not resolve millisecond kernels or instantaneous peaks.',
                       'FPGA counter duty includes boardDDR/drain waits and is not DSP switching activity.',
                       'Three coarse READ_POUT rails contribute+/-3W sum and+/-6W difference quantization; these are not complete seven-rail uncertainty bounds.',
                       'Four rails use measured VOUT times IOUT; their quantization and sensor errors are not fully evaluated, and V/I reads are not simultaneous.',
                       'MAX20751 READ_VOUT is feedback-node voltage; direct rail voltage remains unavailable.',
                       'No conversion losses, other board loads, Host power or full-duty extrapolation are included.'])
    # Sweep objects contain rail measurements and clocks only. Reject accidental
    # host identity fields instead of silently deleting unexpected evidence.
    public_lines = []
    forbidden = ('adapter_serial', 'executable', 'C:\\Users\\', 'D:/', '/home/')
    for sample in samples:
        line = json.dumps(sample, ensure_ascii=False, separators=(',', ':'))
        if any(value in line for value in forbidden):
            raise ValueError('Private host identity unexpectedly present in sweep')
        public_lines.append(line)
    summary['public_telemetry'] = write_public_telemetry(public, public_lines)
    with (public/'power_sweeps.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(points[0]))
        writer.writeheader()
        writer.writerows(points)
    commits = []
    with (base/'device/progress.jsonl').open() as stream:
        for line in stream:
            event = json.loads(line)
            if event['event'] == 'position_committed':
                commits.append(event)
    if len(commits) != len(run['steps']):
        raise ValueError('Actual round-commit timestamps are incomplete')
    origin_utc = datetime.fromisoformat(phases['model_begin']['utc'].replace('Z', '+00:00')).timestamp()
    with (public/'rounds.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=('round', 'committed_utc_unix',
            'commit_seconds_since_model_begin_utc', 'fpga_cycles', 'fpga_seconds',
            'active_mask', 'wall_seconds_energy_axis'))
        writer.writeheader()
        for index, step in enumerate(run['steps']):
            writer.writerow(dict(round=index+1, fpga_cycles=step['fpga_cycles'],
                                 committed_utc_unix=commits[index]['utc'],
                                 commit_seconds_since_model_begin_utc=commits[index]['utc']-origin_utc,
                                 fpga_seconds=step['fpga_cycles']/80000000,
                                 active_mask=hex(run['receipts'][64*index]['active_mask']),
                                 wall_seconds_energy_axis=step['seconds']))
    (public/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    # Preserve all numbers needed to reproduce this analysis, omitting private
    # process identities, adapter serial, executable paths and unrelated fields.
    public_receipt = {key: receipt[key] for key in
                      ('state', 'bit_sha256', 'qpc_frequency', 'phases', 'survivors', 'lease_released')}
    if 'requested_interval_ms' in receipt:
        public_receipt['requested_interval_ms'] = receipt['requested_interval_ms']
    public_receipt['error'] = receipt.get('error')
    public_receipt['sampler'] = {'native_exit': receipt['sampler'].get('native_exit')}
    public_receipt['operations'] = [
        {key: entry[key] for key in ('name', 'exit_code')}
        for entry in receipt['operations'] if entry['name'] == 'inference']
    (public/'receipt.json').write_text(json.dumps(public_receipt, indent=2)+'\n')
    public_run = {key: run[key] for key in
                  ('execution', 'handles_closed', 'final_status', 'checkpoint_sha256', 'receipts', 'outputs', 'abi')}
    public_run['steps'] = [{key: step[key] for key in ('fpga_cycles', 'seconds')}
                           for step in run['steps']]
    public_run['slots'] = [{'generated': slot['generated']} for slot in run['slots']]
    (public/'device').mkdir()
    (public/'device/run.json').write_text(json.dumps(public_run, indent=2)+'\n')
    (public/'device/progress.jsonl').write_text(''.join(
        json.dumps({'event': 'position_committed', 'utc': event['utc']})+'\n'
        for event in commits))
    (public/'reference_run.json').write_text(json.dumps({'outputs': reference['outputs']}, indent=2)+'\n')
    (public/'README.md').write_text(
        '# Synchronized seven-rail model power data\n\n'
        'The measured quantities are selected FPGA regulator outputs, not whole-board input or isolated chip power. '
        'Model wall timestamps are an energy integration axis; only DONE_CYCLES/80MHz describes FPGA command time.\n\n'
        'telemetry.jsonl.gz preserves every complete sweep, raw words, conversion sources, per-rail timings and validity, with deterministic gzip mtime=0. '
        'receipt.json and device/ contain only the actual fields required by the analysis; private process/device identities '
        'and machine paths were omitted. reference_run.json contains prior actual generated IDs for repeatability, not gold. '
        'No vendor executable/driver is included.\n\n'
        + ('The inference completed successfully, but the original overall stage is FAIL: the sampler exceeded its finalization timeout after all observed windows. Its native exit is unknown (null), never replaced with0. The explicit exception below accepts only this exact failure with a clean model/release, valid complete sweeps and100% coverage of all three windows.\n\n' if timeout_qualified else '')
        +
        'Recompute using a new output directory:\n\n'
        '```text\npython tools/power/analyze_model_power.py --measurement <dataset-dir> '
        '--reference-run <dataset-dir>/reference_run.json --public-dir <new-output-dir>'
        + (' --allow-sampler-finalization-timeout' if timeout_qualified else '')
        + '\n```\n\n'
        +
        'Adjacent sample midpoints are integrated with clipped linear trapezoids. Gaps above the reported threshold '
        'and unobserved boundary time are excluded and reported; no defaults fill missing measurements. '
        'The +/-3W sum and +/-6W difference numbers cover only the three coarse READ_POUT channels. The other four rails and additional sensor errors are not fully evaluated. '
        'Roughly1s sampling cannot resolve millisecond kernel peaks or justify full-duty extrapolation.\n')
    print(json.dumps({key: summary[key] for key in
                     ('sample_count', 'fpga_counter_seconds', 'repeated_generated_ids_match_previous_actual')}))


if __name__ == '__main__':
    main()
