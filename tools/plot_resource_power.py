#!/usr/bin/env python3
"""Plot all recorded seven-rail VxI points inside the twelve retest windows.

This is an offline presentation tool. It does not access hardware, smooth or
resample observations, or estimate whole-board/strict-active power.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

KINDS = ('idle', 'attention_repeat', 'mlp_repeat', 'full_kv128_step')
STYLES = {
    'idle': ('Idle', '#89949d', 'o'),
    'attention_repeat': ('Attention replay', '#0072b2', 'o'),
    'mlp_repeat': ('MLP frontend replay', '#d55e00', '^'),
    'full_kv128_step': ('Full KV128 decode step', '#009e73', 's'),
}
RAILS = (
    ('0x70', 'VCCINT'), ('0x11', 'VCC1V8'), ('0x14', 'VCC1V2'),
    ('0x15', 'VCCINTIO / BRAM'), ('0x12', 'VADJ 1V8'),
    ('0x72', 'MGTAVCC'), ('0x73', 'MGTAVTT'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--telemetry', type=Path, required=True)
    parser.add_argument('--windows', type=Path, required=True)
    parser.add_argument('--output-prefix', type=Path, required=True)
    args = parser.parse_args()
    outputs = [Path(str(args.output_prefix) + suffix) for suffix in ('.png', '.svg', '.json')]
    require(all(not p.exists() for p in outputs), 'Use new output paths to preserve prior figures')
    metadata = read_json(args.metadata)
    windows = [json.loads(line) for line in args.windows.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    require(len(windows) == 12 and Counter(w['kind'] for w in windows) == dict.fromkeys(KINDS, 3),
            'Expected the complete twelve-window retest')
    frequency = metadata['qpc_frequency']
    require(frequency > 0, 'Invalid QPC frequency')
    require(all(w['status'] == 'COMPLETE' and w['qpc_frequency'] == frequency
                and w['run_id'] == metadata['run_id'] for w in windows),
            'Window identity/clock/completion mismatch')
    require(all(a['end_ticks'] < b['start_ticks'] for a, b in zip(windows, windows[1:])),
            'Windows must be ordered and disjoint')
    origin = windows[0]['start_ticks']
    groups = {(rail, kind): ([], []) for rail, _ in RAILS for kind in KINDS}
    with args.telemetry.open(encoding='utf-8-sig') as stream:
        for line in stream:
            point = json.loads(line)
            if point.get('record') != 'rail_point':
                continue
            require(point['run_id'] == metadata['run_id'], 'Telemetry run identity differs')
            a, b = point['vi_before_ticks'], point['vi_after_ticks']
            require(a < b, 'Invalid V/I read envelope')
            for window in windows:
                if window['start_ticks'] <= a and b <= window['end_ticks']:
                    x, y = groups[(point['address'], window['kind'])]
                    x.append(((a + b) / 2 - origin) / frequency / 60)
                    y.append(point['vi_w'])
                    break
    require(all(values[0] for values in groups.values()), 'A rail/workload has no complete V/I observations')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#687787', 'xtick.color': '#4c5b6b',
                         'ytick.color': '#4c5b6b', 'svg.fonttype': 'none'})
    figure = plt.figure(figsize=(13.2, 11.8), facecolor='white')
    grid = figure.add_gridspec(4, 2, height_ratios=[1.3, 1, 1, 1], hspace=.52, wspace=.24)
    axes = [figure.add_subplot(grid[0, :])]
    axes.extend(figure.add_subplot(grid[row, col], sharex=axes[0])
                for row in range(1, 4) for col in range(2))
    end_minutes = (windows[-1]['end_ticks'] - origin) / frequency / 60
    repeat_starts = [w['start_ticks'] for w in windows if w['kind'] == 'idle']
    for index, ((rail, name), axis) in enumerate(zip(RAILS, axes)):
        for window in windows:
            _, color, _ = STYLES[window['kind']]
            axis.axvspan((window['start_ticks'] - origin) / frequency / 60,
                         (window['end_ticks'] - origin) / frequency / 60,
                         color=color, alpha=.045, linewidth=0)
        for kind in KINDS:
            _, color, marker = STYLES[kind]
            x, y = groups[(rail, kind)]
            axis.scatter(x, y, s=4 if marker == 'o' else 5, c=color,
                         marker=marker, alpha=.65, edgecolors='none')
        for tick in repeat_starts[1:]:
            axis.axvline((tick - origin) / frequency / 60, color='#687787',
                         linewidth=.7, linestyle=(0, (3, 4)))
        axis.set_title(f'({chr(97 + index)}) {name}', loc='left', fontsize=12, pad=8)
        axis.set_xlim(0, end_minutes)
        axis.grid(axis='y', color='#dce2e7', alpha=.8)
        axis.set_axisbelow(True)
        all_values = [value for kind in KINDS for value in groups[(rail, kind)][1]]
        if rail in {'0x70', '0x11', '0x14', '0x15'}:
            axis.set_ylim(0, max(all_values) * 1.10)
        if max(all_values) - min(all_values) < 1e-10:
            value = all_values[0]
            margin = max(abs(value) * .12, .08)
            axis.set_ylim(value - margin, value + margin)
            axis.text(.99, .88, f'Constant code: {value:.3g} W; variation unresolved',
                      transform=axis.transAxes, ha='right', va='top', fontsize=8, color='#4c5b6b')
    for index, tick in enumerate(repeat_starts, 1):
        block_end = repeat_starts[index] if index < len(repeat_starts) else windows[-1]['end_ticks']
        midpoint_minutes = ((tick + block_end) / 2 - origin) / frequency / 60
        axes[0].text(midpoint_minutes, 1.025, f'Repeat {index}', ha='center',
                     transform=axes[0].get_xaxis_transform(), fontsize=10, color='#536575')
    legend = [Line2D([], [], linestyle='none', marker=marker, color=color, markersize=6, label=label)
              for label, color, marker in STYLES.values()]
    figure.legend(handles=legend, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(.53, .94))
    figure.suptitle('ScaleLLM | All-DSP ScaleCode recovery: seven-rail power retest',
                   fontsize=17, fontweight='bold', x=.53, y=.992)
    figure.text(.53, .96, 'VCU118 · 80 MHz · KV128 · 16 requests · three repeats',
                ha='center', fontsize=11, color='#536575')
    figure.supylabel('PMBus telemetry: measured V × I (W)', x=.012, fontsize=12)
    figure.supxlabel('Elapsed time from first measured window (min)', y=.055, fontsize=12)
    figure.text(.53, .019,
                'Raw observations with complete V/I read envelopes inside each measured window; no smoothing.\n'
                'Seven regulator outputs; whole-board input power and strict hardware-active power are not established.',
                ha='center', fontsize=9, color='#536575')
    figure.subplots_adjust(left=.075, right=.985, bottom=.105, top=.865)
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(outputs[0], dpi=180, bbox_inches='tight')
    figure.savefig(outputs[1], bbox_inches='tight')
    plt.close(figure)
    provenance = {'schema': 'scalellm_resource_power_figure_v1', 'run_id': metadata['run_id'],
                  'window_count': len(windows), 'qpc_frequency': frequency,
                  'target_period_ms': metadata['target_period_ms'],
                  'selection': 'complete V/I read envelope contained in one of the twelve measured windows',
                  'sampling_or_smoothing': 'NONE',
                  'points': {rail: {kind: len(groups[(rail, kind)][0]) for kind in KINDS} for rail, _ in RAILS},
                  'input_sha256': {str(p): digest(p) for p in [args.metadata, args.telemetry, args.windows]},
                  'figure_sha256': {p.name: digest(p) for p in outputs[:2]}}
    outputs[2].write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'status': 'COMPLETE', 'outputs': [str(p) for p in outputs]}, indent=2))


if __name__ == '__main__':
    main()
