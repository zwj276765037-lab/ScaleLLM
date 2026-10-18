#!/usr/bin/env python3
"""A007 bounded native-text review of initial route warnings; no EDA or DCP access."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).resolve().parent
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
OLD=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route'
checks={}
def ident(p):
    p=Path(p).resolve();assert p.suffix.lower()!='.dcp';a=p.stat();h=hashlib.sha256(p.read_bytes()).hexdigest();b=p.stat()
    assert (a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns)
    d=dict(path=str(p),bytes=b.st_size,sha256=h);checks[str(p)]=d;return d
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def line_range(p,first,last):
    out=[]
    with p.open() as f:
        for n,l in enumerate(f,1):
            if first<=n<=last:out.append(l)
            if n==last:break
    assert len(out)==last-first+1
    return ''.join(out)
factpath=AT/'route_initial_global_warnings_observed_facts.json';factid=ident(factpath)
assert factid['bytes']==3371 and factid['sha256'].startswith('b3cd15ae')
facts=read(factpath);excerptpath=ROOT/facts['native_excerpt']['path'];excerptid=ident(excerptpath)
assert {k:excerptid[k] for k in ['bytes','sha256']}=={k:facts['native_excerpt'][k] for k in ['bytes','sha256']}
assert excerptid['bytes']==5399 and excerptid['sha256']=='9696cc377b923b596891c8ef908583fd56145033ad4998beb76ceab4e0287cc7'
current=excerptpath.read_text();first=facts['native_excerpt_first_line'];last=facts['native_excerpt_last_line']
assert (first,last)==(254216,254289) and line_range(ROOT/facts['live_native_log'],first,last)==current
assert facts['route_terminal'] is False
oldid=ident(OLD/'vivado.log');oldall=(OLD/'vivado.log').read_text()
oldfirst=168;oldlast=234;old=line_range(OLD/'vivado.log',oldfirst,oldlast)
oldexcerpt=OUT/'E005_route_initial_warning_comparison_excerpt.json'
save(oldexcerpt,dict(source=oldid,first_line=oldfirst,last_line=oldlast,text=old))
current_header=line_range(RPT/'vivado.log',1,8)
for txt in [oldall,current_header]:
    assert 'Vivado v2025.2 (64-bit)' in txt and 'SW Build 6299465' in txt
assert "Loading part xcvu9p-flga2104-2L-e" in oldall
assert 'Command: route_design -directive Default' in oldall and 'using a maximum of 8 CPUs' in oldall
route_start=read(OUT/'physopt_combined_stage_review.json');route_startid=ident(OUT/'physopt_combined_stage_review.json')
assert route_startid['sha256']=='205b56d13bcccd61490888629aef8f2c31bae2e3962c94504fabb58893342505'
assert route_start['actual_route_start']['native_command']['text']=='Command: route_design -directive Default'

# Native estimate tables occur twice, in Phase 3 and Phase 3.1; these are repeated snapshots.
slr={}
for lower,upper,cells,total,avail,pct in re.findall(r'  SLR \[(\d)-(\d)\](.*?)\s+Demand: (\d+) Available: (\d+) Utilization\(%\): ([\d.]+)',current):
    parsed=[(int(a),int(b)) for a,b in re.findall(r'(\d+) \(\s*(\d+)%\)',cells)]
    assert len(parsed)==12
    key=f'SLR{lower}_to_{upper}'
    row=dict(column_order=[a for a,b in parsed],native_rounded_percent=[b for a,b in parsed],total=int(total),available=int(avail),reported_utilization_percent=float(pct))
    assert sum(row['column_order'])==row['total'] and row['available']==12*1440
    assert abs(row['total']/row['available']*100-row['reported_utilization_percent'])<.005
    assert {k:row[k] for k in facts['estimated_SLL_demands'][key]}==facts['estimated_SLL_demands'][key]
    if key in slr:assert slr[key]['native_estimate']==row;slr[key]['identical_native_occurrences']+=1
    else:
        over=[dict(table_column_ordinal_1_based=i,demand=v,excess=v-1440,percent=100*v/1440) for i,v in enumerate(row['column_order'],1) if v>1440]
        slr[key]=dict(native_estimate=row,identical_native_occurrences=1,over_capacity_columns=over,excess_sum=sum(v['excess'] for v in over),maximum=max(row['column_order']),aggregate_headroom=int(avail)-int(total))
assert set(slr)=={'SLR1_to_2','SLR0_to_1'} and all(v['identical_native_occurrences']==2 for v in slr.values())
assert [(len(slr[k]['over_capacity_columns']),slr[k]['excess_sum']) for k in ['SLR1_to_2','SLR0_to_1']]==[(2,313),(4,2233)]
assert current.count('[Route 35-3311]')==2 and 'Estimated SLL Demand Per Column' not in oldall and '[Route 35-3311]' not in oldall

def warnings(txt,line_offset):
    failed=[];ignored=[]
    for m in re.finditer(r'WARNING: \[Route 35-462\] Failed to populate (\d+) paths in bus skew group \(internal name : (grp_\d+)\)\. These paths are:\n((?:\t[^\n]+\n)+)',txt):
        pins=m[3].splitlines();pins=[p.strip() for p in pins];assert len(pins)==int(m[1])
        failed.append(dict(native_line=line_offset+txt.count('\n',0,m.start()),group=m[2],count=int(m[1]),destination_pins=pins))
    for m in re.finditer(r'WARNING: \[Route 35-470\] Driver (\S+) is being shared with (\d+) other bits in the bus skew group\. The bus skew group will be ignored\.',txt):
        ignored.append(dict(native_line=line_offset+txt.count('\n',0,m.start()),driver_pin=m[1],other_bits=int(m[2]),native_group_ID='NOT_PRINTED'))
    return dict(failed_to_populate=failed,ignored_groups=ignored)
cw=warnings(current,first);ow=warnings(old,oldfirst)
assert {r['group']:r['count'] for r in cw['failed_to_populate']}==facts['bus_skew_warnings']['Route35_462']=={'grp_84':2,'grp_85':2,'grp_86':2}
assert len(cw['ignored_groups'])==1 and cw['ignored_groups'][0]['other_bits']==2
assert len(ow['failed_to_populate'])==2 and len(ow['ignored_groups'])==2
assert {r['group']:r['destination_pins'] for r in ow['failed_to_populate']}=={r['group']:r['destination_pins'] for r in cw['failed_to_populate'] if r['group'] in {'grp_85','grp_86'}}
assert cw['ignored_groups'][0]['driver_pin']==ow['ignored_groups'][1]['driver_pin']
assert ow['ignored_groups'][0]['driver_pin'].rsplit('/',1)[0].rsplit('/',1)[0]==cw['failed_to_populate'][0]['destination_pins'][0].rsplit('/',2)[0]

# Match explicit warned cells to named prior report constraint sets, never infer internal IDs arithmetically.
globalid=ident(OUT/'physopt_global_POST_review.json');assert globalid['sha256']=='e5dacc52b15e8e7a55d488bf4b110b1c73e630639d5612884ef97052b1b6a600'
glob=read(globalid['path']);busid=ident(RPT/'bus_skew_physopt.rpt')
assert busid==next(v for v in glob['all_identity_checks'] if v['path']==busid['path'])
bus=(RPT/'bus_skew_physopt.rpt').read_text();assert '| Design State      : Physopt postPlace' in bus
begin=bus.index('Id  Position');end=bus.index('2. Bus Skew Report Per Constraint',begin);summary=bus[begin:end]
constraints={}
for part in re.split(r'(?m)^(?=\d+\s+\d+\s+\[get_cells)',summary):
    match=re.match(r'^(\d+)\s+(\d+)\s+',part)
    if not match:continue
    lists=re.findall(r'\[get_cells \[list (.*?)\]\]',part,re.S);assert len(lists)==2
    sets=[re.findall(r'\{([^{}]+)\}',v) for v in lists]
    numeric=re.findall(r'^\s+(Slow|Fast)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s*$',part,re.M);assert len(numeric)==1
    constraints[int(match[1])]=dict(report_ID=int(match[1]),position=int(match[2]),from_cells=sets[0],to_cells=sets[1],requirement_ns=float(numeric[0][1]),actual_ns=float(numeric[0][2]),slack_ns=float(numeric[0][3]))
assert len(constraints)==glob['bus_skew']['constraints']==94 and min(v['slack_ns'] for v in constraints.values())==3.262
matches=[]
for warning in cw['failed_to_populate']:
    cells=[p.removesuffix('/D') for p in warning['destination_pins']]
    matching=[v for v in constraints.values() if all(c in v['to_cells'] for c in cells)];assert len(matching)==1
    v=matching[0]
    matches.append(dict(warning_type='35-462',warning_native_group=warning['group'],matched_by='all exact warned destination cells in the named report To set',report_ID=v['report_ID'],position=v['position'],requirement_ns=v['requirement_ns'],prior_report_slack_ns=v['slack_ns'],from_cell_count=len(v['from_cells']),to_cell_count=len(v['to_cells']),warning_cells=cells))
for warning in cw['ignored_groups']:
    cell=warning['driver_pin'].removesuffix('/Q');matching=[v for v in constraints.values() if cell in v['from_cells']];assert len(matching)==1
    v=matching[0]
    matches.append(dict(warning_type='35-470',warning_native_group='NOT_PRINTED',matched_by='exact shared-driver cell in one named report From set; native ignored-group ID not inferred',report_ID=v['report_ID'],position=v['position'],requirement_ns=v['requirement_ns'],prior_report_slack_ns=v['slack_ns'],from_cell_count=len(v['from_cells']),to_cell_count=len(v['to_cells']),warning_cells=[cell]))
assert [v['report_ID'] for v in matches]==[85,86,87,88]

def initialization(txt):
    names={'Failed Nets':'failed_nets','Unrouted Nets':'unrouted_nets','Partially Routed Nets':'partially_routed_nets','Node Overlaps':'node_overlaps'}
    vals={v:int(re.search(r'Number of '+k+r'\s*=\s*(\d+)',txt)[1]) for k,v in names.items()}
    assert vals['failed_nets']==vals['unrouted_nets']+vals['partially_routed_nets'];return vals
def timing(txt):
    return [dict(zip(['wns','tns','whs','ths'],map(float,m))) for m in re.findall(r'Intermediate Timing Summary \| WNS=([\d.-]+)\s*\| TNS=([\d.-]+)\s*\| WHS=([\d.-]+)\s*\| THS=([\d.-]+)\|',txt)]
assert initialization(current)==facts['initialization_counts_not_final_failure']
assert timing(current)==list(facts['intermediate_timing_not_final'].values())
pin_current=int(re.search(r'At least (\d+) CLBs have high pin utilization',current)[1]);pin_old=int(re.search(r'At least (\d+) CLBs have high pin utilization',old)[1])
assert (pin_current,pin_old)==(135,804)
runs_current=re.findall(r'^\t\(\d+ \d+\) -> \(\d+ \d+\)\s+\[[^\n]+\]',current,re.M)
runs_old=re.findall(r'^\t\(\d+ \d+\) -> \(\d+ \d+\)\s+\[[^\n]+\]',old,re.M)
assert len(runs_current)==7 and len(runs_old)==10
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='READ_ONLY_NATIVE_TEXT_WARNING_REVIEW_COMPLETED; ROUTE_OBSERVATION_NONTERMINAL',verdict='LOCAL_SLL_OVERSUBSCRIPTION_AND_BUS_SKEW_OPTIMIZATION_COVERAGE_GAPS_CONFIRMED; ROUTE_OUTCOME_UNDETERMINED; FORMAL_RESET_CDC_IO_OPEN',applicability='AT004 route Phase2 initialization and Phase3/3.1 estimates at captured lines254216..254289; E005 R004 AT004 comparison restricted to matching Phase2 categories',review='INDEPENDENT_BOUNDED_REVIEW_COMPLETE_NO_NEW_GATE',engineering_facts=factid,current_excerpt=excerptid,current_excerpt_exact_live_log_lines_verified=[first,last],engineering_live_resource_process_fields='Attributed to engineering; not independently checked by this reviewer',old_log=oldid,old_excerpt=ident(oldexcerpt),same_tool_build_part_and_Default_router=True,current_SLL_estimates=slr,old_same_stage_SLL_estimate='NOT_PRESENT_IN_LOG; no quantitative old/new comparison and absence is not proof of zero demand',current_bus_skew_warnings=cw,old_bus_skew_warnings=ow,prior_physopt_bus_report=busid,prior_report_94_MET_retained_as_stage_scoped_fact=glob['bus_skew'],exact_warned_object_matches_to_prior_report=matches,bus_skew_comparison='grp85 and grp86 missing destinations repeat exactly; MLP command0 shared-driver ignored warning repeats exactly; attention command1 changed from old shared-driver ignored warning to current two missing destinations; no evidence that any affected CDC is now fully covered or safe',high_pin_CLB_observation=dict(current_at_least=135,old_at_least=804,reported_count_delta=-669,current_listed_runs=runs_current,old_listed_runs=runs_old,scope='Same Route35-445 stage/category, different placements and sites; not exact all-CLB count, fixed hotspot relief, C01 causality or routability proof'),initialization_counts=dict(current=initialization(current),old=initialization(old),scope='Both precede routing; neither failed-net count nor zero overlaps is a final legal routing verdict'),intermediate_timing=dict(current=timing(current),old=timing(old),scope='Phase2 intermediate estimated timing; not final timing, signoff or isolated optimization benefit'),interpretation=[
    'Per-column estimates are distinct from candidate cut logical pairs and final assigned SLL usage. Tables repeat between Phase3 and Phase3.1; do not sum them.',
    'SLR1-2 column ordinal8 is1445/1440 despite rounded100%; ordinal11 is1748/1440. SLR0-1 ordinals5,6,7,8 exceed1440, maximum2296/1440. Ordinals are display order, not inferred physical X coordinates.',
    'Route35-3311 says the router might not find a solution; it is evidence of risk, not a native terminal failure or permission to interrupt.',
    'Route35-462 records six paths not populated in router bus-skew groups. It does not by itself prove logical disconnection or CDC functional failure.',
    'Route35-470 explicitly says the shared-driver bus-skew group will be ignored. The ignored group ID is not printed; only its source-cell report-set match is established.',
    'A report constraint existing and showing MET at physopt does not establish that every intended path is populated/enforced during route. Preserve94 MET only as a current pre-route report fact; do not subtract warnings to invent a verified90/91-group count.',
    'Warnings are not an authorization to remove/relax constraints. Shared-driver cause, valid bit equivalence and handshake/CDC correctness require appropriate exact-object evidence; none is inferred here.'
],existing_final_validation_implications=[
    'After natural terminal, use actual current route status/timing/DRC and complete current bus-skew report under the existing contract; numeric MET alone must not silently erase these coverage warnings.',
    'Reconcile the six exact destination pins and shared source with actual resolved constraint object sets and current path/group coverage; separately state any ignored/unpopulated paths and unsupported safety conclusions.',
    'Formal reset/CDC/IO remains OPEN until its existing proof requirements are satisfied. Native route success alone does not close safety or constraint coverage.',
    'No new pause, wait, retry or approval gate; normal same-C01 route continues naturally under existing authorization.'
],all_identity_checks=list(checks.values()),audit_program=ident(__file__),limits='No EDA/native query, DCP content access/hash, process/lock control, source/constraint changes or engineering evidence writes. Observation is frozen, not ongoing monitoring.')
output=OUT/'route_initial_global_warnings_review.json';save(output,out)
human=OUT/'route_initial_global_warnings_review.md'
with human.open('x') as f:f.write('''# AT004 route 中途警告独立审核

execution：已完成只读原文核对；观察位于 route 初始化及 Phase 3/3.1，属于非终态。verdict：确认列局部 SLL 超额与 bus-skew 路由优化覆盖缺口，route 成败未定，正式 reset/CDC/IO 安全保持 OPEN。review：独立有界审核完成，不新增停点。

工程 facts 和 74 行原生片段已校验身份，并与实际 vivado.log 第 254216–254289 行逐字一致。

| SLR 边界 | 总估计需求/容量 | 超容量列数 | 最大列需求/1440 |
| --- | ---: | ---: | ---: |
| 1–2 | 11,721/17,280（67.83%） | 2 | 1,748（121%） |
| 0–1 | 12,180/17,280（70.49%） | 4 | 2,296（159%） |

SLR1–2 另一列为 1,445/1,440，原生日志四舍五入显示 100%，仍已超额。总余量不能抵消列局部需求；两次表格是 Phase 3 与 3.1 的重复估计，不相加，也不等同候选 cut pair、最终已分配 SLL 或带宽。Route 35-3311 表示可能无法找到布线解，尚不是失败终态。

Route 35-462 明确列出 6 条未 populate 的目的路径：attention command1 的 bit14/16（grp84）、attention command0 的 bit14/16（grp85）、MLP command1 的 bit16/15（grp86）。Route 35-470 明确说 MLP command0 的 src_hsdata_ff_reg[16]/Q 与另外 2 bits 共享，相关 bus-skew 组将被忽略；日志未打印该组 ID。

按对象名核对，前三组的目的 cells 分别属于 physopt 报告约束 ID85/86/87，忽略警告的源 cell 属于 ID88；对应 requirement 均为 10 ns，之前报告 slack 为 +8.877/+9.292/+9.411/+9.469 ns。内部 grp 编号和报告 ID 不按数字猜映射，第四项只确认源对象集合匹配。既有 94 项 MET 仍是此前 physopt 报告事实，不能证明 route 中所有路径均被纳入优化，也不能换算成“剩余若干组已完整覆盖”。警告本身不证明断连或 CDC 功能失效，但覆盖缺口不能被 MET 数字掩盖。

旧 E005 R004/AT004 同为 Vivado 2025.2 build6299465、同器件、Default router、8 CPUs。grp85/86 的 4 条缺失目的路径和 MLP command0 忽略警告逐项相同；attention command1 旧为共享驱动导致整组忽略，本次变成 2 条路径未 populate，不能据此认定已经修复。旧 route 日志未出现同阶段 SLL 需求表或 35-3311，无法作跨轮 SLL 数值改善比较，缺少警告也不证明旧需求为零。

同阶段 35-445 的高 pin CLB 报告下界为旧 804、本次 135，分别列出 10/7 段。仅可报告该类别数字减少 669；位置和全局布局不同，尚不能据此证明固定热点改善、C01 因果收益或已可布通。

初始化的 2,031,260 failed nets = 1,827,047 unrouted + 204,213 partially routed，node overlaps=0；旧初始化也有 2,031,299 failed nets 和 0 overlaps。这些都不是最终合法性结论。中间 WNS +0.181 ns、WHS −0.562 ns 等同样不作最终时序验收。

按现有合同继续正常 route。自然终态后，现行最终验证须结合实际 route status/timing/DRC、bus-skew 报告和上述精确对象覆盖核对，保留 ignored/unpopulated 差异；不能删除或放松约束来消除警告，也不能仅以 route 命令成功关闭正式安全 OPEN。本审核不新增停点或批准门。

详细对象、原文行号、身份与比较范围见 [JSON 审核记录](route_initial_global_warnings_review.json)。
''')
print(json.dumps(dict(review=ident(output),human=ident(human),facts=factid,SLL_over_columns={k:len(v['over_capacity_columns']) for k,v in slr.items()},report_matches=matches),ensure_ascii=False))
