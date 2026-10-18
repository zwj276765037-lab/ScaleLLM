"""A007 closed place timing report and fresh80 substep; no EDA/DCP."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        path=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if path.lower().endswith('.dcp'):raise RuntimeError('DCP content access forbidden')
sys.addaudithook(guard)
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib,csv,re,math,ast,tkinter

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
ATTEMPT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
def read(path):return json.loads(Path(path).read_text())
def identity(path):
    path=Path(path).resolve();assert path.suffix.lower()!='.dcp'
    a=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4194304),b''):h.update(block)
    b=path.stat();assert(a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns)
    return dict(path=str(path),bytes=b.st_size,sha256=h.hexdigest())
def bound_relative(row):
    actual=identity(ROOT/row['path']);assert actual['bytes']==row['bytes'] and actual['sha256']==row['sha256'];return actual
def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def tsv(path):
    with Path(path).open() as stream:return list(csv.DictReader(stream,delimiter='\t'))
def kv(path):return dict(line.split('=',1) for line in Path(path).read_text().splitlines())

facts_path=ATTEMPT/'place_full_timing_report_available_facts.json';facts=read(facts_path)
assert identity(facts_path)['sha256']=='290da28834f77fbed8fa8e8c7bf1c09e706d76132b0efa0f5cd4da70d9145fde'
clarification_path=ATTEMPT/'place_full_timing_report_observation_clarification.json';clarification=read(clarification_path)
assert bound_relative(clarification['original_derived_facts'])==identity(facts_path)
actual_id=bound_relative(facts['actual_timing_report']);old_id=bound_relative(facts['baseline_timing_report'])
assert actual_id['sha256']=='907192931f6d44d1c21ea66b76d069590283b9af14c350c353f737e99609d0b8'
global_review=read(OUT/'restored_pre_place_global_incremental_review.json')
accepted={row['path']:row for row in global_review['all_identity_checks']}
source=REPORT/'stage_sources/m002_physical_evidence.py';assert identity(source)==accepted[str(source)]
pure_names={'timing_metrics','timing_verdict','check_timing_counts'}
functions=[node for node in ast.parse(source.read_text()).body if isinstance(node,ast.FunctionDef) and node.name in pure_names]
assert {node.name for node in functions}==pure_names
namespace=dict(Path=Path,math=math,re=re)
exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),namespace)
metrics=namespace['timing_metrics'](Path(actual_id['path']));old_metrics=namespace['timing_metrics'](Path(old_id['path']))
assert metrics==facts['actual_timing_metrics'] and old_metrics==facts['baseline_timing_metrics']
assert namespace['timing_verdict'](metrics)==facts['actual_timing_verdict']=='FAIL'

def section(lines,name):
    start=lines.index('| '+name)
    end=next((i for i in range(start+2,len(lines)) if lines[i].startswith('| ') and not lines[i].startswith('| -')),len(lines))
    return lines[start:end]
def inspect_report(path,expected):
    lines=Path(path).read_text().splitlines()
    header={line[1:].split(':',1)[0].strip():line.split(':',1)[1].strip() for line in lines[:13] if line.startswith('|') and ':' in line}
    assert header['Design State']=='Fully Placed' and header['Design']=='scalellm_vcu118_f05_bd_wrapper' and header['Device']=='xcvu9p-flga2104'
    assert 'Vivado v.2025.2' in header['Tool Version'] and 'Build 6299465' in header['Tool Version']
    assert header['Command']=='report_timing_summary -delay_type min_max -report_unconstrained -file '+str(path)
    summary=section(lines,'Design Timing Summary')
    number_rows=[]
    for line in summary:
        if re.fullmatch(r'\s*[+-]?\d+(?:\.\d+)?(?:\s+[+-]?\d+(?:\.\d+)?){11}\s*',line):number_rows.append([float(x) for x in line.split()])
    assert len(number_rows)==1 and number_rows[0]==list(expected.values())
    assert 'Timing constraints are not met.' in summary
    per_group=[]
    for table in ['Intra Clock Table','Inter Clock Table','Other Path Groups Table']:
        block=section(lines,table);header_line=next(i for i,line in enumerate(block) if 'WNS(ns)' in line)
        for line in block[header_line+2:]:
            if not line.strip() or line.startswith('-'):continue
            matches=list(re.finditer(r'(?<!\S)[+-]?\d+(?:\.\d+)?(?!\S)',line))
            if not matches:continue
            values=[float(m[0]) for m in matches];name=line[:matches[0].start()].strip()
            names=['wns','tns','setup_failing','setup_total','whs','ths','hold_failing','hold_total','wpws','tpws','pw_failing','pw_total']
            if table=='Intra Clock Table' and len(values)==4:names=names[8:]
            elif len(values)==4:names=names[:4]
            else:names=names[:len(values)]
            assert len(values)==len(names) and len(values) in {4,8,12}
            per_group.append(dict(table=table,name=name,**dict(zip(names,values))))
    assert min(row['wns'] for row in per_group if 'wns' in row)==expected['wns']
    assert min(row['whs'] for row in per_group if 'whs' in row)==expected['whs']
    assert min(row['wpws'] for row in per_group if 'wpws' in row)==expected['wpws']
    for native,key in [('setup_failing','setup_failing_endpoints'),('hold_failing','hold_failing_endpoints'),('pw_failing','pw_skew_failing_endpoints')]:
        assert sum(row.get(native,0) for row in per_group)==expected[key]
    assert abs(sum(row.get('ths',0) for row in per_group)-expected['ths'])<=0.05
    clocks=[]
    for line in section(lines,'Clock Summary'):
        parts=re.split(r'\s{2,}',line.strip())
        if len(parts)==4 and parts[1].startswith('{'):
            clocks.append(dict(name=parts[0],waveform=parts[1],period_ns=float(parts[2]),frequency_MHz=float(parts[3])))
    assert len(clocks)==len({row['name'] for row in clocks})
    clockmap={row['name']:row for row in clocks}
    for name,period in [('clk_out1_scalellm_vcu118_f05_bd_clk_core_0',10.0),('mmcm_clkout0',5.0),('mmcm_clkout0_1',5.0)]:assert clockmap[name]['period_ns']==period
    return dict(header=header,metrics=expected,summary_line=lines.index('Timing constraints are not met.')+1,
        coverage=namespace['check_timing_counts'](Path(path)),
        settings=section(lines,'Timer Settings'),clocks=clocks,per_group=per_group,
        methodology_available=not any('No report available as report_methodology has not been run prior.' in line for line in lines),
        ignored_rows=sum(line.startswith('(none)') for line in section(lines,'User Ignored Path Table')),
        unconstrained_groups=sum(line.startswith('(none)') for line in section(lines,'Unconstrained Path Table')))

actual=inspect_report(Path(actual_id['path']),metrics);old=inspect_report(Path(old_id['path']),old_metrics)
assert actual['settings']==old['settings'] and actual['clocks']==old['clocks']
assert actual['coverage']==old['coverage']==global_review['fresh_live']['clock_coverage']
assert not actual['methodology_available']
delta={key:round(metrics[key]-old_metrics[key],6) for key in metrics}
for key,value in delta.items():assert math.isclose(value,facts['same_phase_metric_delta'][key],abs_tol=1e-6)

parent=read(REPORT/'recovery_parent.json');prior_report=Path(parent['source_report'])
structure_source=REPORT/'stage_sources/m002_optimized_structure.tcl';assert identity(structure_source)==accepted[str(structure_source)]
boundary_path=REPORT/'optimized_boundaries_place.tsv';boundaries=tsv(boundary_path)
old_boundaries=tsv(prior_report/'optimized_boundaries_place.tsv')
assert len(boundaries)==len({row['cell'] for row in boundaries})==80
counts=Counter(row['scope'] for row in boundaries);assert counts==dict(input=48,gate=16,down=16)
tcl=tkinter.Tcl()
def tdict(value):
    parts=tcl.splitlist(value);assert len(parts)%2==0
    return dict(zip(parts[::2],parts[1::2]))
stable=['scope','cell','REF_NAME','INIT','DONT_TOUCH','leaf_input_pins','load_REF_counts','load_pin_counts']
old_by_cell={row['cell']:row for row in old_boundaries}
load_placement=Counter();changed_driver=0;changed_load_layout=0
for row in boundaries:
    ref,width,load_ref={'input':('LUT6',256,'FDCE'),'gate':('LUT1',384,'FDRE'),'down':('LUT1',512,'FDRE')}[row['scope']]
    assert row['REF_NAME']==ref and row['DONT_TOUCH']=='1' and int(row['leaf_input_pins'])==width
    assert tdict(row['load_REF_counts'])=={load_ref:str(width)} and tdict(row['load_pin_counts'])=={'CE':str(width)}
    assert row['driver_LOC'].startswith('SLICE_X') and row['driver_BEL']
    loads={key:int(value) for key,value in tdict(row['load_SLR_counts']).items()}
    assert set(loads)<={'SLR0','SLR1','SLR2'} and sum(loads.values())==width
    bounds=[int(x) for x in tcl.splitlist(row['load_slice_XY_bounds'])]
    assert len(bounds)==4 and bounds[0]<=bounds[2] and bounds[1]<=bounds[3]
    for slr,count in loads.items():load_placement[(row['scope'],slr)]+=count
    assert {key:row[key] for key in stable}=={key:old_by_cell[row['cell']][key] for key in stable}
    changed_driver+=(row['driver_LOC'],row['driver_BEL'])!=(old_by_cell[row['cell']]['driver_LOC'],old_by_cell[row['cell']]['driver_BEL'])
    changed_load_layout+=(row['load_SLR_counts'],row['load_slice_XY_bounds'])!=(old_by_cell[row['cell']]['load_SLR_counts'],old_by_cell[row['cell']]['load_slice_XY_bounds'])
control_path=REPORT/'optimized_control_sources_place.tsv';controls=tsv(control_path)
assert len(controls)==len({row['net'] for row in controls})==14
for row in controls:
    assert int(row['leaf_input_pins'])>0 and row['drivers'] and row['driver_LOCs']
    assert sum(int(value) for value in tdict(row['load_pin_counts']).values())==int(row['leaf_input_pins'])
    assert len(tcl.splitlist(row['drivers']))==len(tcl.splitlist(row['driver_LOCs']))
native_result=kv(REPORT/'optimized_structure_place_result.txt')
assert native_result==dict(phase='place',issues='',boundary_contract='48input_16gate_16down',physical_signoff='false')
with (REPORT/'vivado.log').open('rb') as stream:
    prefix_size=(REPORT/'vivado.log').stat().st_size;prefix=stream.read(prefix_size)
loglines=prefix.decode().splitlines()
markers=[dict(line=i+1,text=line) for i,line in enumerate(loglines) if line.startswith('E005_OPTIMIZED_STRUCTURE_COMPLETED place')]
assert len(markers)==1 and markers[0]['text']=='E005_OPTIMIZED_STRUCTURE_COMPLETED place 48/16/16 boundary CE graphs'
success=[i+1 for i,line in enumerate(loglines) if line=='place_design completed successfully'];assert len(success)==1 and success[0]<markers[0]['line']
observed_status={name:(REPORT/name).read_text() if (REPORT/name).is_file() else 'NOT_PRESENT_AT_OBSERVATION' for name in ['place_result.txt','candidate_phase_place_status.txt']}

timing_output=OUT/'place_full_timing_report_review.json'
save(timing_output,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='completed_closed_native_full_place_timing_report_review',
    verdict='FAIL_TIMING_DUE_TO_HOLD; SETUP_SUMMARY_PASS_AND_REPORTED_PW_SKEW_SUMMARY_ZERO_FAILURES',
    applicability='AT004 Fully Placed graph; no routed timing signoff or full POST/locality acceptance',review='accepted_actual_report_and_mixed_same_phase_comparison',
    actual_report=actual_id,baseline_report=old_id,engineering_facts=identity(facts_path),observation_clarification=identity(clarification_path),
    current=actual,baseline=old,same_phase_delta=delta,clock_periods_and_timer_settings_equal=True,
    scope_limits=['Global report_timing_summary min_max/report_unconstrained, not a listing of every path or proof all interfaces are constrained.',
        'Internal no_clock/constant/PW-clock/unconstrained counts zero; external input1/output2 without delay and six unconstrained clock groups remain explicit. Formal reset/CDC/IO OPEN.',
        'WPWS/TPWS zero refers to this report summary; report_methodology not run and separate POST safety/DRC/PW/skew checks are not accepted by this substep.',
        'Better WNS/WHS/THS together with 3157 more hold-failing endpoints is mixed. Endpoint totals changed by 11 and PW/skew total by59; no uniform improvement or C01 causality claim.',
        'Sum of per-group endpoint totals is not used as a global unique endpoint count. Minima/failing counts were cross-checked against groups; totals use the native global row.',
        'No new EDA or DCP read/hash. Old DRC-now-running phrase was corrected as stale narration; report identity and numbers stay unchanged.'],
    parser_source=identity(source),reviewer_parser_correction=dict(original_program=identity(OUT/'audit_place_timing_and_fresh80.py'),note='V1 numeric-row regex admitted the dash separator and failed before outputs; V2 requires digits. Native evidence unchanged; not an EDA or design failure.'),audit_program=identity(__file__)))

structure_output=OUT/'place_fresh80_structure_review.json'
save(structure_output,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='completed_fresh_current_place_80_boundary_and_control_source_text_review',
    verdict='ACCEPT_CURRENT_PLACE_80_PROTECTED_BOUNDARY_SUBSTEP',applicability='AT004 place native POST structure substep only; full POST/locality/route remain separate',review='accepted_no_new_gate',
    actual_artifacts=[identity(boundary_path),identity(control_path),identity(REPORT/'optimized_structure_place_result.txt')],
    native_collector=identity(structure_source),native_closed_marker=markers[0],observed_log_prefix_bytes=prefix_size,
    observed_log_prefix_sha256=hashlib.sha256(prefix).hexdigest(),log_scope='Observed prefix and exact closed marker; no immutable whole-live-log claim',
    boundary_counts=dict(counts),all80_DONT_TOUCH_1=True,all80_REF_INIT_and_payload_CE_contracts_equal_previous_accepted_place=True,
    exact_widths=dict(input=256,gate=384,down=512),all_current_driver_locations_and_BEL_nonempty=True,all_payload_SLR_and_bounds_resolved=True,
    current_payload_pin_counts_by_scope_and_SLR=[dict(scope=scope,SLR=slr,load_pins=count) for (scope,slr),count in sorted(load_placement.items())],
    physical_changes_from_old=dict(driver_LOC_or_BEL_changed=changed_driver,load_SLR_counts_or_bounds_changed=changed_load_layout,interpretation='Observed placement differences only, not candidate causality or congestion/timing improvement'),
    control_source_rows=14,control_source_unique_nets=True,control_source_terminal_totals_and_driver_location_vectors_consistent=True,
    native_result=native_result,observed_post_status=observed_status,
    inherited_comparison=identity(prior_report/'optimized_boundaries_place.tsv'),
    limits=['Fresh AT004 actual table, not reuse of the inherited pre_place 80-boundary claim.',
        'These are the 48 input +16 gate +16 down protected boundaries, not the full C01 normalized P/locality population.',
        'Does not close complete reset/CDC/BRAM/DRC/timing or candidate reconciliation/compliance. Later physopt/route require their own fresh80 evidence.',
        'No EDA/DCP/process/lock/production operations.'],audit_program=identity(__file__)))
human=OUT/'place_timing_and_fresh80_review.md'
with human.open('x') as stream:
    stream.write('# AT004 place 完整时序与 fresh80 子步骤审核\n\n'
                 '本轮全局 place 时序 **未通过，原因是 hold**。Fully Placed 原生报告及完整摘要重放一致：WNS +0.147 ns / TNS 0 / setup 违例端点 0；WHS −0.562 ns / THS −1879.853 ns / hold 违例端点 34,042。该报告 WPWS/TPWS 与 PW-skew 违例数为 0。\n\n'
                 '相同阶段旧 E005 为 WNS +0.103、WHS −0.695、THS −2145.408、hold 违例端点 30,885。本轮 worst slack 和累计 hold slack较好，但 hold 违例端点增加 3,157；setup/hold 总端点增加 11，PW-skew 总端点增加 59。变化混合，不判整体改善或 C01 因果。timer settings、时钟表及 core100MHz/双DDR UI200MHz保持一致。\n\n'
                 '内部 no_clock/constant/PW-clock/unconstrained 为 0，外部 input1/output2 无delay及 6 项 unconstrained clock groups 保留；report_methodology 未运行的声明仍在。完整时序摘要不是所有接口约束、安全或 routed timing 签核，工程原“DRC now running”已用独立澄清记录标明为旧观察措辞，时序身份和数值未改。\n\n'
                 '本轮 **fresh80 结构子步骤通过**：80 个唯一保护边界为 input48/gate16/down16，DONT_TOUCH全1，LUT类型/INIT/CE负载宽度256/384/512与已审合同一致；所有driver LOC/BEL与负载SLR/范围均有实际值。14条control-source原始行及闭合结果/原生日志marker已核。此处是本轮新测，不再只是pre-place继承证据。\n\n'
                 '完整POST、候选P对应关系/SLR2落区和后续physopt/route仍须各自真实验收；本记录不替代这些门，也不新增审批或EDA。\n\n'
                 '[完整时序审核](place_full_timing_report_review.json) · [fresh80结构审核](place_fresh80_structure_review.json)\n')
print(json.dumps(dict(timing_review=identity(timing_output),structure_review=identity(structure_output),human=identity(human),metrics=metrics,structure_counts=dict(counts),physical_change_rows=dict(driver=changed_driver,loads=changed_load_layout)),ensure_ascii=False))
