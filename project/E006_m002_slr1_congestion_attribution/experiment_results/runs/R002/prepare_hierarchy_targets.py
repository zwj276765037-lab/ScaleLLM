"""Parse bounded archived hierarchy and identify exact/candidate attribution roots."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).parent
P=ROOT/'project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly/physopt/utilization_hierarchy_depth7.rpt'
data=P.read_bytes();lines=data.decode().splitlines();stack={};rows=[];headers=None
for i,line in enumerate(lines,1):
    cols=line.split('|')[1:-1]
    if cols and cols[0].strip()=='Instance':headers=[v.strip() for v in cols];continue
    if len(cols)<3 or not cols[2].strip().isdigit():continue
    first=cols[0];name=first.strip();leading=len(first)-len(first.lstrip())
    assert leading>=1 and (leading-1)%2==0
    depth=(leading-1)//2;is_self=name.startswith('(') and name.endswith(')')
    if is_self:full=stack[depth-1]
    elif depth==0:full='';stack={0:''}
    else:
        full='/'.join(x for x in [stack[depth-1],name] if x);stack[depth]=full;stack={k:v for k,v in stack.items() if k<=depth}
    rows.append(dict(native_line=i,depth=depth,display_name=name,full_path=full,is_local_self_row=is_self,
        module=cols[1].strip(),metrics={key:int(value.strip()) for key,value in zip(headers[2:],cols[2:])}))
by_path={r['full_path']:r for r in rows if not r['is_local_self_row']};assert len(by_path)==sum(not r['is_local_self_row'] for r in rows)
BD='scalellm_vcu118_f05_bd_i';C=BD+'/core/inst/u_core';ATT=C+'/u_compute/u_attention';MLP=C+'/u_compute/u_mlp'
groups=[('attention',[ATT]),('mlp',[MLP]),('weight_metadata',[C+'/u_meta_bank']),('weight_loader',[C+'/u_paired_weight']),
        ('core_other',[BD+'/core']),('ddr0',[BD+'/ddr4_0',BD+'/d0_smc',BD+'/d0_mig_slice']),
        ('ddr1',[BD+'/ddr4_1',BD+'/d1_smc',BD+'/d1_mig_slice']),('pcie',[BD+'/xdma_0']),('debug',['dbg_hub'])]
owner_rules=[dict(owner=owner,exact_hierarchy_roots=roots,selection='longest matching hierarchy prefix, then core_other remainder' if owner=='core_other' else 'descendant primitives of exact roots') for owner,roots in groups]
owner_rules.append(dict(owner='interconnect_other',exact_hierarchy_roots=[],selection='all primitives not matched above, including top-level primitives; retain actual NAME'))
native_targets=[]
for owner,roots in groups:
    for path in roots:
        assert path in by_path
        native_targets.append(dict(target_id=f'H{len(native_targets)+1:03}',owner=owner,full_path=path,
            evidence='native depth7 hierarchy row; actual native lookup must still verify exact NAME',source_row=by_path[path],report_scope='inclusive subtree, not exclusive owner cut'))
for parent in (ATT,MLP,C+'/u_meta_bank'):
    for path,row in by_path.items():
        if path.rsplit('/',1)[0] == parent:
            native_targets.append(dict(target_id=f'H{len(native_targets)+1:03}',owner='submodule',full_path=path,
                evidence='native depth7 direct child',source_row=row,report_scope='inclusive subtree'))
serial=MLP+'/u_serial_command';compute=ATT+'/u_compute'
route=json.loads((OUT/'route_failure_sample_targets.json').read_text())
netnames=[r['net_name'] for r in route['unique_contender_nets']]
def source_identity(relative):
    path=ROOT/relative;b=path.read_bytes();return dict(path=str(path),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
source_files={relative:source_identity(relative) for relative in [
    'project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv',
    'project/hardware/rtl/attention/hap_attention_compute_cohort16_top.sv',
    'project/hardware/rtl/integration/hap_attention_mlp_production_core.sv']}
candidates=[]
for path,role,relative,line in [
    (serial+'/u_w4_frontend','MLP weight frontend','project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv',241),
    (serial+'/u_gate_scheduler','MLP Gate/Up scheduler','project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv',328),
    (serial+'/u_down_scheduler','MLP Down scheduler','project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv',434),
    (serial+'/u_shared_compute','MLP shared projection compute','project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv',495),
    (compute+'/g_projection_rtl.u_projection','Attention projection, actual native generate-name form','project/hardware/rtl/attention/hap_attention_compute_cohort16_top.sv',207),
    (compute+'/u_postprocess_store','Attention postprocess storage','project/hardware/rtl/attention/hap_attention_compute_cohort16_top.sv',307),
    (compute+'/u_context_store','Attention context storage','project/hardware/rtl/attention/hap_attention_compute_cohort16_top.sv',504)]:
    raw=(ROOT/relative).read_text().splitlines()[line-1]
    candidates.append(dict(full_path=path,role=role,RTL_source=source_files[relative],RTL_native_line=line,RTL_raw=raw,
        failed_route_net_prefix_present=any(n.startswith(path+'/') for n in netnames),
        status='below depth7: candidate exact root requires native unique lookup; preserve NOT_FOUND or MULTIPLE'))
deeper=[
    (serial+'/u_shared_compute/u_branch1','MLP branch1 appears in native failed-route samples'),
    (serial+'/u_gate_scheduler/u_swiglu','Gate SwiGLU appears in native failed-route samples'),
    (serial+'/u_gate_scheduler/u_projection_repack','Gate repack, exact E005 native hierarchy target previously verified'),
    (serial+'/u_down_scheduler/u_projection_repack','Down repack, exact E005 native hierarchy target previously verified'),
    (serial+'/u_down_scheduler/u_weight_repack','Down weight repack appears in native failed-route samples'),
    (compute+'/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7','Attention projection region appears in native peak report and failed samples')]
for path,role in deeper:candidates.append(dict(full_path=path,role=role,failed_route_net_prefix_present=any(n.startswith(path+'/') for n in netnames),status='bounded deeper attribution candidate; native unique lookup required'))
footnote=next((dict(native_line=i,raw=line) for i,line in enumerate(lines,1) if 'cross-hierarchy LUT combining' in line),None);assert footnote
mlp_children=[by_path[MLP+'/u_input_frontend'],by_path[serial]]
mlp_self=next(r for r in rows if r['full_path']==MLP and r['is_local_self_row'])
example=dict(parent=by_path[MLP],children=mlp_children,local_self=mlp_self,
    child_plus_local_Total_LUTs=sum(r['metrics']['Total LUTs'] for r in mlp_children+[mlp_self]),
    parent_Total_LUTs=by_path[MLP]['metrics']['Total LUTs'])
assert example['child_plus_local_Total_LUTs']==481896 and example['parent_Total_LUTs']==481854
record=dict(schema='E006_A007_hierarchy_attribution_targets_v1',recorded_utc=datetime.now(timezone.utc).isoformat(),
    hierarchy_source=dict(path=str(P),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),
    global_report_row=by_path[''],scope='existing whole-design totals guide exact hierarchy targets; no SLR distribution inferred',
    owner_rules=owner_rules,native_report_roots=native_targets,bounded_deeper_candidates=candidates,
    required_owner_matching='match NAME equal root or prefix root+/; deepest explicit owner root wins, with remaining core and design objects retained',
    selected_core_direct_children=[r for r in rows if not r['is_local_self_row'] and r['full_path'].rsplit('/',1)[0]==C],
    native_hierarchy_nonadditivity=dict(footnote=footnote,example=example),
    resource_semantics=['Primitive ownership must partition actual unique cell NAMEs. Parent inclusive report is separate and never added to descendants.',
        'Native Total LUTs/Logic LUTs/LUTRAM/SRL/FF/BRAM/DSP columns are native report quantities, not generic primitive row counts.',
        'Native footnote explicitly permits child LUT totals above parent from cross-hierarchy combining. Preserve, do not force reconciliation by editing counts.',
        'DSP_ALU/A_B_DATA/C_DATA/MULTIPLIER/M_DATA/OUTPUT/PREADD/PREADD_DATA may share one DSP48E2 site; count unique physical site or native DSP Blocks.',
        'BRAM RAMB36/RAMB181/RAMBFIFO18 are alternative site modes; do not add site capacity as block equivalents.',
        'One SLICE can contain cells owned by multiple modules. Report module-touched sites, exclusive sites and shared-owner sets separately; their sum is not physical unique sites.',
        'Per-NW rows overlap; compute actual union cells/sites by unique identity rather than summing10regions.',
        'u_meta_bank is MLP weight metadata residency672URAM; Attention/u_meta is another80URAM inside Attention. Do not double-count or describe these as full weight payload cache without RTL evidence.',
        'u_paired_weight is shared dedicated AXI read/loader logic; u_tensor is tensor DMA/control. Separate these from compute and from DDR IP.',
        'Depth7 truncates MLP serial-command and Attention compute children. Candidate deeper roots are verified only by actual native lookup; source presence alone is not preserved netlist hierarchy.'])
dest=OUT/'hierarchy_attribution_targets.json'
with dest.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(dict(path=str(dest),bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),native_roots=len(native_targets),bounded_deeper_candidates=len(candidates),nonadditivity_example=example['child_plus_local_Total_LUTs']-example['parent_Total_LUTs']),indent=2))
