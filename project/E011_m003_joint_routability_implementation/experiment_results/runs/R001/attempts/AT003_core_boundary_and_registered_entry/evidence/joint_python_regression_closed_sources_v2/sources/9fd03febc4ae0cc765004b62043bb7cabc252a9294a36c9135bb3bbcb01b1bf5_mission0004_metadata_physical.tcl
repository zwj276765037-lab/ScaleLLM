proc mission0004_require_metadata {floorplan {board 1}} {
    set widths [get_cells -hier -filter {REF_NAME =~ *hap_mlp_weight_meta_uram_width_local*}]
    if {[llength $widths] != 16} { error "Expected16 metadata width domains" }
    set mapping [dict create gate {2 0 1 1} down {2 0 1 0}]
    array set expected_members {0 {} 1 {} 2 {}}
    set identities [dict create]
    set memory_count 0
    foreach width $widths {
        set name [get_property NAME $width]
        if {![regexp {(^|/)u_(gate|down)_bank([01])/g_width\[([0-3])\]\.u_width_local$} \
            $name -> prefix kind bank index]} { error "Unexpected metadata domain: $name" }
        set key $kind/$bank/$index
        if {[dict exists $identities $key]} { error "Duplicate metadata domain: $key" }
        dict set identities $key $name
        set slr [lindex [dict get $mapping $kind] $index]
        lappend expected_members($slr) $name
        set expected_uram [expr {$kind eq "gate" ? 56 : 28}]
        set memories [get_cells -hier -filter [format {NAME =~ "%s/*" && REF_NAME == URAM288} $name]]
        if {[llength $memories] != $expected_uram} { error "Metadata URAM domain mismatch: $name" }
        incr memory_count [llength $memories]
        foreach direction {wr rd} {
            set regs [get_cells -hier -filter [format {NAME =~ "%s/%s_addr_local_r_reg*" && REF_NAME =~ FD*} $name $direction]]
            set expected_addr [expr {$kind eq "gate" ? 18 : 17}]
            if {[llength $regs] != $expected_addr} { error "Metadata address replica count mismatch: $name $direction" }
            set enable [get_cells -hier -filter [format {NAME == "%s/%s_en_local_r_reg" && REF_NAME =~ FD*} $name $direction]]
            if {[llength $enable] != 1} { error "Metadata enable replica missing: $name $direction" }
        }
    }
    if {$memory_count != 672} { error "Expected672 metadata URAMs" }
    if {$board} {
        if {[llength [get_cells -hier -filter {REF_NAME == URAM288}]] != 752} {
            error "Expected752 board URAMs, including80 Attention URAMs"
        }
        foreach branch {0 1} {
            set dsps [get_cells -hier -filter [format {NAME =~ */u_shared_compute/u_branch%s/u_kernel/* && REF_NAME == DSP48E2} $branch]]
            if {[llength $dsps] != 1536} { error "Expected1536 kernel DSPs in branch$branch" }
        }
        puts "MISSION0004_TOPOLOGY_CHECK widths=16 metadata_uram=672 board_uram=752 kernel_dsps=3072"
    } else {
        puts "MISSION0004_TOPOLOGY_CHECK widths=16 metadata_uram=672 scope=metadata_ooc"
    }
    if {$floorplan} {
        foreach {slr count} {0 6 1 6 2 4} {
            set block [get_pblocks -quiet mission0004_metadata_slr${slr}]
            if {[llength $block] != 1 || ![get_property IS_SOFT $block]} {
                error "Missing/nonsoft metadata pblock SLR$slr"
            }
            set members [get_cells -of_objects $block -filter {REF_NAME =~ *hap_mlp_weight_meta_uram_width_local*}]
            if {[llength $members] != $count ||
                [lsort [get_property NAME $members]] ne [lsort $expected_members($slr)]} {
                error "Metadata pblock membership mismatch SLR$slr"
            }
            puts "MISSION0004_SOFT_WIDTH_MAP slr=$slr members=[get_property NAME $members]"
        }
    }
    return $widths
}

proc mission0004_report_metadata {out} {
    set widths [mission0004_require_metadata 1]
    set summary [open [file join $out metadata_address_locality.tsv] w]
    puts $summary "width\tdirection\tregister\tsource_slr\tsource_cr\tsink_pins\tinter_slr_sink_pins\tinter_cr_sink_pins\trpm_x_span\trpm_y_span"
    set cells [open [file join $out metadata_physical_cells.tsv] w]
    puts $cells "cell\tref\tloc\tclock_region\tslr"
    foreach width $widths {
        set name [get_property NAME $width]
        set leaves [get_cells -hier -filter [format {NAME =~ "%s/*" && (REF_NAME == URAM288 || NAME =~ *addr_local_r_reg* || NAME =~ *en_local_r_reg*)} $name]]
        foreach cell $leaves {
            set sites [get_sites -of_objects $cell]
            if {[llength $sites] != 1} { error "Metadata cell is not placed: $cell" }
            puts $cells [join [list [get_property NAME $cell] [get_property REF_NAME $cell] \
                [get_property LOC $cell] [get_clock_regions -of_objects $sites] [get_slrs -of_objects $sites]] \t]
        }
        foreach direction {wr rd} {
            set regs [get_cells -hier -filter [format {NAME =~ "%s/%s_addr_local_r_reg*" && REF_NAME =~ FD*} $name $direction]]
            set expected [expr {[string match */u_gate_bank* $name] ? 18 : 17}]
            if {[llength $regs] != $expected} { error "Metadata address replica count mismatch: $name $direction" }
            foreach reg $regs {
                set sites [get_sites -of_objects $reg]
                set source_slr [get_slrs -of_objects $sites]
                set source_cr [get_clock_regions -of_objects $sites]
                set xs [list [get_property RPM_X $sites]]
                set ys [list [get_property RPM_Y $sites]]
                set cross_slr 0
                set cross_cr 0
                set nets [get_nets -of_objects [get_pins -of_objects $reg -filter {REF_PIN_NAME == Q}]]
                set sinks [get_pins -leaf -of_objects $nets -filter {DIRECTION == IN}]
                if {[llength $sinks] == 0} { error "Metadata address has no native sink: $reg" }
                foreach sink $sinks {
                    set sink_sites [get_sites -of_objects [get_cells -of_objects $sink]]
                    if {[llength $sink_sites] != 1} { error "Unplaced metadata address sink: $sink" }
                    if {[get_slrs -of_objects $sink_sites] ne $source_slr} { incr cross_slr }
                    if {[get_clock_regions -of_objects $sink_sites] ne $source_cr} { incr cross_cr }
                    lappend xs [get_property RPM_X $sink_sites]
                    lappend ys [get_property RPM_Y $sink_sites]
                }
                set xs [lsort -integer $xs]
                set ys [lsort -integer $ys]
                puts $summary [join [list $name $direction [get_property NAME $reg] $source_slr $source_cr \
                    [llength $sinks] $cross_slr $cross_cr \
                    [expr {[lindex $xs end]-[lindex $xs 0]}] [expr {[lindex $ys end]-[lindex $ys 0]}]] \t]
            }
        }
    }
    close $summary
    close $cells
}

proc mission0004_report_regions {out} {
    set handle [open [file join $out per_cr_resources.tsv] w]
    puts $handle "clock_region\tslr\tprimitive_family\tcount"
    foreach cr [get_clock_regions] {
        set cells [get_cells -of_objects $cr]
        set slr [get_slrs -of_objects $cr]
        array set counts {}
        array set slices {}
        array set clbm {}
        foreach cell $cells ref [get_property REF_NAME $cells] loc [get_property LOC $cells] {
            if {[regexp {^(LUT|FD|RAMB|URAM288|RAMD|RAMS|SRL|MUXF|CARRY)} $ref -> family]} {
                if {![info exists counts($family)]} { set counts($family) 0 }
                incr counts($family)
            }
            if {[string match SLICE* $loc]} { set slices($loc) 1 }
            if {[regexp {^(RAMD|RAMS|SRL)} $ref]} { set clbm($loc) 1 }
        }
        foreach family [lsort [array names counts]] {
            puts $handle [join [list $cr $slr $family $counts($family)] \t]
        }
        foreach {family count} [list OCCUPIED_SLICE_SITES [array size slices] \
            OCCUPIED_CLBM_SITES [array size clbm] \
            AVAILABLE_SLICE_SITES [llength [get_sites -of_objects $cr -filter {SITE_TYPE =~ SLICE*}]] \
            AVAILABLE_CLBM_SITES [llength [get_sites -of_objects $cr -filter {SITE_TYPE == SLICEM}]]] {
            puts $handle [join [list $cr $slr $family $count] \t]
        }
        unset counts slices clbm
        if {[llength $cells]} {
            report_control_sets -verbose -cells $cells -file [file join $out control_sets_${cr}.rpt]
        }
    }
    close $handle
    set handle [open [file join $out dsp_clock_regions.tsv] w]
    puts $handle "cell\tloc\tclock_region\tslr"
    foreach cell [get_cells -hier -filter {REF_NAME == DSP48E2}] {
        set site [get_sites -of_objects $cell]
        puts $handle [join [list [get_property NAME $cell] [get_property LOC $cell] \
            [get_clock_regions -of_objects $site] [get_slrs -of_objects $site]] \t]
    }
    close $handle
}
