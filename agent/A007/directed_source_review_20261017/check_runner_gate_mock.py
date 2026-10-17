"""Execute the actual prior-closure guard in a CPU fixture, with no process I/O."""
from pathlib import Path
import ast
import hashlib
import json
import sys

SOURCE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(exist_ok=False)
text = SOURCE.read_text()
tree = ast.parse(text)
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'actual_prior_closure')
isolated = compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(SOURCE), 'exec')


def identity(path):
    p = Path(path).resolve()
    b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def require(value, message):
    if not value:
        raise ValueError(message)


checks = ['no_survivors', 'no_original_live', 'lane_released', 'production_144_unchanged', 'source_physopt_DCP_unchanged',
          'archived_8_sources_unchanged', 'all_bound_external_targets_sources_unchanged', 'all_bound_reused_closed_inputs_unchanged',
          'replacement_authorization_unchanged', 'contract_unchanged', 'resource_helper_unchanged', 'no_post_integrity_error',
          'wrapper_after_freeze_agrees', 'no_physical_commands', 'no_checkpoint_write', 'resource_extrema_agree']
results = []
for case in ['natural_failed_native_closed', 'still_running', 'survivors', 'live_original_identity', 'missing_integrity',
             'stopped_without_new_authorization', 'stopped_wrong_attempt', 'stopped_exact_authorization', 'natural_not_observed']:
    e = OUT / case / 'E006'
    prior = e / 'experiment_results/runs/R004/attempts/AT001_exact'
    prior.mkdir(parents=True)
    status = dict(execution_state='completed', owned_survivors=[], stop_reason=None, native_natural_terminal_observed=True, native_exit_code=1)
    if case == 'still_running': status['execution_state'] = 'running'
    if case == 'survivors': status['owned_survivors'] = [123]
    if case == 'natural_not_observed': status['native_natural_terminal_observed'] = False
    if case.startswith('stopped_'): status['stop_reason'] = 'MOCK_CONTROLLED_STOP'
    (prior / 'status.json').write_text(json.dumps(status))
    (prior / 'started.json').write_text(json.dumps(dict(supervisor_pid=123, supervisor_start_ticks=456)))
    flags = {key: True for key in checks}
    if case == 'missing_integrity': flags['production_144_unchanged'] = False
    facts = dict(status=identity(prior / 'status.json'), checks=flags)
    (prior / 'facts.json').write_text(json.dumps(facts))
    auth = dict(prior_terminal_status=identity(prior / 'status.json'), prior_terminal_facts=identity(prior / 'facts.json'))
    if case in {'stopped_wrong_attempt', 'stopped_exact_authorization'}:
        stop = dict(approval_kind='user_explicit_controlled_stop', authorized_stop_attempt=str(prior if case == 'stopped_exact_authorization' else prior.parent / 'WRONG_ATTEMPT'))
        (prior / 'stop.json').write_text(json.dumps(stop)); auth['controlled_stop_evidence'] = identity(prior / 'stop.json')
    namespace = dict(Path=Path, json=json, PRIOR=prior, E006=e, identity=identity, require=require,
                     prior_registered_identities=lambda status, started: ['MOCK_IDENTITY_NO_PROCESS_QUERY'],
                     require_registered_closed=lambda values: require(case != 'live_original_identity', 'Mock registered identity still live'))
    exec(isolated, namespace)
    accepted = True; error = None
    try:
        namespace['actual_prior_closure'](auth)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        accepted = False; error = str(exc)
    expected = case in {'natural_failed_native_closed', 'stopped_exact_authorization'}
    results.append(dict(case=case, expected_accept=expected, actual_accept=accepted, error=error))
    assert accepted == expected, results[-1]
report = dict(execution='CPU_mock_only', source=identity(SOURCE), cases=results, EDA_or_signal_or_lock_operations=0,
              actual_process_queries=0, limitation='Actual authorization evidence, terminal PID/start identities and lane still require real execution validation')
(OUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
