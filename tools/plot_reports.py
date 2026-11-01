#!/usr/bin/env python3
"""Render standalone figures from the published measurement tables."""
import argparse
import csv
import json
import math
from pathlib import Path
import textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def save(fig, path):
    fig.savefig(path.with_suffix('.svg'), bbox_inches='tight', metadata={'Date': None})
    fig.savefig(path.with_suffix('.png'), dpi=180, bbox_inches='tight')
    plt.close(fig)


def power_figure(directory):
    summary = json.loads((directory / 'summary.json').read_text())
    window = summary['windows']['model']
    mean = window['time_weighted_mean_w']
    duration = window['window_seconds']
    with (directory / 'power_sweeps.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    times = [float(row['time_s']) for row in rows]
    watts = [float(row['power_w']) for row in rows]

    # Integrate every observation, including spikes, using the report's linear
    # interpolation. Clip the final bin to the actual end of inference.
    centers, averages, total_energy = [], [], 0.0
    for start in range(0, math.ceil(duration), 60):
        end = min(start + 60, duration)
        energy, covered = 0.0, 0.0
        for t0, t1, p0, p1 in zip(times, times[1:], watts, watts[1:]):
            if t1 - t0 > summary['gap_exclusion_threshold_seconds']:
                continue
            a, b = max(start, t0), min(end, t1)
            if b <= a:
                continue
            slope = (p1 - p0) / (t1 - t0)
            pa, pb = p0 + slope * (a - t0), p0 + slope * (b - t0)
            energy += (pa + pb) * (b - a) / 2
            covered += b - a
        if not math.isclose(covered, end - start, rel_tol=1e-10):
            raise ValueError('A plotted minute lacks complete power coverage')
        centers.append((start + end) / 120)
        averages.append(energy / covered)
        total_energy += energy
    if not math.isclose(total_energy, window['integrated_joules'], rel_tol=1e-10):
        raise ValueError('Minute averages differ from the published energy integral')

    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor='white')
    fig.subplots_adjust(left=.10, right=.97, top=.80, bottom=.24)
    ax.plot(centers, averages, color='#2161a6', linewidth=2,
            marker='o', markersize=2.5, label='1-minute average')
    ax.axhline(mean, color='#c26b23', linewidth=1.5, linestyle='--',
               label=f'Full-run mean: {mean:.2f} W')
    ax.set(xlabel='Time since inference start (minutes)',
           ylabel='Average measured power (W)', xlim=(0, duration / 60),
           ylim=(math.floor(min(averages)), math.ceil(max(averages))))
    ax.tick_params(labelsize=10)
    ax.grid(axis='y', alpha=.18)
    ax.legend(loc='upper right', frameon=False, fontsize=10)
    ax.set_axisbelow(True)
    fig.suptitle('Average Power During Inference', fontsize=19,
                 fontweight='bold', y=.97)
    fig.text(.535, .89, 'VCU118 | 80 MHz | 16 requests x 32 generated tokens',
             ha='center', fontsize=11, color='#475569')
    fig.text(.10, .075,
             'Time-weighted means in 60-second bins; the final bin covers the remaining time.\n'
             'Seven FPGA-related regulator outputs, including host/transfer gaps; not whole-board input power.',
             fontsize=8.5, linespacing=1.5, color='#475569')
    fig.text(.10, .025,
             'Coarse READ_POUT quantization contribution: +/-3 W; other errors are not fully characterized.',
             fontsize=8, color='#64748b')
    save(fig, directory / 'full_inference_power')


def wrap_recorded_text(value, width):
    return '\n'.join(textwrap.fill(line, width=width, break_long_words=False,
                                  break_on_hyphens=False) if line else ''
                     for line in value.split('\n'))


def output_figures(directory):
    records = json.loads((directory / 'outputs.json').read_text())
    if [record['slot'] for record in records] != list(range(16)):
        raise ValueError('Expected all 16 recorded request slots in order')
    for offset in range(0, 16, 4):
        fig, axes = plt.subplots(2, 2, figsize=(14, 9.2), facecolor='white')
        fig.subplots_adjust(left=.035, right=.965, top=.87, bottom=.07,
                            hspace=.09, wspace=.04)
        for ax, record in zip(axes.flat, records[offset:offset + 4]):
            ax.set_facecolor('#f3f6fa')
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_color('#dce4ee')
            ax.set(xticks=[], yticks=[], xlim=(0, 1), ylim=(0, 1))
            ax.text(.045, .93, f'Request slot {record["slot"]:02d}', va='top',
                    fontsize=13, fontweight='bold', color='#164c7e')
            ax.text(.955, .93, f'{record["new_tokens"]} new tokens', ha='right', va='top',
                    fontsize=10, color='#008b88')
            ax.text(.045, .82, 'PROMPT', fontsize=9, fontweight='bold', color='#64748b')
            ax.text(.045, .77, wrap_recorded_text(record['prompt'], 66),
                    va='top', fontsize=11.5, linespacing=1.3)
            ax.text(.045, .60, 'RECORDED OUTPUT', fontsize=9, fontweight='bold', color='#64748b')
            ax.text(.045, .55, wrap_recorded_text(record['generated_text'], 66),
                    va='top', fontsize=11.5, linespacing=1.25, parse_math=False)
            ax.text(.045, .035, f'Stop: {record["stop_reason"]}', fontsize=8.5, color='#64748b')
        fig.suptitle(f'ScaleLLM | Actual inference outputs — slots {offset:02d}–{offset + 3:02d}',
                     fontsize=19, fontweight='bold', y=.965)
        fig.text(.5, .915, 'Llama-3.1-8B-Instruct  |  16 independent incremental-KV requests  |  FPGA + CPU',
                 ha='center', fontsize=11, color='#475569')
        fig.text(.035, .025, 'Exact recorded text, wrapped for display. Each request was capped at 32 new tokens; incomplete endings are preserved.',
                 fontsize=10, color='#475569')
        save(fig, directory / f'generated_outputs_{offset:02d}_{offset + 3:02d}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inference', type=Path)
    parser.add_argument('--power', type=Path)
    parser.add_argument('--outputs', type=Path, help='Directory containing the 16 recorded outputs.json entries')
    args = parser.parse_args()
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'svg.hashsalt': 'scalellm-final'})
    if args.inference:
        with (args.inference / 'fpga_rounds.csv').open() as f:
            rows = list(csv.DictReader(f))
        x = [int(r['round']) for r in rows]
        active = [int(r['active_slots']) for r in rows]
        retired = [i for i, count in enumerate(active) if count < 16]
        fig, (ax, counts) = plt.subplots(
            2, 1, figsize=(10.8, 6.8), sharex=True,
            gridspec_kw={'height_ratios': [3.5, 1], 'hspace': .13})
        fig.subplots_adjust(left=.09, right=.97, top=.81, bottom=.20)
        fig.suptitle('Earlier 32-token run: requests finish at different rounds',
                     x=.09, ha='left', y=.97, fontsize=17, fontweight='bold')
        fig.text(.09, .895,
                 'VCU118 / 80 MHz / all 32 layers per round / includes prompt processing',
                 fontsize=10, color='#475569')
        for key, label, color in [('fpga_seconds', 'Total FPGA command time', '#164c7e'),
                                  ('attention_seconds', 'Attention', '#008b88'),
                                  ('mlp_seconds', 'MLP: H32/A8 + Gate/Up + SiLU x Up', '#c26b23')]:
            values = [float(r[key]) for r in rows]
            # Dashed segments retain every original point while exposing the
            # changed active-count condition; no interpolation replaces data.
            full = [v if n == 16 else math.nan for v, n in zip(values, active)]
            ax.plot(x, full, label=label, color=color, linewidth=2.2)
            if retired:
                start = max(0, retired[0] - 1)
                ax.plot(x[start:], values[start:], color=color, linewidth=2,
                        linestyle='--', marker='o', markersize=4)
        if retired:
            boundary = x[retired[0]] - .5
            for panel in (ax, counts):
                panel.axvspan(boundary, x[-1] + .5, color='#fff0db', zorder=0)
                panel.axvline(boundary, color='#c69045', linestyle=':', linewidth=1)
            tail = ' / '.join(str(active[i]) for i in retired)
            ax.text(.98, .96, f'Requests finishing: {tail} active\n'
                    'Dashed tail has less work per round', transform=ax.transAxes,
                    ha='right', va='top', fontsize=9, color='#8a581d')
        ax.set(ylabel='FPGA command time (s)', xlim=(x[0], x[-1] + .6),
               ylim=(0, max(float(r['fpga_seconds']) for r in rows) * 1.18))
        ax.grid(axis='y', alpha=.18)
        ax.legend(loc='upper left', frameon=False, fontsize=9)
        counts.step(x, active, where='mid', color='#475569', linewidth=1.8)
        changes = [i for i in range(len(rows)) if i == 0 or active[i] != active[i - 1]]
        counts.scatter([x[i] for i in changes], [active[i] for i in changes],
                       color='#475569', s=23, zorder=3)
        for i in changes:
            counts.annotate(str(active[i]), (x[i], active[i]), xytext=(0, 5),
                            textcoords='offset points', ha='center', fontsize=9)
        counts.set(xlabel='Execution round (KV length grows for each remaining request)',
                   ylabel='Active\nrequests', yticks=[0, 8, 16], ylim=(0, 20))
        counts.grid(axis='y', alpha=.15)
        fig.text(.09, .075,
                 'The tail falls because requests reach their 32-token limit; it is not a fixed-16-request KV sweep.\n'
                 'Time = sum(DONE_CYCLES) / 80 MHz. CPU Down and command-external host/transfer gaps are excluded.',
                 fontsize=9, linespacing=1.6, color='#475569')
        save(fig, args.inference / 'fpga_round_time')
    if args.power:
        power_figure(args.power)
    if args.outputs:
        output_figures(args.outputs)


if __name__ == '__main__':
    main()
