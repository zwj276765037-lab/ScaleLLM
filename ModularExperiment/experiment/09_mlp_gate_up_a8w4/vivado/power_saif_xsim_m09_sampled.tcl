# SAIF capture specialized for the 96-lane M09 physical wrapper.
#
# Recursively materializing every simulation object below this DUT expands to
# more than 55k scopes and did not finish object enumeration in 16 minutes.
# Capture all wrapper/core boundary objects plus twelve structurally identical
# lanes distributed across every column pair and twelve activation rows.  The
# remaining implemented lane internals are handled by Vivado's probabilistic
# propagation and the result is explicitly labelled sampled-internal SAIF.

proc hap_power_saif_prepare {simset} {
    if {[info exists ::env(HAP_SAIF_RAW_PATH)]} {
        set_property xsim.simulate.runtime 0ns [get_filesets $simset]
    }
}

proc m09_add_direct_objects {scope_name object_var} {
    upvar 1 $object_var objects
    current_scope $scope_name
    foreach object [get_objects -quiet *] {
        lappend objects $object
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
    set all_scopes [get_scopes -quiet -r *]
    set dut_scopes [list]
    foreach candidate $all_scopes {
        set candidate_name [get_property NAME $candidate]
        if {[regexp $scope_re $candidate_name]} {
            lappend dut_scopes $candidate_name
        }
    }
    if {[llength $dut_scopes] != 1} {
        error "SAIF scope regex '$scope_re' matched [llength $dut_scopes] scopes: $dut_scopes"
    }
    set dut_path [lindex $dut_scopes 0]
    set wrapper_path ${dut_path}/u_wrapper

    set core_path ""
    foreach candidate $all_scopes {
        set candidate_name [get_property NAME $candidate]
        # Scope names contain escaped identifiers (leading backslashes) and
        # generated indices.  Treating the full path as a Tcl glob therefore
        # misinterprets those characters.  Use a literal prefix test instead.
        if {[string first "${wrapper_path}/" $candidate_name] == 0 &&
                [regexp {u_core[[:space:]]*$} $candidate_name]} {
            set core_path $candidate_name
            break
        }
    }
    if {$core_path eq ""} {
        error "could not locate M09 u_core below $wrapper_path"
    }

    set dut_objects [list]
    m09_add_direct_objects $dut_path dut_objects
    m09_add_direct_objects $wrapper_path dut_objects
    m09_add_direct_objects $core_path dut_objects

    set sampled_lanes 0
    set sampled_lane_names [list]
    foreach candidate $all_scopes {
        set candidate_name [get_property NAME $candidate]
        if {[string first "${core_path}/" $candidate_name] != 0} {
            continue
        }
        if {[regexp {g_row\[([0-9]+)\]\.g_pair\[([0-9]+)\]\.u_lane[[:space:]]*$} \
                $candidate_name -> row pair] &&
                $row < 12 && $pair == ($row % 6)} {
            current_scope $candidate_name
            foreach object [get_objects -quiet -r *] {
                lappend dut_objects $object
            }
            lappend sampled_lane_names [string trim $candidate_name]
            incr sampled_lanes
        }
    }
    if {$sampled_lanes != 12} {
        error "expected 12 sampled M09 lanes, found $sampled_lanes: $sampled_lane_names"
    }
    if {[llength $dut_objects] == 0} {
        error "no simulation objects selected for M09 sampled SAIF"
    }

    puts "POWER_SAIF_DUT_SCOPE: $dut_path"
    puts "POWER_SAIF_CAPTURE_MODE: sampled_internal_12_of_96_lanes"
    puts "POWER_SAIF_SAMPLED_LANES: $sampled_lane_names"
    puts "POWER_SAIF_OBJECT_COUNT: [llength $dut_objects]"
    open_saif $::env(HAP_SAIF_RAW_PATH)
    log_saif $dut_objects
    run all
    close_saif
}
