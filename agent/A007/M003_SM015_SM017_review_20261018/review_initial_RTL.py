#!/usr/bin/env python3
"""Bounded independent source review; does not compile or invoke EDA."""
import datetime
import difflib
import hashlib
import itertools
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DESIGN = ROOT / 'agent/A006/M003_SM014_design_20261018'
AT = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R001/attempts/AT001_selected_RTL_and_functional_integration'


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def eval_bool(expression, values):
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    expression = ' '.join(expression.split())
    return bool(eval(expression.strip(), {'__builtins__': {}}, values))


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    receipt_path = AT / 'selected_RTL_applied.json'
    receipt = json.loads(receipt_path.read_text())
    baseline = {x['path']: x for x in json.loads((DESIGN / 'design_input_identities.json').read_text())['production_inputs']}
    sources = {}
    for change in receipt['changes']:
        for key in ('before', 'after', 'diff'):
            assert identity(Path(change[key]['path'])) == change[key]
        before, after = Path(change['before']['path']), Path(change['after']['path'])
        assert baseline[str(after)]['sha256'] == change['before']['sha256']
        assert baseline[str(after)]['bytes'] == change['before']['bytes']
        old, new = before.read_text(), after.read_text()
        actual_diff = ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(before), tofile=str(after)))
        assert actual_diff == Path(change['diff']['path']).read_text()
        sources[after.name] = (old, new)

    old, new = sources['hap_mlp_shared_dual_slice16x12_s44_s54.sv']
    original_start = old.index('    always @(posedge clk) begin\n        if (!rst_n || clear) begin\n            parent_count_r')
    new_start = new.index('    // M003 C-M2:')
    end_marker = '    always @(posedge clk) begin\n        if (!rst_n || clear) begin\n            input_transaction_count'
    assert old[:original_start] == new[:new_start]
    assert old[old.index(end_marker):] == new[new.index(end_marker):]
    map_data = json.loads((DESIGN / 'F1_F3_C_M2_region_groups.json').read_text())
    group_results = {}
    for family, count in (('head', 42), ('tail', 39)):
        function = re.search(r'function automatic integer m003_' + family + r'_ce_group\(input integer bit_index\);(.*?)endfunction', new, re.S).group(1)
        body = function.split('case (bit_index)', 1)[1].split('default:', 1)[0]
        found = re.findall(r'([\d,\s]+):\s*m003_' + family + r'_ce_group\s*=\s*(\d+)\s*;', body)
        assert len(found) == count
        mapping = {}
        parsed_groups = {}
        for bits, number in found:
            number = int(number)
            assert number not in parsed_groups
            parsed_groups[number] = [int(x) for x in bits.split(',')]
            for bit in parsed_groups[number]:
                assert bit not in mapping
                mapping[bit] = number
        expected_groups = [g['bits'] for g in map_data['groups'] if g['family'] == family]
        assert [parsed_groups[i] for i in range(count)] == expected_groups
        assert set(mapping) == set(range(6560))
        assert all(0 < len(x) <= 256 for x in parsed_groups.values())
        group_results[family] = {'groups': count, 'bits': len(mapping), 'max_fanout': max(map(len, parsed_groups.values()))}

    head_ce = re.search(r'wire parent_head_write_ce\s*=\s*(.*?);', new, re.S).group(1)
    tail_ce = re.search(r'wire parent_tail_write_ce\s*=\s*(.*?);', new, re.S).group(1)
    head_condition = re.search(r'wire \[PARENT_PAYLOAD_W-1:0\] parent_head_write_data\s*=\s*(.*?)\?', new, re.S).group(1)
    cases = 0
    for rst, clear, count, inv, r0, r1, h, t, x in itertools.product(range(2), range(2), range(4), *([range(2)] * 6)):
        active = bool(rst and not clear)
        i = bool(active and count != 2 and inv)
        p = bool(active and count != 0 and r0 and r1)
        expected_h, expected_t, expected_n = h, t, count
        if not active:
            expected_n = 0
        elif i and not p:
            if count == 0:
                expected_h = x
            else:
                expected_t = x
            expected_n = (count + 1) & 3
        elif p and not i:
            if count == 2:
                expected_h = t
            expected_n = (count - 1) & 3
        elif i and p:
            expected_h = x
        values = {'rst_n': bool(rst), 'clear': bool(clear), 'in_fire': i,
                  'parent_pop': p, 'parent_empty': count == 0, 'parent_full': count == 2}
        actual_h = (t if eval_bool(head_condition, values) else x) if eval_bool(head_ce, values) else h
        actual_t = x if eval_bool(tail_ce, values) else t
        actual_n = 0 if not active else ((count + int(i) - int(p)) & 3)
        assert (actual_h, actual_t, actual_n) == (expected_h, expected_t, expected_n)
        cases += 1
    assert "if (TILE_W == 9 && PARENT_PAYLOAD_W == 6560)" in new
    assert new.count("LUT1 #(.INIT(2'b10)) u_ce_buffer") == 2
    assert 'parent_head_r[payload_bit] <= parent_head_write_data[payload_bit];' in new
    assert 'parent_tail_r[payload_bit] <= parent_input_payload[payload_bit];' in new

    old_core, core = sources['hap_attention_board_cohort16_core.sv']
    core_without_additions = core.replace('hap_weight_meta_resident #(.LOCAL_ADDR_COPIES(1)) u_meta (', 'hap_weight_meta_resident u_meta (', 1)
    core_without_additions = core_without_additions.replace('        .addr_system_clear(system_clear),\n        .addr_launch(state_r==ST_LAUNCH && weight_command_ready),\n', '', 1)
    assert core_without_additions == old_core
    old_resident, resident = sources['hap_weight_meta_resident.sv']
    state_marker = '    always @(posedge clk or negedge rst_n) begin'
    old_control = old_resident[old_resident.index(state_marker):].split('endmodule', 1)[0]
    control = resident[resident.index(state_marker):].split('endmodule', 1)[0]
    assert old_control.replace('inside the SLR2 metadata pblock', 'inside the metadata bank') == control
    assert 'parameter integer LOCAL_ADDR_COPIES = 0' in resident
    assert 'if (LOCAL_ADDR_COPIES == 1)' in resident
    assert 'rsp_meta_r[slice_index*128 +: 128] <= meta_mem[local_rd_addr];' in resident
    assert 'meta_mem[wr_addr] <= wr_meta16[slice_index*128 +: 128];' in resident
    assert '.system_clear(addr_system_clear), .launch(addr_launch)' in resident
    assert '.rsp_fire(rsp_fire), .addr(local_rd_addr)' in resident
    assert "LUT3 #(.INIT(8'hfe)) u_local_ce" in resident
    assert '.I0(system_clear), .I1(launch), .I2(rsp_fire), .O(local_ce)' in resident
    assert "LUT2 #(.INIT(4'h2)) u_local_increment" in resident
    assert '.I0(rsp_fire), .I1(system_clear), .O(local_increment)' in resident
    assert "address_r <= local_increment ? address_r + 1'b1 : {ADDR_W{1'b0}};" in resident
    assert 'DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO"' in resident

    result = {
        'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'execution': 'completed',
        'verdict': 'INITIAL_RTL_SOURCE_SEMANTICS_AND_IDENTITY_ACCEPTED_NOT_G3A',
        'applicability': 'Exact three-source application receipt reviewed; no compilation, RTL simulation, synthesis or physical result',
        'review': 'A007 independent mapping parser, unchanged-scope comparison and actual emitted CE expression evaluation against original case semantics',
        'source_application_receipt': identity(receipt_path),
        'changes': receipt['changes'],
        'M2_exact_groups': group_results,
        'M2_actual_expression_case_count': cases,
        'MLP_outside_replaced_parent_block_byte_identical': True,
        'core_outside_parameter_and_two_sidebands_byte_identical': True,
        'resident_control_counter_error_logic_unchanged_except_comment': True,
        'A3_source_connections_and_literal_LUT_inputs_match_reviewed_equations': True,
        'baseline_prechange_three_hashes_match_frozen144': True,
        'diffs_reproduced_exactly': 3,
        'blocking_source_findings': [],
        'remaining_G3a': ['native compile with real production parameters', 'actual old/new cycle differential simulation and independent expected results', 'LUT model truth qualification', 'full cases/legacy/reset/abort/collision evidence and current input identities'],
        'remaining_G4': ['native inference and real CE consumers', 'preserved own-state helpers/URAM mapping/RDW', 'budget and physical qualification'],
        'resources': {'affinity': sorted(os.sched_getaffinity(0)), 'nice': os.getpriority(os.PRIO_PROCESS, 0)},
    }
    target = HERE / 'initial_RTL_source_review.json'
    with target.open('x') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({'result': identity(target), 'cases': cases, 'groups': group_results, 'execution': 'completed'}, indent=2))


if __name__ == '__main__':
    main()
