set ::env(HAP_REPORT_DIR) {/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/agent/A007/M003_SM015_SM017_review_20261018/R002_native_entry_fix_v3_cpu}
set ::env(HAP_PROJECT_DIR) {/fixture/project}
set ::env(HAP_SYNTH_REPORT_DIR) {/fixture/prior-report}
set ::env(HAP_SYNTH_ATTEMPT_DIR) {/fixture/prior-attempt}
source {/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/scripts/m003_joint_checks.tcl}

set ::env(HAP_M003_RECOVERED_SYNTHESIS) 1
proc get_runs {args} {set x {};for {set i 0} {$i<23} {incr i} {lappend x run$i};return $x}
rename m003::prop m003::actual_prop
proc m003::prop {object property} {
 switch $property {
  NAME {return $object}
  DIRECTORY {return /fixture/project/runs/$object}
  STATUS {if {$object eq "run22"} {return Out-of-date};return {synth_design Complete!}}
  PROGRESS {return 100%}
  NEEDS_REFRESH {return [expr {$object eq "run22"}]}
  default {error "unexpected property $property"}
 }
}
proc require_complete_run {args} {error "recovery branch must call content guard"}
rename m003_python actual_m003_python
proc m003_python {args} {set ::captured $args}
m003::require_synthesis_runs
puts [lrange $::captured 1 end]
