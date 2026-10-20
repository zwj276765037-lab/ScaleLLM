"""Bind completed resident groups and explicit independent reports for analysis."""
import argparse
import json
from pathlib import Path
from aggregate_final import identity, verified, read, require, session_binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-analysis', type=Path, required=True)
    parser.add_argument('--core-audit-pattern', required=True, help='absolute path template containing {group_id}')
    parser.add_argument('--extension-audit-pattern', required=True, help='absolute path template containing {group_id}')
    parser.add_argument('--core-auditor-sha', required=True)
    parser.add_argument('--extension-auditor-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    complete = read(args.session_analysis)
    runtime_plan = read(verified(complete['plan']))
    formal_plan_source = runtime_plan['formal_batch_plan']
    formal_plan = read(verified(formal_plan_source))
    stream_source = formal_plan['input_stream_manifest']
    target = {doc['doc_id']: doc for doc in read(verified(stream_source))['documents']}
    session_binding(identity(args.session_analysis), target, args.extension_auditor_sha)
    require('{group_id}' in args.core_audit_pattern and '{group_id}' in args.extension_audit_pattern,
            'explicit per-group audit path patterns required')
    groups = []
    frozen = {row['path']: row['sha256'] for row in runtime_plan['source_identities']}
    worker_sources = None
    for group in complete['ordered_groups']:
        attempt = Path(group['attempt_path']).resolve()
        receipt = read(verified(group['receipt']))
        sources = read(attempt / 'paired_worker_manifest.json')['code']
        require(all(frozen.get(row['path']) == row['sha256'] for row in sources), 'worker sources outside frozen session plan')
        require(worker_sources in (None, sources), 'actual worker source lists changed across groups')
        worker_sources = sources
        core = Path(args.core_audit_pattern.format(group_id=group['group_id'])).resolve()
        extension = Path(args.extension_audit_pattern.format(group_id=group['group_id'])).resolve()
        require(read(core)['source_identity']['sha256'] == args.core_auditor_sha
                and read(extension)['source_identity']['sha256'] == args.extension_auditor_sha,
                'explicit frozen auditor SHA differs')
        groups.append(dict(group_id=group['group_id'], attempt=str(attempt), doc_ids=receipt['doc_ids'],
                           core_audit=identity(core), extension_audit=identity(extension)))
    inputs = dict(schema='m005_r005_analysis_inputs_v1', formal_plan=formal_plan_source, formal_stream=stream_source,
                  session_analysis_manifest=identity(args.session_analysis), expected_worker_sources=worker_sources,
                  expected_core_auditor_sha256=args.core_auditor_sha,
                  expected_extension_auditor_sha256=args.extension_auditor_sha,
                  groups=groups, builder_source=identity(__file__))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(inputs, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
