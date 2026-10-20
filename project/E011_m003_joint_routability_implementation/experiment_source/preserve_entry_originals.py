from pathlib import Path
import json,hashlib,difflib
root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');here=Path(__file__).resolve().parent;out=here/'prechange_entry';out.mkdir(exist_ok=True)
expected={Path(e['path']).name:e for e in json.loads((root/'agent/A006/M003_SM014_design_20261018/design_input_identities.json').read_text())['production_inputs']}
base=root/'project/hardware/vivado/scripts';receipt=[]
for name in ['create_vcu118_board.tcl','build_vcu118_board.tcl','m002_physical.tcl','m002_diagnostic_common.tcl']:
 p=base/name;current=p.read_text();old=current
 if name=='create_vcu118_board.tcl':
  a=old.index('\nset m003_xdc ');b=old.index('\nset validate_only',a);old=old[:a]+old[b:]
  old=old.replace(' $m003_xdc {*}$m003_inputs','')
  a=old.index('\nadd_files -norecurse -fileset constrs_1 $m003_xdc');b=old.index('\n# Legacy native025',a);old=old[:a]+old[b:]
 elif name=='build_vcu118_board.tcl':
  a=old.index('    foreach path [concat [glob -nocomplain [file join $root vivado constraints m003_*]]');b=old.index('    foreach path [glob -nocomplain -directory [file join $root vivado manifests]',a);old=old[:a]+old[b:]
  old=old.replace('    m003_joint_locality.xdc\n','')
  old=old.replace('source [file join $script_dir m003_joint_checks.tcl]\nm003::require_project\n','')
  a=old.index('# Synthesis-only XDC registration');b=old.index('close_design\n\nif {$stage eq "place"}',a);old=old[:a]+old[b:]
 elif name=='m002_physical.tcl':
  old=old.replace(' ddr_timing_recovery.xdc m003_joint_locality.xdc}', ' ddr_timing_recovery.xdc}')
  old=old.replace('source [file join $script_dir m003_joint_checks.tcl]\nm003::require_project\n','')
  old=old.replace('if {([info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation") || [info exists ::env(HAP_M003_ACTIVE)]} {','if {[info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation"} {')
 else:
  a=old.index('    if {[info exists ::env(HAP_M003_ACTIVE)]} {');b=old.index('    if {$point in {place physopt route}} {',a);old=old[:a]+old[b:]
 digest=hashlib.sha256(old.encode()).hexdigest();assert digest==expected[name]['sha256'],(name,digest,expected[name])
 target=out/name;assert not target.exists();target.write_text(old)
 (here/(name+'.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),current.splitlines(True),fromfile='prechange/'+name,tofile=str(p))))
 receipt.append(dict(path=str(p),original=expected[name],preserved=str(target),original_reconstruction='exact inverse of recorded narrow patches, SHA verified against frozen SM014 input; original not overwritten'))
(here/'entry_originals_preserved.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(verified=len(receipt))))
