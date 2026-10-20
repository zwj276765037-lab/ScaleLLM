#!/usr/bin/env python3
"""Small synthetic attribution oracle and source-scope/syntax checks; no EDA."""
import csv,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def tab(p,header,data):
    with p.open('w') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(header);w.writerows(data)
def scalar_property_oracle(tcl):
    # Exact two-backslash native NAME saved in AT002's direct scalar row and
    # native handle. The failed vals-parsed NAME lost one literal backslash.
    saved_name=r'scalellm_vcu118_f05_bd_i/xdma_0/inst/udma_wrapper/dma_top/axi4mm_bridge_top_inst/axi4mm_axi_mm_master_top_soft_dma_inst/mi_h2c_rd_brg_dat\\.radr[4]_INST_0_i_1_n_0'
    assert saved_name.count('\\')==2 and len(saved_name)==162
    actual_vals=tcl[tcl.index('proc vals '):tcl.index('proc exact ')]
    actual_alias=tcl[tcl.index('proc alias '):tcl.index('proc flushpins ')]
    fixture='''
set ::exact [encoding convertfrom utf-8 [binary decode hex @EXACT_HEX@]]
set ::meta [encoding convertfrom utf-8 [binary decode hex @META_HEX@]]
set ::props [dict create scalar $::exact meta $::meta empty {} left $::exact right $::meta]
set ::calls 0;set ::fallback 0;set ::records [list];set ::align ignored
proc row {channel xs} {lappend ::records $xs}
proc get_property {quiet prop objects} {
    incr ::calls
    if {$quiet ne "-quiet" || $prop ne "NAME"} {error "unexpected getter fixture request"}
    if {[dict exists $::props $objects]} {return [dict get $::props $objects]}
    if {$::fallback} {return ONE_WRONG_VECTOR_ITEM}
    set result [list]
    foreach object $objects {lappend result [dict get $::props $object]}
    return $result
}
'''+actual_vals+'''
if {[llength [vals [list] NAME]]!=0 || $::calls!=0} {error "empty object collection must not call getter"}
foreach {object expected} [list scalar $::exact meta $::meta] {
    set got [vals [list $object] NAME]
    if {[llength $got]!=1 || [lindex $got 0] ne $expected} {error "singleton scalar bytes changed: $object"}
}
set got [vals [list empty] NAME 1]
if {[llength $got]!=1 || [lindex $got 0] ne ""} {error "optional empty scalar lost its element"}
if {![catch {vals [list empty] NAME} why] || $why ne "required property empty: NAME"} {error "required empty scalar accepted"}
set got [vals [list left right] NAME]
if {[llength $got]!=2 || [lindex $got 0] ne $::exact || [lindex $got 1] ne $::meta} {error "vector values changed"}
set ::fallback 1
set got [vals [list left right] NAME]
if {[llength $got]!=2 || [lindex $got 0] ne $::exact || [lindex $got 1] ne $::meta || [llength $::records]!=1} {error "scalar alignment fallback failed"}
set ::fallback 0
set got [vals [list left empty] NAME 1]
if {[llength $got]!=2 || [lindex $got 1] ne ""} {error "optional vector empty element changed"}
if {![catch {vals [list left empty] NAME} why] || $why ne "required property empty: NAME"} {error "required vector empty accepted"}
# Exercise the actual vals and actual alias bodies together with a scalar
# getter, including saved escaped NAME and a true identity mismatch.
set ::mocknet $::exact;dict set ::props $::mocknet $::exact
proc get_nets {args} {return [list $::mocknet]}
set ::aliases [dict create];set ::segments [dict create]
set ::aliasIdentityPairs 0;set ::aliasRepresentationDifferences 0
set ::aliasIdentity [open /dev/null w];set ::aliasout ignored
'''+actual_alias+'''
set canonical [alias $::mocknet]
if {$canonical ne $::exact || $::aliasIdentityPairs!=1} {error "integrated escaped alias bytes changed"}
set ::aliases [dict create];set ::segments [dict create]
dict set ::props $::mocknet DIFFERENT_NATIVE_NAME
if {![catch {alias $::mocknet} why] || ![string match {*element identity mismatch*} $why]} {error "integrated actual NAME mismatch accepted"}
close $::aliasIdentity
puts SCALAR_PROPERTY_AND_ALIAS_ORACLE_PASS
'''
    fixture=fixture.replace('@EXACT_HEX@',saved_name.encode().hex()).replace('@META_HEX@','white space {unclosed [index] \\ slash; $var'.encode().hex())
    check=subprocess.run(['tclsh'],input=fixture,text=True,capture_output=True,check=True)
    assert 'SCALAR_PROPERTY_AND_ALIAS_ORACLE_PASS' in check.stdout and not check.stderr,check.stderr
def main():
    for p in HERE.glob('*.py'):compile(p.read_text(),str(p),'exec')
    tcl=(HERE/'attribution.tcl').read_text()
    for prohibited in ['opt_design','place_design','phys_opt_design','route_design','write_checkpoint','read_xdc','set_property']:
        assert not any(line.strip().startswith(prohibited+' ') for line in tcl.splitlines())
    check=subprocess.run(['tclsh'],input='set f [open {'+str(HERE/'attribution.tcl')+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 1}\nputs TCL_COMPLETE\n',text=True,capture_output=True,check=True)
    assert 'TCL_COMPLETE' in check.stdout
    scalar_property_oracle(tcl)
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
    print('CPU_ONLY_PASS actual Tcl vals body: exact saved 162-byte/two-backslash scalar, whitespace/list metacharacters, zero objects, optional/required empty scalar/vector, proper vector and scalar alignment fallback; actual vals+alias integration retains bytes and rejects true NAME mismatch. Existing actual alias body accepts representation-only difference, rejects NAME/cardinality mismatch. Syntax/read-only scope, synthetic unique-group/unknown/union oracle unchanged; no native EDA.')
if __name__=='__main__':main()
