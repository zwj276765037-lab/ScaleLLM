"""Exercise only the installed Tcl qualifier call on real saved native data."""
from pathlib import Path
import json,shutil,subprocess,sys
import physical_literal_adapter as a
out=a.HERE/'actual_OPT_Tcl_entry_replay';out.mkdir()
source=a.HW/'vivado/reports/m003_E011_R002_AT031_verified_restore_parser_to_OPT/m003_native_opt.json'
text=(a.HERE/'physical_literal_adapter.tcl').read_text().split('set h [open [file join $physical_original_dir m003_physical.tcl]',1)[0]
text=text.replace('set physical_adapter_dir [file dirname [file normalize [info script]]]','set physical_adapter_dir {'+str(a.HERE)+'}')
results=[]
for kind in ['positive','unknown_cell_literal_negative']:
    report=out/kind;report.mkdir();raw=report/'m003_native_opt.json'
    if kind=='positive':shutil.copyfile(source,raw)
    else:
        snapshot=json.loads(source.read_text());ep=next(x for x in snapshot['reset_provenance'] if x.get('kind')=='endpoint' and x['family']=='core');ep['IS_CLR_INVERTED']="1'bx";raw.write_text(json.dumps(snapshot))
    code='source {'+str(a.HW/'vivado/scripts/m003_joint_checks.tcl')+'}\n'+text+'\nm003_physical_install_qualifier\n'
    code+='set out {'+str(report)+'}\nset phase opt\nset spec_path {'+str(a.HW/'vivado/constraints/m003_joint_locality_spec.json')+'}\n'
    code+='set calls {}\nforeach line [split [info body m003::snapshot_body] \\n] {if {[string match {*m003_python*qualify --snapshot*} $line]} {lappend calls $line}}\n'
    code+='if {[llength $calls]!=1} {error {exactly one actual qualifier call required}}\nif {[catch {eval [lindex $calls 0]} message options]} {puts stderr $message;exit 1}\nputs $message\n'
    proc=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
    (report/'Tcl_stdout.log').write_text(proc.stdout);(report/'Tcl_stderr.log').write_text(proc.stderr)
    qualification=json.loads((report/'m003_qualification_opt.json').read_text())
    if kind=='positive':assert proc.returncode==0 and qualification['passed'] is True and qualification['normalized_cell_literals']==17 and a.literal.old.sha256(raw)==a.literal.old.sha256(source)
    else:assert proc.returncode==1 and qualification['passed'] is False and any('invalid or missing native pin/cell inversion boolean' in x for x in qualification['errors'])
    results.append(dict(kind=kind,exit_code=proc.returncode,qualification=a.literal.old.file_id(report/'m003_qualification_opt.json'),native_executed=False))
a.literal.save(out/'final_receipt.json',dict(completed=True,new_EDA=False,whole_original_validator_and_source_checks=True,actual_native_source=a.literal.old.file_id(source),installed_Tcl_call_executed=True,results=results,dependency_package=a.literal.old.file_id(a.HERE/'dependency_package.json'),original_core48_unchanged=True,G4_or_physical_success_claimed=False))
print(json.dumps(dict(completed=True,native_executed=False,full_actual_Tcl_positive=True,unknown_cell_negative=True)))
