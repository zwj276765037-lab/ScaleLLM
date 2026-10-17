"""Independent CPU acceptance/mutation checks against a snapshotted adapter."""
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import sys
import tkinter

HERE = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1]).resolve()
FIXTURES = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3]).resolve()
OUT.mkdir(exist_ok=False)
T = tkinter.Tcl()
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('reviewed_adapter', SOURCE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def tl(values):
    return T.call('format', '%s', T.call('list', *values))


def td(mapping):
    return tl([item for pair in mapping.items() for item in pair])


def rewrite_tsv(path, change):
    lines = path.read_text().splitlines()
    header = lines[0].split('\t')
    rows = [dict(zip(header, line.split('\t'))) for line in lines[1:]]
    rows = change(rows)
    path.write_text('\t'.join(header) + '\n' + ''.join('\t'.join(row[key] for key in header) + '\n' for row in rows))


def mutate_query(report, kind, change):
    p = report / 'candidate_native_role_queries_test.tcllist'
    rows = adapter.ledger(p)
    for row in rows:
        if row['query_kind'] == kind:
            change(row)
    p.write_text(''.join(td(row) + '\n' for row in rows))


def single_alias(report):
    def change(row):
        command = adapter.split(row['command'])
        command[3] = 'n0'
        row['command'] = tl(command)
    mutate_query(report, 'NONLOAD_LEAF', change)


def single_top_alias(report):
    def change(row):
        command = adapter.split(row['command'])
        command[2] = 'n0'
        row['command'] = tl(command)
    mutate_query(report, 'ALL_TOP_PORTS', change)


def counter(report):
    def change(rows):
        rows[0]['exported_endpoint_rows'] = str(int(rows[0]['exported_endpoint_rows']) + 1)
        return rows
    rewrite_tsv(report / 'candidate_nets_test.tsv', change)


def missing_candidate(report):
    rewrite_tsv(report / 'candidate_endpoints_test.tsv', lambda rows: [r for r in rows if r['NAME'] != 'candidate/D'])


def full_flag(report):
    def change(rows):
        rows[0]['full_net_endpoint_coverage'] = 'true'
        return rows
    rewrite_tsv(report / 'candidate_nets_test.tsv', change)


def timing_omission(report):
    rewrite_tsv(report / 'candidate_boundary_timing_scope_test.tsv', lambda rows: [])


def local_ref_disagrees(report):
    def change(rows):
        for row in rows:
            if row['NAME'] == 'candidate/D':
                row['REF_NAME'] = 'GND'
        return rows
    rewrite_tsv(report / 'candidate_pins_test.tsv', change)


def endpoint_ref_disagrees(report):
    def change(rows):
        for row in rows:
            if row['NAME'] == 'candidate/D':
                row['REF_NAME'] = 'GND'
                row['pin_class'] = 'CONSTANT'
        return rows
    rewrite_tsv(report / 'candidate_endpoints_test.tsv', change)
    def change_counts(rows):
        counts = adapter.tdict(rows[0]['retained_classes'])
        del counts['DATA_REGISTER']
        counts['CONSTANT'] = '1'
        rows[0]['retained_classes'] = td(counts)
        return rows
    rewrite_tsv(report / 'candidate_nets_test.tsv', change_counts)
    def change_timing(rows):
        rows[0]['pin_class'] = 'CONSTANT'
        return rows
    rewrite_tsv(report / 'candidate_boundary_timing_scope_test.tsv', change_timing)


def forbidden_full_receipt(report):
    p = report / 'candidate_native_role_queries_test.tcllist'
    rows = adapter.ledger(p)
    rows.append(dict(canonical_net='n0', query_kind='FULL_LEAF', command=tl(['get_pins', '-leaf', '-of_objects', tl(['n0', 'n1'])]),
                     actual_segment_NAMES=tl(['n0', 'n1']), native_tcl_code='0', raw_objects='3', unique_objects='3', actual_NAMES=tl(['external/O', 'candidate/D', 'peer/D'])))
    p.write_text(''.join(td(row) + '\n' for row in rows))


results = []
for name, mutate in [('control', lambda _: None), ('single_alias_role_command', single_alias), ('single_alias_top_command', single_top_alias),
                     ('wrong_counter', counter), ('missing_candidate', missing_candidate), ('false_full_flag', full_flag),
                     ('timing_omission', timing_omission), ('local_REF_mismatch', local_ref_disagrees),
                     ('endpoint_REF_mismatch', endpoint_ref_disagrees), ('forbidden_ingress_full_query', forbidden_full_receipt)]:
    report = OUT / name
    shutil.copytree(FIXTURES / 'ingress', report, ignore=shutil.ignore_patterns('candidate_cut_summary_test.json', 'adapter_stdout.txt', 'adapter_stderr.txt'))
    mutate(report)
    run = subprocess.run([sys.executable, str(SOURCE), 'cut', 'test', str(report)], capture_output=True, text=True)
    (report / 'adapter_stdout.txt').write_text(run.stdout)
    (report / 'adapter_stderr.txt').write_text(run.stderr)
    results.append(dict(case=name, expected_accept=(name == 'control'), actual_accept=(run.returncode == 0), returncode=run.returncode,
                        last_error=run.stderr.strip().splitlines()[-1] if run.stderr.strip() else None))

sample = OUT / 'parser_columns.tsv'
sample.write_text('NAME\tempty_middle\tmultiword\tempty_last\ncell[7]/D\t\tword one word two\t\n')
parsed = list(adapter.rows(sample))
assert parsed == [{'NAME': 'cell[7]/D', 'empty_middle': '', 'multiword': 'word one word two', 'empty_last': ''}]
nested = {'values': tl(['cell[7]/D', '', 'word one word two']), 'other': ''}
assert adapter.tdict(td(nested)) == nested
assert adapter.split(adapter.tdict(td(nested))['values']) == ['cell[7]/D', '', 'word one word two']
(OUT / 'results.json').write_text(json.dumps(dict(parser_brackets_multiword_empty_pass=True, cases=results), indent=2) + '\n')
print(json.dumps(results, indent=2))
