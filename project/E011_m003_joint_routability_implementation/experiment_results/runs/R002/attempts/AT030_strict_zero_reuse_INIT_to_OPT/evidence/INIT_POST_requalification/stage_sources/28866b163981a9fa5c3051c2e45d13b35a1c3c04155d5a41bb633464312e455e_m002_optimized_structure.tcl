# Bounded new-graph observations; no full-design endpoint graph export.
proc m002_optimized_structure {phase out} {
    set base scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute
    set topology [dict create]
    if {$phase in {place physopt route}} {
        foreach slr [get_slrs] {
            foreach site [get_property NAME [get_sites -of_objects $slr]] {dict set topology $site [get_property NAME $slr]}
        }
    }
    set h [open [file join $out optimized_boundaries_${phase}.tsv] {WRONLY CREAT EXCL}]
    puts $h "scope\tcell\tREF_NAME\tINIT\tDONT_TOUCH\tdriver_LOC\tdriver_BEL\tleaf_input_pins\tload_REF_counts\tload_pin_counts\tload_SLR_counts\tload_slice_XY_bounds"
    set source_nets [dict create]
    set issues [list]
    foreach {tag scope suffix ref expected width} [list \
        input $base/u_attention/u_input_buffer u_capture_decode LUT6 48 256 \
        gate $base/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack u_output_payload_ce LUT1 16 384 \
        down $base/u_mlp/u_serial_command/u_down_scheduler/u_projection_repack u_output_payload_ce LUT1 16 512] {
        set cells [get_cells -hier -quiet -filter [format {NAME =~ "%s/*%s" && REF_NAME == "%s"} $scope $suffix $ref]]
        if {[llength $cells] != $expected} {lappend issues "$tag.boundaries=[llength $cells],expected=$expected"}
        foreach cell $cells {
            set op [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
            set nets [get_nets -segments -of_objects $op]
            set pins [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == IN}]
            set loads [get_cells -quiet -of_objects $pins]
            set refs [dict create];set terminals [dict create];set slrs [dict create]
            foreach value [get_property REF_NAME $loads] {dict incr refs $value}
            foreach value [get_property REF_PIN_NAME $pins] {dict incr terminals $value}
            set xs [list];set ys [list]
            foreach loc [get_property LOC $loads] {
                set slr [expr {[dict exists $topology $loc] ? [dict get $topology $loc] : {UNPLACED_OR_UNKNOWN}}]
                dict incr slrs $slr
                if {[regexp {^SLICE_X([0-9]+)Y([0-9]+)$} $loc -> x y]} {lappend xs $x;lappend ys $y}
            }
            set bounds UNPLACED_OR_NONSLICE
            if {[llength $xs]} {
                set xs [lsort -integer $xs];set ys [lsort -integer $ys]
                set bounds [list [lindex $xs 0] [lindex $ys 0] [lindex $xs end] [lindex $ys end]]
            }
            puts $h "$tag\t$cell\t[get_property REF_NAME $cell]\t[get_property INIT $cell]\t[get_property DONT_TOUCH $cell]\t[get_property LOC $cell]\t[get_property BEL $cell]\t[llength $pins]\t$refs\t$terminals\t$slrs\t$bounds"
            if {[llength $pins] != $width || [dict size $terminals] != 1 || ![dict exists $terminals CE]} {lappend issues "$cell.nonexpected_payload_CE=$terminals,count=[llength $pins]"}
            foreach ip [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN}] {
                foreach net [get_nets -quiet -of_objects $ip] {dict set source_nets $net 1}
            }
        }
    }
    close $h
    set h [open [file join $out optimized_control_sources_${phase}.tsv] {WRONLY CREAT EXCL}]
    puts $h "net\tleaf_input_pins\tload_REF_counts\tload_pin_counts\tdrivers\tdriver_LOCs"
    dict for {net unused} $source_nets {
        set seg [get_nets -segments $net]
        set pins [get_pins -quiet -leaf -of_objects $seg -filter {DIRECTION == IN}]
        set refs [dict create];set terminals [dict create]
        foreach ref [get_property REF_NAME [get_cells -quiet -of_objects $pins]] {dict incr refs $ref}
        foreach pin [get_property REF_PIN_NAME $pins] {dict incr terminals $pin}
        set drivers [get_pins -quiet -leaf -of_objects $seg -filter {DIRECTION == OUT}]
        puts $h "$net\t[llength $pins]\t$refs\t$terminals\t$drivers\t[get_property LOC [get_cells -quiet -of_objects $drivers]]"
    }
    close $h
    set h [open [file join $out optimized_structure_${phase}_result.txt] {WRONLY CREAT EXCL}]
    puts $h "phase=$phase\nissues=$issues\nboundary_contract=48input_16gate_16down\nphysical_signoff=false"
    close $h
    if {[llength $issues]} {error "E005 new boundary graph mismatch: $issues"}
    puts "E005_OPTIMIZED_STRUCTURE_COMPLETED $phase 48/16/16 boundary CE graphs"
}
