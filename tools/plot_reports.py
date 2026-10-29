#!/usr/bin/env python3
"""Render standalone figures from the published measurement tables."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def save(fig, path):
    fig.savefig(path.with_suffix('.svg'), bbox_inches='tight', metadata={'Date': None})
    fig.savefig(path.with_suffix('.png'), dpi=180, bbox_inches='tight')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inference', type=Path)
    parser.add_argument('--power', type=Path)
    args = parser.parse_args()
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'svg.hashsalt': 'scalellm-final'})
    if args.inference:
        with (args.inference / 'fpga_rounds.csv').open() as f:
            rows = list(csv.DictReader(f))
        fig, ax = plt.subplots(figsize=(9, 4.3))
        x = [int(r['round']) for r in rows]
        for key, label, color in [('fpga_seconds', 'Total FPGA command time', '#164c7e'),
                                  ('attention_seconds', 'Attention', '#008b88'),
                                  ('mlp_seconds', 'MLP H32/A8 + Gate/Up + SiLU x Up', '#c26b23')]:
            ax.plot(x, [float(r[key]) for r in rows], label=label, color=color, linewidth=2)
        ax.axvspan(47.5, 50.5, color='#eeeeee', label='14 / 7 / 3 active requests')
        ax.set(xlabel='Round (KV length increases by one for active requests)',
               ylabel='FPGA command time, seconds', xlim=(1, 50), ylim=(0, 1.55),
               title='80 MHz VCU118 — all 32 layers per round')
        ax.grid(axis='y', alpha=.2)
        ax.legend(loc='upper left', fontsize=8)
        fig.text(.12, -.02, 'Counters include onboard memory/control; CPU Down and host gaps are excluded.', fontsize=9)
        save(fig, args.inference / 'fpga_round_time')
    if args.power:
        with (args.power / 'power_sweeps.csv').open() as f:
            rows = list(csv.DictReader(f))
        summary = json.loads((args.power / 'summary.json').read_text())
        x = [float(r['time_s']) / 60 for r in rows]
        y = [float(r['power_w']) for r in rows]
        duration = summary['windows']['model']['window_seconds'] / 60
        mean = summary['windows']['model']['time_weighted_mean_w']
        fig, ax = plt.subplots(figsize=(10, 4.6))
        ax.plot(x, y, linewidth=.65, color='#164c7e', label='Seven-rail sequential sweep sum')
        ax.axhline(mean, color='#c26b23', linewidth=1.4, label=f'Model-window mean: {mean:.3f} W')
        ax.axvline(0, color='#888888', linestyle='--', linewidth=1)
        ax.axvline(duration, color='#888888', linestyle='--', linewidth=1)
        ax.set(xlabel='Minutes since model launch (energy integration axis)',
               ylabel='Selected regulator output power, W',
               title='Continuous 16-request x 32-token inference power')
        ax.grid(axis='y', alpha=.2)
        ax.legend(loc='best', fontsize=8)
        fig.subplots_adjust(bottom=.28)
        fig.text(.125, .02, 'Seven measured rails; excludes board input and host power.\n'
                             'Three coarse READ_POUT channels contribute +/-3 W quantization uncertainty; other errors are not fully characterized.\n'
                             'Approximately one-second sweeps cannot resolve individual kernel peaks.', fontsize=8.5)
        save(fig, args.power / 'full_inference_power')


if __name__ == '__main__':
    main()
