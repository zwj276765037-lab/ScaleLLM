"""Plot measured document-level relative errors, preserving trajectory and scope."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from run_numerical_fidelity import identity, write_json


def plot_rows(summary, series, trajectory, evidence_role, domain=None):
    rows = [row for row in summary['document_metrics'] if row['series'] == series
            and row['trajectory'] == trajectory and row['evidence_role'] == evidence_role
            and (domain is None or row['domain'] == domain)]
    if not rows:
        raise ValueError('no measured document metrics for requested scope')
    if len({row['split'] for row in rows}) > 1:
        raise ValueError('plot must not merge train/dev/eval roles')
    return rows


def render(summary_path, output_dir, series, trajectory, evidence_role, domain=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    summary = json.loads(Path(summary_path).read_text())
    rows = plot_rows(summary, series, trajectory, evidence_role, domain)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sites = sorted({str(row.get('op') or row['node']) for row in rows})
    fig, axes = plt.subplots(1, 2, figsize=(max(12., len(sites)*1.1), 5.2), constrained_layout=True)
    for i, site in enumerate(sites):
        subset = [row for row in rows if str(row.get('op') or row['node']) == site]
        # Each plotted value is a document x layer x node/site tensor metric.
        values = [row['relative_l2_percent'] for row in subset if row['relative_l2_percent'] is not None]
        if values:
            x = np.full(len(values), i, dtype=float)
            # Deterministic spread conveys measured values without random sampling.
            x += np.linspace(-.13, .13, len(values)) if len(values)>1 else 0
            axes[0].scatter(x, values, s=14, alpha=.65, color=plt.get_cmap('tab10')(i%10),rasterized=True)
        max_docs=max(len({row['doc_id'] for row in subset if row['layer']==layer}) for layer in {row['layer'] for row in subset})
        for quantile, style in ([(.5, '-'), (.95, '--')] if max_docs>1 else [(.5,'-')]):
            layers = sorted({row['layer'] for row in subset})
            ys = []
            for layer in layers:
                cell = [row['relative_l2_percent'] for row in subset if row['layer']==layer and row['relative_l2_percent'] is not None]
                ys.append(float(np.quantile(cell, quantile)) if cell else np.nan)
            axes[1].plot([layer+1 for layer in layers], ys, style, marker='o', markersize=3,
                         color=plt.get_cmap('tab10')(i%10),
                         label=site + ((' P50' if quantile==.5 else ' P95') if max_docs>1 else ' observed'))
    axes[0].set_xticks(range(len(sites)), sites, rotation=45, ha='right')
    axes[0].set_title('Measured document/layer/site tensors')
    continuous = all('continuous' in row['trajectory'] for row in rows)
    axes[1].set_title('32-layer propagation' if continuous else 'Local comparison at measured layers')
    axes[1].set_xlabel('Layer (1-based)')
    measured_layers=sorted({row['layer']+1 for row in rows})
    ticks=measured_layers if len(measured_layers)<=10 else [measured_layers[round(i*(len(measured_layers)-1)/8)] for i in range(9)]
    axes[1].set_xticks(ticks)
    axes[1].legend(fontsize=7, ncol=2)
    for axis in axes:
        axis.set_ylabel('Relative L2 error (%)')
        axis.grid(alpha=.2)
        axis.set_ylim(bottom=0)
    docs = len({row['doc_id'] for row in rows})
    zeros = sum(row.get('zero_signal',False) for row in rows)
    series_label={'current_vs_reference':'Current implementation vs output-only rounding',
                  'current_vs_exact':'Current implementation vs exact node value'}[series]
    final_report=Path(summary_path).parent/'final_norm_comparison.json'
    final_norm=None
    if continuous and final_report.exists():
        final_norm=json.loads(final_report.read_text())['metrics']['current_vs_reference']['relative_l2_percent']
    extra=f'; final host RMSNorm relative L2={final_norm:.4f}%' if final_norm is not None else ''
    fig.suptitle(f'{evidence_role} | {trajectory} | {series_label} | {docs} document(s)\n'
                 f'Zero-signal tensors excluded: {zeros}; descriptive observations{extra}',fontsize=10)
    targets=[]
    for suffix in ('png','pdf'):
        target = output_dir / f'numerical_fidelity_{series}.{suffix}'
        if target.exists():
            raise FileExistsError(target)
        fig.savefig(target,dpi=180)
        targets.append(identity(target))
    plt.close(fig)
    write_json(output_dir/f'plot_{series}_manifest.json',{'source':identity(summary_path),'code':identity(__file__),
               'series':series,'trajectory':trajectory,'evidence_role':evidence_role,'domain':domain,
               'measured_documents':docs,'measured_tensors':len(rows),'outputs':targets,
               'final_norm_report':identity(final_report) if final_norm is not None else None,
               'scope':'propagation' if continuous else 'local; not a measured propagation result'})
    return targets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--series',choices=['current_vs_reference','current_vs_exact'],required=True)
    parser.add_argument('--trajectory',required=True)
    parser.add_argument('--evidence-role',required=True)
    parser.add_argument('--domain')
    args=parser.parse_args()
    render(args.summary,args.output_dir,args.series,args.trajectory,args.evidence_role,args.domain)


if __name__=='__main__':
    main()
