"""A007 bounded independent candidate review. No native or production mutation."""
from pathlib import Path
import datetime,difflib,hashlib,importlib.util,json,subprocess,time
ROOT=Path(__file__).resolve().parents[3]
OWN=Path(__file__).resolve().parent
DIR=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/grouped_connectivity_v1/production_candidate'
def identity(p):
 b=p.read_bytes(); return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
record=json.loads((DIR/'serialization_fields_pending.json').read_text())
current=ROOT/'project/hardware/vivado/scripts/m003_joint_checks.tcl'
proposed=DIR/'m003_joint_checks.serialization_fields_pending.tcl.proposed'
for key,p in [('baseline',current),('proposed',proposed)]:
 actual=identity(p);assert actual['bytes']==record[key]['bytes'] and actual['sha256']==record[key]['sha256']
for key in ('tests','log'):
 p=Path(record['affected_CPU'][key]['path']);actual=identity(p)
 assert actual['bytes']==record['affected_CPU'][key]['bytes'] and actual['sha256']==record['affected_CPU'][key]['sha256']
old=current.read_text();new=proposed.read_text()
assert (DIR/'m003_joint_checks.tcl').read_text()==old
expected=old
changes=[('CLR_nets [pin_net $cell CLR]','CLR_nets [collection_property NAME [pin_net $cell CLR]]',2),('CE_nets $cen CE_drivers','CE_nets [collection_property NAME $cen] CE_drivers',1),('dict set control_sources write_enable [pin_net $meta_scope meta_wr_valid]','dict set control_sources write_enable [collection_property NAME [pin_net $meta_scope meta_wr_valid]]',1)]
for before,after,count in changes:
 assert expected.count(before)==count,(before,expected.count(before)); expected=expected.replace(before,after)
assert expected==new,'Candidate has changes outside the four wrappers'
# Reuse the already-reviewed supplied scope harness; add independent assertions
# at the real consumer and error-stack boundaries, not just source matching.
spec=importlib.util.spec_from_file_location('owner_field_fixture',DIR/'test_serialization_fields_pending.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
start=time.monotonic();cases=[]
def run(scope,target=False):
 script=module.script(new,scope,target)
 script=script.replace('proc get_pins {args} {return actual_pin}',r'''proc get_pins {args} {
 if {[lsearch -exact $args -leaf]>=0} {
  set i [lsearch -exact $args -of_objects]
  if {$i<0 || [lindex $args [expr {$i+1}]] ne "opaque_native_CE"} {error "CE native consumer received serialized names"}
  set ::native_ce_checked 1
 }
 return actual_pin
}''')
 script=script.replace('puts "$code|$message|[dict get $options -errorcode]"','puts [m003::jobject [dict create code $code message $message errorcode [dict get $options -errorcode] errorinfo [dict get $options -errorinfo]]]')
 if scope=='address':script+='\nif {![info exists ::native_ce_checked]} {error "actual CE native consumer was not exercised"}\n'
 r=subprocess.run(['tclsh'],input='if {[catch {\n'+script+'\n} message options]} {puts stderr [dict get $options -errorinfo];exit 1}\n',text=True,capture_output=True)
 assert r.returncode==0,r.stderr
 return json.loads(r.stdout)
for scope,fields in [('core',{'CLR_nets':'CLR'}),('address',{'CE_nets':'CE','CLR_nets':'CLR'}),('control',{'write_enable':'meta_wr_valid'})]:
 actual=run(scope)
 for field,terminal in fields.items():
  assert actual[field].split()==[f'actual_name_opaque_native_{terminal}_{i}' for i in range(600)]
  baseline=json.loads(module.run(old,scope));assert baseline[field]==f'opaque_native_{terminal}'
  cases.append({'case':scope+'/'+field,'result':'PASS','actual_NAME_values':600,'baseline_opaque_negative_control':True,'native_CE_object_consumer_checked':scope=='address'})
for scope,target in [('core','CLR'),('address','CE'),('address','CLR'),('control','meta_wr_valid')]:
 actual=run(scope,target)
 assert actual['code']=='1' and actual['message']=='actual NAME getter failed' and actual['errorcode']=='NATIVE JSONFIELD',actual
 assert 'get_property' in actual['errorinfo'] and 'collection_property NAME' in actual['errorinfo'] and 'm003::snapshot_body synth unused' in actual['errorinfo'],actual
 cases.append({'case':scope+'/'+target+'/getter_error_stack','result':'PASS','original_errorcode_message_and_stack':True})
result={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'offline_independent_review_completed','verdict':'four_serialization_wrappers_supported_by_source_and_CPU_boundary_evidence','review':'accepted_with_native_applicability_limit','applicability':'Exact d915 candidate only; not applied to frozen AT024; actual nonclock cardinalities/truncation unknown','identities':{name:identity(path) for name,path in [('delivery',DIR/'serialization_fields_pending.json'),('baseline',current),('proposed',proposed),('supplied_test',DIR/'test_serialization_fields_pending.py'),('supplied_log',DIR/'serialization_fields_pending_CPU.log'),('independent_review_script',Path(__file__))]},'exact_four_wrapper_diff':True,'unchanged_native_pin_net_guards_and_consumers':True,'independent_boundary_cases':cases,'seconds':time.monotonic()-start,'supplied_CPU_evidence':{'functions':2,'log_runner_seconds':0.204,'delivery_total_elapsed_seconds':record['affected_CPU']['seconds'],'rerun_unchanged_suite':False},'limits':['CPU opaque-token model is not a native collection performance or cardinality measurement','No hot edit or stop of AT024','No fullgraph/G4/physical acceptance from this review'],'G4':False}
p=OWN/'AT024_serialization_fields_pending_independent_review.json'
with p.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'receipt':identity(p),'case_count':len(cases),'seconds':result['seconds']}))
