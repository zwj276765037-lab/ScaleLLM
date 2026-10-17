"""Bounded independent CPU audit. Does not import or run any EDA launcher."""
from pathlib import Path
from collections import defaultdict
import ast
import hashlib
import json
import tempfile
import tkinter
from datetime import datetime, timezone

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HERE=ROOT/'agent/A006/exact_hotspot_offload'
OLD=HERE/'review_before_site_lifecycle_fix'
E007=ROOT/'agent/A006/slr2_input_locality'
ARCH=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/attempts/AT001_exact_candidate_comparison/sources'
T=tkinter.Tcl()
bound={}

def identity(path):
    p=Path(path);b=p.read_bytes()
    r=dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    bound[str(p)]=r
    return r

def verify(row):
    assert identity(row['path'])==row,row['path']

def procs(path):
    lines=path.read_text().splitlines(True);out={};i=0
    while i<len(lines):
        s=lines[i];i+=1
        if not s.startswith('proc '):continue
        name=s.split()[1]
        while not T.call('info','complete',s):s+=lines[i];i+=1
        out[name]=s
    return out

def ast_functions(path):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}

manifest=identity(HERE/'prepared_manifest.json')
assert manifest['sha256']=='b59d11262626f9acad735569dfee182978d7fcbd4a213fb6da3b336a94762072'
M=json.loads((HERE/'prepared_manifest.json').read_text())
refs=M['own_sources']+M['reused_sources']+M['CPU_checks']+M['documentation']+[M[k] for k in ('contract','selector_reference','source_reuse_manifest')]
for row in refs:verify(row)
verify(M['original_target_authority'])
assert not M['EDA_executed'] and M['candidate_selected'] is None
assert len(refs)==32
for row in M['own_sources']:
    p=Path(row['path'])
    if p.suffix=='.py':ast.parse(p.read_text())
    elif p.suffix=='.tcl':assert T.call('info','complete',p.read_text())==1

old_manifest=identity(OLD/'prepared_manifest.json')
assert old_manifest['sha256']=='19924f7d6ab382ba4c08972d328356cc88d9c5631259e0d06fdf2b7b673c24fb'
old=json.loads((OLD/'prepared_manifest.json').read_text())
old_source_bridges=[]
for row in old['own_sources']:
    archived=identity(OLD/Path(row['path']).name)
    assert archived['sha256']==row['sha256'] and archived['bytes']==row['bytes']
    old_source_bridges.append(dict(old=row,archive=archived))
bridge_path=HERE/'site_lifecycle_fix_bridge_20261017.json'
identity(bridge_path)
bridge=json.loads(bridge_path.read_text())
assert bridge['new_manifest']['sha256']=='2147c23fc2be7e75a028e1dd30f236280fccb1696546896388c783da2bf5cd94' and bridge['old_manifest']==old_manifest
dedup_bridge_path=HERE/'property_support_dedup_source_bridge_20261017.json'
identity(dedup_bridge_path)
dedup=json.loads(dedup_bridge_path.read_text())
middle=HERE/'review_before_property_support_dedup'
middle_manifest=identity(middle/'prepared_manifest.json')
assert middle_manifest['sha256']==bridge['new_manifest']['sha256']
middle_sources=json.loads((middle/'prepared_manifest.json').read_text())['own_sources']
for row in middle_sources:
    actual=identity(middle/Path(row['path']).name)
    assert all(actual[k]==row[k] for k in ('sha256','bytes'))
old_hooks=(OLD/'candidate_hooks.tcl').read_text()
hooks=(HERE/'candidate_hooks.tcl').read_text()
old_proc=procs(OLD/'candidate_hooks.tcl')['slr2::resolve']
new_proc=procs(HERE/'candidate_hooks.tcl')['slr2::resolve']
assert hooks==old_hooks.replace('candidate_site_members_${point}.tsv','candidate_literal_site_members_${point}.tsv',1)
runtime=procs(HERE/'runtime_hooks.tcl')
phase=runtime['slr2::phase']
def open_statement(body,token):
    result=[s.strip() for s in body.splitlines() if 'set h [open ' in s and token in s]
    assert len(result)==1
    return result[0]
old_stmt=open_statement(old_proc,'candidate_site_members_${point}.tsv')
new_stmt=open_statement(new_proc,'candidate_literal_site_members_${point}.tsv')
phase_stmt=open_statement(phase,'candidate_site_members_${point}.tsv')
lifecycle=[]
with tempfile.TemporaryDirectory(prefix='A007_E008_lifecycle_') as temp:
    for label,statement,should_fail in [('original',old_stmt,True),('fixed',new_stmt,False)]:
        for point in ('place','physopt','route'):
            directory=Path(temp)/label/point;directory.mkdir(parents=True)
            T.setvar('::m002_report_dir',str(directory));T.setvar('point',point)
            T.eval(statement);T.eval('puts $h literal_root_snapshot; close $h')
            error=None
            try:T.eval(phase_stmt)
            except tkinter.TclError as exc:error=str(exc)
            if error is None:T.eval('puts $h settled_actual_P_snapshot; close $h')
            assert bool(error)==should_fail
            files={p.name:p.read_text().strip() for p in directory.iterdir()}
            assert len(files)==(1 if should_fail else 2)
            assert list(files.values()).count('literal_root_snapshot')==1
            lifecycle.append(dict(version=label,phase=point,second_exclusive_open_error=error,files=files))

fn_new=ast_functions(HERE/'evidence_adapter.py');fn_old=ast_functions(E007/'evidence_adapter.py')
unchanged=[name for name,value in fn_new.items() if value==fn_old.get(name)]
assert 'successful_pre_place_parent' in unchanged
assert (HERE/'implementation.tcl').read_text()==(E007/'implementation.tcl').read_text().replace('slr2::cut pre_place\n','slr2::cut pre_place\nslr2::scoped_timing pre_place\n',1)
reused=json.loads((HERE/'source_reuse_manifest.json').read_text())
for value in reused.values():
    if isinstance(value,dict) and 'path' in value:verify(value)
assert (HERE/'property_alignment.tcl').read_bytes()==(ARCH/'property_alignment.tcl').read_bytes()
candidate=procs(HERE/'candidate_hooks.tcl');r004=procs(ARCH/'candidate_inspector.tcl')
assert candidate['slr2::timing_boundary_selection']==r004['slr2::timing_boundary_selection'].replace('proc slr2::timing_boundary_selection {','proc slr2::timing_boundary_selection {',1)
assert runtime['slr2::scoped_timing']==r004['slr2::scoped_timing']

# Execute only selected pure functions; no native command is installed.
T.eval('namespace eval slr2 {}')
for name in ('prefix','group','selected','bindable','timing_boundary_selection'):
    T.eval(candidate['slr2::'+name])
T.eval(runtime['slr2::resource_class'])
targets=json.loads((HERE/'target_authority.json').read_text())['candidates']
checks=[]
for target in targets:
    root=target['root'];T.setvar('::slr2::root',root)
    assert T.call('slr2::selected',root+'/actual[3]')==1
    assert T.call('slr2::selected',root+'_extra/actual')==0
    if '[1]' in root:assert T.call('slr2::selected',root.replace('[1]','[0]')+'/actual')==0
    checks.append(dict(check='literal_root',candidate=target['id'],passed=True))
for ref,cls in [('RAMB18E2','RAMB18'),('RAMB36E2','RAMB36'),('URAM288','URAM288'),('DSP48E2','DSP48E2'),('BUFGCE','DEDICATED_CLOCK_IO_REQUIRES_SEPARATE_PROOF'),('UNRECOGNIZED_RESOURCE','UNKNOWN_RESOURCE_REQUIRES_EXPLANATION')]:
    assert T.call('slr2::bindable',ref)==1
    assert T.call('slr2::resource_class',ref)==cls
    checks.append(dict(check='semantic_retention_separate_from_migration',REF_NAME=ref,resource_class=cls,passed=True))

# Compile the actual pure reconciliation code into a sandbox with simple require.
def require(ok,message):
    if not ok:raise AssertionError(message)
class E:
    pass
e=E();e.require=require
tree=ast.parse((HERE/'evidence_adapter.py').read_text())
selected_nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('selected','bindable','reconcile_objects')]
namespace=dict(e=e,CANDIDATE_ROOT=targets[0]['root'],collections=__import__('collections'))
exec(compile(ast.Module(body=selected_nodes,type_ignores=[]),'<actual E008 pure reconciliation>','exec'),namespace)
reconcile=namespace['reconcile_objects'];root=targets[0]['root'];old_name=root+'/old';clone='outside/actual_origin_clone'
original={old_name:'DSP48E2'}
def row(name,origin=''):
    return dict(NAME=name,REF_NAME='DSP48E2',ORIG_CELL_NAME=origin,ORIG_REF_NAME='DSP48E2',LOC='DSP48E2_X1Y1',SLR='SLR2')
cases=[('survives',original,[row(old_name)],[],True),('native_origin_replacement',{},[row(clone,old_name)],[row(clone,old_name)],True),('suffix_only',{},[row(old_name+'_replica')],[],False),('origin_clone_outside_Pblock',original,[row(old_name)],[row(clone,old_name)],False),('missing_unexplained',{},[],[],False)]
reconciliation=[]
for name,literal,actual,origins,expected in cases:
    value=reconcile(original,literal,actual,origins)
    assert value['qualified']==expected,(name,value)
    reconciliation.append(dict(case=name,expected_qualified=expected,actual=value))

result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),execution='bounded_CPU_source_review_complete',verdict='source_preparation_supported_after_F01_repair',applicability='E008 manifest b59d1126 only; no selected candidate, native start, placement, routing, or pre-place qualification',review='A007 independent identity/static/pure-function and actual Tcl file-lifecycle checks',manifest=manifest,verified_manifest_references=len(refs),F01=dict(original_manifest=old_manifest,problem='resolve and phase exclusively create the same candidate_site_members path',fix='literal-root snapshot name separated from reconciled actual-P snapshot',strict_single_filename_substitution=True,independent_lifecycle=lifecycle,engineering_repair_bridge=identity(bridge_path)),previous_sources_preserved=old_source_bridges,adapter_unchanged_AST_functions=unchanged,implementation_only_adds_pre_place_scoped_timing=True,R004_property_alignment_and_scoped_timing_byte_identity=True,pure_checks=checks,pure_origin_reconciliation=reconciliation,static_review=['Exact actual closeout requires one authority C01/C02, current contract/manifest, real terminal identities and nonempty review evidence.', 'Single nonblocking EDA lock and prior PID/start absence are checked before runtime preparation; no normal wall/no-output stop added.', 'Runtime RAW/S/P is derived anew; only GND/VCC excluded from S, actual DSP parents normalized, memory retained, dedicated/unknown migration refused.', 'P plus exact descendants/ancestors policies recorded and preserved; macro partner uncertainty remains a runtime refusal, no clearing or softening.', 'Original P and actual Pblock plus global ORIG_CELL_NAME matches reconcile before complete cut. Missing/unplaced/outside or unproved origin cannot qualify.', 'Eight unchanged adapter function ASTs include successful-parent provenance and compliance helpers; constraint_chain adds qualified overlay identities; E007 is source preparation only.', 'Native controller remains successful E005-derived full place SSI_SpreadSLLs, physopt Default, route Default; no synthesis/debug repeat, no incremental.'],N01=dict(classification='nonblocking export-size improvement, applied',previous_manifest=middle_manifest,source_bridge=identity(dedup_bridge_path),verified_prior_own_source_archives=len(middle_sources),finding='Every object still calls list_property and supported PRIMITIVE_* reads; sorted exact support lists are deduplicated into dictionary; per-object support_id retained; dictionary is bound in physical overlay. No REF sampling substituted.'),remaining=['actual R004 cut, directional timing, UNION and terminal closure','at most one independently supported candidate and Root actual closure binding','actual E008 native pre-place qualification and subsequent physical results'],identities=list(bound.values()),audit_script=identity(Path(__file__)))
output=ROOT/'agent/A007/independent_E008_source_preparation_review_b59d1126.json'
with output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(output=identity(output),unchanged_adapter_functions=unchanged,lifecycle_cases=len(lifecycle),origin_cases=len(reconciliation)),indent=2))
