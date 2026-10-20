"""Bind each fresh state query to that same native phase's saved checkpoint."""
from pathlib import Path
import argparse
import json
import os
import qualify_placed_sources as qualifier
import state_equivalence as proof

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', required=True, choices=['restore', 'place', 'physopt', 'route'])
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    package_path = Path(os.environ['HAP_M003_CONTINUE_PLACE_PACKAGE'])
    package = json.loads(package_path.read_text())
    for row in package['bindings']:
        assert proof.identity(row['path']) == row
    context_path = args.report / f'state_{args.phase}_native_context.json'
    context = json.loads(context_path.read_text())
    assert context['phase'] == args.phase and context['new_state_query'] == 'true'
    assert context['selected_cells'] == '12' and context['selected_root_pins'] == '24'
    snapshot = json.loads(args.snapshot.read_text())
    assert snapshot['meta']['phase'] == args.phase
    expected_checkpoint = package['checkpoint']['path'] if args.phase in ['restore', 'place'] else str(args.report / f'{args.phase}.dcp')
    assert context['checkpoint'] == expected_checkpoint
    query = json.loads(Path(package['selection_package']['path']).read_text())
    query['checkpoint'] = proof.identity(expected_checkpoint)
    # Old query bindings remain immutable input provenance, not a claim of
    # observing an old graph after a new physopt/route transformation.
    query['bindings'] += [proof.identity(path) for path in [package_path, args.snapshot, context_path, Path(expected_checkpoint)]]
    query['actual_native_phase'] = args.phase
    query['fresh_state_source'] = proof.identity(args.report / f'state_{args.phase}_actual.jsonl')
    query['original_place_checkpoint'] = package['checkpoint']
    phase_package = args.report / f'state_{args.phase}_same_graph_package.json'
    with phase_package.open('x') as stream:
        json.dump(query, stream, indent=2)
        stream.write('\n')
    result = qualifier.qualify(args.snapshot, args.spec,
                               args.report / f'state_{args.phase}_actual.jsonl',
                               phase_package, args.output)
    print(json.dumps(dict(passed=result['passed'], errors=result['errors'],
                          phase=args.phase, fresh_actual_state_query=True)))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
