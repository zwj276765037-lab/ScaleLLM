"""Independent four-phase and evidence-continuity CPU checks for E008 view."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
SOURCE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(exist_ok=False)
os.environ['SLR2_WORKSPACE_ROOT'] = str(ROOT)
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location('reviewed_E008_adapter', SOURCE)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
fixtures = ROOT / 'agent/A007/directed_source_review_20261017/mock_round3'
internal = ROOT / 'agent/A007/E008_directed_review_20261017/mock_internal/internal'


def is_timing(name):
    return name.startswith(('candidate_timing_queries_', 'candidate_scoped_timing_', 'candidate_cut_timing_'))


def prepare(case, point, use_internal=False):
    target = OUT / case
    target.mkdir()
    src = internal if use_internal else fixtures / 'dsp_copy'
    deferred = []
    for p in src.iterdir():
        if not p.name.startswith('candidate_') or 'summary' in p.name or 'validation' in p.name:
            continue
        dest = target / p.name.replace('_test', '_' + point)
        if is_timing(p.name):
            deferred.append((p, dest))
        else:
            shutil.copy2(p, dest)
    if point != 'pre_place':
        actual = target / f'candidate_reconciled_P_{point}.tsv'
        actual.write_bytes((target / f'candidate_P_{point}.tsv').read_bytes())
        resolved = {r['NAME']: r['REF_NAME'] for r in a.rows(actual)}
        (target / f'candidate_reconciliation_{point}.json').write_text(json.dumps(dict(qualified=True, resolved=resolved)))
        (target / f'candidate_P_{point}.tsv').write_text('NAME\tREF_NAME\ncandidate\tFDRE\ndsp\tDSP48E2\n')
    return target, deferred


results = []
cases = [('pre_place_empty_boundary', 'pre_place', True, None),
         ('place_DSP_and_origin_copy', 'place', False, None),
         ('physopt_DSP_and_origin_copy', 'physopt', False, None),
         ('route_DSP_and_origin_copy', 'route', False, None),
         ('changed_literal_P_rejected', 'place', False, 'literal'),
         ('changed_actual_P_rejected', 'place', False, 'actual'),
         ('changed_projection_link_rejected', 'place', False, 'symlink')]
for case, point, empty, mutation in cases:
    report, deferred = prepare(case, point, empty)
    literal = report / f'candidate_P_{point}.tsv'
    before = a.directed.identity(literal)
    expected_accept = mutation is None
    accepted = False; error = None; cut_pass = False
    try:
        value = a.cut_summary(point, report)
        cut_pass = value['directed_boundary_complete']
        projection = report / f'candidate_directed_validation_{point}' / 'projection_identity.json'
        original_projection = json.loads(projection.read_text())
        assert f'candidate_timing_queries_{point}.tcllist' not in original_projection['inputs']
        if point != 'pre_place':
            assert value['actual_candidate_native_leaf_pins'] == 4
            assert value['artifacts']['P'] == a.directed.identity(report / f'candidate_reconciled_P_{point}.tsv')
        if mutation == 'literal':
            literal.write_text(literal.read_text().replace('candidate\tFDRE', 'candidate\tLUT1'))
        elif mutation == 'actual':
            p = report / f'candidate_reconciled_P_{point}.tsv'
            p.write_text(p.read_text().replace('origin_copy\tFDRE', 'origin_copy\tLUT1'))
        elif mutation == 'symlink':
            p = report / f'candidate_directed_validation_{point}' / f'candidate_endpoints_{point}.tsv'
            p.unlink()
            wrong = report / 'wrong_shadow.tsv'
            wrong.write_text('WRONG')
            p.symlink_to(wrong)
        for src, dest in deferred:
            shutil.copy2(src, dest)
        timing = a.directed_timing(point, report)
        assert timing['complete_directional_query_sets']
        if empty:
            assert timing['native_query_count'] == 0 and not timing['query_sets']
        if mutation is None:
            assert a.directed.identity(literal) == before
        revisions = sorted(projection.parent.glob('projection_identity_*.json'))
        assert revisions
        revision = json.loads(revisions[-1].read_text())
        assert f'candidate_timing_queries_{point}.tcllist' in revision['inputs']
        accepted = True
    except (ValueError, AssertionError, FileNotFoundError) as exc:
        error = str(exc)
    results.append(dict(case=case, phase=point, cut_pass=cut_pass, expected_accept=expected_accept, actual_accept=accepted, error=error))

output = dict(execution='independent_CPU_projection_checks_not_native', adapter=a.directed.identity(SOURCE), cases=results,
              all_expected=all(r['expected_accept'] == r['actual_accept'] for r in results))
(OUT / 'results.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps(output, indent=2))
