#!/usr/bin/env python3
"""Actual Tcl entries and real adapter imports, stopped at mocked design open."""
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'agent/A006/directed_candidate_cut_system_python'
OLD = ROOT / 'agent/A006/directed_candidate_cut_owner_fix'
E008_OLD = ROOT / 'agent/A006/directed_candidate_cut/E008_entry'
OUT = HERE / 'independent_runtime_entry_checks'
OUT.mkdir(exist_ok=False)


def identity(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


pollute = r'''
set vendor /home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/tps/lnx64/python-3.13.0
set ::env(PATH) "$vendor/bin:$::env(PATH)"
set ::env(PYTHONHOME) $vendor
set ::env(PYTHONPATH) "$vendor/lib/python3.13"
set ::env(PYTHONPLATLIBDIR) polluted_platform_dir
set ::env(PYTHONUSERBASE) /not/a/python/userbase
set ::env(LD_LIBRARY_PATH) /home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/lib/lnx64.o
set ::env(LD_PRELOAD) {}
set ::env(TCL_LIBRARY) /not/a/tcl/library
set ::env(TK_LIBRARY) /not/a/tk/library
set ::env(__PYVENV_LAUNCHER__) /not/a/python/launcher
'''
results = {}
for label, directory, entry in [('R005', SOURCE, 'attribution_directed.tcl'),
                                ('E008', SOURCE / 'E008_entry', 'implementation.tcl')]:
    report = OUT / label
    report.mkdir()
    env = os.environ.copy()
    env.update(SLR2_WORKSPACE_ROOT=str(ROOT), HAP_REPORT_DIR=str(report), HAP_PROJECT_DIR=str(report),
               HAP_STAGE='place', HAP_EXECUTION_MODE='checkpoint_restored_commands',
               SLR2_REUSED_SCRIPT_DIR=str(ROOT / 'project/hardware/vivado/scripts'),
               SLR2_HOOKS=str(directory / 'candidate_hooks.tcl'),
               SLR2_ADAPTER=str(directory / 'evidence_adapter.py'), SLR2_CANDIDATE_ID='C01',
               SLR2_CANDIDATE_ROOT='CPU_PREFLIGHT_FIXTURE_ONLY',
               E006_OUT=str(report), E006_DCP='NO_DCP_READ_ALLOWED',
               E006_TARGETS=str(directory / 'targets.tcl'),
               E006_CANDIDATE_ADAPTER=str(directory / 'directed_evidence.py'))
    code = pollute + r'''
proc version args {return 2025.2}
proc set_param args {}
proc open_checkpoint args {error "A007_EXPECTED_BEFORE_NATIVE_OPEN\nSECOND_LINE\tTAB"}
proc open_project args {error "A007_EXPECTED_BEFORE_NATIVE_OPEN\nSECOND_LINE\tTAB"}
source [lindex $argv 0]
'''
    proc = subprocess.run(['/usr/bin/tclsh', '/dev/stdin', str(directory / entry)],
                          input=code, text=True, capture_output=True, env=env)
    (OUT / (label + '.stdout')).write_text(proc.stdout)
    (OUT / (label + '.stderr')).write_text(proc.stderr)
    native_receipt = report / 'native_system_python_preflight.json'
    assert proc.returncode == 1 and native_receipt.is_file(), (label, proc.returncode, proc.stderr)
    value = json.loads(native_receipt.read_text())
    assert value['runtime_preflight'] is True and value['sanitized_python_library_environment'] is True
    assert value['native_design_qualification'] is False
    if label == 'R005':
        lines = (report / 'query_receipts.tsv').read_text().splitlines()
        assert len(lines) == 3 and all(len(line.split('\t')) == 5 for line in lines)
        assert lines[1].startswith('system_python_runtime_preflight\t0\t')
        assert lines[2].startswith('open_checkpoint\t1\t')
        assert r'\nSECOND_LINE\tTAB' in lines[2]
        assert 'SECOND_LINE\tTAB' in (report / 'error_open_checkpoint.txt').read_text()
    else:
        assert value['E008_full_adapter_imported'] is True
        assert 'A007_EXPECTED_BEFORE_NATIVE_OPEN' in proc.stderr
    results[label] = dict(entry=identity(directory / entry), source_wrapper=identity(directory / 'system_python.tcl'),
                          real_preflight_receipt=identity(native_receipt), receipt=value,
                          observed_returncode=proc.returncode, stopped_at_mock_design_open=True,
                          original_environment_polluted=True)

# Load actual original diagnostics and revised hooks with no native command
# implementations at all, then inspect their real composed procedure bodies.
t = tkinter.Tcl()
t.setvar('env(HAP_REPORT_DIR)', str(OUT / 'composition'))
t.setvar('env(SLR2_CANDIDATE_ROOT)', 'CPU_PREFLIGHT_FIXTURE_ONLY')
t.setvar('env(SLR2_CANDIDATE_ID)', 'C01')
t.call('source', str(ROOT / 'project/hardware/vivado/scripts/m002_diagnostic_common.tcl'))
t.call('source', str(SOURCE / 'E008_entry/candidate_hooks.tcl'))
procedure_calls = {}
for name in t.splitlist(t.call('info', 'procs')) + t.splitlist(t.call('info', 'procs', 'slr2::*')):
    body = t.call('info', 'body', name)
    assert 'exec python3' not in body, name
    if 'm002_system_python' in body:
        procedure_calls[name] = body.count('m002_system_python')
assert procedure_calls['m002_post'] == 2 and procedure_calls['m002_live_pre_place_restore'] == 1

def functions(path):
    return {x.name: ast.dump(x, include_attributes=False)
            for x in ast.parse(path.read_text()).body if isinstance(x, ast.FunctionDef)}

old_functions = functions(OLD / 'directed_evidence.py')
new_functions = functions(SOURCE / 'directed_evidence.py')
assert all(new_functions[name] == body for name, body in old_functions.items())
assert set(new_functions) - set(old_functions) == {'runtime_preflight'}
old_e008 = functions(E008_OLD / 'evidence_adapter.py')
new_e008 = functions(SOURCE / 'E008_entry/evidence_adapter.py')
assert all(new_e008[name] == body for name, body in old_e008.items() if name != 'main')
assert (SOURCE / 'directed_exporter.tcl').read_text().replace(
    'm002_system_python $adapter cut', 'exec python3 $adapter cut') == (OLD / 'directed_exporter.tcl').read_text()
result = dict(recorded_utc=dt.datetime.now(dt.timezone.utc).isoformat(), execution='CPU_Tcl_entries_actual_adapter_imports',
              cases=results, actual_E008_composed_wrapper_call_counts=procedure_calls,
              all_original_directed_validator_functions_AST_unchanged=True,
              Tcl_list_split_and_dictionary_semantics_unchanged=True,
              all_non_main_E008_adapter_functions_AST_unchanged=True,
              collector_only_callback_replacement=True,
              no_real_EDA_or_native_design_calls=True,
              source_identities=[identity(SOURCE / p) for p in ['system_python.tcl','attribution_directed.tcl','directed_evidence.py','directed_exporter.tcl']] +
                                [identity(SOURCE / 'E008_entry' / p) for p in ['system_python.tcl','candidate_hooks.tcl','runtime_hooks.tcl','implementation.tcl','evidence_adapter.py']],
              producer=identity(__file__),
              limits='Mocked version/thread parameter/design open only; actual entry, helper composition and adapter imports executed. No native graph/class/role/cut qualification, source mutation, lock or process control.')
(OUT / 'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(identity(OUT / 'results.json')))
