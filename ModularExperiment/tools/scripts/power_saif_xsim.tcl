proc hap_power_saif_prepare {simset} {
    if {[info exists ::env(HAP_SAIF_RAW_PATH)]} {
        # Prevent launch_simulation from consuming its default 1000 ns before
        # the controlled warm-up and capture window below.
        set_property xsim.simulate.runtime 0ns [get_filesets $simset]
    }
}

proc hap_power_saif_run {} {
    if {![info exists ::env(HAP_SAIF_RAW_PATH)]} {
        run all
        return
    }

    set warmup_ns 100
    if {[info exists ::env(HAP_SAIF_WARMUP_NS)]} {
        set warmup_ns $::env(HAP_SAIF_WARMUP_NS)
    }
    run ${warmup_ns}ns

    set scope_re {([/.])dut$}
    if {[info exists ::env(HAP_SAIF_SCOPE_REGEX)]} {
        set scope_re $::env(HAP_SAIF_SCOPE_REGEX)
    }
    set dut_scopes [list]
    foreach candidate [get_scopes -quiet -r *] {
        set candidate_name [get_property NAME $candidate]
        if {[regexp $scope_re $candidate_name]} {
            lappend dut_scopes $candidate
        }
    }
    if {[llength $dut_scopes] != 1} {
        error "SAIF scope regex '$scope_re' matched [llength $dut_scopes] scopes: $dut_scopes"
    }
    set dut_path [lindex $dut_scopes 0]
    set dut_objects [get_objects -quiet -r ${dut_path}/*]
    if {[llength $dut_objects] == 0} {
        error "no simulation objects found below SAIF DUT scope $dut_path"
    }
    puts "POWER_SAIF_DUT_SCOPE: $dut_path"
    open_saif $::env(HAP_SAIF_RAW_PATH)
    log_saif $dut_objects
    run all
    close_saif
}
