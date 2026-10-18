#!/usr/bin/env python3
"""A007 actual outer physopt command and fresh full timing substeps only."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import ast,hashlib,json,math,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
checks={}
def require(c,m):assert c,m
def identity(p):
    p=Path(p).resolve();assert p.suffix.lower()!='.dcp';before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def read(p):return json.loads(Path(p).read_text())
def verify(v):
    x=identity(v['path']);assert x['bytes']==v['bytes'] and x['sha256']==v['sha256'];return x
def kv(p):return dict(l.split('=',1) for l in Path(p).read_text().splitlines() if '=' in l)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
facts_paths={
 'command':('physopt_command_zero_POST_pending_facts.json','6436c5b756e8e964c641b98f5ddfbfdde9276bf58555b343dc957e0c495c3db5'),
 'timing':('physopt_full_timing_report_available_facts.json','1e3e084d80e26f61865035f938cb88e2e73fb651bdb149f6a388d38d5d39b6d4'),
 'checkpoint':('physopt_checkpoint_saved_identity.json','035af7694e0b8520a85fc163b0a7b96d238d19cc22a2e726bf8069f77b00b0cd')}
facts={};facts_ids={}
for key,(name,digest) in facts_paths.items():
    facts_ids[key]=identity(AT/name);assert facts_ids[key]['sha256']==digest;facts[key]=read(AT/name)
command=kv(RPT/'physopt_command_result.txt');verify(facts['command']['receipt_identity'])
assert command==facts['command']['actual_command_receipt']==dict(phase='physopt',command='phys_opt_design -directive Default',started_epoch='1792243426',ended_epoch='1792243575',native_tcl_code='0')
assert int(command['ended_epoch'])-int(command['started_epoch'])==facts['command']['duration_seconds']==149
assert facts['command']['native_declares_netlist_unmodified'] is True
prior_combined=identity(OUT/'place_combined_stage_review.json')
assert prior_combined['sha256']=='d360c153a9f8d97d12398394cc0538fa24fefc13c6e97feed5e7285e73f0f362'
assert read(prior_combined['path'])['actual_status_receipt']['ended_epoch']==command['started_epoch']
prior_path=OUT/'place_full_timing_report_review.json';priorid=identity(prior_path)
assert priorid['sha256']=='386dced9df9391fb485a45d1f0847247683f7afb4e3910a4563eecc3861219b4'
prior=read(prior_path);verify(prior['actual_report'])
actual_id=verify(facts['timing']['actual_timing_report'])
assert actual_id['bytes']==2399433 and actual_id['sha256']=='1d54a07e4bc74ecd4c1d078f751f851e4669ede28ccbef865475556a796ca5f4'
source=RPT/'stage_sources/m002_physical_evidence.py';assert identity(source)==prior['parser_source']
selected={'timing_metrics','timing_verdict','check_timing_counts'}
body=[n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in selected];assert {n.name for n in body}==selected
namespace=dict(Path=Path,math=math,re=re,require=require)
exec(compile(ast.Module(body=body,type_ignores=[]),str(source),'exec'),namespace)
metrics=namespace['timing_metrics'](Path(actual_id['path']))
assert metrics==facts['timing']['actual_current_physopt_timing']==prior['current']['metrics']
assert facts['timing']['equal_to_actual_place_metrics'] is True
assert namespace['timing_verdict'](metrics)==facts['timing']['timing_verdict']=='FAIL'

# Reuse the independently accepted full report/group checker. Only expected
# native Design State is changed from Fully Placed to Physopt postPlace.
audit_source=Path(prior['audit_program']['path']);verify(prior['audit_program'])
audit_text=audit_source.read_text();audit_ast=ast.parse(audit_text)
selected_nodes=[n for n in audit_ast.body if isinstance(n,ast.FunctionDef) and n.name in {'section','inspect_report'}]
assert len(selected_nodes)==2
parsed_functions='\n\n'.join(ast.get_source_segment(audit_text,n) for n in selected_nodes)
assert parsed_functions.count("header['Design State']=='Fully Placed'")==1
parsed_functions=parsed_functions.replace("header['Design State']=='Fully Placed'","header['Design State']=='Physopt postPlace'")
review_ns=dict(Path=Path,re=re,namespace=namespace)
exec(compile(parsed_functions,str(audit_source)+'[physopt expected state]','exec'),review_ns)
actual=review_ns['inspect_report'](Path(actual_id['path']),metrics)
assert {k:v for k,v in actual.items() if k!='header'}=={k:v for k,v in prior['current'].items() if k!='header'}
assert {k:v for k,v in actual['header'].items() if k not in {'Date','Command','Design State'}}=={k:v for k,v in prior['current']['header'].items() if k not in {'Date','Command','Design State'}}
old_lines=Path(prior['actual_report']['path']).read_text().splitlines();new_lines=Path(actual_id['path']).read_text().splitlines()
assert new_lines[13:]==old_lines[13:]
differences=[dict(line=i+1,place=a,physopt=b) for i,(a,b) in enumerate(zip(old_lines,new_lines)) if a!=b]
assert len(old_lines)==len(new_lines) and [r['line'] for r in differences]==[2,4,6,10,12]
assert not actual['methodology_available'] and actual['unconstrained_groups']==6
groups=dict(Counter(r['table'] for r in actual['per_group']));assert groups=={'Intra Clock Table':42,'Inter Clock Table':20,'Other Path Groups Table':17}
stamp=datetime.strptime(actual['header']['Date'],'%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone(timedelta(hours=8)))
assert int(stamp.timestamp())>int(command['ended_epoch'])

# Frozen command excerpt must match actual native lines; checkpoint content forbidden.
saved=facts['checkpoint'];dcp=saved['actual_checkpoint'];dcppath=ROOT/dcp['path']
assert dcppath.name=='physopt.dcp' and dcppath.stat().st_size==dcp['bytes']==580691314
assert saved['command_code']==0
log=[];capture=False;command_excerpt=[];checkpoint_line=None
with (RPT/'vivado.log').open() as f:
    for number,line in enumerate(f,1):
        if line.startswith('Command: phys_opt_design -directive Default'):capture=True
        if capture:
            log.append(dict(line=number,text=line.removesuffix('\n')))
            if not command_excerpt:pass
        if capture and line.startswith('phys_opt_design: Time (s):'):
            command_excerpt=list(log)
        if saved['actual_native_checkpoint_generated_message'] in line:
            checkpoint_line=dict(line=number,text=line.removesuffix('\n'));break
assert command_excerpt and checkpoint_line
assert '\n'.join(r['text'] for r in command_excerpt)==facts['command']['actual_native_closed_command_excerpt']
assert checkpoint_line['text']=='INFO: [Common 17-1381] '+saved['actual_native_checkpoint_generated_message']
assert command_excerpt[-1]['line']<checkpoint_line['line']
assert any(r['text']=='phys_opt_design completed successfully' for r in command_excerpt)
assert any('All physical synthesis setup optimizations will be skipped.' in r['text'] for r in command_excerpt)
assert any('No setup violation found. The netlist was not modified.' in r['text'] for r in command_excerpt)
snapshot=OUT/'physopt_command_and_saved_checkpoint_native_excerpt.json'
save(snapshot,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),source=str(RPT/'vivado.log'),scope='Closed command and checkpoint generated message only; no whole growing log identity',command_lines=command_excerpt,saved_checkpoint_line=checkpoint_line))
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_ACTUAL_OUTER_PHYSOPT_COMMAND_AND_FRESH_FULL_TIMING_SUBSTEP_REVIEW',
    verdict='ACCEPT_NATIVE_COMMAND_ZERO_AND_CURRENT_FULL_REPORT; GLOBAL_TIMING_FAIL_DUE_TO_HOLD',
    applicability='AT004 actual Physopt postPlace graph and outer Default command; complete physopt POST/fresh80/locality/route not accepted by this substep',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',
    actual_command=command,command_duration_seconds=149,command_end_utc=datetime.fromtimestamp(int(command['ended_epoch']),timezone.utc).isoformat(),native_setup_optimizations_skipped=True,native_netlist_unmodified_statement=True,
    engineering_facts=facts_ids,accepted_place_combined=prior_combined,accepted_place_timing=priorid,actual_report=actual_id,current=actual,
    all12_summary_metrics_equal_actual_place=True,all_report_body_lines_after_header_equal_actual_place=True,only_report_differences=differences,table_group_counts=groups,
    parser_source=identity(source),accepted_full_report_checker=identity(audit_source),checker_adaptation='Expected Design State only: Fully Placed -> Physopt postPlace; identical metric/group/clock/coverage validation',
    saved_DCP_engineering_identity=dcp,saved_DCP_metadata_size=dcppath.stat().st_size,DCP_sha_attributed_to='A006 saved checkpoint identity record',reviewer_DCP_read_or_hash=False,native_closed_excerpt=identity(snapshot),
    interpretation='Native command succeeded but skipped setup optimization with WNS>=0. Fresh full timing body unchanged; hold failure remains. Native netlist-unmodified does not claim DCP byte identity or completed POST/locality.',
    scope_limits=['WNS +0.147/TNS0/setup failing0; WHS -0.562/THS -1879.853/hold failing34042; timing FAIL remains.',
      'No global hold repair, routed timing or congestion improvement inferred from command return0.',
      'Same 50 clocks/timer settings, internal clock coverage; external input1/output2 delay gaps,6 unconstrained groups and report_methodology not run remain.',
      'PW/skew summary zero failures does not establish formal reset/CDC/IO safety; formal safety remains OPEN.',
      'Actual native command+full timing substeps only; complete fresh physopt POST,80-protections and candidate locality require their own real closure.',
      'No native queries/EDA, DCP content read/hash, process/lock control, production/consumed-package edits or new gate/agent.'],
    reviewer_harness_correction=dict(failed_v1=identity(OUT/'audit_physopt_command_and_full_timing.py'),reason='V1 stripped native trailing space on estimated timing line with rstrip; v2 removes newline only and preserves exact evidence. Native data unchanged, not EDA/design failure.'),all_identity_checks=list(checks.values()),audit_program=identity(__file__))
output=OUT/'physopt_command_and_full_timing_review.json';save(output,result)
human=OUT/'physopt_command_and_full_timing_review.md'
with human.open('x') as f:f.write('''# AT004 outer physopt命令与新完整时序子步骤审核

execution：实际原生命令及新完整时序证据独立核验完成。verdict：接受命令native0与当前报告；全局时序仍因hold FAIL。applicability：AT004 Physopt postPlace图，完整physopt POST/fresh80/locality另审。review：独立子步骤接受，无新增停点。

phys_opt_design -directive Default实际149秒、13:26:15Z返回0。原生明确WNS≥0跳过全部setup物理综合优化，netlist未修改；命令、许可、结束文本与工程excerpt精确一致。physopt.dcp保存文本与580,691,314字节元数据已核；SHA仅引用A006身份记录，未读取或哈希DCP。

新timing_physopt.rpt为Physopt postPlace、min_max/report_unconstrained，12列指标及页眉后全部正文与实际place报告相同。独立复核42 intra/20 inter/17 other组表、50时钟与timer settings；setup WNS+0.147ns、TNS0、违例0，但hold WHS−0.562ns、THS−1879.853ns、违例34,042，时序仍FAIL。PW/skew摘要违例0。

报告仅日期、命令输出路径、阶段及页眉横线变化；没有hold修复或物理收益证据。外部input1/output2未设delay、6组unconstrained、report_methodology未运行及正式reset/CDC/IO OPEN保持。命令成功/新时序报告不等于完整physopt POST/locality通过，也不声称route成功。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),metrics=metrics,body_identical=True,design_state=actual['header']['Design State']),ensure_ascii=False))
