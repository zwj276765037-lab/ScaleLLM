#!/usr/bin/env python3
"""A007 bounded file binding; no EDA, DCP access, or production rehash."""
import datetime
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DESIGN = ROOT / 'agent/A006/M003_SM014_design_20261018'


def identity(path):
    assert path.suffix.lower() != '.dcp', path
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size,
            'sha256': digest.hexdigest()}


def check(expected):
    actual = identity(Path(expected['path']))
    assert actual == expected, (actual, expected)
    return actual


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest_path = DESIGN / 'design_delivery_manifest.json'
    manifest_identity = identity(manifest_path)
    assert manifest_identity['bytes'] == 9655
    assert manifest_identity['sha256'] == '6d74e85db325a939c8b1ffbd637de6dbd35e2016188bdd0050d62cc5a2b9706b'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['G2_approved'] is False
    assert manifest['production_changed'] is False and manifest['new_EDA'] is False
    entries = manifest['files']
    assert len(entries) == 34 and len({x['path'] for x in entries}) == 34
    for entry in entries:
        assert Path(entry['path']).parent == DESIGN
    verified = [check(entry) for entry in entries]
    names = {Path(entry['path']).name for entry in entries}
    assert set(manifest['authoritative_design']).issubset(names)
    delivery_path = DESIGN / 'delivery_execution_receipt.json'
    delivery = json.loads(delivery_path.read_text())
    assert delivery['observed_native_tool_exit_code'] == 0
    assert delivery['tool_chunk_id'] == '7b224a'
    output = json.loads(delivery['output'])
    assert output['manifest'] == manifest_identity
    assert output['files'] == 34
    cpu_identity = check(output['CPU_receipt'])
    cpu = json.loads(Path(cpu_identity['path']).read_text())
    assert cpu['affinity_observed'] == list(range(8))
    assert cpu['nice_observed'] == 5 and cpu['max_threads'] == 1
    assert cpu['production_inputs_current_equals_E009_baseline'] == 144
    inputs_path = DESIGN / 'design_input_identities.json'
    inputs = json.loads(inputs_path.read_text())
    baseline_identity = check(inputs['baseline_identity'])
    baseline = json.loads(Path(baseline_identity['path']).read_text())
    expected = baseline['production_inputs']
    recorded = inputs['production_inputs']
    assert len(recorded) == len(expected) == 144
    assert len({x['path'] for x in recorded}) == 144
    fields = ('path', 'bytes', 'sha256')
    assert {x['path']: {k: x[k] for k in fields} for x in recorded} == {
        x['path']: {k: x[k] for k in fields} for x in expected}
    extraction_identities = [check(x) for x in inputs['existing_native_extraction_manifests']]
    review_names = [
        'F4_existing_C01_physical_evidence.json', 'F4_and_G2_preparation.md',
        'F1_first_subtable_review.json', 'F4_full_metadata_inventory_review.json',
        'C_A3_F4_resource_rules_review.json', 'C_M2_regional_buffer_design_review.json',
        'review_M2_equations.py', 'M2_equation_check.json',
        'review_A3_LUT_equations.py', 'A3_LUT_equation_check.json']
    review_identities = [identity(HERE / n) for n in review_names]
    result = {
        'started_utc': started_utc,
        'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'execution': 'completed',
        'verdict': 'all34 design files match frozen manifest; delivery output and144 recorded baseline identities consistent',
        'applicability': 'SM014 design package binding only; production rehash performed by A006, not repeated by A007',
        'review': 'A007 independent bounded file identities and receipt/source semantics',
        'manifest': manifest_identity,
        'verified_design_files': verified,
        'verified_design_bytes': sum(x['bytes'] for x in verified),
        'delivery_receipt': identity(delivery_path),
        'CPU_receipt': cpu_identity,
        'design_input_identities': identity(inputs_path),
        'baseline_metadata': baseline_identity,
        'production_identity_records_equal': 144,
        'extraction_identities': extraction_identities,
        'review_artifacts': review_identities,
        'actual_review_process': {'pid': os.getpid(), 'affinity': sorted(os.sched_getaffinity(0)),
                                  'nice': os.getpriority(os.PRIO_PROCESS, 0), 'threads': 1},
        'receipt_caveat': 'A006 started_utc=0 is invalid: source reuses start for group chunk offset after assigning UTC. Do not use as execution start timestamp. observed_utc and actual delivery exit remain separate valid evidence; original package is preserved.',
        'not_performed': ['EDA invocation', 'DCP access or hash', 'large native-table rescan',
                          'production144 input rehash', 'production modification', 'signal or lock operation']
    }
    target = HERE / 'G2_final_binding_check.json'
    with target.open('x') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({'result': identity(target), 'files': len(verified),
                      'bytes': result['verified_design_bytes'], 'baseline_records': 144,
                      'execution': 'completed'}, indent=2))


if __name__ == '__main__':
    main()
