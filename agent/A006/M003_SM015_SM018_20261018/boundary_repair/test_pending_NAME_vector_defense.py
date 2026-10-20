from pathlib import Path
import json,hashlib,subprocess,sys,datetime,importlib.util,unittest
r=Path.cwd();w=r/'agent/A006/M003_SM015_SM018_20261018/boundary_repair';p=r/'project/hardware/vivado/scripts/m003_joint_checks.tcl';s=p.read_text();old='if {![llength $nets] || $net ni $nets || [llength $nets]!=[llength [lsort -unique $nets]] || [llength $names]!=[llength [lsort -unique $names]]}'
new='if {![llength $nets] || $net ni $nets || [llength $names]!=[llength $nets] || {} in $names || [llength $nets]!=[llength [lsort -unique $nets]] || [llength $names]!=[llength [lsort -unique $names]]}'
assert s.count(old)==1;pending=w/'m003_joint_checks.NAME_vector_guard.pending.tcl';pending.write_text(s.replace(old,new))
spec=importlib.util.spec_from_file_location('boundary_test',w/'test_boundary_repair.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);helper=pending.read_text().split('proc m003::boundary_net',1)[1].split('proc m003::snapshot_body',1)[0];helper='proc m003::boundary_net'+helper
prefix=m.PREFIX.replace(' };return $result',' };return $result')
needle='set result {};foreach o $objects {lappend result [dict get $::props $o $key]};return $result'
replacement='''set result {};foreach o $objects {lappend result [dict get $::props $o $key]}
 if {$key eq "NAME" && [llength $objects]>1} {
  if {$::case eq "short_NAME"} {return [lrange $result 0 end-1]}
  if {$::case eq "empty_NAME"} {lset result end {}}
 }
 return $result'''
assert needle in prefix;prefix=prefix.replace(needle,replacement)
rows=[]
for label,source in [('frozen_current',m.HELPERS),('offline_pending',helper)]:
 for case in ['good','short_NAME','empty_NAME']:
  result=m.tcl('set case '+case+'\n'+prefix+m.ONE+m.PROP+source+'\nset net [m003::boundary_net $anchor];m003::boundary_names S $net\n')
  rows.append(dict(source=label,case=case,exit_code=result.returncode,stderr=result.stderr))
assert [x['exit_code'] for x in rows[:3]]==[0,0,0];assert [x['exit_code'] for x in rows[3:]]==[0,1,1]
def ident(p):return dict(path=str(p.relative_to(r)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
receipt=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='OFFLINE ONLY; current AT025 frozen production not modified. Synthetic API short/empty NAME is a static defense gap, not observed native failure. On successful AT025 compare six control_source NAME vectors with native trace segment_count and anchor membership; current clock has separate actual group proof.',frozen_current=ident(p),pending=ident(pending),checks=rows,passed=True,production_applied=False,extra_native_run=False)
(w/'pending_NAME_vector_defense_CPU_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
