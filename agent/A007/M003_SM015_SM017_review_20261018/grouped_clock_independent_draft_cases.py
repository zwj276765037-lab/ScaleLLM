"""Targeted independent grouped-evidence cases; no EDA or large raw tables."""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json

OWN = Path(__file__).resolve().parent
ROOT = OWN.parents[2]


def fixture():
    endpoints, aliases = [], []
    for s in range(2):
        for i in range(40):
            cell = f'inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice[{s}].meta_mem_reg_uram_{i}'
            net = f'native_alias_{s}_{i}'
            aliases.append(net)
            endpoints.append(dict(cell=cell, slice=s, ordinal=i, CLK_pin=cell+'/CLK', group='G000000', direct_nets=[net]))
    aliases.append('core_clk')
    groups = [dict(id='G000000', nets=aliases, canonical_top_net='core_clk', leaf_drivers=[], driver_cells=[], driver_refs=[], primary_ports=['core_clk'], primary_port_directions=['IN'])]
    return groups, endpoints


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--tag', required=True)
    args = p.parse_args()
    saved = OWN / f'grouped_clock_{args.tag}_reviewed.py'
    raw = args.candidate.read_bytes()
    with saved.open('xb') as f:
        f.write(raw)
    spec = importlib.util.spec_from_file_location('reviewed_grouped_validator', saved)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = []

    def run(name, mutate, wanted):
        groups, endpoints = fixture()
        mutate(groups, endpoints)
        try:
            result, expanded = mod.validate(groups, endpoints)
            actual, error = result['passed'], None
        except Exception as exc:
            result, actual, error = None, False, f'{type(exc).__name__}: {exc}'
        rows.append(dict(name=name, expected_accept=wanted, actual_accept=actual, expectation_met=actual == wanted, result=result, exception=error))

    def rename(endpoints, old, new):
        e = endpoints[0]
        e['cell'] = e['cell'].replace(old, new)
        e['CLK_pin'] = e['cell'] + '/CLK'

    run('valid80_one_group', lambda g,e: None, True)
    run('wrong_separator_in_exact_cell_identity', lambda g,e: rename(e, 'width_slices.g_slice', 'width_slicesXg_slice'), False)
    run('noncanonical_leading_zero_ordinal', lambda g,e: rename(e, 'uram_0', 'uram_00'), False)
    run('wrong_direct_group_member', lambda g,e: e[0].update(direct_nets=['unrelated_net']), False)
    run('dangling_group_reference', lambda g,e: e[0].update(group='G999999'), False)
    run('same_count_duplicate_endpoint', lambda g,e: e.__setitem__(1, copy.deepcopy(e[0])), False)
    run('mixed_primary_and_leaf_source', lambda g,e: g[0].update(leaf_drivers=['drv/O'], driver_cells=['drv'], driver_refs=['BUFG']), False)
    run('duplicate_alias_identity', lambda g,e: g[0]['nets'].append(g[0]['nets'][0]), False)
    run('wrong_primary_direction', lambda g,e: g[0].update(primary_port_directions=['OUT']), False)
    run('unresolved_clock_source', lambda g,e: g[0].update(primary_ports=[], primary_port_directions=[]), False)
    out = OWN / f'grouped_clock_{args.tag}_independent_cases.json'
    result = dict(schema='A007_grouped_clock_targeted_independent_cases_v1', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), reviewed_candidate=dict(original_path=str(args.candidate), preserved_path=str(saved.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), test_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), cases=rows, failures=[r['name'] for r in rows if not r['expectation_met']], unchanged_suites_rerun=False, native_used=False, scope='Targeted normalized-evidence identity/membership/source rejection only; not production integration, API count, source boundary or timing acceptance.')
    with out.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(cases=len(rows), failures=result['failures'], receipt=str(out.relative_to(ROOT)), reviewed_sha256=result['reviewed_candidate']['sha256'])))
    return 0 if not result['failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
