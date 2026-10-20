# Diagnostic capture cannot turn a failed native route into a successful stage.
proc m002_failed_exclusive_put {path value} {
    set handle [open $path {WRONLY CREAT EXCL}]
    puts $handle $value
    close $handle
}
proc m002_capture_failed_route {code result options command} {
    set out $::env(HAP_REPORT_DIR)
    set original [file join $out route_failed_original_error.tcllist]
    catch {m002_failed_exclusive_put $original [list code $code result $result options $options command $command epoch [clock seconds] disposition diagnostic_failed_route]}
    # A second invocation must never overwrite evidence from the first failure.
    if {[catch {open [file join $out route_failed_capture_receipts.tsv] {WRONLY CREAT EXCL}} handle]} {
        puts "M002_FAILED_ROUTE_CAPTURE_UNAVAILABLE $handle"
        return
    }
    puts $handle "label\tcode\tstarted_epoch\tended_epoch\tresult"
    set design_code [catch {current_design} design]
    if {$design_code || $design eq ""} {
        puts $handle "design_unavailable\t1\t[clock seconds]\t[clock seconds]\tno_open_design"
        close $handle
        return
    }
    foreach {label filename call} {
        checkpoint route_failed.dcp {write_checkpoint}
        route_status route_failed_status.rpt {report_route_status -file}
        timing route_failed_timing.rpt {report_timing_summary -file}
        congestion route_failed_congestion.rpt {report_design_analysis -congestion -file}
        drc route_failed_drc.rpt {report_drc -file}
    } {
        set path [file join $out $filename]
        set start [clock seconds]
        set rc [catch {
            if {[file exists $path]} {error "existing_evidence_not_overwritten: $path"}
            uplevel #0 [list {*}$call $path]
        } message capture_options]
        puts $handle "$label\t$rc\t$start\t[clock seconds]\t[string map [list \n { } \t { }] $message]"
        flush $handle
        if {$rc} {catch {m002_failed_exclusive_put [file join $out route_failed_${label}_error.tcllist] [list result $message options $capture_options]}}
    }
    close $handle
}
proc m002_route_with_failure_capture {command} {
    set code [catch {uplevel 1 $command} result options]
    if {$code} {
        # Capture itself is best effort. Always rethrow the original options.
        catch {m002_capture_failed_route $code $result $options $command} capture_issue
        return -options $options $result
    }
    return $result
}
proc m002_install_route_failure_capture {} {
    if {[llength [info commands ::m002_native_route_design]]} {return}
    rename ::route_design ::m002_native_route_design
    proc ::route_design {args} {
        return [m002_route_with_failure_capture [list ::m002_native_route_design {*}$args]]
    }
}
