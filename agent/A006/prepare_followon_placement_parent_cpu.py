#!/usr/bin/env python3
"""Bind existing E005 OPT/pre-place parents for a future placement contract.

CPU/filesystem reads only: no Vivado, checkpoint copies, RTL/XDC writes or launch.
"""
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).with_name('E006_slr1_attribution')))
from capture_stage import identity


def package(path):
    with zipfile.ZipFile(path) as archive:
        raw = archive.read('dcp.xml')
    doc = ET.fromstring(raw)
    values = {node.tag: node.get('Name') for node in doc}
    expected = {'Part': 'xcvu9p-flga2104-2L-e', 'Top': 'scalellm_vcu118_f05_bd_wrapper',
        'BoardPart': 'xilinx.com:vcu118:part0:2.0', 'BUILD_NUMBER': '6299465',
        'PRODUCT': 'Vivado v2025.2 (64-bit)'}
    assert doc.tag == 'Checkpoint' and all(values.get(k) == v for k, v in expected.items())
    return dict(**expected, xml_sha256=hashlib.sha256(raw).hexdigest())


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    out = ROOT / 'agent/A006/followon_placement_parent_cpu_preparation_2026-10-16.json'
    assert not out.exists(), 'Never overwrite a fixed preparation receipt'
    report = ROOT / 'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
    preplace_path = report / 'pre_place_evidence.json'
    preplace = json.loads(preplace_path.read_text())
    proof_path = report / 'inherited_opt_execution_proof.json'
    proof = json.loads(proof_path.read_text())
    constraints_path = report / 'constraints_debug_materialized.json'
    constraints = json.loads(constraints_path.read_text())
    assert preplace['phase'] == 'debug_materialized_pre_place'
    assert identity(preplace['checkpoint']['path']) == preplace['checkpoint']
    assert identity(proof['checkpoint']['path']) == proof['checkpoint']
    inherited_opt_path = report.parent / 'm002_E005_R004_AT002_native_OPT_POST_recovery_place_physopt/opt.dcp'
    inherited = identity(inherited_opt_path)
    assert (inherited['bytes'], inherited['sha256']) == (proof['checkpoint']['bytes'], proof['checkpoint']['sha256'])
    parents = dict(original_OPT=proof['checkpoint'], inherited_identical_OPT=inherited,
        admitted_pre_place=preplace['checkpoint'])
    packages = {name: package(Path(row['path'])) for name, row in parents.items()}
    assert identity(constraints_path) == preplace['constraints']
    constraint_inputs = []
    errors = []
    for path, expected in constraints['hashes'].items():
        try:
            actual = identity(path)
            if actual['sha256'] != expected:
                errors.append(dict(path=path, expected_sha256=expected, actual=actual))
            constraint_inputs.append(actual)
        except FileNotFoundError:
            errors.append(dict(path=path, expected_sha256=expected, missing=True))
    custom = {path: dict(metadata=meta,
        actual=next(r for r in constraint_inputs if r['path'] == path))
        for path, meta in constraints['metadata'].items()
        if Path(path).parent == ROOT / 'project/hardware/vivado/constraints'}
    settings_path = report / 'implementation_settings.txt'
    settings = dict(line.split('=', 1) for line in settings_path.read_text().splitlines() if '=' in line)
    selected = {key: settings[key] for key in ['STRATEGY', 'AUTO_INCREMENTAL_CHECKPOINT',
        'INCREMENTAL_CHECKPOINT', 'STEPS.OPT_DESIGN.ARGS.DIRECTIVE',
        'STEPS.PLACE_DESIGN.ARGS.DIRECTIVE', 'STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE',
        'STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE']}
    assert selected['STEPS.PLACE_DESIGN.ARGS.DIRECTIVE'] == 'SSI_SpreadSLLs'
    assert selected['STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE'] == selected['STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE'] == 'Default'
    assert constraints['mode'] == 'embedded_checkpoint_inherited'
    reads_path = report / 'actual_xdc_reads_debug_materialized.json'
    reads = json.loads(reads_path.read_text())
    assert reads['mode'] == 'embedded_checkpoint_inherited' and reads['new_actual_reads'] == []
    log_path = report / 'implementation_run.log'
    markers = [dict(native_line=i, text=line) for i, line in enumerate(log_path.read_text().splitlines(), 1)
        if line.startswith('Command: place_design') or line.startswith('Command: phys_opt_design')
        or 'placer was invoked with' in line]
    archived_controller = report / 'stage_sources/m002_resume_physical.tcl'
    current_controller = ROOT / 'project/hardware/vivado/scripts/m002_resume_physical.tcl'
    assert identity(archived_controller)['sha256'] == identity(current_controller)['sha256']
    documents = [preplace_path, proof_path, constraints_path, settings_path, reads_path,
        report / 'xdc_registry_debug_materialized_hashed.tsv', report / 'command.json',
        report / 'pre_place_evidence.json', report / 'implementation_settings_scope.txt',
        report / 'archived_sources.sha256', archived_controller, current_controller,
        ROOT / 'project/hardware/vivado/scripts/m002_physical_evidence.py',
        ROOT / 'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json']
    value = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
        role='A006 engineering; future placement preparation only, E006 native session untouched',
        status='CPU_PREPARED_PENDING_NEW_CONTRACT_AND_NATIVE_GRAPH_REQUALIFICATION',
        parent_checkpoints=parents, checkpoint_packages=packages,
        preferred_mechanical_entry='admitted_pre_place to avoid repeated synthesis/OPT/debug; parent decision and new contract still required',
        preplace_phase=preplace['phase'], preplace_physical_signoff=False,
        OPT_qualification=proof['qualified_scope'], original_OPT_execution_state=proof['original_execution_state'],
        constraints_mode=constraints['mode'], candidate_registered_XDC_metadata_count=len(constraints['metadata']),
        recorded_constraint_source_hash_count=len(constraints['hashes']), checked_constraint_sources=constraint_inputs,
        constraint_source_identity_errors=errors, custom_constraint_inputs=custom,
        actual_XDC_reads=reads, original_candidate_project_settings=selected,
        actual_native_command_markers=markers,
        command_entry=dict(path=str(current_controller), supported_phase='post_debug_pre_place',
            effective_policy='Direct command directives after open_checkpoint; original XPR settings alone do not configure the temporary checkpoint project.',
            caution='Existing launcher is bound to E005 contract. Future attempt needs its own contract/source/extra-constraint bindings, fresh report/attempt, and the same EDA lane admission; do not reinterpret original impl_1 FAIL as success.'),
        candidate_requalification='77,360 physopt primitives and hierarchy names do not guarantee OPT/preplace membership. Re-query each proposed exact root/leaf on the actual selected parent; preserve names, REF/IS_PRIMITIVE, cardinality, duplicates, exclusions/cache/bundles and assignment readback before any placement.',
        query_cost_policy='Native exact hierarchy utilization plus closed primitive/site/LOC exclusive CPU counts; avoid large primitive-list report_utilization.',
        unverified=['No selected candidate has been resolved in OPT/preplace by this CPU preparation.',
            'No new placement constraint was loaded or applied.', 'No new EDA, physical command, checkpoint write/copy, route or bitstream.',
            'Original formal reset/CDC/IO safety remains OPEN; no legal-routed timing or board signoff.'],
        evidence=[identity(p) for p in documents], producer=identity(Path(__file__)))
    with out.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(preparation=identity(out), parents=parents,
        constraints_checked=len(constraint_inputs), constraint_errors=len(errors),
        phase=preplace['phase'], actual_commands=markers), ensure_ascii=False))


if __name__ == '__main__':
    main()
