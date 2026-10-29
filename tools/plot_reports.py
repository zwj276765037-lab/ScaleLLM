#!/usr/bin/env python3
"""Render standalone figures from the published measurement tables."""
import argparse
import csv
import json
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
    mean = summary['windows']['model']['time_weighted_mean_w']
    fig, ax = plt.subplots(figsize=(8, 6.2), facecolor='white')
    fig.subplots_adjust(left=.14, right=.96, top=.79, bottom=.27)
    ax.bar([0], [mean], width=.52, color='#2161a6')
    ax.text(0, mean + .35, f'{mean:.2f} W', ha='center', va='bottom',
            fontsize=22, fontweight='bold', color='#164c7e')
    ax.set(xticks=[0], xticklabels=['Full inference run'],
           ylabel='Average measured power (W)', xlim=(-.85, .85),
           ylim=(0, max(15, mean * 1.3)))
    ax.tick_params(labelsize=12)
    ax.grid(axis='y', alpha=.18)
    ax.set_axisbelow(True)
    fig.suptitle('Average FPGA-Related Rail Power', fontsize=20,
                 fontweight='bold', y=.96)
    fig.text(.55, .87, 'VCU118 | 80 MHz | 16 requests x 32 generated tokens',
             ha='center', fontsize=11, color='#475569')
    fig.text(.14, .125,
             'Time-weighted mean over the complete inference window.\n'
             'Sum of seven FPGA-related regulator outputs; includes host/transfer gaps.',
             fontsize=9.5, linespacing=1.5, color='#475569')
    fig.text(.14, .045,
             'Not continuous full-load or whole-board input power.\n'
             'Coarse READ_POUT quantization contribution: +/-3 W; other errors are not fully characterized.',
             fontsize=8, linespacing=1.5, color='#64748b')
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
        power_figure(args.power)
    if args.outputs:
        output_figures(args.outputs)


if __name__ == '__main__':
    main()
