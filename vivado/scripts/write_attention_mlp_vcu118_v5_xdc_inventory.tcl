# Export the exact implementation constraint file set with Vivado's own
# SCOPED_TO_REF/SCOPED_TO_CELLS metadata.  This is the authoritative active
# inventory consumed by the post-route gate; the shell source-tree scan is an
# additional preflight, not the signoff classifier.
set out [file normalize $::env(HAP_XDC_INVENTORY)]
set core_refs {
    hap_attention_mlp_board_core
    hap_attention_mlp_production_core
    hap_mlp_serial_ddr_command16_v5_s45
    hap_mlp_shared_dual_slice16x12_s43_s45
    hap_mlp_shared_local_slice8x12_s43_s45
    hap_a8w4_slice8x12_group_s36
}
set user_xdc_name attention_mlp_vcu118_board_v5.xdc
set fp [open $out w]
puts $fp "class|file|sha256|false_path|datapath_only|scoped_ref_count|scoped_cells_count|scoped_ref_values|scoped_cell_values|core_selector_hits|scope_safe|active_in_run"
set seen {}
foreach file [get_files -quiet -all -compile_order constraints \
        -used_in implementation] {
    set path [file normalize [get_property NAME $file]]
    if {[lsearch -exact $seen $path] >= 0 || ![file exists $path] ||
        ![file isfile $path]} {continue}
    lappend seen $path
    set fh [open $path r]
    set text [read $fh]
    close $fh
    set command ""
    set false_count 0
    set datapath_count 0
    set core_hits 0
    foreach raw [split $text "\n"] {
        set line [string trim $raw]
        if {$command eq "" && ($line eq "" ||
            [string index $line 0] eq "#")} {continue}
        append command $raw "\n"
        if {![info complete $command]} {continue}
        set flat [string map [list "\n" " "] $command]
        set forbidden 0
        if {[regexp -nocase \
                {(^|[;[:space:]])set_false_path([;[:space:]]|$)} $flat]} {
            incr false_count
            set forbidden 1
        }
        if {[regexp -nocase -- {-datapath_only([;[:space:]]|$)} $flat]} {
            incr datapath_count
            set forbidden 1
        }
        if {$forbidden} {
            foreach selector [concat $core_refs {/core/inst/ core/inst/}] {
                if {[string first $selector $flat] >= 0} {
                    incr core_hits
                    break
                }
            }
        }
        set command ""
    }
    if {[string trim $command] ne ""} {
        error "Incomplete command in active XDC: $path"
    }

    set scoped_ref [get_property -quiet SCOPED_TO_REF $file]
    set scoped_cells [get_property -quiet SCOPED_TO_CELLS $file]
    set scoped_ref_count [llength $scoped_ref]
    set scoped_cells_count [llength $scoped_cells]
    set scoped_ref_values [expr {$scoped_ref_count == 0 ? "-" :
        [join $scoped_ref ,]}]
    set scoped_cell_values [expr {$scoped_cells_count == 0 ? "-" :
        [join $scoped_cells ,]}]
    if {[string first "|" $scoped_ref_values] >= 0 ||
        [string first "|" $scoped_cell_values] >= 0} {
        error "Illegal pipe in active XDC scope: $path"
    }
    set tail [file tail $path]
    if {$tail eq $user_xdc_name} {
        set class USER
    } elseif {[string match "*/ip/*" $path] ||
        [string match "*.gen/sources_1/bd/*" $path]} {
        set class VENDOR_IP
    } else {
        set class UNKNOWN
    }

    # For an exception-bearing vendor XDC, a scoped REF/CELL must be present
    # and must not select a production-core module reference.  Broad global
    # vendor exceptions are fail-closed even if their text has no core name.
    set scope_safe 1
    if {$class eq "VENDOR_IP" &&
        ($false_count > 0 || $datapath_count > 0)} {
        foreach scope [concat $scoped_ref $scoped_cells] {
            foreach core_ref $core_refs {
                if {[string first $core_ref $scope] >= 0} {
                    set scope_safe 0
                }
            }
        }
    }
    # Some generated IP XDCs become part of an IP OOC DCP and then appear in
    # the parent compile order without retained file scope.  Preserve them in
    # the inventory, but defer the definitive scope decision to the exported
    # valid/merged exception selector audit after the board is routed.
    if {$class ne "VENDOR_IP" &&
        ($false_count > 0 || $datapath_count > 0)} {
        set scope_safe 0
    }
    if {$core_hits > 0} {set scope_safe 0}
    set sha [lindex [exec sha256sum $path] 0]
    puts $fp [join [list $class $path $sha $false_count $datapath_count \
        $scoped_ref_count $scoped_cells_count $scoped_ref_values \
        $scoped_cell_values $core_hits $scope_safe 1] |]
}
close $fp
if {[llength $seen] == 0} {error "Active implementation XDC inventory is empty"}
