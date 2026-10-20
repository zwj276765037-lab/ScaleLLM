#!/usr/bin/env python3
"""Small synthetic attribution oracle and source-scope/syntax checks; no EDA."""
import csv,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def tab(p,header,data):
    with p.open('w') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(header);w.writerows(data)
def main():
    for p in HERE.glob('*.py'):compile(p.read_text(),str(p),'exec')
    tcl=(HERE/'attribution.tcl').read_text()
    for prohibited in ['opt_design','place_design','phys_opt_design','route_design','write_checkpoint','read_xdc','set_property']:
        assert not any(line.strip().startswith(prohibited+' ') for line in tcl.splitlines())
    check=subprocess.run(['tclsh'],input='set f [open {'+str(HERE/'attribution.tcl')+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 1}\nputs TCL_COMPLETE\n',text=True,capture_output=True,check=True)
    assert 'TCL_COMPLETE' in check.stdout
    actual_alias=tcl[tcl.index('proc alias '):tcl.index('proc flushpins ')]
    fixture='''
set ::mocknet {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_shared_compute/parent_head_r[0]}
set ::mockname $::mocknet
proc get_nets {args} {return [list $::mocknet]}
proc vals {args} {return $::mockname}
proc row {channel xs} {lappend ::records $xs}
set ::records [list]
set ::aliases [dict create];set ::segments [dict create]
set ::aliasIdentityPairs 0;set ::aliasRepresentationDifferences 0
set ::aliasIdentity [open /dev/null w];set ::aliasout ignored
'''+actual_alias+'''
set canonical [alias $::mocknet]
if {$canonical ne $::mocknet || $::aliasIdentityPairs!=1 || $::aliasRepresentationDifferences!=1} {error "representation false-positive repair did not preserve native element identity"}
set ::aliases [dict create];set ::segments [dict create]
set ::mockname DIFFERENT_NATIVE_NAME
set code [catch {alias $::mocknet} result]
if {!$code || ![string match {*element identity mismatch*} $result]} {error "real identity mismatch was not rejected"}
set ::mockname [list $::mocknet EXTRA]
set code [catch {alias $::mocknet} result]
if {!$code || ![string match {*cardinality*} $result]} {error "cardinality mismatch was not rejected"}
close $::aliasIdentity
puts ALIAS_DELTA_ORACLE_PASS
'''
    check=subprocess.run(['tclsh'],input=fixture,text=True,capture_output=True,check=True)
    assert 'ALIAS_DELTA_ORACLE_PASS' in check.stdout and not check.stderr,check.stderr
    with tempfile.TemporaryDirectory() as td:
        out=Path(td);base='b/u_compute'
        plan=dict(normalization_base=base,driver_normalization='test frozen normalization',representative_nets_per_group=16)
        (out/'plan.json').write_text(json.dumps(plan))
        tab(out/'cells.tsv',['name','REF_NAME','LOC','BEL','IS_PRIMITIVE'],[[base+'/a/d','FDRE','SITE0','A',1],[base+'/b/l','LUT1','SITE1','A',1],[base+'/a/e','FDRE','SITE0','B',1]])
        tab(out/'sites.tsv',['site','SLR','clock_region'],[['SITE0','SLR0','CR0'],['SITE1','SLR1','CR1']])
        tab(out/'net_inventory.tsv',['canonical','aliases','conflict','seed_tags'],[['n1',2,1,'FIXED'],['n2',1,1,''],['n3',1,1,''],['n4',1,1,''],['n5',1,0,'FIXED']])
        tab(out/'raw_conflicts.tsv',['native_net'],[['n1'],['n1_alias'],['n2'],['n3'],['n4']])
        ends=[]
        def ep(n,cell,pin,d):ends.append([n,'LEAF_PIN',cell+'/'+pin,d,pin,0,cell])
        ep('n1',base+'/a/d','Q','OUT');ep('n1',base+'/b/l','I0','IN')
        ep('n2',base+'/b/l','I0','IN')
        ep('n3',base+'/a/d','Q','OUT');ep('n3',base+'/a/e','Q','OUT');ep('n3',base+'/b/l','I0','IN')
        ep('n4',base+'/b/l','IO','INOUT')
        ep('n5',base+'/a/d','Q','OUT');ep('n5',base+'/b/l','I0','IN')
        tab(out/'endpoints.tsv',['canonical','kind','name','DIRECTION','REF_PIN_NAME','IS_CLOCK','owner'],ends)
        subprocess.run(['/usr/bin/python3',str(HERE/'aggregate.py'),'--out',str(out),'--plan',str(out/'plan.json')],check=True,capture_output=True,text=True)
        c=json.loads((out/'unknowns_and_coverage.json').read_text())
        assert c['native_raw_conflict_objects']==5 and c['canonical_conflict_nets']==4
        assert c['primary_group_sum']==4 and c['primary_groups']==4
        assert c['unknown_driver_nets']==c['multidriver_nets']==c['inout_ambiguous_nets']==1
        assert c['top20_plus_supplemental_union']==4 and c['supplemental_unique_conflict_nets']==1
        assert c['reconciliation']=='DIFFERENT_COUNTS_RETAINED_REQUIRES_REVIEW'
        fs=list(csv.DictReader((out/'failed_nets.tsv').open(),delimiter='\t'))
        assert next(r for r in fs if r['canonical']=='n1')['load_SLRs']=='SLR1'
        assert len(fs)==4 and all(r['canonical']!='n5' for r in fs)
    print('CPU_ONLY_PASS actual Tcl alias body: representation-only difference accepted, real NAME mismatch and cardinality mismatch rejected; syntax/read-only-command scope, native-alias count distinction, unique groups, explicit unknown/multidriver/inout, overlapping supplemental union, source/load SLR attribution; no native EDA.')
if __name__=='__main__':main()
