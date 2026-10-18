#!/usr/bin/env python3
"""A007 actual place membership/origin/SLR2 substep; no engineering writes or EDA."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import ast,collections,csv,hashlib,json,re,tkinter
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
CANDIDATE='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf'
checks={}
def require(c,m):assert c,m
def identity(p):
    p=Path(p).resolve();assert p.suffix.lower()!='.dcp';before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):
    x=identity(v['path']);assert x['bytes']==v['bytes'] and x['sha256']==v['sha256'];return x
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    identity(p)
    with Path(p).open() as f:
        out=list(csv.DictReader(f,delimiter='\t',quoting=csv.QUOTE_NONE))
    assert all(None not in r and all(v is not None for v in r.values()) for r in out)
    return out
def names(p,key='NAME'):
    values=rows(p);assert len({r[key] for r in values})==len(values);return {r[key]:r for r in values}
def kv(p):return dict(x.split('=',1) for x in Path(p).read_text().splitlines())
factpath=AT/'place_membership_reconciliation_closed_facts.json';factid=identity(factpath)
assert factid['sha256']=='ab90261d7ac37bd5995ec652ef1b0e05096137b12d923431847abd06819ca774'
facts=read(factpath)
for v in facts['artifacts']:verify(v)
verify(facts['actual_native_index_captured_fact'])
priorid=identity(OUT/'pre_place_membership_incremental_review.json')
assert priorid['sha256']=='09216f538a0bec5bad6ac45d8a8d75db85aa1c645c0b23a7347b41ef51628650'
prior=read(priorid['path']);prior_checks={r['name']:r['actual'] for r in prior['ten_actual_ledgers_and_closure_byte_equal_to_reviewed_AT003']}
for kind in ['RAW','S','P']:
    original=identity(RPT/f'candidate_{kind}_pre_place.tsv');assert original==prior_checks[f'candidate_{kind}_pre_place.tsv']
    current=identity(RPT/f'candidate_{kind}_place.tsv');assert (current['bytes'],current['sha256'])==(original['bytes'],original['sha256'])

# Only inspected parser functions; save is replaced by an in-memory capture.
src=RPT/'stage_sources/evidence_adapter.py';srcid=identity(src)
global_review=read(OUT/'place_global_POST_review.json')
qualified_sources={v['path']:v for v in global_review['all_identity_checks']}
assert srcid==qualified_sources[str(src)]
captured={}
def capture(path,value):
    assert Path(path)==RPT/'candidate_membership_place.json';captured[str(path)]=value
chosen={'rows','selected','bindable','accepted_raw_resource','membership','reconcile_objects','require_origin_query'}
functions=[n for n in ast.parse(src.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in chosen]
assert {n.name for n in functions}==chosen
ns=dict(Path=Path,csv=csv,hashlib=hashlib,collections=collections,CANDIDATE_ROOT=CANDIDATE,e=SimpleNamespace(require=require,file_id=identity),save=capture)
exec(compile(ast.Module(body=functions,type_ignores=[]),str(src),'exec'),ns)
membership=ns['membership']('place',RPT);actualmembership=read(RPT/'candidate_membership_place.json');identity(RPT/'candidate_membership_place.json')
assert membership==actualmembership==captured[str(RPT/'candidate_membership_place.json')]
assert (membership['raw_selector_count'],membership['semantic_S_count'],membership['placeable_P_count'])==(9514,9507,9491)
assert membership['excluded_from_S_REF_counts']=={'GND':4,'VCC':3}
raw=names(RPT/'candidate_RAW_place.tsv');semantic=names(RPT/'candidate_S_place.tsv');physical=names(RPT/'candidate_P_place.tsv')
members=names(RPT/'candidate_membership_place.tsv');mapping=names(RPT/'candidate_physical_mapping_place.tsv','raw_NAME')
parents=names(RPT/'candidate_physical_members_place.tsv');before=names(RPT/'candidate_physical_members_pre_place.tsv')
assert len(raw)==len(members)==len(mapping)==9514 and len(semantic)==9507 and len(physical)==len(parents)==len(before)==9491
assert all(n.startswith(CANDIDATE+'/') for n in raw)
internal=[r for r in members.values() if r['REF_NAME'].startswith('DSP') and r['REF_NAME']!='DSP48E2']
assert len(internal)==16 and len({r['physical_parent'] for r in internal})==2
assert all(r['NAME'].startswith(r['physical_parent']+'/') and physical[r['physical_parent']]['REF_NAME']=='DSP48E2' for r in internal)
policy=['USER_SLR_ASSIGNMENT','RLOC','RLOC_ORIGIN','MACRO_NAME','DONT_TOUCH']
fixed_flag_deltas={}
for flag in ['IS_LOC_FIXED','IS_BEL_FIXED']:
    observed=collections.Counter((before[n][flag],r[flag]) for n,r in parents.items())
    assert observed=={('', '0'):9491}
    fixed_flag_deltas[flag]=dict(before='',after='0',objects=9491,scope='Actual cross-phase observation: blank pre-place field becomes explicit false after placement; not asserted byte-equal or silently normalized')
assert all({k:r[k] for k in policy}=={k:before[n][k] for k in policy} for n,r in parents.items())
assert all(r['SLR']=='SLR2' and r['LOC'] and r['BEL'] and r['native_site']==r['LOC'] and r['native_tile'] not in {'','UNKNOWN'} for r in parents.values())
regions=collections.Counter(r['native_clock_region'] for r in parents.values())
for region in regions:
    m=re.fullmatch(r'X(\d+)Y(\d+)',region);assert m and 0<=int(m[1])<=5 and 10<=int(m[2])<=14
assert all(r['actual_PBLOCKS']=='m002_exact_hotspot_SLR2' for r in parents.values())

querypath=RPT/'candidate_native_origin_query_place.txt';query=kv(querypath);ns['require_origin_query'](query)
assert query==dict(native_tcl_code='0',query_executed='1',required_origin_property_verified='1',rule='global_native_ORIG_CELL_NAME_correspondence',issue='')
assert querypath.read_text()==facts['native_origin_query']
origins=rows(RPT/'candidate_native_origin_objects_place.tsv');assert origins==[]
actualpb=names(RPT/'candidate_pblock_physical_place.tsv','physical_NAME')
actualrows=[dict(r,NAME=n) for n,r in actualpb.items()]
orig={n:r['REF_NAME'] for n,r in before.items()};literal={n:r['REF_NAME'] for n,r in physical.items()}
replay=ns['reconcile_objects'](orig,literal,actualrows,origins);replay['native_origin_query']=identity(querypath)
reconciliation=read(RPT/'candidate_reconciliation_place.json');assert replay==reconciliation
assert reconciliation['qualified'] and reconciliation['issues']==[] and reconciliation['explained_replacements']=={}
assert reconciliation['resolved']==orig==literal and len(reconciliation['lineage'])==9491
assert all(r['lineage']=='ORIGINAL_SURVIVING' and r['SLR']=='SLR2' and r['LOC'] for r in reconciliation['lineage'])
assert facts['actual_counts']=={k:reconciliation[k] for k in ['original_count','literal_count','actual_physical_Pblock_count']}
assert facts['resolved_P']==facts['lineage_rows']==9491 and facts['all_resolved_P_in_SLR2'] and facts['all_original_surviving'] and facts['replacements']==0 and facts['issues']==[]
resolved=names(RPT/'candidate_reconciled_P_place.tsv');assert resolved==physical
lineage=names(RPT/'candidate_reconciliation_place.tsv');compliance=names(RPT/'candidate_compliance_place.tsv');pbactual=names(RPT/'candidate_pblock_actual_place.tsv')
assert set(lineage)==set(compliance)==set(pbactual)==set(parents)==set(actualpb)==set(physical)
for row in reconciliation['lineage']:
    name=row['NAME'];assert all(lineage[name][k]==row[k] for k in lineage[name])
    assert compliance[name]==dict(lineage[name],SLR2_compliant='1')
    assert all(parents[name][k]==row[k] for k in ['REF_NAME','LOC','SLR','ORIG_CELL_NAME','ORIG_REF_NAME'])
    assert all(pbactual[name][k]==row[k] for k in ['NAME','REF_NAME','LOC','SLR','ORIG_CELL_NAME','ORIG_REF_NAME']) and pbactual[name]['selector_P']=='1'
pbpath=RPT/'candidate_effective_pblock_place.txt';pblock=kv(pbpath)
assert pblock==dict(NAME='m002_exact_hotspot_SLR2',GRID_RANGES='CLOCKREGION_X0Y10:CLOCKREGION_X5Y14',IS_SOFT='0',EXCLUDE_PLACEMENT='0',CONTAIN_ROUTING='0',physical_members='9491')
assert pbpath.read_text()==facts['effective_pblock']
marker=kv(RPT/'candidate_membership_place_closed.txt')
assert marker['completed']=='1' and marker['root']==marker['actual_exact_root']==CANDIDATE
assert [marker[k] for k in ['RAW','S','P']]==['9514','9507','9491'] and marker['physical_policy_modified']=='false'

# Confirm actual native ORIG property support and archived global-query semantics.
tcl=tkinter.Tcl();support=names(RPT/'candidate_property_support_place.tsv','REF_NAME')
for ref in set(literal.values()):
    props=tcl.splitlist(support[ref]['actual_native_property_names'])
    if len(props)==1:props=tcl.splitlist(props[0])
    assert 'ORIG_CELL_NAME' in props
hook=RPT/'stage_sources/runtime_hooks.tcl';assert identity(hook)==qualified_sources[str(hook)]
hooktext=hook.read_text()
for fragment in ['get_cells -quiet -hier -filter $query','if {![dict exists $originalP $origin]} {continue}','required_origin_property_verified=$origin_supported']:
    assert fragment in hooktext

# Physical primitive counts and native packed utilization are different quantities.
utilpath=Path(membership['native_exact_hierarchy_resources']['path']);util=utilpath.read_text()
assert re.search(r'^\| Design State\s+: Fully Placed$',util,re.M)
slrrows={}
for line in util.splitlines():
    cells=[x.strip() for x in line.split('|')[1:-1]]
    if len(cells)==7 and all(re.fullmatch(r'\d+',x) for x in cells[1:4]):slrrows[cells[0]]=list(map(int,cells[1:4]))
packed={k:slrrows[k] for k in ['CLB','CLB LUTs','CLB Registers','Block RAM Tile','DSPs','URAM']}
assert packed=={'CLB':[0,0,971],'CLB LUTs':[0,0,1883],'CLB Registers':[0,0,6317],'Block RAM Tile':[0,0,6],'DSPs':[0,0,2],'URAM':[0,0,0]}
indexid=identity(OUT/'place_native_index_alias_review.json')
assert indexid['sha256']=='1d7c6d13daeb354c1ffdaf3514d79df932a38e8d75ef14236f3fab0d96cff674'
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_ACTUAL_PLACE_MEMBERSHIP_NATIVE_ORIGIN_AND_POSITION_REPLAY',
 verdict='ACCEPT_EXACT_C01_9491_ORIGINAL_SURVIVING_P_ALL_IN_SLR2_SUBSTEP',applicability='AT004 actual place graph; combined candidate compliance/cut/timing/phase receipt separately pending',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',
 facts=factid,prior_membership_review=priorid,accepted_global_POST_review=identity(OUT/'place_global_POST_review.json'),accepted_current_index_review=indexid,
 exact_root=CANDIDATE,raw_count=9514,semantic_S_count=9507,placeable_P_count=9491,raw_S_P_byte_equal_to_accepted_actual_pre_place=True,excluded_constants={'GND':4,'VCC':3},DSP_internal_count=16,DSP_physical_parent_count=2,
 full_membership_replay_matches_current_summary=True,full_reconciliation_replay_matches_current_JSON=True,original_P_equals_literal_P_equals_actual_Pblock_equals_resolved_P=True,all_lineage_original_surviving=True,replacements=0,
 native_origin_query=query,native_origin_objects=0,native_origin_property_support_verified_for_all_P_REFs=True,all_P_LOC_BEL_nonempty=True,all_P_in_SLR2=True,all_P_native_clock_regions_within_effective_range=True,native_clock_region_primitive_counts=dict(regions),
 current_effective_Pblock=pblock,five_existing_P_policy_fields_equal_pre_place=policy,actual_fixed_flag_cross_phase_deltas=fixed_flag_deltas,all_compliance_rows_SLR2_compliant_1=True,physical_primitive_REF_counts=dict(collections.Counter(literal.values())),native_candidate_packed_utilization_by_SLR=packed,
 reviewer_parser_correction=dict(failed_v1=identity(OUT/'audit_place_membership_reconciliation.py'),reason='V1 overstrictly asserted all seven policy columns byte-equal across placement; raw fixed flags are blank pre-place and explicit 0 after place for all 9491. V2 records these actual deltas and checks only the other five columns for equality; no engineering source/data changed.'),all_identity_checks=list(checks.values()),pure_parser_source=srcid,audit_program=identity(__file__),
 limits=['Candidate membership/origin/positions only; no combined candidate cut/timing/compliance/phase acceptance here.',
 'Empty origin list qualifies only with actual successful supported native query and complete original surviving membership; no guessed suffix lineage.',
 'Native SLR2 and clock-region observations establish actual placement. 9491 physical objects are not packed LUT count or routing demand/bandwidth.',
 'Resource placement alone does not establish reduced original hotspot congestion, overall place/route timing improvement, or C01 causality.',
 'Hold timing FAIL and formal reset/CDC/IO OPEN retained by separate global POST review.',
 'No EDA/native queries, DCP content read/hash, process/lock control, engineering/production edits or new agents/gates.'])
outpath=OUT/'place_membership_reconciliation_review.json'
with outpath.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
md=OUT/'place_membership_reconciliation_review.md'
with md.open('x') as f:
    f.write('''# AT004 place 成员、原生对应关系与实际SLR2落区审核

execution：当前真实文本证据重放完成；verdict：接受精确C01的9491个原始P对象全部实际落在SLR2这一子步骤；applicability：AT004 place图，combined候选compliance/cut/timing/阶段回执另审；review：独立接受，不新增停点。

RAW9514/S9507/P9491三份名称与REF账本同本轮已审pre-place逐字节相同。4 GND、3 VCC排除，16 DSP内部对象按真实映射归一为2个DSP48E2父。当前完整membership与reconciliation纯函数重放均等于工程JSON；original/literal/actual-Pblock/resolved全9491，无丢失、外来对象或replacement，lineage全部ORIGINAL_SURVIVING。

全局native ORIG_CELL_NAME查询实际执行、属性支持、Tcl code0，空origin表有成功回执支撑。所有P均有非空LOC/BEL、native SLR2及范围内clock-region。有效Pblock为CLOCKREGION_X0Y10:X5Y14、IS_SOFT/EXCLUDE_PLACEMENT/CONTAIN_ROUTING全0。5个已有物理策略字段与pre-place一致；IS_LOC_FIXED/IS_BEL_FIXED各9491项从pre-place空字段变为当前0，保留实际跨阶段差异，不声称逐字节相同。9491条位置与SLR2_compliant=1逐表互证。

独立原生端口索引审核另已通过：269端口/269组、2772别名、2170调用；167160条闭合别名事件完整配对。当前候选native packed利用率为SLR2内CLB971、LUT1883、register6317、BRAM6、DSP2、URAM0；9491是物理对象数，不是packed LUT数或路由需求。当前落区不单独证明拥塞改善、时序收益或布通。

全局hold FAIL与正式reset/CDC/IO OPEN保持。完整候选cut/timing/compliance/阶段回执另审；未调用EDA、读取或哈希DCP、控制进程/锁或修改工程文件。
''')
print(json.dumps(dict(review=identity(outpath),human=identity(md),verdict=out['verdict'],native_regions=dict(regions)),ensure_ascii=False))
