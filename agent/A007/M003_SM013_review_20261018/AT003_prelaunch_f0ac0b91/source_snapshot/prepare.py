#!/usr/bin/env python3
"""CPU-only fixed-scope preparation and launch-integrity checks."""
import csv, datetime, fcntl, hashlib, json, os, re, shutil, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(parent for parent in HERE.parents if (parent/'.research-agent/project.json').is_file())
E=ROOT/'project/E009_m003_failed_net_attribution'
AT=E/'experiment_results/runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix'
PRIOR=E/'experiment_results/runs/R001/attempts/AT002_failed_route_full_attribution_alias_fix'
OLD=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
DCP=REPORT/'route_failed.dcp'
FREEZE=ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json'
BASE='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute'

def ident(p):
    p=Path(p).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def q(s):
    assert not any(c in s for c in '{}\n\r')
    return '{'+s+'}'
def proc(pid):
    try:
        fs=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=int(pid),start_ticks=int(fs[19]),state=fs[0],ppid=int(fs[1]),pgrp=int(fs[2]))
    except FileNotFoundError:return None
def resources():
    mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    disk=shutil.disk_usage(ROOT).free
    assert mem>=48*1024**3 and disk>=30*1024**3,'resource reserves unavailable'
    return dict(MemAvailable=mem,disk_free=disk,cpu_allowed=sorted(os.sched_getaffinity(0)))
def check_baseline(b):
    for r in b['identities']:
        assert ident(r['path'])==r,f"changed baseline: {r['path']}"
    assert len(b['production_inputs'])==144
    for r in b['production_inputs']:
        assert ident(r['path'])==r,f"changed production input: {r['path']}"
    current=json.loads((OLD/'status.json').read_text())
    ids=dict(current['tracked_identities'])
    for role in ['supervisor','leader']:
        if role+'_start_ticks' in current:ids[str(current[role+'_pid'])]=current[role+'_start_ticks']
    alive=[]
    for pid,start in ids.items():
        p=proc(pid)
        if p and p['start_ticks']==start and p['state']!='Z':alive.append(p)
    assert not alive,f'prior E008 identities live: {alive}'
    assert current['native_exit_code']==1 and current['exit_code']==1 and current['stop_reason'] is None
    assert not current['owned_survivors']
    prior=json.loads((PRIOR/'status.json').read_text())
    assert prior['native_exit_code']==1 and prior['exit_code']==1 and prior['stop_reason'] is None
    assert not prior['owned_survivors'] and prior['post_integrity_error'] is None
    assert json.loads((PRIOR/'terminal_facts_v2.json').read_text())['engineering_closure_verified'] is True
    prior_ids=dict(prior['tracked_identities'])
    for role in ['supervisor','leader']:prior_ids[str(prior[role+'_pid'])]=prior[role+'_start_ticks']
    for pid,start in prior_ids.items():
        actual=proc(pid)
        assert not actual or actual['start_ticks']!=start or actual['state']=='Z','prior AT002 owned process live'
    active=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            cmd=(d/'cmdline').read_bytes().split(b'\0')
            names={Path(x.decode(errors='replace')).name for x in cmd[:2]}
            if names & {'vivado','loader','xsim','xvlog','xelab','xsc','gcc','g++','cc1','cc1plus','clang','clang++'}:
                p=proc(d.name)
                if p and p['state']!='Z':active.append(dict(**p,argv=[x.decode(errors='replace') for x in cmd if x]))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    assert not active,f'EDA/compilation lane occupied: {active}'
    return dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),production_inputs=144,prior_pid_start_absent=True,active_eda_or_compilers=active,resources=resources())

def main():
    assert not (HERE/'baseline.json').exists(),'preparation is append-only; use a new attempt/package for a changed scope'
    dcp=ident(DCP)
    assert dcp['bytes']==765705446 and dcp['sha256']=='51679d9a4f8dc35c5e5b167ebbecd72260b0862f85ad8168782646f0fc16da21'
    f=ident(FREEZE);assert f['sha256']=='a5643a9e8adb13d6e76f3e78b2dfb6804b9b8ac193f7006f5ceff1b0c4f5a26f'
    production=json.loads(FREEZE.read_text())['files']
    references=[ROOT/'mission/M003_joint_routability_closure/contract.md',ROOT/'mission/M003_joint_routability_closure/tasks/SM013.md',ROOT/'mission/M003_joint_routability_closure/verification_matrix.md']
    baseline=dict(identities=[dcp,f]+[ident(p) for p in [OLD/'terminal_facts.json',OLD/'failed_route_terminal_facts.json',OLD/'status.json',REPORT/'route_failed_status.rpt',REPORT/'route_failed_congestion.rpt',REPORT/'vivado.log',REPORT/'candidate_endpoints_route_failed.tsv',ROOT/'project/hardware/vivado/scripts/run_m002_no_wall.py',ROOT/'project/hardware/vivado/scripts/m002_execution_profile.py',PRIOR/'status.json',PRIOR/'terminal_facts_v2.json',PRIOR/'observer_terminal_facts.json']],reference_documents=[ident(p) for p in references],production_inputs=production)
    checked=check_baseline(baseline)
    with (ROOT/'project/hardware/vivado/.m002_eda.lock').open('r') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);checked['eda_lock_probe']='ACQUIRED_AND_RELEASED';fcntl.flock(f,fcntl.LOCK_UN)
    # Capture the exact native sample, deduplicated, without using it as a census.
    log=(REPORT/'vivado.log').read_text();section=log.split('Below is a list of the top 10 physical nodes with signal overlaps',1)[1]
    section=section.split('Phase 9 Verifying routed nets |',1)[0]
    literal=[];innets=False
    for line in section.splitlines():
        if re.match(r'^\d+\. \(',line):innets=False
        if line=='Nets:':innets=True;continue
        if innets and line.startswith('scalellm_'):literal.append(line.strip())
        if len(literal)>100:raise ValueError('sample parser escaped native top10 section')
        if 'Number of Node Overlaps' in line or 'Phase 10' in line:break
    literal=sorted(set(literal));assert 20<=len(literal)<=50,len(literal)
    boundary_slrs={}
    with (REPORT/'candidate_endpoints_route_failed.tsv').open() as f:
        for r in csv.DictReader(f,delimiter='\t'):
            if r['SLR'] in ('SLR0','SLR1','SLR2'):
                boundary_slrs.setdefault(r['canonical_net'],set()).add(r['SLR'])
    known=sorted(k for k,v in boundary_slrs.items() if len(v)>1)[:16]
    assert known,'prior closed C01 cut lacks measured cross-SLR seeds'
    netq=[('MLP_PARENT_HEAD',r'^'+re.escape(BASE+'/u_mlp/u_serial_command/u_shared_compute/parent_head_r')+r'.*'),('MLP_PARENT_TAIL',r'^'+re.escape(BASE+'/u_mlp/u_serial_command/u_shared_compute/parent_tail_r')+r'.*'),('ATT_META_READ_ADDR',r'^'+re.escape(BASE+'/u_attention/meta_read_addr_r')+r'.*')]
    protect=[('input',r'^'+re.escape(BASE+'/u_attention/u_input_buffer')+r'/.*u_capture_decode$','LUT6',48),('gate',r'^'+re.escape(BASE+'/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack')+r'/.*u_output_payload_ce$','LUT1',16),('down',r'^'+re.escape(BASE+'/u_mlp/u_serial_command/u_down_scheduler/u_projection_repack')+r'/.*u_output_payload_ce$','LUT1',16)]
    plan=dict(schema=1,scope='SM013 full conflict-net census plus frozen supplemental one-hop endpoint detail',normalization_base=BASE,
        driver_normalization='Primitive containing RTL instance capped at first four path levels below literal u_compute; outside u_compute first four containing-module path segments; preserve generate indices; no net-name semantics. TOP_PORT/MULTIDRIVER/UNKNOWN_DRIVER/INOUT_OR_AMBIGUOUS are explicit buckets.',
        primary_group_key=['normalized_driver_module','source_SLR','sorted_unique_load_SLR_set'],primary_sort='unique_net_count DESC, full group tuple lexical ASC',top_groups=20,representative_nets_per_group=16,
        supplemental_net_queries=netq,protection_queries=protect,literal_net_seeds=literal,known_cross_slr_net_seeds=known,
        candidate_literal_roots=[BASE+'/u_mlp/u_serial_command/u_shared_compute',BASE+'/u_attention/u_meta',BASE+'/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_quantizer[3].u_quantizer/g_div[0].u_div',BASE+'/u_attention/u_compute/g_projection_rtl.u_projection/u_frontend/g_quantizer[2].u_quantizer/g_div[4].u_div'],
        known_cross_boundary_seed_evidence=[str(REPORT/'candidate_cut_summary_route_failed.json'),str(REPORT/'candidate_endpoints_route_failed.tsv')],
        endpoints='Complete native leaf pins and top ports of census and frozen supplementary alias closures; selected net endpoints only, no transitive fanin/fanout expansion.',
        detailed_properties=['REF_NAME','LOC','BEL','IS_LOC_FIXED','IS_BEL_FIXED','ORIG_CELL_NAME','ORIG_REF_NAME','RLOC','RLOC_ORIGIN','MACRO_NAME','DONT_TOUCH','USER_SLR_ASSIGNMENT','PARENT'],
        timing=dict(groups='top20 plus frozen supplementary tags',representative_nets=16,lexical_load_pin_cap=16,max_paths=2,nworst=1,delay_types=['max','min'],full_TNS='NOT_MEASURED'),
        overlap_nodes=dict(native_report=702396,full_node_mapping='NOT_MEASURED',never_equal_to_net_count=True),
        end_condition='fixed conflict-net and supplementary object lists exhausted, then bounded deep properties/timing and independent aggregation complete; no wall/no-output cutoff',
        limits=dict(cpu=list(range(8)),threads=8,nice=5,tree_rss_bytes=192*1024**3,MemAvailable_floor_bytes=48*1024**3,mem_low_seconds=30,disk_free_floor_bytes=30*1024**3),
        prohibited=['synthesis','opt_design','place_design','phys_opt_design','route_design','write_checkpoint','read_xdc','set_property','bitstream','board','GPU','PPL','ACC'])
    save(HERE/'baseline.json',baseline);save(HERE/'query_plan.json',plan);save(AT/'preflight.json',checked)
    for source,name in zip(references,['reference_contract.md','reference_SM013.md','reference_verification_matrix.md']):shutil.copy2(source,HERE/name)
    with (HERE/'targets.tcl').open('x') as f:
        f.write('set net_seed_queries [list '+' '.join('[list '+q(t)+' '+q(r)+']' for t,r in netq)+']\n')
        f.write('set protection_queries [list '+' '.join('[list '+q(t)+' '+q(r)+' '+q(ref)+' '+str(count)+']' for t,r,ref,count in protect)+']\n')
        f.write('set literal_net_seeds [list '+' '.join(q(n) for n in literal)+']\n')
        f.write('set known_cross_slr_net_seeds [list '+' '.join(q(n) for n in known)+']\n')
    save(AT/'offline_reuse.json',dict(native_conflict_nets=547548,overlap_nodes=702396,fields_already_measured=['route counts','candidate C01 endpoints/locality','global failed timing','place/physopt resources'],fields_missing=['full conflict canonical census','whole conflict driver/consumer grouping','exact candidate full endpoint intersection'],top10_unique_net_seeds=len(literal),claim='Native sample seeds only; not full attribution. No EDA started.'))
    save(HERE/'prepared_manifest.json',dict(schema=1,files=[ident(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in ('.py','.tcl','.json','.md') and p.name not in ('prepared_manifest.json','summary.md','protocol.md')],preflight=ident(AT/'preflight.json')))
    print(json.dumps(dict(E='E009',R='R001',AT='AT003',preflight=checked,manifest=ident(HERE/'prepared_manifest.json')),indent=2))
if __name__=='__main__':main()
