"""Bounded text-only assessment of actual AT004 placement warnings."""
import sys
sys.dont_write_bytecode=True
def forbid_dcp(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        name=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if name.lower().endswith('.dcp'):raise RuntimeError('DCP access forbidden')
sys.addaudithook(forbid_dcp)
import json,hashlib,re,tkinter
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).resolve().parent
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
CONTRACT=ROOT/'mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md'
CANDIDATE='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf'
def read(path):return json.loads(Path(path).read_text())
def identity(path):
    path=Path(path).resolve();assert path.suffix.lower()!='.dcp'
    a=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(4*1024*1024),b''):h.update(b)
    z=path.stat();assert(a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns)
    return dict(path=str(path),bytes=z.st_size,sha256=h.hexdigest())
def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
parent=read(REPORT/'recovery_parent.json')
prior_log=Path(parent['child_log']['path'])
assert identity(prior_log)==parent['child_log']
current_log=REPORT/'vivado.log'
with current_log.open('rb') as stream:
    size=current_log.stat().st_size
    prefix=stream.read(size)
assert len(prefix)==size
with current_log.open('rb') as stream:assert stream.read(size)==prefix
observed=datetime.now(timezone.utc).isoformat()

def extract(data):
    lines=data.decode().splitlines();selected=[];warnings=[];sll=[];suppressed=[];phases=[];success=[]
    for number,line in enumerate(lines,1):
        row=dict(line=number,text=line)
        if '[Place 30-1229]' in line:
            warnings.append(dict(row,cell=line.split('cell: ',1)[1]))
        if "Message 'Place 30-1229'" in line:suppressed.append(row)
        if '[Place 30-356]' in line:
            match=re.search(r'requires\s+(\d+)\s+Super Long Lines \(SLLs\) out of (\d+).*SLR#\s*(\d+) to SLR#\s*(\d+)',line)
            assert match
            need,total,source,target=map(int,match.groups())
            sll.append(dict(row,required=need,available=total,source_SLR=source,target_SLR=target,ratio_percent=100*need/total))
        if line.startswith('Phase ') or line.startswith('Command: place_design'):phases.append(row)
        if line=='place_design completed successfully':success.append(row)
        if '[Place 30-1229]' in line or "Message 'Place 30-1229'" in line or '[Place 30-356]' in line or 'currently routable' in line or 'future design changes' in line or line.startswith('Phase 2') or line.startswith('Command: place_design') or line=='place_design completed successfully':selected.append(row)
    cells={row['cell'] for row in warnings}
    return dict(warnings=warnings,warning_cells=cells,suppression=suppressed,SLL=sll,phases=phases,place_success=success,selected_lines=selected)
current=extract(prefix);prior=extract(prior_log.read_bytes())
assert len(current['warnings'])==len(current['warning_cells'])==100
assert len(prior['warnings'])==len(prior['warning_cells'])==100
assert len(current['suppression'])==len(prior['suppression'])==1
assert all(name.startswith('scalellm_vcu118_f05_bd_i/d0_mig_slice/inst/ar15.ar_multi/') for name in current['warning_cells'])
assert all(not name.startswith(CANDIDATE+'/') and name!=CANDIDATE for name in current['warning_cells'])
assert len(current['SLL'])==len(prior['SLL'])==1
assert [current['SLL'][0][key] for key in ['required','available','source_SLR','target_SLR']]==[10865,17280,1,2]
assert [prior['SLL'][0][key] for key in ['required','available','source_SLR','target_SLR']]==[10594,17280,0,1]
assert len(prior['place_success'])==1 and not current['place_success']
assert current['phases'][-1]['text']=='Phase 2.1.1.1 PBP: Partition Driven Placement'

tcl=tkinter.Tcl()
parts=tcl.splitlist((REPORT/'candidate_policy_before.tcllist').read_text());policies=dict(zip(parts[::2],parts[1::2]))
fields=set()
for value in policies.values():fields.update(tcl.splitlist(value)[::2])
assert len(policies)==9525 and not current['warning_cells'] & policies.keys() and 'USER_SLL_REG' not in fields
assert (REPORT/'candidate_policy_before.tcllist').read_bytes()==(REPORT/'candidate_policy_after.tcllist').read_bytes()
assert 'USER_SLL_REG' not in (REPORT/'candidate_effective_physical.xdc').read_text()
global_review=read(OUT/'restored_pre_place_global_incremental_review.json')
assert identity(OUT/'restored_pre_place_global_incremental_review.json')['sha256']=='2b5963a1f6489077b9644a2d8cc0a38b592e9c67f6a32a2820251c774c0f0587'
accepted_ids={v['path']:v for v in global_review['all_identity_checks']}
source_ids=[]
for name in ['candidate_hooks.tcl','evidence_adapter.py','m002_diagnostic_common.tcl','m002_optimized_structure.tcl']:
    path=REPORT/'stage_sources'/name;row=identity(path)
    assert row==accepted_ids[str(path)]
    source_ids.append(row)
# Bounded source-text observation: absence in XDC source text is not absence in embedded netlist attributes.
constraint_mentions=[]
for original in parent['hashes']:
    path=Path(original)
    if not path.is_file():path=Path(parent['source_archives'][original]['path'])
    if 'USER_SLL_REG' in path.read_text():constraint_mentions.append(str(path))
assert constraint_mentions==[]

excerpt_path=OUT/'AT004_place_warning_observed_excerpt_20261017.json'
save(excerpt_path,dict(observed_utc=observed,
    current_source_log=str(current_log),current_observed_prefix_bytes=size,
    current_observed_prefix_sha256=hashlib.sha256(prefix).hexdigest(),
    scope='Selected exact lines from the observed prefix; prefix hash is not a claim that the growing whole log is immutable.',
    current_lines=current['selected_lines'],prior_source_log=parent['child_log'],prior_lines=prior['selected_lines']))
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',
    execution='completed_readonly_actual_log_warning_and_contract_impact_review',
    verdict='warnings_require_interpretation_in_existing_POST_and_route_acceptance; no_new_stop_or_contract_violation_established',
    applicability='AT004 C01, observed floorplanning/PBP prefix only; placement and POST incomplete',
    review='accepted_bounded_warning_assessment_no_new_gate',
    evidence_excerpt=identity(excerpt_path),contract=identity(CONTRACT),archived_stage_sources=source_ids,
    accepted_current_global_review=identity(OUT/'restored_pre_place_global_incremental_review.json'),
    accepted_current_policy_review=identity(OUT/'actual_policy_preservation_incremental_review.json'),
    current_stage=current['phases'][-1],
    ignored_USER_SLL_REG=dict(
        visible_warnings=100,visible_unique_cells=100,message_suppression=current['suppression'][0],
        actual_total='UNKNOWN_AFTER_TOOL_MESSAGE_SUPPRESSION; 100 visible is a lower bound',
        visible_hierarchy='d0_mig_slice/inst/ar15.ar_multi/triple_slr.fwd.*',
        visible_candidate_overlap=0,scope_warning='No claim about suppressed cells or the complete DDR/MIG device-wide population',
        native_text_meaning='SLR partitioner explicitly could not obey USER_SLL_REG for the visible cells; placement preference application is not proven by preserved input bytes.',
        input_preservation='144 production and 175 constraint-source identities and candidate overlay were accepted previously; these warnings do not themselves show user/source constraints were edited, cleared or softened.',
        policy_receipt_limit=dict(candidate_ancestor_objects=9525,fields=sorted(fields),visible_warning_cells_in_policy_receipt=0,USER_SLL_REG_value_field_present=False,physical_xdc_USER_SLL_REG_mentions=0,constraint_source_USER_SLL_REG_mentions=constraint_mentions,
            interpretation='The accepted candidate/ancestor policy before-after receipt is not a per-cell DDR USER_SLL_REG census. No native pre/post DDR property census is available here; text absence does not establish absence from the embedded netlist.'),
        prior_same_stage=dict(visible_warnings=100,suppressed=True,visible_hierarchies=dict(Counter(n.split('/inst/',1)[1].split('/',1)[0] for n in prior['warning_cells'])),visible_cell_overlap=len(current['warning_cells']&prior['warning_cells']),old_place_completed=prior['place_success'][0],
            interpretation='Same warning class predates C01 and was nonfatal in that prior placement. Different visible censored subsets cannot establish growth, improvement or C01 causation; prior completion does not make current warning harmless.')),
    SLL_warning=dict(current=current['SLL'][0],prior=prior['SLL'][0],
        interpretation='10865/17280 = 62.8761574% is this floorplanning warning for the whole-design SLR1-to-SLR2 crossing. It is not candidate-only connectivity, routed SLL use, bandwidth, legal route completion or timing signoff.',
        tool_qualifier='currently routable however performance may be impacted due to high connectivity utilization',
        comparison='Prior warning is 10594/17280 on SLR0-to-SLR1, a different crossing. No same-boundary delta or causal shift can be inferred from the two threshold-triggered warning messages.',
        capacity_limit='Below the stated total does not guarantee legal node-level routing, low congestion, setup/hold/PW closure or physical margin.'),
    contract_effect=dict(
        active_variable='unchanged single C01 hard SLR2 Pblock; no RTL/IP/clock/interface/algorithm or property edits authorized by this assessment',
        current_violation_evidence='No direct evidence these two warnings changed the hard C01 Pblock, soft flags or declared source inputs; no new stop condition is established.',
        actual_candidate_landing='NOT_ESTABLISHED. Existing post-phase native membership, normalized P reconciliation, effective Pblock and actual LOC/SLR must prove all surviving/new resolved P lie in SLR2 with no unexplained missing, unknown, unplaced or outside objects.',
        required_existing_POST=['Current candidate compliance/locality and complete directed cut with bounded timing',
            'Fresh 80 protected boundaries, DONT_TOUCH and CE fanout checks for each natural place/physopt/route POST',
            'Global SLR utilization/crossing/congestion, clocks, timing setup/hold/PW, reset/CDC/IO/BRAM and DRC under unchanged acceptance',
            'Actual route status with no conflicting/unrouted signals and full reports before legal-route acceptance'],
        handling='Retain warnings in current results and compare completed same-stage full reports. Normal placement continues under existing authorization; no runtime query, message-limit change, new EDA, forced stop or new approval gate.'),
    no_EDA_DCP_process_signal_lock_control_production_edits=True,
    audit_program=identity(__file__))
output=OUT/'place_warning_contract_impact_review.json';save(output,result)
human=OUT/'place_warning_contract_impact_review.md'
with human.open('x') as stream:
    stream.write('# AT004 布局 warning 的合同影响\n\n'
                 'execution：只读核查完成；verdict：需纳入既有 POST/route 解释，未据此建立新增停点或合同违规；applicability：当前 floorplanning/PBP，place 与 POST 未完成；review：A007。\n\n'
                 '`Place 30-1229` 明确说明 partitioner 未能遵从部分 USER_SLL_REG。可见 100 个唯一对象均在 d0_mig_slice/ar15，均不属于 C01；工具随后抑制后续同类消息，总数和隐藏对象范围未知。原输入/约束字节保持与 placer 是否实际采用该属性是两件事：已审 9,525 对象策略快照覆盖候选及祖先，不包含这些 DDR 对象，也不记录 USER_SLL_REG 值；物理 XDC 和 175 约束来源文本未出现该字段，不等于嵌入网表无此属性。故不能把“策略保持通过”写成“DDR USER_SLL_REG 全部实际兑现”，也不能由该 warning 反推工程删除/软化了约束。\n\n'
                 '同阶段旧 E005 也显示 100 条后抑制，覆盖 ar15/aw15，可见对象交集 51；该轮 place 后来成功。它证明此类提示此前存在且曾非致命，不能证明本轮无影响，也不能比较被截断的受影响总量或归因于 C01。\n\n'
                 '`Place 30-356` 报整个设计的 SLR1→SLR2 需求 10,865/17,280（62.88%）。工具的 currently routable 是该阶段估计，并同时提示性能影响；不是候选专属开销、最终 SLL 用量、带宽或已合法布通。旧轮 10,594/17,280 指向 SLR0→SLR1，边界不同，不能相减作为改善/恶化或压力迁移证据。\n\n'
                 'C01 是否实际全部落入 SLR2，要等既有 POST 的实际 LOC/SLR、P 对应关系和有效 Pblock 核验；缺失、unknown、未放置或越界不能假通过。后续仍核当前阶段的 80 个保护边界、全局拥塞/跨区/时序/DRC/复位与 CDC，并以真实 route 状态验收合法布通。这些 warning 不增设独立属性硬门；正常流程按原合同继续，不改源码、约束或消费包。\n\n'
                 '[机器审核](place_warning_contract_impact_review.json) · [带原行号的冻结观察摘录](AT004_place_warning_observed_excerpt_20261017.json)\n')
print(json.dumps(dict(review=identity(output),human=identity(human),excerpt=identity(excerpt_path),visible_warning_overlap=result['ignored_USER_SLL_REG']['prior_same_stage']['visible_cell_overlap'],SLL_percent=current['SLL'][0]['ratio_percent']),ensure_ascii=False))
