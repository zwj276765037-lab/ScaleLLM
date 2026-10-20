"""New bounded CPU fixtures for offline boundary-vector defense/export audit only."""
from pathlib import Path
import base64,copy,datetime,hashlib,importlib.util,json,subprocess,time
ROOT=Path.cwd(); OWN=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'; A=ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair'
sp=importlib.util.spec_from_file_location('independent_export_checker',A/'check_native_boundary_exports.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
rows=[];started=time.monotonic()
def check(label,fn):
 value=fn();assert value is not False,label;rows.append(dict(case=label,passed=True,detail=value))
def reject(fn):
 try:fn()
 except (ValueError,KeyError) as e:return dict(rejected=True,error=str(e))
 raise AssertionError('invalid evidence accepted')
def fixture():
 cs={k:' '.join([v]+[f'alias/{k}[{i}]' for i in range(599)]) for k,v in m.ANCHORS.items()};cs.update(clock_group='Gclock',clock_pin='clock_input')
 raw=dict(schema='M003_native_grouped_stream_v1',meta=dict(kind='native'),cells=[],helper_pins=[],memory_pins=[],control_sources=cs,connection_groups=[dict(id='Gclock',nets=[m.CORE+'/core_clk','clock_net'],canonical_top_net='clock_net',leaf_drivers=[],driver_cells=[],driver_refs=[],primary_ports=['clock_input'],primary_port_directions=['IN'])],connection_endpoints=[dict(pin='clock_input',group='Gclock',direct_nets=['clock_net'])],connection_counts=dict(groups=1,endpoints=1),connection_api_counts={k:dict(calls=1) for k in ['segments','drivers','canonical','ports']})
 ev=[dict(event='boundary_source_selected',tag=k,anchor=v,segment_count='600') for k,v in m.ANCHORS.items()];ev.append(dict(event='boundary_clock_source',anchor=m.CORE+'/core_clk',endpoint='clock_input',group='Gclock'));return raw,ev
raw,ev=fixture();before=copy.deepcopy(raw);out=m.verify(raw,ev)
check('six_600_alias_vectors_and_primary_IN_clock',lambda: {'counts':[r['exported_NAME_count'] for r in out['nonclock_sources']]} if all(r['exported_NAME_count']==600 for r in out['nonclock_sources']) else False)
check('strict_decoder_does_not_mutate_raw_export',lambda:raw==before)
check('Tcl_list_quoting_braces_whitespace_backslash_and_brackets',lambda:m.names(r'{space name} {brace{name}} a\ b {bus[0]} {back\slash}')==['space name','brace{name}','a b','bus[0]','back\\slash'])
check('malformed_Tcl_list_rejected',lambda:reject(lambda:m.names('{unterminated')))
# Forge an internally consistent boundary endpoint reference to an actual clock sink.
# The strict decoder accepts the reference coverage, but source membership must reject it.
bad,e=fixture();bad['control_sources']['clock_pin']='sink/C';bad['connection_endpoints'][0]['pin']='sink/C';e[-1]['endpoint']='sink/C'
check('consistent_sink_reference_cannot_impersonate_actual_clock_source',lambda:reject(lambda:m.verify(bad,e)))
# Add another independently bound group; K is the real table size, not assumed 1.
r2,e2=fixture();r2['cells']=[dict(NAME='otherFF',role='payload',C_nets_group='Gother')];r2['connection_groups'].append(dict(id='Gother',nets=['otherclk'],canonical_top_net='otherclk',leaf_drivers=['otherbuf/O'],driver_cells=['otherbuf'],driver_refs=['BUFGCE'],primary_ports=[],primary_port_directions=[]));r2['connection_endpoints'].append(dict(pin='otherFF/C',group='Gother',direct_nets=['otherclk']));r2['connection_counts']=dict(groups=2,endpoints=2)
for v in r2['connection_api_counts'].values():v['calls']=2
check('actual_K_two_groups_accepted',lambda:m.verify(r2,e2)['passed'])
r2['connection_api_counts']['ports']['calls']=1
check('underreported_API_count_also_rejected',lambda:reject(lambda:m.verify(r2,e2)))
# Execute only the real candidate boundary_names procedure with an independent API stub.
pending=A/'m003_joint_checks.NAME_vector_guard.pending.tcl';src=pending.read_text();proc='proc m003::boundary_names'+src.split('proc m003::boundary_names',1)[1].split('proc m003::snapshot_body',1)[0]
prefix='''namespace eval m003 {}
namespace eval m003_conn {}
proc m003_conn::bounded_objects {value label} {return $value}
proc m003_conn::event {kind value} {set ::event $kind}
proc get_nets {args} {return {anchor alias}}
proc get_property {key obj} {if {$key eq "CLASS"} {return net};return $obj}
proc m003::collection_property {key objects} {return $::returned_names}
'''
for case,names,expected in [('good','anchor alias',0),('overlong_NAME','anchor alias foreign',1),('empty_first_NAME','{} alias',1),('duplicate_NAME','anchor anchor',1)]:
 script=prefix+proc+'\nset returned_names {'+names+'}\nif {[catch {m003::boundary_names S anchor} result options]} {puts stderr $result;exit 1}\nputs $result\n'
 p=subprocess.run(['tclsh'],input=script,text=True,capture_output=True)
 assert p.returncode==expected,(case,p.returncode,p.stdout,p.stderr)
 rows.append(dict(case='pending_guard_'+case,passed=True,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
def identity(p):b=p.read_bytes();return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
receipt=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,elapsed_seconds=time.monotonic()-started,checks=rows,identities=[identity(p) for p in [Path(__file__),pending,A/'check_native_boundary_exports.py',ROOT/'project/hardware/vivado/scripts/m003_snapshot_decode.py',ROOT/'project/hardware/vivado/scripts/m003_joint_checks.tcl']],scope='Independent new CPU fixtures only; no original 128 regressions or AT023 native tables repeated. Offline candidate not applied; actual AT025 export evidence still pending.',production_mutation=False,EDA=False)
with (OWN/'AT025_pending_guard_checker_independent_CPU_receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps({'passed':True,'checks':len(rows),'elapsed_seconds':receipt['elapsed_seconds']}))
