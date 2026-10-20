"""Retain full frozen qualification; prove exact physical FF copies at one guard."""
from pathlib import Path
import argparse
import inspect
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'AT028_init_recovery'))
import native_init_recovery as base
import state_equivalence as proof

NEEDLE = "require(ds==[expected_write],'URAM root write-address bit source changed')"
REPLACEMENT = "require(ds==[expected_write] or proven_physical_write_source(name,bit,ds,expected_write),'URAM root write-address bit source changed')"

def qualify(snapshot_path, spec_path, raw_path, package_path, output):
    certificate = proof.prove(raw_path, snapshot_path, package_path)
    exact = {(row['cell'], row['pin']): row for row in certificate['affected_root_bindings']}
    def proven_physical_write_source(name, bit, ds, expected):
        row = exact.get((name, f'ADDR_B[{bit}]'))
        return bool(row and ds == [row['actual_driver']] and expected == row['original_state'])
    original = base.joint.validate_effective_memories
    source = inspect.getsource(original)
    assert source.count(NEEDLE) == 1 and source.count('proven_physical_write_source') == 0
    namespace = {**base.joint.__dict__, 'proven_physical_write_source': proven_physical_write_source}
    exec(compile(source.replace(NEEDLE, REPLACEMENT), str(Path(__file__)) + ':single_source_predicate', 'exec'), namespace)
    spec = json.loads(spec_path.read_text())
    snapshot = base.joint.decode_grouped_snapshot(json.loads(snapshot_path.read_text()))
    observations = base.normalize_cell_literals(snapshot)
    base.joint.validate_effective_memories = namespace['validate_effective_memories']
    try:
        result = base.joint.validate(snapshot, spec, fixture=False)
    finally:
        base.joint.validate_effective_memories = original
    def bind(ok, message):
        if not ok:
            result['errors'].append(message)
            result['passed'] = False
    bind(snapshot.get('meta', {}).get('spec_sha256') == base.joint.sha(spec_path), 'source/spec identity mismatch')
    base.entry.check_sources()
    bind(snapshot.get('meta', {}).get('source_manifest_sha256') == base.joint.sha(base.entry.MANIFEST), 'native source manifest binding changed')
    for row in spec['source_RTL']:
        bind(Path(row['path']).is_file() and base.joint.sha(Path(row['path'])) == row['sha256'], 'selected RTL source identity changed')
    bind(base.joint.sha(base.ROOT / 'mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md') == base.joint.G2_SHA, 'G2 source binding changed')
    result.update(observed_utc=base.stage.now(), snapshot_sha256=base.joint.sha(snapshot_path),
                  spec_sha256=base.joint.sha(spec_path), execution='completed',
                  verdict='NATIVE_STRUCTURE_ONLY_NOT_TIMING_OR_OVERALL_G4',
                  explicit_adapter=proof.identity(Path(__file__)),
                  prior_literal_adapter=proof.identity(Path(base.__file__)),
                  original_frozen_validator=proof.identity(base.HW / 'vivado/scripts/m003_joint_evidence.py'),
                  physical_state_equivalence=certificate,
                  single_guard_extension=dict(original=NEEDLE, replacement=REPLACEMENT),
                  raw_snapshot_unchanged=True, raw_reset_endpoint_observations=observations,
                  normalized_cell_literals=sum(row['normalization'] == 'width1_binary_cell_literal' for row in observations),
                  pin_evidence_unchanged_and_required=True,
                  original_full_function_evaluation_retained=True,
                  no_alias_expansion_or_source_renaming=True)
    base.save(output, result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.snapshot, args.spec, args.raw, args.package, args.output)
    print(json.dumps(dict(passed=result['passed'], errors=result['errors'],
                          actual_state_pairs=len(result['physical_state_equivalence']['state_pairs']))))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    sys.exit(main())
