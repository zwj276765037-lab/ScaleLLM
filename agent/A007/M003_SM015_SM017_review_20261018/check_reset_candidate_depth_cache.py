from pathlib import Path
import copy,datetime,hashlib,importlib.machinery,importlib.util,json,subprocess,sys,tempfile,tkinter
ROOT=Path.cwd();OWN=ROOT/'agent/A007/M003_SM015_SM017_review_20261018';W=ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair';sys.path.insert(0,str(ROOT/'project/hardware/vivado/scripts'))
loader=importlib.machinery.SourceFileLoader('a007_reset_candidate',str(W/'m003_joint_evidence.reset_semantics.py.proposed'));sp=importlib.util.spec_from_loader(loader.name,loader);E=importlib.util.module_from_spec(sp);loader.exec_module(E)
sp=importlib.util.spec_from_file_location('a007_reset_mock',W/'test_reset_provenance.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
raw=[json.loads(x) for x in (ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT026_fresh_core_reset_provenance/reset_provenance.jsonl').read_text().splitlines()];tcl=tkinter.Tcl();groups={x['id']:x for x in raw if x['kind']=='group'}
originals=[dict(NAME=e['cell'],REF_NAME=e['REF_NAME'],bit=e['bit'],CLR_nets=groups[e['group']]['nets']) for e in raw if e['kind']=='endpoint' and e['family']=='core'];helpers=[dict(NAME=e['cell'],REF_NAME=e['REF_NAME'],bit=e['bit'],slice=e['slice'],CLR_nets=groups[e['group']]['nets']) for e in raw if e['kind']=='endpoint' and e['family']=='helper'];sources={'reset':set(tcl.splitlist(groups['R1']['nets']))}
def verify(rows):
 errors=[];E.validate_native_reset({'reset_provenance':rows},originals,helpers,sources,lambda ok,msg:errors.append(msg) if not ok else None);return errors
assert not verify(raw)
rows=copy.deepcopy(raw);node=next(x for x in rows if x['kind']=='node' and x['output_group']=='R3');next(x for x in rows if x['kind']=='input' and x['cell']==node['cell'])['group']='X1'
for i in (1,2,3):
 cell=f'added_chain_{i}';gid=f'X{i}';target=f'X{i+1}' if i<3 else 'R2'
 rows.extend([dict(kind='group',id=gid,actual_segment_count='1',nets=f'net_{gid}',direct_net=f'net_{gid}',leaf_drivers=cell+'/O',primary_ports='',source_directions='OUT'),dict(kind='node',cell=cell,REF_NAME='LUT1',INIT="2'h1",output_pin=cell+'/O',output_direction='OUT',output_group=gid),dict(kind='input',cell=cell,pin='I0',actual_pin=cell+'/I0',direction='IN',group=target)])
next(x for x in rows if x['kind']=='complete').update(nodes='6',input_pins='6',groups='7')
normal=verify(rows);reordered=verify([x for x in rows if x['kind']=='endpoint' and x['group']=='R3']+[x for x in rows if not(x['kind']=='endpoint' and x['group']=='R3')])
source=(W/'m003_joint_checks.reset_semantics.tcl.proposed').read_text();lib=source[source.index('namespace eval m003_reset'):source.index('proc m003::snapshot_body')]
extra=r'''
namespace eval m003 {}
proc m003::stream_row {section row} {if {[dict get $row kind] eq "complete"} {puts "COMPLETE $row"}}
proc m003_conn::check {token} {}
rename get_nets original_mock_get_nets
proc get_nets {args} {
 if {[lsearch -exact $args -of_objects]<0} {return [dict get $::groups [lindex $args end]]}
 return [original_mock_get_nets {*}$args]
}
obj root_out NAME independent_reset_driver/O DIRECTION OUT CLASS pin
dict set netpin root_out rn0;dict set netdrivers rn0 root_out
for {set i 1} {$i<=3} {incr i} {
 set c X$i;set n nX$i;set d dX$i;set p pX$i
 obj $n NAME $n CLASS net;dict set groups $n [list $n]
 obj $d NAME $c/O DIRECTION OUT REF_PIN_NAME O CLASS pin;dict set netpin $d $n;dict set netdrivers $n [list $d];dict set owners $d $c
 obj $c NAME $c REF_NAME LUT1 INIT 2'h1 CLASS cell
 obj $p NAME $c/I0 DIRECTION IN REF_PIN_NAME I0 CLASS pin;dict set cellinputs $c [list $p]
 dict set netpin $p [expr {$i==3?"core_net":"nX[expr {$i+1}]"}]
}
dict set netpin h0_in nX1
set r [dict create core_address {} addresses [dict create 0 {} 1 {}]]
for {set b 0} {$b<17} {incr b} {dict set r core_address $b core_ff$b;dict set r addresses 0 $b h0_ff$b;dict set r addresses 1 $b h1_ff$b}
if {[catch {m003_reset::run $r rn0 test} msg opts]} {puts stderr [dict get $opts -errorinfo];exit 1}
'''
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'check.tcl';p.write_text(M.MOCK+'\nsource {'+str(W/'frozen_shared_connectivity.tcl')+'}\n'+lib+extra);cp=subprocess.run(['tclsh',str(p),'good',td],text=True,capture_output=True)
def ident(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
out=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),candidate=[ident(W/x) for x in ('m003_joint_evidence.reset_semantics.py.proposed','m003_joint_checks.reset_semantics.tcl.proposed')],baseline_native_raw_semantics_pass=True,constructed_path='R3 -> X1 -> X2 -> X3 -> R2 -> R1(root), root depth5',constructed_scope='6nodes/6inputs/7groups, all INV and exact51 endpoints; core R2 already seen/cached before helper R3',validator_original_order_errors=normal,validator_reordered_errors=reordered,collector_returncode=cp.returncode,collector_stdout=cp.stdout,collector_stderr=cp.stderr,verdict='Longest-path depth4 bound is bypassed for cached shared subcone; order-dependent acceptance. Semantic truth remains NOT(root), so this is resource-bound proof issue, not observed AT026 malfunction.',suggested_fix='Track max remaining subcone depth/height and check current depth+height <=4 on cache reuse, or run a small bounded graph-depth DFS after collecting <=16nodes. Same principle in Python evaluator and Tcl collector; do not repeat native EDA or old suites for this CPU issue.')
q=OWN/'reset_semantic_candidate_depth_cache_counterexample.json';q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));print(json.dumps(ident(q)))
