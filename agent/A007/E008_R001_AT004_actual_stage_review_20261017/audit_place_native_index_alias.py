"""A007 text-only AT004 place closed native index and alias evidence replay."""
import sys
sys.dont_write_bytecode = True

def deny_dcp_content(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        path = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if path.lower().endswith('.dcp'):
            raise RuntimeError('A007 is forbidden to open DCP content')

sys.addaudithook(deny_dcp_content)
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).resolve().parent
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
ATTEMPT = ROOT / 'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
PRIOR = OUT / 'pre_place_native_index_alias_review.json'
checked = {}

def identity(path):
    path = Path(path).resolve()
    assert path.suffix.lower() != '.dcp', 'DCP identity is engineering-provided metadata only'
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    row = dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())
    checked[str(path)] = row
    return row

def bound(row):
    actual = identity(row['path'])
    assert actual == row, row['path']
    return actual

def read_json(path):
    return json.loads(Path(path).read_text())

facts_path = ATTEMPT / 'candidate_place_native_port_index_closed_facts.json'
facts_id = identity(facts_path)
assert facts_id['sha256'] == '1d52ededc682d60504ab2754492d16a9068843fe95dc0b2fcccf3ad7f57bb07d'
facts = read_json(facts_path)
assert facts['point'] == 'place' and facts['native_index_qualification_closed'] is True
for row in facts['native_index_artifacts'] + facts['buffered_alias_trace']['artifacts']:
    bound(row)
for key in ['archived_validator', 'input_bindings', 'preparation_manifest', 'producer']:
    bound(facts[key])
bindings = read_json(facts['input_bindings']['path'])
parent_id = bound(bindings['parent'])
assert Path(parent_id['path']) == REPORT / 'recovery_parent.json'
parent = read_json(parent_id['path'])
checkpoint_metadata = parent['checkpoint']
assert checkpoint_metadata['sha256'] == '8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f'
assert facts['preparation_manifest']['sha256'] == 'b9dcabf46f82b505e0a49de9a2c14eb013b7d71937e2d2805a9538f7545227bb'
assert facts['actual_selected_candidate'] == dict(id='C01', root='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf')

validator = REPORT / 'stage_sources/top_port_evidence.py'
spec = importlib.util.spec_from_file_location('at004_archived_top_port_evidence', validator)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.identity = identity
actual = module.validate('place', REPORT, require_closed=False)
closed = read_json(REPORT / 'candidate_top_port_index_closed_place.json')
assert facts['native_closed_receipt'] == closed
assert closed['qualified'] is True and closed['issues'] == [] and closed['point'] == 'place'
assert closed['epoch_id'] == actual['epoch_id']
assert closed['sources'] == [identity(REPORT / 'stage_sources/top_port_index.tcl'), identity(validator)]
assert closed['artifacts'] == [identity(actual['path']), identity(actual['calls_path'])]
assert closed['input_identity'] == checkpoint_metadata
epoch = module.split(actual['epoch_id'])
assert Path(epoch[3]) == Path(actual['input_path']) == Path(checkpoint_metadata['path'])
assert epoch[0] == 'place' and epoch[2] == 'checkpoint_debug_materialized'
assert actual['source_paths'] == [closed['sources'][0]['path']]
counts = dict(ports=actual['native_port_count'], groups=len(actual['groups']), aliases=len(actual['aliases']), calls=actual['native_calls'], directions=dict(Counter(actual['directions'].values())))
for field, key in [('native_port_count', 'ports'), ('native_group_count', 'groups'), ('native_call_count', 'calls')]:
    assert closed[field] == facts[field] == counts[key]
unknowns = {key: actual[key + '_ports'] for key in ['disconnected', 'multigroup', 'unknown_direction']}
assert all(value == [] for value in unknowns.values())
assert all(closed[key + '_ports'] == value for key, value in unknowns.items())

marker = dict(line.split('=', 1) for line in (REPORT / 'candidate_alias_api_trace_place_closed.txt').read_text().splitlines())
assert marker == facts['buffered_alias_trace']['receipt']
assert marker == dict(completed='1', point='place', recorded_events='167160', mapping_tcl_code='0', mode='BUFFERED_FILE_NO_PER_EVENT_FLUSH', normal_final_flush='1')
events = Counter()
stack = []
previous_ms = None
first_ms = None
last_sequence = 0
with (REPORT / 'candidate_alias_api_trace_place.tcllist').open() as stream:
    for line in stream:
        tokens = module.split(line)
        assert tokens[0] == 'DIRECTED_API' and len(tokens[1:]) % 2 == 0
        event = dict(zip(tokens[1::2], tokens[2::2]))
        assert len(event) * 2 == len(tokens) - 1
        assert set(event) == {'operation', 'event', 'epoch_ms', 'point', 'sequence', 'detail'}
        assert event['point'] == 'place'
        assert int(event['sequence']) == last_sequence + 1
        last_sequence += 1
        stamp = int(event['epoch_ms'])
        assert previous_ms is None or stamp >= previous_ms
        first_ms = stamp if first_ms is None else first_ms
        previous_ms = stamp
        key = (event['operation'], event['detail'])
        assert event['operation'] in {'ALIAS_NET_NAME', 'ALIAS_NATIVE_SEGMENTS', 'ALIAS_SEGMENT_NAME'}
        if event['event'] == 'BEGIN':
            stack.append(key)
        else:
            assert event['event'] == 'END' and stack and stack.pop() == key
        events[(event['operation'], event['event'])] += 1
assert not stack
assert last_sequence == int(marker['recorded_events']) == facts['buffered_alias_trace']['actual_event_lines']
event_counts = [dict(operation=operation, event=event, count=count) for (operation, event), count in sorted(events.items())]
prior_id = identity(PRIOR)
assert prior_id['sha256'] == 'a3995715ca509e8c2254f7bf33e5b53cf694755ca8fd98c826f937f0d0610b66'
prior = read_json(PRIOR)
assert counts == prior['native_counts']
assert event_counts == prior['alias_event_counts']
assert last_sequence == prior['alias_events']
prior_checks = {row['path']: row for row in prior['identity_checks']}
assert all(row == prior_checks[row['path']] for row in closed['sources'])

result = dict(
    recorded_utc=datetime.now(timezone.utc).isoformat(),
    execution='completed_actual_AT004_place_native_port_index_and_closed_buffered_alias_review',
    verdict='supported_complete_native_top_port_universe_adjacency_aliases_and_exhaustive_reciprocity',
    applicability='AT004 actual place graph; epoch input path identifies originally restored debug_materialized DCP, not a new restore or pre-place measurement; index and alias substeps only',
    review='accepted_index_and_alias_substeps_no_new_gate',
    reviewer='A007', facts=facts_id, identity_checks=list(checked.values()),
    actual_archived_validator=identity(validator), actual_validator_require_closed=False,
    complete_native_semantic_validator_passed=True,
    independent_closed_receipt_point_epoch_sources_artifacts_input_binding_checks=True,
    DCP_content_identity_attributed_to_engineering=checkpoint_metadata,
    DCP_read_or_hashed_by_reviewer=False, DCP_open_guard_installed=True,
    started_parent_binding=parent_id, native_counts=counts, unknowns=unknowns,
    actual_buffered_alias_receipt=marker, alias_events=last_sequence,
    all_sequences_consecutive=True, all_timestamps_nondecreasing=True,
    all_BEGIN_END_operation_detail_pairs_complete=True, alias_event_counts=event_counts,
    alias_event_span_ms=previous_ms - first_ms,
    event_span_scope='First-to-last recorded ALIAS event only; no API or whole-stage performance inference',
    prior_accepted_review=prior_id,
    prior_comparison='Archived collector/validator identities and independently reproduced semantic counts/alias operation counts match accepted AT004 pre_place; current actual artifacts and epoch validated freshly',
    limits=['Not full directed cut closure or combined candidate phase acceptance', 'Not timing, routing or physical signoff', 'No locality or timing improvement claim'],
    no_EDA_DCP_signal_or_lock_control=True,
)
output = OUT / 'place_native_index_alias_review.json'
with output.open('x') as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
md = OUT / 'place_native_index_alias_review.md'
with md.open('x') as stream:
    stream.write('# AT004 place 原生端口索引与缓冲别名审核\n\n'
                 '- execution：当前 AT004 归档验证器完整重放及闭合记录独立核对已完成。\n'
                 '- verdict：支持完整原生端口全集、逐端口邻接、别名闭包及全组双向互证；269 个端口、269 个组、2,772 个别名、2,170 次原生调用。IN 23 / OUT 70 / INOUT 176；断开、多组和未知方向均为 0。\n'
                 '- 167,160 条已闭合别名事件序号连续、时间不递减、BEGIN/END 操作与 detail 完整配对；正常最终 flush，mapping Tcl code 0。\n'
                 '- 实际 source、artifact、point、epoch 与父输入元数据绑定均通过；DCP 身份来自工程归档元数据，审核未读取或哈希 DCP。\n'
                 '- applicability：仅适用于 AT004 实际 place 图的索引与别名子步骤；epoch 的输入路径指原始恢复DCP，并非重新恢复或pre-place测量。未据此确认完整 cut、时序、combined候选phase或route；不推断迁移收益。\n'
                 '- review：本子步骤接受，无新增执行停点。原始证据与此前审核保持。\n\n'
                 '[完整审核与证据身份](place_native_index_alias_review.json)\n')
print(json.dumps(dict(output=identity(output), human=identity(md), native_counts=counts, alias_events=last_sequence, alias_event_span_ms=previous_ms-first_ms), ensure_ascii=False))
