#!/usr/bin/env python3
"""Freeze same-scope system-Python/receipt repair without executing EDA."""
import ast
from datetime import datetime,timezone
import json
from pathlib import Path
from directed_evidence import identity,save
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=HERE.parent/'directed_candidate_cut_owner_fix'


def main():
    target=HERE/'prepared_source_manifest.json';assert not target.exists()
    base=json.loads((BASE/'prepared_source_manifest.json').read_text())
    for row in base['source_files']+base['CPU_checks']:assert identity(row['path'])==row
    for name in ['candidate_inspector.tcl','property_alignment.tcl','targets.tcl','reuse_manifest.json','run_directed_attribution.py','launch_detached.py','controlled_stop_R004.py']:
        assert (HERE/name).read_bytes()==(BASE/name).read_bytes(),'Unexpected functional source change: '+name
    def functions(path):return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef)}
    before=functions(BASE/'directed_evidence.py');after=functions(HERE/'directed_evidence.py');assert all(after[name]==value for name,value in before.items())
    assert (HERE/'directed_exporter.tcl').read_text()==(BASE/'directed_exporter.tcl').read_text().replace('    exec python3 $adapter cut $point $::m002_report_dir','    m002_system_python $adapter cut $point $::m002_report_dir')
    check=HERE/'CPU_checks/CT012_system_python_entry.json';runtime=json.loads(check.read_text());assert all(runtime['checks'].values())
    cpu=HERE/'CPU_checks/CT013_final_control_membership.json';value=json.loads(cpu.read_text());assert all(value['checks'].values())
    for row in value['source_files']:assert identity(row['path'])==row
    runtime_names=base['runtime_source_names']+['system_python.tcl']
    own=runtime_names+['README.md','check_preparation_CPU.py','check_system_python_CPU.py','freeze_prepared_manifest.py']
    old=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R005/attempts/AT002_owner_helper_repaired_directed_cut'
    external=dict(base['external_inputs']);external.update(original_a660_manifest=identity(BASE/'prepared_source_manifest.json'),
        failed_AT002_terminal_status=identity(old/'status.json'),failed_AT002_terminal_facts=identity(old/'terminal_facts.json'),
        system_python_binary=identity('/usr/bin/python3'),system_env_binary=identity('/usr/bin/env'))
    manifest=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CPU_PREPARED_NOT_EXECUTED',EDA_executed=False,
        exporter_protocol_complete=True,source_protocol_and_CPU_checks_complete=True,native_design_or_class_qualification=False,
        coverage_version='candidate_directed_cut_v1',runtime_source_names=runtime_names,source_files=[identity(HERE/name) for name in own],
        CPU_checks=[identity(check),identity(cpu)]+base['CPU_checks'],external_inputs=external,scope_revision=base['scope_revision'],
        repair=dict(kind='same_scope_explicit_CPU_interpreter_and_receipt_framing',prior_package=identity(BASE/'prepared_source_manifest.json'),
            prior_native_failure=identity(old/'terminal_facts.json'),
            root_cause='Vivado exec python3 resolves bundled Python3.13 lacking _tkinter; actual native member ledgers completed but CPU validation import failed',
            interpreter='/usr/bin/python3 via absolute /usr/bin/env with Python/Tcl/loader library environment removed only for child',
            preflight='Complete real evidence-adapter import before native checkpoint open; no native design/class/role proof is claimed by this preflight',
            receipt_repair='Escape newline/CR/TAB in bounded TSV result; full original error/options retained in per-query Tcl error artifact',
            graph_validation_functions_AST_unchanged=True,collector_only_callback_interpreter_changed=True,
            production_native_API_scope_algorithms_clocks_unchanged=True),
        native_member_evidence='AT002 actual member tables replayed separately under system Python and match R004, original failed query code preserved',
        source_guard_tail='Byte-identical resource/process/post-integrity tail to actual frozen R004',
        E008='Separate matching system-Python entry prepared, no selection or physical execution yet',
        launch_dependencies=['Actual new source-bound R005 execution binding and all prior ownership closures','Single nonblocking EDA lane, same144 production inputs and same DCP',
            'Actual native system-Python preflight before DCP; then fresh member/class/role/directed cut/bounded timing'],
        limitations=['CPU full Tcl entries stop at mocked native open boundaries; no new EDA qualification yet','No candidate supported, routed success, or timing signoff inferred'])
    save(target,manifest);print(json.dumps(identity(target)))

if __name__=='__main__':main()
