#!/usr/bin/env python3
"""A007 fresh native physopt 80-boundary substep, no EDA or DCP content."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import csv,hashlib,json,tkinter
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
checks={}
def identity(path):
    p=Path(path).resolve();assert p.suffix.lower()!='.dcp';before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f,delimiter='\t'))
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
priorpath=OUT/'place_fresh80_structure_review.json';priorid=identity(priorpath)
assert priorid['sha256']=='6d65874583f952cbb619f6cc865da1433c8108af117cd80618b293e4c0c2834a'
prior=read(priorpath)
timingpath=OUT/'physopt_command_and_full_timing_review.json';timingid=identity(timingpath)
assert timingid['sha256']=='7105a1c0f74b275248fc24808b01e75405ca394f90c8dd4fde64f57d6db8e3f0'
timing=read(timingpath)
assert timing['actual_command']['phase']=='physopt' and timing['actual_command']['native_tcl_code']=='0'
assert timing['native_netlist_unmodified_statement'] and timing['all_report_body_lines_after_header_equal_actual_place']
for v in prior['actual_artifacts']:assert identity(v['path'])==v
source=RPT/'stage_sources/m002_optimized_structure.tcl';assert identity(source)==prior['native_collector']
common=RPT/'stage_sources/m002_diagnostic_common.tcl'
global_review=read(OUT/'place_global_POST_review.json');sourceids={v['path']:v for v in global_review['all_identity_checks']}
assert identity(common)==sourceids[str(common)]
assert 'm002_optimized_structure $point $::m002_report_dir' in common.read_text()
for expected in ['optimized_boundaries_${phase}.tsv','optimized_control_sources_${phase}.tsv','optimized_structure_${phase}_result.txt','WRONLY CREAT EXCL','E005_OPTIMIZED_STRUCTURE_COMPLETED $phase 48/16/16 boundary CE graphs']:
    assert expected in source.read_text()
current_paths=[RPT/n for n in ['optimized_boundaries_physopt.tsv','optimized_control_sources_physopt.tsv','optimized_structure_physopt_result.txt']]
currentids=[identity(p) for p in current_paths]
assert currentids[0]['sha256']=='d414f43b54dbfc41d6c24f0f5bb27f87377093380775917a53da99aaaed02089'
assert currentids[1]['sha256']=='b24b5a2e560d90ab9dd403f40170a5b6b09d0e63c831fb3df9e33ba458f6f130'
assert currentids[2]['sha256']=='d1870f6626587d59b6ccacffb00364bf4f8790f28ecbc421e324f55a0bfe2cf8'
for p in current_paths:assert not p.is_symlink()
for p in current_paths[:2]:
    old=RPT/p.name.replace('physopt','place')
    assert p.read_bytes()==old.read_bytes() and p.stat().st_ino!=old.stat().st_ino
tcl=tkinter.Tcl()
def tdict(value):
    parts=tcl.splitlist(value);assert len(parts)%2==0 and len(set(parts[::2]))==len(parts)//2;return dict(zip(parts[::2],parts[1::2]))
boundaries=rows(current_paths[0]);counts=Counter(r['scope'] for r in boundaries)
assert len(boundaries)==len({r['cell'] for r in boundaries})==80 and counts=={'input':48,'gate':16,'down':16}
load_positions=Counter()
for r in boundaries:
    ref,width,load_ref={'input':('LUT6',256,'FDCE'),'gate':('LUT1',384,'FDRE'),'down':('LUT1',512,'FDRE')}[r['scope']]
    assert r['REF_NAME']==ref and r['DONT_TOUCH']=='1' and int(r['leaf_input_pins'])==width
    assert tdict(r['load_REF_counts'])=={load_ref:str(width)} and tdict(r['load_pin_counts'])=={'CE':str(width)}
    assert r['driver_LOC'].startswith('SLICE_X') and r['driver_BEL']
    loads={k:int(v) for k,v in tdict(r['load_SLR_counts']).items()}
    assert set(loads)<={'SLR0','SLR1','SLR2'} and sum(loads.values())==width
    bounds=[int(v) for v in tcl.splitlist(r['load_slice_XY_bounds'])]
    assert len(bounds)==4 and bounds[0]<=bounds[2] and bounds[1]<=bounds[3]
    for slr,n in loads.items():load_positions[(r['scope'],slr)]+=n
controls=rows(current_paths[1]);assert len(controls)==len({r['net'] for r in controls})==14
for r in controls:
    assert int(r['leaf_input_pins'])>0 and r['drivers'] and r['driver_LOCs']
    assert sum(int(v) for v in tdict(r['load_pin_counts']).values())==int(r['leaf_input_pins'])
    assert len(tcl.splitlist(r['drivers']))==len(tcl.splitlist(r['driver_LOCs']))
native=dict(l.split('=',1) for l in current_paths[2].read_text().splitlines())
assert native==dict(phase='physopt',issues='',boundary_contract='48input_16gate_16down',physical_signoff='false')
events=[]
with (RPT/'vivado.log').open() as f:
    for number,line in enumerate(f,1):
        if line.startswith('E005_OPTIMIZED_STRUCTURE_COMPLETED physopt') or line=='phys_opt_design completed successfully\n' or "physopt.dcp' has been generated." in line:
            events.append(dict(line=number,text=line.removesuffix('\n')))
assert len(events)==3 and events[0]['text']=='phys_opt_design completed successfully'
assert events[-1]==dict(line=169805,text='E005_OPTIMIZED_STRUCTURE_COMPLETED physopt 48/16/16 boundary CE graphs')
assert events[0]['line']<events[1]['line']<events[2]['line']
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_FRESH_CURRENT_PHYSOPT_80_BOUNDARY_AND_CONTROL_SOURCE_REVIEW',
    verdict='ACCEPT_CURRENT_PHYSOPT_FRESH80_PROTECTION_SUBSTEP',applicability='AT004 actual physopt native POST structure substep; complete global POST/locality/route separate',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',
    actual_artifacts=currentids,actual_native_result=native,actual_native_closed_events=events,native_collector=identity(source),native_POST_caller=identity(common),accepted_actual_place_fresh80=priorid,accepted_current_physopt_command_and_full_timing=timingid,
    fresh_phase_qualification='Native phase-specific exclusive output files and current physopt completed marker, after actual native command and saved checkpoint; not an inherited pre-place-only receipt',
    actual_current_tables_byte_equal_to_place=True,distinct_regular_output_files_not_symlink_or_same_inode_as_place=True,
    boundary_counts=dict(counts),all80_unique=True,all80_DONT_TOUCH_1=True,REF_INIT_and_all_table_fields_equal_accepted_place=True,CE_widths={'input':256,'gate':384,'down':512},all_current_driver_LOC_BEL_nonempty=True,all_payload_SLR_and_XY_bounds_resolved=True,
    current_payload_pin_counts_by_scope_SLR=[dict(scope=k[0],SLR=k[1],load_pins=v) for k,v in sorted(load_positions.items())],control_source_rows=14,control_source_net_uniqueness_and_terminal_totals_and_driver_vectors_consistent=True,
    limits=['80 protected boundaries are distinct from C01 all9491 P; no fresh physopt candidate membership/reconciliation/compliance acceptance here.',
      'Current tables unchanged from place corroborate native netlist-unmodified declaration; no hold fix, congestion or timing benefit inferred.',
      'Physopt global hold FAIL/34042 endpoints and formal reset/CDC/IO OPEN remain; full global POST and locality separately required.',
      'No EDA/native query, DCP content read/hash, process/lock control, engineering edits, extra gate or agent.'],all_identity_checks=list(checks.values()),audit_program=identity(__file__))
output=OUT/'physopt_fresh80_structure_review.json';save(output,out)
human=OUT/'physopt_fresh80_structure_review.md'
with human.open('x') as f:f.write('''# AT004 physopt fresh80独立审核

execution：本轮physopt新采集结构子步骤核验完成。verdict：接受当前fresh80保护边界。applicability：实际physopt POST结构检查，完整global POST/locality另审。review：独立子步骤通过，无新增停点。

80个唯一边界为input48/gate16/down16，DONT_TOUCH全1，LUT类型/INIT及CE负载宽度256/384/512保持；实际driver LOC/BEL、负载SLR及XY范围完整。14条control-source行的网唯一性、terminal总数及driver/LOC向量一致。

当前两份physopt表与已审place表逐字节相同，但为本轮phase独立原生输出文件；归档collector以CREAT EXCL生成phase文件，physopt专属结果issues为空，日志169805行明确完成48/16/16 CE graphs，且位于实际physopt命令与DCP保存之后。本轮新测资格由这些当前证据建立。

表未变化与原生netlist未修改声明相符，不推断hold修复或物理收益。全局hold FAIL、正式reset/CDC/IO OPEN保持；本审核不替代完整physopt POST、C01成员/落区/cut/timing或route验收。未调用EDA、读取/hash DCP、控制进程/锁或改工程。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),counts=dict(counts),native_marker=events[-1]),ensure_ascii=False))
