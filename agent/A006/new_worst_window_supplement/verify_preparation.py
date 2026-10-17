#!/usr/bin/env python3
"""CPU-only evidence for the bounded target guard and Tcl structure."""
import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
wrapper = HERE / 'run_closed_comparison.py'
spec = importlib.util.spec_from_file_location('new_peak_guard', wrapper)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
base = json.loads((HERE / 'new_worst_targets_manifest.json').read_text())
cases = []


def check(name, mutate=None, reject=False):
    value = copy.deepcopy(base)
    if mutate:
        mutate(value)
    with tempfile.TemporaryDirectory(prefix='E005_peak_guard_') as temporary:
        folder = Path(temporary)
        (folder / 'new_worst_targets_manifest.json').write_text(json.dumps(value))
        try:
            module.new_peak_target_check(folder)
            rejected = False
        except (ValueError, KeyError, FileNotFoundError):
            rejected = True
        assert rejected == reject, (name, rejected, reject)
    cases.append(dict(case=name, expected_rejection=reject, PASS=True))
    print('PASS', name)


check('actual source and48/12/10 associations')
check('missing phase rejected', lambda x: x['phases'].pop('physopt'), True)
check('missing report row rejected', lambda x: x['phases']['place']['source_rows'].pop(), True)
check('duplicate unique region rejected', lambda x: x['phases']['place']['unique_regions'].__setitem__(1, copy.deepcopy(x['phases']['place']['unique_regions'][0])), True)
check('foreign source path rejected', lambda x: x['phases']['place']['source_report'].__setitem__('path', '/tmp/foreign.rpt'), True)
check('changed targets hash rejected', lambda x: x['targets_tcl'].__setitem__('sha256', '0' * 64), True)
check('peak maximum changed rejected', lambda x: next(r for r in x['phases']['place']['source_rows'] if r['selected_peak']).__setitem__('level', 5), True)
check('peak wrong region rejected', lambda x: next(r for r in x['phases']['place']['source_rows'] if r['selected_peak']).__setitem__('region_id', 'wrong'), True)
check('direction coverage missing rejected', lambda x: next(r for r in x['phases']['place']['source_rows'] if r['selected_peak']).__setitem__('direction', 'BAD'), True)
old = ast.parse((HERE.parent / 'physical_supplement/run_closed_comparison.py').read_text())
new = ast.parse(wrapper.read_text())
functions = ['prior_terminal_kind', 'prior_registered_identities', 'require_registered_closed', 'prior_attempts_closed', 'closed_status', 'still_live', 'freeze_check']
same = {name: ast.dump(next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == name)) == ast.dump(next(node for node in new.body if isinstance(node, ast.FunctionDef) and node.name == name)) for name in functions}
assert all(same.values())
program = '''
foreach path {readonly_physical_supplement.tcl readonly_two_phase_driver.tcl targets.tcl} {
 set h [open $path r];set text [read $h];close $h
 if {![info complete $text]} {error "Incomplete Tcl: $path"}
 puts "STRUCTURE_COMPLETE $path"
}
source targets.tcl
foreach phase {place physopt} {
 if {[llength $source_rows($phase)] != 48 || [llength $new_worst_windows($phase)] != 10} {error "Wrong bounded targets"}
 puts "BOUNDED_TARGETS $phase rows=48 regions=10"
}
'''
native = subprocess.run(['tclsh'], input=program, text=True, cwd=HERE, capture_output=True)
assert native.returncode == 0 and not native.stderr, (native.returncode, native.stderr)
print(native.stdout, end='')
facts = dict(CPU_only_no_EDA=True, cases=cases, guard_functions_AST_identical_to_reviewed_4cfa=same,
    Tcl_structure_and_bounds_stdout=native.stdout, Tcl_structure_stderr=native.stderr, Tcl_exit=native.returncode,
    new_wrapper_sha256=hashlib.sha256(wrapper.read_bytes()).hexdigest(),
    producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(HERE / 'cpu_guard_facts.json').write_text(json.dumps(facts, indent=2) + '\n')
print('CPU_PREPARATION_VERIFICATION_PASS', len(cases))
