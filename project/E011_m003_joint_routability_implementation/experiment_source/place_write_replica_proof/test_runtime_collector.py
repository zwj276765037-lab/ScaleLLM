"""CPU integration of fresh per-phase collector extraction and cache lifecycle."""
from pathlib import Path
import json
import runpy
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
fixture = runpy.run_path(str(HERE / 'test_cached_collector.py'))
prefix = fixture['prefix']
needle = 'set code [catch {source $collector} message options]'
assert prefix.count(needle) == 1
with tempfile.TemporaryDirectory() as directory:
    report = Path(directory)
    checkpoint = report / 'CPU_fixture_input_identity_only.txt'
    checkpoint.write_text('CPU fixture; no native checkpoint or EDA execution\n')
    replacement = '\n'.join([
        'set ::env(HAP_RECOVERY_CHECKPOINT) {' + str(checkpoint) + '}',
        'set code [catch {',
        ' source {' + str(ROOT / 'project/hardware/vivado/scripts/m003_joint_checks.tcl') + '}',
        ' source {' + str(HERE / 'runtime_state_collector.tcl') + '}',
        ' m003_collect_actual_write_states restore $out',
        ' m003_collect_actual_write_states place $out',
        '} message options]',
    ])
    script = report / 'CPU_runtime_mock.tcl'
    script.write_text(prefix.replace(needle, replacement))
    result = subprocess.run(['tclsh', str(script), 'positive', str(report),
                             str(HERE / 'query_cached.tcl')], text=True, capture_output=True)
    assert result.returncode == 0 and not result.stderr, result.stderr
    for phase in ['restore', 'place']:
        rows = [json.loads(line) for line in (report / f'state_{phase}_actual.jsonl').read_text().splitlines()]
        assert len(rows) == 108
        counts = {kind: sum(row['kind'] == kind for row in rows) for kind in ['cell', 'state_pin', 'memory_root_pin', 'state_clock', 'parent']}
        assert counts == dict(cell=12, state_pin=48, memory_root_pin=24, state_clock=12, parent=12)
        context = json.loads((report / f'state_{phase}_native_context.json').read_text())
        assert context['phase'] == phase and context['checkpoint'] == str(checkpoint)
        trace = [json.loads(line) for line in (report / f'state_{phase}_API_trace.jsonl').read_text().splitlines()]
        begin = [row for row in trace if row['event'] == 'api_begin']
        assert {api: sum(row['api'] == api for row in begin) for api in ['segments', 'drivers', 'ports', 'canonical']} == dict(segments=15, drivers=15, ports=15, canonical=15)
        assert all(row['input_objects'] == '1' for row in begin if row['api'] == 'ports')
    assert not (report / 'vivado.log').exists()
print(json.dumps(dict(passed=True, CPU_fixture_only=True, native_executed=False,
                      fresh_phases=['restore', 'place'], each_selected_rows=108,
                      each_endpoints=72, each_groups=15,
                      cache_invalidated_between_phases=True)))
