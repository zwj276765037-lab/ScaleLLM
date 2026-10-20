proc mission0005_domains {} {
    return {
        attention_center {.*u_array/u_center12$} SLR0 1632
        attention_left {.*u_array/u_left2$} SLR1 272
        attention_right {.*u_array/u_right2$} SLR2 272
        mlp_branch0 {.*u_shared_compute/u_branch0$} SLR1 1536
        mlp_branch1 {.*u_shared_compute/u_branch1$} SLR2 1536
    }
}

proc mission0005_require_partition {placed out} {
    set failures {}
    set violations [open [file join $out coordinated_domain_violations.tsv] w]
    puts $violations "scope\texpected_slr\tcell\tref\tsite\tactual_slr\treason"
    foreach {owner slr} {u_array SLR0 u_meta_bank SLR1 u_meta_sched SLR1 u_shared_compute SLR1} {
        set domain [get_cells -hier -regexp [format {.*%s$} $owner]]
        if {[llength $domain] != 1 || [get_property USER_SLR_ASSIGNMENT $domain] ne $slr} {
            lappend failures "endpoint owner missing/wrong assignment: $owner"
            puts $violations [join [list root_$owner $slr $owner NA NA NA MISSING_OR_ASSIGNMENT] \t]
            continue
        }
        if {$placed} {
            foreach cell [get_cells -hier -regexp [format {.*%s/[^/]+$} $owner] \
                    -filter {IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND}] {
                set site [get_sites -quiet -of_objects $cell]
                set actual [get_slrs -quiet -of_objects $site]
                if {[llength $site] != 1 || $actual ne $slr} {
                    lappend failures "root endpoint escaped: $cell"
                    puts $violations [join [list root_$owner $slr \
                        [get_property NAME $cell] [get_property REF_NAME $cell] \
                        $site $actual ROOT_LOCALITY] \t]
                }
            }
        }
    }
    set report [open [file join $out coordinated_domains.tsv] w]
    puts $report "domain\tslr\tprimitive_count\tdsp\tlut\tff\tbram36\tbram18\turam\twrong_slr"
    foreach {label selector slr dsp_expected} [mission0005_domains] {
        set domain [get_cells -hier -regexp $selector]
        if {[llength $domain] != 1} {
            lappend failures "domain missing/nonunique: $label"
            puts $report [join [list $label $slr 0 0 0 0 0 0 0 0] \t]
            puts $violations [join [list $label $slr $selector NA NA NA MISSING_OR_NONUNIQUE] \t]
            continue
        }
        set name [get_property NAME $domain]
        if {[get_property USER_SLR_ASSIGNMENT $domain] ne $slr} {
            lappend failures "wrong complete-domain assignment: $label"
            puts $violations [join [list $label $slr $name \
                [get_property REF_NAME $domain] NA NA WRONG_ASSIGNMENT] \t]
        }
        set leaves [get_cells -hier -filter [format {NAME =~ "%s/*" && IS_PRIMITIVE && REF_NAME != VCC && REF_NAME != GND} $name]]
        array set count {dsp 0 lut 0 ff 0 bram36 0 bram18 0 uram 0 wrong 0}
        foreach cell $leaves ref [get_property REF_NAME $leaves] {
            if {$ref eq "DSP48E2"} {incr count(dsp)}
            if {[string match LUT* $ref]} {incr count(lut)}
            if {[string match FD* $ref]} {incr count(ff)}
            if {[string match RAMB36* $ref]} {incr count(bram36)}
            if {[string match RAMB18* $ref]} {incr count(bram18)}
            if {$ref eq "URAM288"} {incr count(uram)}
            if {$placed} {
                set site [get_sites -quiet -of_objects $cell]
                set actual [get_slrs -quiet -of_objects $site]
                if {[llength $site] != 1 || $actual ne $slr} {
                    incr count(wrong)
                    puts $violations [join [list $label $slr \
                        [get_property NAME $cell] $ref $site $actual \
                        COMPLETE_DOMAIN_LOCALITY] \t]
                }
            }
        }
        puts $report [join [list $label $slr [llength $leaves] $count(dsp) $count(lut) \
            $count(ff) $count(bram36) $count(bram18) $count(uram) $count(wrong)] \t]
        if {$count(dsp) != $dsp_expected || $count(wrong) != 0} {
            lappend failures "domain $label DSP=$count(dsp) wrongSLR=$count(wrong)"
        }
        unset count
    }
    close $report
    close $violations

    foreach {block count} {
        attention_cols2_3 1 attention_cols4_7 1 attention_cols8_11 1
        attention_cols12_13 1 attention_left 1 attention_right 1
        mlp_body0 4 mlp_body1 4
    } {
        set pb [get_pblocks -quiet mission0005_$block]
        set ok [expr {[llength $pb] == 1}]
        if {$ok} {
            set ok [expr {[get_property IS_SOFT $pb] &&
                [llength [get_cells -of_objects $pb]] == $count}]
        }
        if {!$ok} {
            lappend failures "soft-domain membership failed: $block"
        }
    }
    foreach block {mlp_endpoints0 mlp_endpoints1 metadata_returns} {
        set pb [get_pblocks -quiet mission0005_$block]
        set ok [expr {[llength $pb] == 1}]
        if {$ok} {
            set ok [expr {[get_property IS_SOFT $pb] &&
                [llength [get_cells -of_objects $pb]] != 0}]
        }
        if {!$ok} {
            lappend failures "endpoint selector matched no cells: $block"
        }
    }
    foreach {block count} {mission0007_mlp_controls0 11 mission0007_mlp_controls1 11} {
        set pb [get_pblocks -quiet $block]
        set ok [expr {[llength $pb] == 1}]
        if {$ok} {
            set ok [expr {![get_property IS_SOFT $pb] &&
                [llength [get_cells -of_objects $pb]] == $count}]
        }
        if {!$ok} {
            lappend failures "hard replicated-control pblock membership failed: $block"
        }
    }
    foreach {block count} {mission0007_mlp_ingress_clear0 1 mission0007_mlp_ingress_clear1 1} {
        set pb [get_pblocks -quiet $block]
        set ok [expr {[llength $pb] == 1}]
        if {$ok} {
            set ok [expr {![get_property IS_SOFT $pb] &&
                [llength [get_cells -of_objects $pb]] == $count}]
        }
        if {!$ok} {
            lappend failures "hard ingress-clear pblock membership failed: $block"
        }
    }
    set report [open [file join $out coordinated_controls.tsv] w]
    puts $report "branch\tfamily\tcell\tref\tloc\tsource_clock_region\tsource_slr\tsink_pins\tsink_cells\tsink_slrs\tsink_clock_regions\tactual_inter_slr_sinks"
    foreach {branch slr} {0 SLR1 1 SLR2} {
        foreach {family exact} {
            clear_kernel_row_r_reg* 8
            clear_ingress_tag_r_reg* 1
            clear_gate_accum_r_reg* 1
            clear_down_accum_r_reg* 1
            clear_result_queues_r_reg* 1
        } {
            set cells [get_cells -hier -filter [format {NAME =~ */u_shared_compute/u_branch%s/%s && IS_PRIMITIVE} $branch $family]]
            if {[llength $cells] != $exact} {
                lappend failures "branch$branch clear family $family count=[llength $cells] expected=$exact"
            }
            foreach cell $cells {
                set site [get_sites -quiet -of_objects $cell]
                set actual UNPLACED
                set cr UNPLACED
                set sinks [get_pins -leaf -of_objects [get_nets -of_objects \
                    [get_pins -of_objects $cell -filter {DIRECTION == OUT}]] -filter {DIRECTION == IN}]
                set cross 0
                set sink_cells [lsort -unique [get_cells -of_objects $sinks]]
                set sink_slrs {}
                set sink_crs {}
                if {$placed} {
                    set actual [get_slrs -quiet -of_objects $site]
                    set cr [get_clock_regions -quiet -of_objects $site]
                    if {[llength $site] != 1 || $actual ne $slr} {
                        lappend failures "branch$branch clear source escaped: $cell"
                    }
                    foreach sink $sinks {
                        set sink_site [get_sites -quiet -of_objects \
                            [get_cells -of_objects $sink]]
                        set sink_slr [get_slrs -quiet -of_objects $sink_site]
                        set sink_cr [get_clock_regions -quiet -of_objects $sink_site]
                        lappend sink_slrs [expr {$sink_slr eq "" ? "UNPLACED" : $sink_slr}]
                        lappend sink_crs [expr {$sink_cr eq "" ? "UNPLACED" : $sink_cr}]
                        if {$sink_slr ne $actual} {incr cross}
                    }
                    if {$cross != 0} {
                        lappend failures "branch$branch clear source has $cross actual cross-SLR sinks: $cell"
                    }
                }
                puts $report [join [list $branch $family [get_property NAME $cell] \
                    [get_property REF_NAME $cell] [get_property LOC $cell] $cr \
                    $actual [llength $sinks] [llength $sink_cells] \
                    [join [lsort -unique $sink_slrs] ,] \
                    [join [lsort -unique $sink_crs] ,] $cross] \t]
            }
        }
        foreach family {tag_first* ingress_count_r_reg*} {
            set cells [get_cells -hier -filter [format {NAME =~ */u_shared_compute/u_branch%s/%s && IS_PRIMITIVE} $branch $family]]
            if {[llength $cells] == 0} {
                lappend failures "missing branch$branch control family $family"
            }
        }
    }
    close $report
    foreach width [mission0004_require_metadata 1] {
        set assigned [get_property USER_SLR_ASSIGNMENT $width]
        if {$assigned ni {SLR0 SLR1 SLR2}} {
            lappend failures "metadata width domain lacks SLR ownership: $width"
        }
        if {$placed} {
            set name [get_property NAME $width]
            foreach cell [get_cells -hier -filter [format {NAME =~ "%s/*" && IS_PRIMITIVE && REF_NAME != VCC && REF_NAME != GND} $name]] {
                if {[get_slrs -of_objects [get_sites -of_objects $cell]] ne $assigned} {
                    lappend failures "metadata domain escaped assigned SLR: $cell"
                }
            }
        }
    }
    if {[llength $failures] != 0} {
        error "Coordinated partition failed with [llength $failures] finding(s): [join $failures {; }]"
    }
    puts "MISSION0005_COORDINATED_PARTITION_PASS placed=$placed complete_domains=5 kernel_dsp=3072 attention_array_dsp=2176"
}

proc mission0005_report_capacity {out} {
    set report [open [file join $out coordinated_region_capacity.tsv] w]
    puts $report "pblock\tslices\tclbm\tlut_slots\tff_slots\tdsp\tbram36\turam"
    foreach pb [get_pblocks {mission0005_* mission0007_*}] {
        set sites [get_sites -of_objects $pb]
        array set count {slice 0 clbm 0 dsp 0 bram 0 uram 0}
        foreach type [get_property SITE_TYPE $sites] {
            if {$type in {SLICEL SLICEM}} {incr count(slice)}
            if {$type eq "SLICEM"} {incr count(clbm)}
            if {$type eq "DSP48E2"} {incr count(dsp)}
            if {$type in {RAMB36 RAMBFIFO36}} {incr count(bram)}
            if {$type eq "URAM288"} {incr count(uram)}
        }
        puts $report [join [list $pb $count(slice) $count(clbm) \
            [expr {8*$count(slice)}] [expr {16*$count(slice)}] \
            $count(dsp) $count(bram) $count(uram)] \t]
        unset count
        report_utilization -pblocks $pb -file [file join $out capacity_${pb}.rpt]
    }
    close $report
}

# Mission0008 is a checkpoint-bound ECO. These procedures intentionally use
# graph and primitive signatures from the open design; frozen names only seed
# the retained baseline witness and never authorize an ownership exception.
proc mission0008_unique {objects} {
    array set seen {}
    set result {}
    foreach object $objects {
        set name [get_property NAME $object]
        if {![info exists seen($name)]} {
            set seen($name) 1
            lappend result $object
        }
    }
    return $result
}

proc mission0008_names {objects} {
    if {[llength $objects] == 0} {return {}}
    return [lsort -unique [get_property NAME $objects]]
}

proc mission0008_union_named_objects {map_name objects} {
    upvar 1 $map_name object_map
    if {[llength $objects] == 0} {return}
    set names [get_property NAME $objects]
    if {[llength $names] != [llength $objects]} {
        error "MISSION0008_QUERY_NAME_COUNT objects=[llength $objects] names=[llength $names]"
    }
    foreach object $objects name $names {
        dict set object_map $name $object
    }
}

proc mission0008_named_object_values {object_map} {
    set result {}
    foreach name [lsort [dict keys $object_map]] {
        lappend result [dict get $object_map $name]
    }
    return $result
}

proc mission0008_graph_query_progress {handle label kind chunk chunks roots total union} {
    set fields [list $label $kind NOTE $chunk $chunks $roots $total $union 0 0]
    puts "MISSION0008_GRAPH_QUERY event=NOTE label=$label kind=$kind chunk=$chunk/$chunks roots=$roots/$total union=$union"
    flush stdout
    if {$handle ne ""} {
        puts $handle [join $fields \t]
        flush $handle
    }
}

proc mission0008_graph_query_begin {handle label kind chunk chunks roots total union} {
    set now [clock milliseconds]
    set fields [list $label $kind START $chunk $chunks $roots $total $union 0 0]
    puts "MISSION0008_GRAPH_QUERY event=START label=$label kind=$kind chunk=$chunk/$chunks roots=$roots/$total union=$union"
    flush stdout
    if {$handle ne ""} {
        puts $handle [join $fields \t]
        flush $handle
    }
    return $now
}

proc mission0008_graph_query_chunk_size {{kind DEFAULT}} {
    global mission0008_query_chunk_sizes
    if {[info exists ::mission0008_query_chunk_size]} {
        set chunk_size $::mission0008_query_chunk_size
    } elseif {[info exists mission0008_query_chunk_sizes] && \
            [dict exists $mission0008_query_chunk_sizes $kind]} {
        set chunk_size [dict get $mission0008_query_chunk_sizes $kind]
    } else {
        set chunk_size 512
    }
    if {![string is integer -strict $chunk_size] || $chunk_size <= 0 || \
            $chunk_size > 65536} {
        error "MISSION0008_BAD_QUERY_CHUNK_SIZE $chunk_size"
    }
    return $chunk_size
}

proc mission0008_graph_query_done {handle label kind chunk chunks roots total union \
        started remaining} {
    global mission0008_query_elapsed_ms mission0008_query_roots
    global mission0008_query_chunk_sizes
    set elapsed [expr {[clock milliseconds]-$started}]
    if {$elapsed < 1} {set elapsed 1}
    if {![info exists mission0008_query_elapsed_ms]} {
        set mission0008_query_elapsed_ms [dict create]
        set mission0008_query_roots [dict create]
        set mission0008_query_chunk_sizes [dict create]
    }
    set cumulative_ms $elapsed
    set cumulative_roots $roots
    if {[dict exists $mission0008_query_elapsed_ms $kind]} {
        set cumulative_ms [expr {$cumulative_ms + \
            [dict get $mission0008_query_elapsed_ms $kind]}]
        set cumulative_roots [expr {$cumulative_roots + \
            [dict get $mission0008_query_roots $kind]}]
    }
    dict set mission0008_query_elapsed_ms $kind $cumulative_ms
    dict set mission0008_query_roots $kind $cumulative_roots
    if {[info exists ::mission0008_query_remaining_total] && \
            [dict exists $::mission0008_query_remaining_total $kind]} {
        set scope_remaining [expr {max(0, \
            [dict get $::mission0008_query_remaining_total $kind]-$roots)}]
        dict set ::mission0008_query_remaining_total $kind $scope_remaining
        set remaining [expr {max($remaining, $scope_remaining)}]
    }
    set elapsed_s [format %.3f [expr {$elapsed/1000.0}]]
    set cumulative_s [format %.3f [expr {$cumulative_ms/1000.0}]]
    set fields [list $label $kind DONE $chunk $chunks $roots $total $union \
        $elapsed_s $cumulative_s]
    puts "MISSION0008_GRAPH_QUERY event=DONE label=$label kind=$kind chunk=$chunk/$chunks roots=$roots/$total union=$union elapsed_s=$elapsed_s cumulative_s=$cumulative_s"
    flush stdout
    if {$handle ne ""} {
        puts $handle [join $fields \t]
        flush $handle
    }

    if {![info exists ::mission0008_query_chunk_size] && $roots > 0} {
        set current [mission0008_graph_query_chunk_size $kind]
        set throughput [expr {$roots*1000.0/$elapsed}]
        set desired [expr {int($throughput*10.0)}]
        set max_chunk [expr {$kind eq "FANIN_ENDPOINT" ? 8192 : 65536}]
        set next $current
        if {$roots >= min($current, 256) && $desired > $current} {
            set next [expr {min($max_chunk, min($current*2, $desired))}]
        } elseif {$elapsed > 30000 && $current > 256} {
            set next [expr {max(256, int($current/2))}]
        }
        dict set mission0008_query_chunk_sizes $kind $next
        set conservative_rate [expr {$cumulative_roots*1000.0/$cumulative_ms/2.0}]
        set projected_s [expr {$remaining > 0 ? $remaining/$conservative_rate : 0.0}]
        puts "MISSION0008_GRAPH_ADAPT kind=$kind current=$current next=$next measured_roots=$cumulative_roots measured_s=$cumulative_s remaining=$remaining projected_s=[format %.3f $projected_s]"
        flush stdout
        if {[llength [info commands mission0008_require_query_fit]] == 1} {
            mission0008_require_query_fit $label:$kind $projected_s
        }
    }
}

proc mission0008_fanin_query_roots {endpoint_pins progress label} {
    set roots {}
    set total [llength $endpoint_pins]
    if {$total == 0} {
        mission0008_graph_query_progress $progress $label FANIN_ROOTS 0 0 0 0 0
    }
    set chunk_index 0
    set first 0
    while {$first < $total} {
        set chunk_size [mission0008_graph_query_chunk_size FANIN_ROOTS]
        incr chunk_index
        set last [expr {min($total-1, $first+$chunk_size-1)}]
        set chunk [lrange $endpoint_pins $first $last]
        set chunks [expr {int(ceil(double($total)/$chunk_size))}]
        set started [mission0008_graph_query_begin $progress $label FANIN_ROOTS \
            $chunk_index $chunks [llength $chunk] $total [dict size $roots]]
        set segments [get_nets -quiet -segments -of_objects $chunk]
        mission0008_union_named_objects roots [get_pins -quiet -leaf \
            -of_objects $segments -filter {DIRECTION == OUT}]
        mission0008_union_named_objects roots [get_ports -quiet \
            -of_objects $segments -filter {DIRECTION == IN}]
        set first [expr {$last+1}]
        mission0008_graph_query_done $progress $label FANIN_ROOTS \
            $chunk_index $chunks [llength $chunk] $total [dict size $roots] \
            $started [expr {$total-$first}]
    }
    return [mission0008_named_object_values $roots]
}

proc mission0008_boundary_fanin_witnesses {endpoint_pins progress label include_starts} {
    set roots [mission0008_fanin_query_roots $endpoint_pins $progress $label]
    set cells {}
    set starts {}
    set total [llength $roots]
    set chunks 0
    if {$total == 0} {
        mission0008_graph_query_progress $progress $label FANIN 0 0 0 0 \
            [dict size $cells]
    }
    set chunk_index 0
    set first 0
    while {$first < $total} {
        set chunk_size [mission0008_graph_query_chunk_size FANIN]
        incr chunk_index
        set last [expr {min($total-1, $first+$chunk_size-1)}]
        set chunk [lrange $roots $first $last]
        set chunks [expr {int(ceil(double($total)/$chunk_size))}]
        set started [mission0008_graph_query_begin $progress $label FANIN \
            $chunk_index $chunks [llength $chunk] $total [dict size $cells]]
        mission0008_union_named_objects cells \
            [get_cells -quiet -of_objects $chunk]
        mission0008_union_named_objects cells \
            [all_fanin -flat -only_cells -to $chunk]
        if {$include_starts} {
            mission0008_union_named_objects starts \
                [all_fanin -flat -startpoints_only -to $chunk]
        }
        set first [expr {$last+1}]
        mission0008_graph_query_done $progress $label FANIN \
            $chunk_index $chunks [llength $chunk] $total [dict size $cells] \
            $started [expr {$total-$first}]
    }
    return [dict create roots $roots cells [mission0008_named_object_values $cells] \
        starts [mission0008_named_object_values $starts] chunks $chunks]
}

proc mission0008_endpoint_fanin_witnesses {endpoint_pins progress label include_starts} {
    set cells {}
    set starts {}
    set total [llength $endpoint_pins]
    set chunks 0
    set first 0
    while {$first < $total} {
        set chunk_size [mission0008_graph_query_chunk_size FANIN_ENDPOINT]
        incr chunks
        set last [expr {min($total-1, $first+$chunk_size-1)}]
        set chunk [lrange $endpoint_pins $first $last]
        set expected_chunks [expr {int(ceil(double($total)/$chunk_size))}]
        set started [mission0008_graph_query_begin $progress $label FANIN_ENDPOINT \
            $chunks $expected_chunks [llength $chunk] $total [dict size $cells]]
        mission0008_union_named_objects cells \
            [all_fanin -flat -only_cells -to $chunk]
        if {$include_starts} {
            mission0008_union_named_objects starts \
                [all_fanin -flat -startpoints_only -to $chunk]
        }
        set first [expr {$last+1}]
        mission0008_graph_query_done $progress $label FANIN_ENDPOINT \
            $chunks $expected_chunks [llength $chunk] $total [dict size $cells] \
            $started [expr {$total-$first}]
    }
    if {$total == 0} {
        mission0008_graph_query_progress $progress $label FANIN_ENDPOINT 0 0 0 0 0
    }
    return [dict create roots $endpoint_pins \
        cells [mission0008_named_object_values $cells] \
        starts [mission0008_named_object_values $starts] chunks $chunks]
}

proc mission0008_chunked_fanin_witnesses {endpoint_pins progress label include_starts} {
    return [mission0008_endpoint_fanin_witnesses \
        $endpoint_pins $progress $label $include_starts]
}

proc mission0008_verify_fanin_query_equivalence {sample_groups progress out} {
    set ::mission0008_fanin_query_mode endpoint
    set handle [open [file join $out fanin_query_equivalence.tsv] w]
    puts $handle "group\tendpoints\tdirect_cells\tendpoint_cells\tdirect_starts\tendpoint_starts\tmatch"
    set mismatch 0
    dict for {group endpoints} $sample_groups {
        if {[llength $endpoints] == 0} {continue}
        set started [mission0008_graph_query_begin $progress pilot_$group \
            DIRECT_CELLS 1 1 [llength $endpoints] [llength $endpoints] 0]
        set direct_cells [mission0008_names \
            [all_fanin -flat -only_cells -to $endpoints]]
        mission0008_graph_query_done $progress pilot_$group DIRECT_CELLS \
            1 1 [llength $endpoints] [llength $endpoints] \
            [llength $direct_cells] $started 0
        set started [mission0008_graph_query_begin $progress pilot_$group \
            DIRECT_STARTS 1 1 [llength $endpoints] [llength $endpoints] 0]
        set direct_starts [mission0008_names \
            [all_fanin -flat -startpoints_only -to $endpoints]]
        mission0008_graph_query_done $progress pilot_$group DIRECT_STARTS \
            1 1 [llength $endpoints] [llength $endpoints] \
            [llength $direct_starts] $started 0
        set endpoint [mission0008_chunked_fanin_witnesses \
            $endpoints $progress pilot_$group 1]
        set endpoint_cells [mission0008_names [dict get $endpoint cells]]
        set endpoint_starts [mission0008_names [dict get $endpoint starts]]
        set match [expr {$direct_cells eq $endpoint_cells && \
            $direct_starts eq $endpoint_starts}]
        puts $handle [join [list $group [llength $endpoints] \
            [llength $direct_cells] [llength $endpoint_cells] \
            [llength $direct_starts] [llength $endpoint_starts] $match] \t]
        flush $handle
        if {!$match} {set mismatch 1}
    }
    puts $handle "adopted_mode\t$::mission0008_fanin_query_mode"
    close $handle
    if {$mismatch} {
        error "MISSION0008_FANIN_QUERY_EQUIVALENCE mode=$::mission0008_fanin_query_mode"
    }
    puts "MISSION0008_FANIN_QUERY_EQUIVALENCE_PASS mode=$::mission0008_fanin_query_mode"
    flush stdout
    return $::mission0008_fanin_query_mode
}

proc mission0008_chunked_fanout_endpoints {source_pins progress label} {
    set roots {}
    set source_total [llength $source_pins]
    set source_chunks 0
    if {$source_total == 0} {
        mission0008_graph_query_progress $progress $label FANOUT_ROOTS 0 0 0 0 0
    }
    set source_chunk_index 0
    set first 0
    while {$first < $source_total} {
        set chunk_size [mission0008_graph_query_chunk_size FANOUT_ROOTS]
        incr source_chunk_index
        set last [expr {min($source_total-1, $first+$chunk_size-1)}]
        set chunk [lrange $source_pins $first $last]
        set source_chunks [expr {int(ceil(double($source_total)/$chunk_size))}]
        set started [mission0008_graph_query_begin $progress $label FANOUT_ROOTS \
            $source_chunk_index $source_chunks [llength $chunk] $source_total \
            [dict size $roots]]
        mission0008_union_named_objects roots $chunk
        set first [expr {$last+1}]
        mission0008_graph_query_done $progress $label FANOUT_ROOTS \
            $source_chunk_index $source_chunks [llength $chunk] $source_total \
            [dict size $roots] $started [expr {$source_total-$first}]
    }
    set roots [mission0008_named_object_values $roots]
    set endpoints {}
    set total [llength $roots]
    set chunks 0
    if {$total == 0} {
        mission0008_graph_query_progress $progress $label FANOUT 0 0 0 0 0
    }
    set chunk_index 0
    set first 0
    while {$first < $total} {
        set chunk_size [mission0008_graph_query_chunk_size FANOUT]
        incr chunk_index
        set last [expr {min($total-1, $first+$chunk_size-1)}]
        set chunk [lrange $roots $first $last]
        set chunks [expr {int(ceil(double($total)/$chunk_size))}]
        set started [mission0008_graph_query_begin $progress $label FANOUT \
            $chunk_index $chunks [llength $chunk] $total [dict size $endpoints]]
        mission0008_union_named_objects endpoints \
            [all_fanout -flat -endpoints_only -from $chunk]
        set first [expr {$last+1}]
        mission0008_graph_query_done $progress $label FANOUT \
            $chunk_index $chunks [llength $chunk] $total [dict size $endpoints] \
            $started [expr {$total-$first}]
    }
    return [dict create roots $roots \
        endpoints [mission0008_named_object_values $endpoints] chunks $chunks]
}

proc mission0008_require_one {objects label} {
    if {[llength $objects] != 1} {
        error "MISSION0008_NONUNIQUE $label count=[llength $objects]"
    }
    return [lindex $objects 0]
}

proc mission0008_pin_net {pin} {
    set nets [mission0008_unique [get_nets -quiet -of_objects $pin]]
    if {[llength $nets] != 1} {
        error "MISSION0008_PIN_NET [get_property NAME $pin] count=[llength $nets]"
    }
    set segments [mission0008_unique [get_nets -quiet -segments -of_objects $pin]]
    if {[llength $segments] == 0} {
        error "MISSION0008_PIN_SEGMENTS [get_property NAME $pin] count=0"
    }
    return [lindex $nets 0]
}

proc mission0008_leaf_peers {pins direction} {
    set segments [mission0008_unique [get_nets -quiet -segments -of_objects $pins]]
    if {[llength $segments] == 0} {return {}}
    return [mission0008_unique [get_pins -quiet -leaf -of_objects $segments \
        -filter [format {DIRECTION == %s} $direction]]]
}

proc mission0008_output_sinks {cell} {
    set outputs [get_pins -quiet -leaf -of_objects $cell -filter {DIRECTION == OUT}]
    return [mission0008_leaf_peers $outputs IN]
}

proc mission0008_output_end_slrs {cell} {
    set outputs [get_pins -quiet -leaf -of_objects $cell -filter {DIRECTION == OUT}]
    set ends [mission0008_unique [all_fanout -flat -endpoints_only -from $outputs]]
    set cells [mission0008_unique [get_cells -quiet -of_objects $ends]]
    return [mission0008_names [get_slrs -quiet -of_objects $cells]]
}

proc mission0008_cell_slr {cell} {
    return [mission0008_names [get_slrs -quiet -of_objects \
        [get_sites -quiet -of_objects $cell]]]
}

proc mission0008_cell_cr {cell} {
    return [mission0008_names [get_clock_regions -quiet -of_objects \
        [get_sites -quiet -of_objects $cell]]]
}

proc mission0008_input_driver_cells {pin} {
    set drivers [mission0008_leaf_peers $pin OUT]
    return [mission0008_unique [get_cells -quiet -of_objects $drivers]]
}

proc mission0008_clear_input {cell branch} {
    set matches {}
    foreach pin [get_pins -quiet -leaf -of_objects $cell -filter {DIRECTION == IN}] {
        foreach driver [mission0008_input_driver_cells $pin] {
            set name [get_property NAME $driver]
            if {[regexp [format {/u_branch%s/clear_(kernel_row|gate_accum|down_accum|result_queues)_r_reg} $branch] $name]} {
                lappend matches $pin
            }
        }
    }
    return [mission0008_unique $matches]
}

proc mission0008_counterpart_clear {branch1_cell} {
    set name [get_property NAME $branch1_cell]
    set peer_name [string map {/u_branch1/ /u_branch0/} $name]
    if {$peer_name eq $name} {error "MISSION0008_CLEAR_NOT_BRANCH1 $name"}
    set peer [mission0008_require_one [get_cells -quiet [list $peer_name]] \
        "branch0 clear counterpart for $name"]
    if {[get_property REF_NAME $peer] ne [get_property REF_NAME $branch1_cell]} {
        error "MISSION0008_CLEAR_REF_MISMATCH $name"
    }
    return $peer
}

proc mission0008_canonical_pin_drivers {pin} {
    set result {}
    foreach driver [mission0008_leaf_peers $pin OUT] {
        lappend result [get_property NAME $driver]
    }
    return [lsort -unique $result]
}

proc mission0008_pin_driver_records {pin} {
    set result {}
    foreach driver [mission0008_leaf_peers $pin OUT] {
        set owner [mission0008_require_one [get_cells -quiet -of_objects $driver] \
            "driver owner for [get_property NAME $pin]"]
        lappend result [list [get_property NAME $driver] \
            [get_property REF_PIN_NAME $driver] [get_property NAME $owner] \
            [get_property REF_NAME $owner]]
    }
    return [lsort -unique $result]
}

proc mission0008_pin_driver_semantics {pin} {
    set records [mission0008_pin_driver_records $pin]
    if {[llength $records] == 1} {
        lassign [lindex $records 0] driver_name driver_refpin owner_name owner_ref
        if {$owner_ref eq "VCC" && $driver_refpin eq "P"} {return CONST1}
        if {$owner_ref eq "GND" && $driver_refpin eq "G"} {return CONST0}
    }
    set result {}
    foreach record $records {lappend result [join $record |]}
    return [lsort -unique $result]
}

proc mission0008_clear_pre_lut1_facts {pre_pin} {
    set result [dict create valid 0 reason UNCHECKED pre_pin NA pre_driver NA \
        lut_cell NA lut_ref NA lut_init NA i0_pin NA i0_driver NA]
    if {[llength $pre_pin] != 1} {
        dict set result reason PRE_PIN_COUNT_[llength $pre_pin]
        return $result
    }
    dict set result pre_pin [get_property NAME $pre_pin]
    if {[catch {mission0008_pin_driver_records $pre_pin} records]} {
        dict set result reason PRE_DRIVER_QUERY_FAILED
        return $result
    }
    if {[llength $records] != 1} {
        dict set result reason PRE_DRIVER_COUNT_[llength $records]
        return $result
    }
    lassign [lindex $records 0] driver_name driver_refpin owner_name owner_ref
    dict set result pre_driver [join [lindex $records 0] |]
    if {$driver_refpin ne "O" || $owner_ref ne "LUT1"} {
        dict set result reason PRE_DRIVER_NOT_LUT1_O
        return $result
    }
    set driver_pins [mission0008_leaf_peers $pre_pin OUT]
    if {[llength $driver_pins] != 1 || \
            [get_property NAME $driver_pins] ne $driver_name} {
        dict set result reason PRE_DRIVER_OBJECT_MISMATCH
        return $result
    }
    set owners [get_cells -quiet -of_objects $driver_pins]
    if {[llength $owners] != 1 || [get_property NAME $owners] ne $owner_name || \
            [get_property REF_NAME $owners] ne "LUT1"} {
        dict set result reason PRE_LUT_OWNER_MISMATCH
        return $result
    }
    set owner [lindex $owners 0]
    set init [get_property -quiet INIT $owner]
    dict set result lut_cell [get_property NAME $owner]
    dict set result lut_ref [get_property REF_NAME $owner]
    dict set result lut_init $init
    if {$init eq ""} {
        dict set result reason PRE_LUT_INIT_MISSING
        return $result
    }
    set i0 [get_pins -quiet -leaf -of_objects $owner \
        -filter {DIRECTION == IN && REF_PIN_NAME == I0}]
    if {[llength $i0] != 1} {
        dict set result reason PRE_LUT_I0_COUNT_[llength $i0]
        return $result
    }
    dict set result i0_pin [get_property NAME $i0]
    if {[catch {mission0008_pin_driver_records $i0} i0_records]} {
        dict set result reason PRE_LUT_I0_DRIVER_QUERY_FAILED
        return $result
    }
    if {[llength $i0_records] != 1} {
        dict set result reason PRE_LUT_I0_DRIVER_COUNT_[llength $i0_records]
        return $result
    }
    dict set result i0_driver [join [lindex $i0_records 0] |]
    dict set result valid 1
    dict set result reason READY
    return $result
}

proc mission0008_write_clear_pre_lut1_fact {handle pair side facts reason} {
    puts $handle [join [list $pair $side [dict get $facts pre_pin] \
        [dict get $facts pre_driver] [dict get $facts lut_cell] \
        [dict get $facts lut_ref] [dict get $facts lut_init] \
        [dict get $facts i0_pin] [dict get $facts i0_driver] $reason] \t]
}

proc mission0008_compare_clear_pre_drivers {pair left_pin right_pin handle} {
    set left_exact [mission0008_pin_driver_semantics $left_pin]
    set right_exact [mission0008_pin_driver_semantics $right_pin]
    if {$left_exact eq $right_exact} {
        set empty [dict create pre_pin NA pre_driver $left_exact lut_cell NA \
            lut_ref NA lut_init NA i0_pin NA i0_driver NA]
        mission0008_write_clear_pre_lut1_fact $handle $pair left $empty \
            EXACT_CANONICAL_PRE_DRIVER
        dict set empty pre_driver $right_exact
        mission0008_write_clear_pre_lut1_fact $handle $pair right $empty \
            EXACT_CANONICAL_PRE_DRIVER
        return [dict create equivalent 1 reason EXACT_CANONICAL_PRE_DRIVER]
    }
    set left [mission0008_clear_pre_lut1_facts $left_pin]
    set right [mission0008_clear_pre_lut1_facts $right_pin]
    if {![dict get $left valid]} {
        set reason LEFT_[dict get $left reason]
        set equivalent 0
    } elseif {![dict get $right valid]} {
        set reason RIGHT_[dict get $right reason]
        set equivalent 0
    } elseif {[dict get $left lut_init] ne [dict get $right lut_init]} {
        set reason LUT1_INIT_MISMATCH
        set equivalent 0
    } elseif {[dict get $left i0_driver] ne [dict get $right i0_driver]} {
        set reason LUT1_I0_EXACT_DRIVER_MISMATCH
        set equivalent 0
    } else {
        set reason LUT1_INIT_AND_I0_EXACT_DRIVER_MATCH
        set equivalent 1
    }
    mission0008_write_clear_pre_lut1_fact $handle $pair left $left $reason
    mission0008_write_clear_pre_lut1_fact $handle $pair right $right $reason
    return [dict create equivalent $equivalent reason $reason \
        left $left right $right]
}

proc mission0008_clear_sources {branch} {
    set controls [mission0008_require_one \
        [get_pblocks -quiet mission0007_mlp_controls${branch}] \
        "branch$branch clear-control pblock"]
    set ingress [mission0008_require_one \
        [get_pblocks -quiet mission0007_mlp_ingress_clear${branch}] \
        "branch$branch ingress-clear pblock"]
    set sources [mission0008_unique [concat [get_cells -quiet -of_objects $controls] \
        [get_cells -quiet -of_objects $ingress]]]
    set valid {}
    foreach cell $sources {
        set name [get_property NAME $cell]
        if {[string match */u_shared_compute/u_branch${branch}/clear_*_r_reg* $name] && \
                [string match FD* [get_property REF_NAME $cell]]} {
            lappend valid $cell
        }
    }
    if {[llength $sources] != 12 || [llength $valid] != 12} {
        error "MISSION0008_CLEAR_SOURCE_MEMBERSHIP branch=$branch members=[llength $sources] valid=[llength $valid]"
    }
    return $valid
}

proc mission0008_require_clear_equivalence {out} {
    set branch1 [mission0008_clear_sources 1]
    set pairs 0
    set failures {}
    set cells_report [open [file join $out clear_equivalence_cells.tsv] w]
    puts $cells_report "pair\tside\tcell\tref_name\tinit\tinversion_properties"
    set drivers_report [open [file join $out clear_equivalence_driverrefs.tsv] w]
    puts $drivers_report "pair\tpin\tside\tdriver_pin\tdriver_ref_pin\tdriver_owner\tdriver_ref_name\tcanonical_semantics"
    set pre_report [open [file join $out clear_pre_lut1_equivalence.tsv] w]
    puts $pre_report "pair\tside\tpre_pin\tpre_driver\tlut_cell\tlut_ref\tlut_init\ti0_pin\ti0_exact_driver\tequivalence_reason"
    foreach right $branch1 {
        set left [mission0008_counterpart_clear $right]
        set pair [get_property NAME $right]
        foreach property {REF_NAME INIT} {
            if {[get_property -quiet $property $left] ne \
                    [get_property -quiet $property $right]} {
                lappend failures "property=$property cell=$pair"
            }
        }
        set left_property_cell [mission0008_require_one [get_cells -quiet \
            [list [get_property NAME $left]]] "left clear property cell"]
        set right_property_cell [mission0008_require_one [get_cells -quiet \
            [list [get_property NAME $right]]] "right clear property cell"]
        set inversion_properties {}
        foreach property [lsort -unique [concat \
                [list_property $left_property_cell] \
                [list_property $right_property_cell]]] {
            if {![string match IS_*_INVERTED $property]} {continue}
            lappend inversion_properties $property
            if {[get_property -quiet $property $left] ne \
                    [get_property -quiet $property $right]} {
                lappend failures "property=$property cell=$pair"
            }
        }
        foreach side_cell [list [list left $left] [list right $right]] {
            lassign $side_cell side cell
            set inversion_values {}
            foreach property $inversion_properties {
                lappend inversion_values "$property=[get_property -quiet $property $cell]"
            }
            puts $cells_report [join [list $pair $side [get_property NAME $cell] \
                [get_property REF_NAME $cell] [get_property -quiet INIT $cell] \
                [join $inversion_values ,]] \t]
        }
        foreach refpin {C D CE PRE CLR R S} {
            set lp [get_pins -quiet -leaf -of_objects $left \
                -filter [format {REF_PIN_NAME == %s} $refpin]]
            set rp [get_pins -quiet -leaf -of_objects $right \
                -filter [format {REF_PIN_NAME == %s} $refpin]]
            if {[llength $lp] != [llength $rp]} {
                lappend failures "pin_count=$refpin cell=$pair left=[llength $lp] right=[llength $rp]"
            }
            foreach side_pin [list [list left $lp] [list right $rp]] {
                lassign $side_pin side pins
                if {[llength $pins] != 1} {continue}
                set semantics [mission0008_pin_driver_semantics $pins]
                set records [mission0008_pin_driver_records $pins]
                if {[llength $records] != 1} {
                    lappend failures "driver_count=$refpin cell=$pair side=$side actual=[llength $records] expected=1"
                }
                foreach record $records {
                    lassign $record driver_name driver_refpin owner_name owner_ref
                    puts $drivers_report [join [list $pair $refpin $side $driver_name \
                        $driver_refpin $owner_name $owner_ref $semantics] \t]
                }
            }
            if {$refpin eq "PRE"} {
                set pre_result [mission0008_compare_clear_pre_drivers \
                    $pair $lp $rp $pre_report]
                if {![dict get $pre_result equivalent]} {
                    lappend failures "driver=PRE cell=$pair reason=[dict get $pre_result reason] left=[mission0008_pin_driver_semantics $lp] right=[mission0008_pin_driver_semantics $rp]"
                }
            } elseif {[llength $lp] == 1 && [llength $rp] == 1 && \
                    [mission0008_pin_driver_semantics $lp] ne \
                    [mission0008_pin_driver_semantics $rp]} {
                lappend failures "driver=$refpin cell=$pair left=[mission0008_pin_driver_semantics $lp] right=[mission0008_pin_driver_semantics $rp]"
            }
        }
        incr pairs
    }
    close $cells_report
    close $drivers_report
    close $pre_report
    if {[llength $failures] != 0} {
        error "MISSION0008_CLEAR_EQUIVALENCE_FAIL [join $failures {; }]"
    }
    return $pairs
}

proc mission0008_collect_d0_terminal {} {
    array set groups {AW {} AR {} W {} B {} R {}}
    set candidates [get_cells -quiet -hier \
        -filter {NAME =~ */d0_mig_slice/inst/*slr_slave/* && IS_PRIMITIVE == 1}]
    foreach cell $candidates {
        set name [get_property NAME $cell]
        set ref [get_property REF_NAME $cell]
        if {![regexp {/inst/(aw|ar|w|b|r)15\.} $name -> channel_lower]} {continue}
        set channel [string toupper $channel_lower]
        set selected 0
        if {$channel in {AW AR W}} {
            set selected [expr {
                [regexp {/mesg_reg_reg\[[0-9]+\]$} $name] ||
                [regexp {/mesg_reg\[[0-9]+\]_i_} $name] ||
                [regexp {/asyncclear_(mvalid_inst|state0_inst|state1_inst)($|_i_)} $name] ||
                [regexp {/common\.ready_d_reg\[[0-9]+\]$} $name] ||
                [regexp {/common\.ready_d\[[0-9]+\]_i_} $name]
            }]
        } else {
            set selected [expr {
                [regexp {/common\.pipe\[[0-9]+\]\.payload_data_reg\[[0-9]+\]$} $name] ||
                [regexp {/common\.pipe\[[0-9]+\]\.payload_valid_asyncclear_inst($|_i_)} $name] ||
                [regexp {/common\.s_ready_i_reg.*$} $name]
            }]
        }
        if {!$selected} {continue}
        if {![string match FD* $ref] && ![string match LUT* $ref]} {
            error "MISSION0008_D0_BAD_PRIMITIVE channel=$channel ref=$ref cell=$name"
        }
        lappend groups($channel) $cell
    }
    set expected {AW 120 AR 120 B 5 W 1166 R 518}
    set all {}
    foreach {channel count} $expected {
        set groups($channel) [mission0008_unique $groups($channel)]
        if {[llength $groups($channel)] != $count} {
            error "MISSION0008_D0_CHANNEL_COUNT channel=$channel actual=[llength $groups($channel)] expected=$count"
        }
        set ff [llength [filter $groups($channel) {REF_NAME =~ FD*}]]
        set lut [llength [filter $groups($channel) {REF_NAME =~ LUT*}]]
        set srl [llength [filter $groups($channel) {REF_NAME =~ SRL*}]]
        switch $channel {
            AW - AR {set expected_types {58 62 0}}
            B {set expected_types {4 1 0}}
            W {set expected_types {581 585 0}}
            R {set expected_types {517 1 0}}
        }
        lassign $expected_types eff elut esrl
        if {$ff != $eff || $lut != $elut || $srl != $esrl} {
            error "MISSION0008_D0_TYPE_COUNT channel=$channel ff=$ff/$eff lut=$lut/$elut srl=$srl/$esrl"
        }
        set all [concat $all $groups($channel)]
    }
    return [dict create all [mission0008_unique $all] AW $groups(AW) \
        AR $groups(AR) B $groups(B) W $groups(W) R $groups(R)]
}

proc mission0008_pcie_destination {} {
    set hard [mission0008_require_one [get_cells -quiet -hier \
        -filter {IS_PRIMITIVE == 1 && REF_NAME == PCIE40E4 && LOC == PCIE40E4_X1Y2}] \
        pcie40e4_x1y2_owner]
    return [mission0008_require_one [get_pins -quiet -leaf -of_objects $hard \
        -filter {REF_PIN_NAME == CFGEXTREADDATAVALID}] pcie_cfg_ext_read_data_valid_pin]
}

proc mission0008_collect_pcie_support {} {
    set destination [mission0008_pcie_destination]
    set drivers [mission0008_leaf_peers $destination OUT]
    set matches {}
    foreach cell [mission0008_unique [get_cells -quiet -of_objects $drivers]] {
        if {[get_property REF_NAME $cell] eq "FDRE"} {lappend matches $cell}
    }
    return [mission0008_require_one $matches pcie_cfg_ext_read_data_valid_support]
}

proc mission0008_collect_diagnostic_originals {out violation_path} {
    if {![file isfile $violation_path]} {
        error "MISSION0008_DIAGNOSTIC_VIOLATION_TABLE_MISSING $violation_path"
    }
    set input [open $violation_path r]
    if {[gets $input header] < 0 || \
            $header ne "scope\texpected_slr\tcell\tref\tsite\tactual_slr\treason"} {
        close $input
        error "MISSION0008_DIAGNOSTIC_VIOLATION_HEADER"
    }
    set report [open [file join $out diagnostic_target_resolution.tsv] w]
    puts $report "$header\tresolved\tdirect_sinks\tdirect_sink_slrs"
    set result {}
    array set seen {}
    while {[gets $input line] >= 0} {
        if {[string trim $line] eq ""} {continue}
        set fields [split $line \t]
        if {[llength $fields] != 7} {
            close $input
            close $report
            error "MISSION0008_DIAGNOSTIC_VIOLATION_ROW fields=[llength $fields]"
        }
        lassign $fields scope expected_slr name ref site actual_slr reason
        if {[info exists seen($name)]} {
            close $input
            close $report
            error "MISSION0008_DIAGNOSTIC_DUPLICATE_TARGET cell=$name"
        }
        set seen($name) 1
        set cell [mission0008_require_one [get_cells -quiet [list $name]] \
            "diagnostic original $name"]
        set observed_ref [get_property REF_NAME $cell]
        set observed_site [get_property LOC $cell]
        set observed_slr [mission0008_cell_slr $cell]
        if {$observed_ref ne $ref || $observed_site ne $site || \
                $observed_slr ne [list $actual_slr] || \
                $reason ne "COMPLETE_DOMAIN_LOCALITY" || \
                $expected_slr ni {SLR0 SLR1 SLR2}} {
            close $input
            close $report
            error "MISSION0008_DIAGNOSTIC_TARGET_IDENTITY cell=$name ref=$observed_ref/$ref site=$observed_site/$site slr=$observed_slr/$actual_slr reason=$reason"
        }
        set sinks [mission0008_output_sinks $cell]
        set sink_cells [mission0008_unique [get_cells -quiet -of_objects $sinks]]
        set sink_slrs [mission0008_names [get_slrs -quiet -of_objects $sink_cells]]
        puts $report [join [concat $fields \
            [list 1 [llength $sinks] [join $sink_slrs ,]]] \t]
        lappend result $cell
    }
    close $input
    close $report
    set result [mission0008_unique $result]
    if {[llength $result] != 22} {
        error "MISSION0008_DIAGNOSTIC_TARGET_COUNT actual=[llength $result] expected=22"
    }
    return $result
}

proc mission0008_collect_candidate {out {mode full} {violation_path {}}} {
    global mission0008_domain_leaf_owner mission0008_domain_leaf_slr
    global mission0008_domain_leaf_ref mission0008_domain_leaves
    catch {array unset mission0008_domain_leaf_owner}
    catch {array unset mission0008_domain_leaf_slr}
    catch {array unset mission0008_domain_leaf_ref}
    catch {array unset mission0008_domain_leaves}
    array set mission0008_domain_leaf_owner {}
    array set mission0008_domain_leaf_slr {}
    array set mission0008_domain_leaf_ref {}
    array set mission0008_domain_leaves {}
    set wrong {}
    set domain_baseline {}
    if {$mode eq "diagnostic"} {
        if {$violation_path eq ""} {
            error "MISSION0008_DIAGNOSTIC_VIOLATION_TABLE_REQUIRED"
        }
        set wrong [mission0008_collect_diagnostic_originals $out $violation_path]
        dict set domain_baseline diagnostic [dict create \
            source $violation_path rows [llength $wrong] \
            topology PENDING_REPLAY_FROM_IMMUTABLE_BASELINE]
    } elseif {$mode eq "full"} {
        array set domain_seen {}
        foreach {label selector expected_slr dsp} [mission0005_domains] {
            set root [mission0008_require_one [get_cells -quiet -hier -regexp $selector] \
                "domain $label"]
            set root_name [get_property NAME $root]
            set leaves [get_cells -quiet -hier -filter \
                [format {NAME =~ "%s/*" && IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND} $root_name]]
            set sequential [filter $leaves {REF_NAME =~ FD* || REF_NAME =~ SRL*}]
            set dsps [filter $leaves {REF_NAME == DSP48E2}]
            if {[llength $dsps] != $dsp} {
                error "MISSION0008_DOMAIN_DSP_BASELINE domain=$label actual=[llength $dsps] expected=$dsp"
            }
            dict set domain_baseline $label [dict create selector $selector root $root_name \
                slr $expected_slr leaves [llength $leaves] sequential [llength $sequential] \
                dsp [llength $dsps]]
            set mission0008_domain_leaves($label) {}
            foreach cell $leaves {
                set leaf_name [get_property NAME $cell]
                if {[info exists domain_seen($leaf_name)]} {
                    error "MISSION0008_DOMAIN_BASELINE_OVERLAP cell=$leaf_name owners=$domain_seen($leaf_name),$label"
                }
                set domain_seen($leaf_name) $label
                set actual_slr [mission0008_cell_slr $cell]
                set mission0008_domain_leaf_owner($leaf_name) $label
                set mission0008_domain_leaf_slr($leaf_name) $actual_slr
                set mission0008_domain_leaf_ref($leaf_name) [get_property REF_NAME $cell]
                lappend mission0008_domain_leaves($label) $leaf_name
                if {$actual_slr ne [list $expected_slr]} {
                    lappend wrong $cell
                }
            }
        }
        set wrong [mission0008_unique $wrong]
    } else {
        error "MISSION0008_BAD_COLLECT_MODE $mode"
    }
    if {[llength $wrong] != 22} {
        error "MISSION0008_BASELINE_CONE_COUNT actual=[llength $wrong] expected=22"
    }

    set center_mixed {}
    set center_to_right {}
    set parent_state {}
    set attention_right {}
    set branch_local {}
    set branch_return {}
    set branch_foreign {}
    set branch_mixed {}
    set classify [open [file join $out core_topology_classification.tsv] w]
    puts $classify "class\tcell\tref\tloc\tactual_slr\tend_slrs\tdirect_sinks"
    foreach cell $wrong {
        set name [get_property NAME $cell]
        set ref [get_property REF_NAME $cell]
        set sinks [mission0008_output_sinks $cell]
        if {$mode eq "diagnostic"} {
            set sink_cells [mission0008_unique [get_cells -quiet -of_objects $sinks]]
            set ends [mission0008_names [get_slrs -quiet -of_objects $sink_cells]]
        } else {
            set ends [mission0008_output_end_slrs $cell]
        }
        if {[string match */u_array/u_center12/* $name]} {
            if {$ends eq {SLR0 SLR2}} {
                set class mixed_center
                lappend center_mixed $cell
            } elseif {$ends eq {SLR2}} {
                set class right_consumer_attention
                lappend center_to_right $cell
            } else {
                error "MISSION0008_CENTER_OWNER_UNCLASSIFIED cell=$name ends=$ends"
            }
        } elseif {[string match */u_array/u_left2/* $name]} {
            if {$ends ne {SLR0}} {error "MISSION0008_PARENT_BOUNDARY_ENDS cell=$name ends=$ends"}
            set class parent_state_boundary
            lappend parent_state $cell
        } elseif {[string match */u_array/u_right2/* $name]} {
            if {$mode eq "diagnostic"} {
                set signature "$ref|[llength $sinks]|[join $ends ,]"
                if {$signature ni {LUT1|57|SLR0,SLR2 LUT6|2|SLR2 LUT2|4|SLR0,SLR2}} {
                    error "MISSION0008_RIGHT_LOCAL_DIRECT_SIGNATURE cell=$name signature=$signature"
                }
            } elseif {$ends ne {SLR2}} {
                error "MISSION0008_RIGHT_LOCAL_ENDS cell=$name ends=$ends"
            }
            set class attention_right_local
            lappend attention_right $cell
        } elseif {[string match */u_shared_compute/u_branch1/* $name]} {
            if {$ref eq "LUT2" && $ends eq {SLR1}} {
                set class foreign_consumer_clear
                lappend branch_foreign $cell
            } elseif {$ref eq "LUT2" && $ends eq {SLR1 SLR2}} {
                set class mixed_branch
                lappend branch_mixed $cell
            } elseif {$ends eq {SLR1}} {
                set class producer_return_boundary
                lappend branch_return $cell
            } elseif {$ends eq {SLR2}} {
                set class branch1_local
                lappend branch_local $cell
            } else {
                error "MISSION0008_BRANCH_OWNER_UNCLASSIFIED cell=$name ref=$ref ends=$ends"
            }
        } else {
            error "MISSION0008_DOMAIN_UNCLASSIFIED cell=$name"
        }
        puts $classify [join [list $class $name $ref [get_property LOC $cell] \
            [mission0008_cell_slr $cell] [join $ends ,] [llength $sinks]] \t]
    }
    close $classify
    foreach {label value expected} [list center_mixed $center_mixed 1 \
            center_to_right $center_to_right 3 parent_state $parent_state 2 \
            attention_right $attention_right 3 branch_local $branch_local 7 \
            branch_return $branch_return 2 branch_foreign $branch_foreign 3 \
            branch_mixed $branch_mixed 1] {
        if {[llength $value] != $expected} {
            error "MISSION0008_CLASS_COUNT class=$label actual=[llength $value] expected=$expected"
        }
    }
    if {$mode eq "diagnostic"} {
        foreach {label value expected_signatures} [list \
                center_mixed $center_mixed {LUT5|87|SLR0,SLR2} \
                center_to_right $center_to_right {LUT5|2|SLR2 LUT5|3|SLR2 LUT5|10|SLR2} \
                parent_state $parent_state {LUT5|1|SLR0 LUT5|1|SLR0} \
                attention_right $attention_right {LUT1|57|SLR0,SLR2 LUT2|4|SLR0,SLR2 LUT6|2|SLR2} \
                branch_local $branch_local {LUT1|12|SLR2 LUT2|16|SLR2 LUT2|124|SLR2 LUT2|471|SLR2 LUT2|1062|SLR2 LUT2|1062|SLR2 LUT3|12|SLR2} \
                branch_return $branch_return {LUT3|2|SLR1 LUT4|4|SLR1} \
                branch_foreign $branch_foreign {LUT2|83|SLR1 LUT2|84|SLR1 LUT2|104|SLR1} \
                branch_mixed $branch_mixed {LUT2|11|SLR1,SLR2}] {
            set actual_signatures {}
            foreach cell $value {
                set direct [mission0008_output_sinks $cell]
                set owners [mission0008_unique [get_cells -quiet -of_objects $direct]]
                set slrs [mission0008_names [get_slrs -quiet -of_objects $owners]]
                lappend actual_signatures \
                    "[get_property REF_NAME $cell]|[llength $direct]|[join $slrs ,]"
            }
            if {[lsort $actual_signatures] ne [lsort $expected_signatures]} {
                error "MISSION0008_DIAGNOSTIC_DIRECT_WITNESS class=$label actual=[lsort $actual_signatures] expected=[lsort $expected_signatures]"
            }
        }
    }
    foreach cell [concat $branch_foreign $branch_mixed] {
        if {[llength [mission0008_clear_input $cell 1]] != 1} {
            error "MISSION0008_CLEAR_SIGNATURE cell=[get_property NAME $cell]"
        }
    }
    if {[mission0008_require_clear_equivalence $out] != 12} {
        error "MISSION0008_CLEAR_EQUIVALENCE_COUNT"
    }
    set d0 [mission0008_collect_d0_terminal]
    set pcie [mission0008_collect_pcie_support]
    return [dict create core_original $wrong center_mixed $center_mixed \
        center_to_right $center_to_right parent_state $parent_state \
        attention_right $attention_right branch_local $branch_local \
        branch_return $branch_return branch_foreign $branch_foreign \
        branch_mixed $branch_mixed domain_baseline $domain_baseline d0 $d0 pcie $pcie]
}

proc mission0008_create_lut_copy {original new_name net_name} {
    set ref [get_property REF_NAME $original]
    if {$ref ni {LUT2 LUT5}} {error "MISSION0008_COPY_REF ref=$ref"}
    if {[llength [get_cells -quiet [list $new_name]]] != 0 || \
            [llength [get_nets -quiet [list $net_name]]] != 0} {
        error "MISSION0008_COPY_ALREADY_EXISTS $new_name"
    }
    create_cell -reference $ref $new_name
    set copy [mission0008_require_one [get_cells -quiet [list $new_name]] "new $ref"]
    set_property INIT [get_property INIT $original] $copy
    set width [string range $ref 3 end]
    for {set index 0} {$index < $width} {incr index} {
        set source_pin [mission0008_require_one [get_pins -quiet -leaf -of_objects $original \
            -filter [format {REF_PIN_NAME == I%s} $index]] "original $ref I$index"]
        set copy_pin [mission0008_require_one [get_pins -quiet -leaf -of_objects $copy \
            -filter [format {REF_PIN_NAME == I%s} $index]] "copy $ref I$index"]
        connect_net -hier -net [mission0008_pin_net $source_pin] -objects $copy_pin
    }
    create_net $net_name
    set new_net [mission0008_require_one [get_nets -quiet [list $net_name]] "new output net"]
    set output [mission0008_require_one [get_pins -quiet -leaf -of_objects $copy \
        -filter {DIRECTION == OUT}] "new LUT output"]
    connect_net -hier -net $new_net -objects $output
    return [list $copy $new_net]
}

proc mission0008_rewire_sinks {original new_net owner_pattern expected} {
    set moved {}
    foreach pin [mission0008_output_sinks $original] {
        set cell [mission0008_require_one [get_cells -quiet -of_objects $pin] "sink cell"]
        if {[string match $owner_pattern [get_property NAME $cell]]} {
            set old_net [mission0008_pin_net $pin]
            disconnect_net -net $old_net -pinlist $pin
            connect_net -hier -net $new_net -objects $pin
            lappend moved $pin
        }
    }
    if {[llength $moved] != $expected} {
        error "MISSION0008_SINK_REWIRE owner=$owner_pattern actual=[llength $moved] expected=$expected"
    }
    return $moved
}

proc mission0008_substitute_clear {cell} {
    set pin [mission0008_require_one [mission0008_clear_input $cell 1] \
        "branch1 clear input for [get_property NAME $cell]"]
    set drivers [mission0008_input_driver_cells $pin]
    set old_driver {}
    foreach driver $drivers {
        if {[string match */u_branch1/clear_*_r_reg* [get_property NAME $driver]]} {
            lappend old_driver $driver
        }
    }
    set old_driver [mission0008_require_one $old_driver "branch1 clear driver"]
    set new_driver [mission0008_counterpart_clear $old_driver]
    set new_q [mission0008_require_one [get_pins -quiet -leaf -of_objects $new_driver \
        -filter {DIRECTION == OUT && REF_PIN_NAME =~ Q*}] "branch0 clear Q"]
    set old_net [mission0008_pin_net $pin]
    set new_net [mission0008_pin_net $new_q]
    if {![string is true -strict [mission0008_property $new_net DONT_TOUCH false]]} {
        error "MISSION0008_CLEAR_REPLACEMENT_NOT_DONT_TOUCH net=[get_property NAME $new_net]"
    }
    set_property DONT_TOUCH false $new_net
    set failed [catch {
        disconnect_net -net $old_net -pinlist $pin
        connect_net -hier -net $new_net -objects $pin
    } message options]
    set_property DONT_TOUCH true $new_net
    if {$failed} {return -options $options $message}
    if {![string is true -strict [mission0008_property $new_net DONT_TOUCH false]]} {
        error "MISSION0008_CLEAR_REPLACEMENT_DONT_TOUCH_NOT_RESTORED net=[get_property NAME $new_net]"
    }
    return [list $pin $old_driver $new_driver]
}

proc mission0008_apply_candidate {candidate out} {
    set center [lindex [dict get $candidate center_mixed] 0]
    set row6 [lindex [dict get $candidate branch_mixed] 0]
    set right_root [mission0008_require_one [get_cells -quiet -hier -regexp \
        {.*u_array/u_right2/u_shard$}] right_shard]
    set center_copy_name [get_property NAME $right_root]/mission0008_center_owner_lut5
    set center_net_name [get_property NAME $right_root]/mission0008_center_owner_lut5_n
    lassign [mission0008_create_lut_copy $center $center_copy_name $center_net_name] \
        center_copy center_net
    set center_moved [mission0008_rewire_sinks $center $center_net \
        */u_array/u_right2/* 28]
    if {[llength [mission0008_output_sinks $center]] != 59} {
        error "MISSION0008_CENTER_RETAINED_SINK_COUNT"
    }

    set row6_parent [file dirname [get_property NAME $row6]]
    set row6_copy_name $row6_parent/mission0008_branch1_row6_qual_lut2
    set row6_net_name $row6_parent/mission0008_branch1_row6_qual_lut2_n
    lassign [mission0008_create_lut_copy $row6 $row6_copy_name $row6_net_name] \
        row6_copy row6_net
    set row6_moved [mission0008_rewire_sinks $row6 $row6_net \
        */u_shared_compute/u_branch1/* 3]
    if {[llength [mission0008_output_sinks $row6]] != 8} {
        error "MISSION0008_ROW6_RETAINED_SINK_COUNT"
    }

    set substitutions {}
    foreach cell [concat [dict get $candidate branch_foreign] [list $row6]] {
        lappend substitutions [mission0008_substitute_clear $cell]
    }
    if {[llength $substitutions] != 4} {error "MISSION0008_SUBSTITUTION_COUNT"}
    set protected [concat [dict get $candidate branch_foreign] [list $row6 $center $center_copy $row6_copy]]
    foreach cell $protected {
        set out_pin [mission0008_require_one [get_pins -quiet -leaf -of_objects $cell \
            -filter {DIRECTION == OUT}] "protected LUT output"]
        set_property KEEP true [mission0008_pin_net $out_pin]
    }
    dict set candidate center_copy $center_copy
    dict set candidate row6_copy $row6_copy
    dict set candidate center_moved_pins $center_moved
    dict set candidate row6_moved_pins $row6_moved
    dict set candidate substitutions $substitutions
    dict set candidate core_all [concat [dict get $candidate core_original] \
        [list $center_copy $row6_copy]]
    return $candidate
}

proc mission0008_empty_slice_sites {clock_region} {
    set cr [mission0008_require_one [get_clock_regions -quiet $clock_region] \
        "clock region $clock_region"]
    set sites [get_sites -quiet -of_objects $cr -filter {SITE_TYPE =~ SLICE*}]
    array set occupied {}
    foreach loc [get_property -quiet LOC [get_cells -quiet -of_objects $cr \
            -filter {IS_PRIMITIVE == 1}]] {
        if {[string match SLICE_X* $loc]} {set occupied($loc) 1}
    }
    set empty {}
    foreach site [lsort -command mission0008_compare_name $sites] {
        set name [get_property NAME $site]
        if {![info exists occupied($name)]} {lappend empty $site}
    }
    return $empty
}

proc mission0008_compare_name {left right} {
    return [string compare [get_property NAME $left] [get_property NAME $right]]
}

proc mission0008_place_reserved {cells clock_region expected_slr map_handle} {
    global mission0008_placed_candidate
    set cells [mission0008_unique $cells]
    set sites [mission0008_empty_slice_sites $clock_region]
    if {[llength $sites] < [llength $cells]} {
        error "MISSION0008_EMPTY_SITE_SHORTAGE cr=$clock_region cells=[llength $cells] empty=[llength $sites]"
    }
    set_property USER_SLR_ASSIGNMENT $expected_slr $cells
    unplace_cell $cells
    set index 0
    foreach cell [lsort -command mission0008_compare_name $cells] {
        set cell_name [get_property NAME $cell]
        if {[info exists mission0008_placed_candidate($cell_name)]} {
            error "MISSION0008_DUPLICATE_PLACEMENT cell=$cell_name"
        }
        set mission0008_placed_candidate($cell_name) \
            [dict create clock_region $clock_region slr $expected_slr]
        set site [lindex $sites $index]
        incr index
        set ref [get_property REF_NAME $cell]
        if {[string match LUT* $ref]} {
            set bels [get_bels -quiet -of_objects $site \
                -filter {TYPE =~ *LUT* && NAME =~ *6LUT}]
        } elseif {[string match FD* $ref]} {
            set bels [get_bels -quiet -of_objects $site \
                -filter {TYPE =~ *FF*}]
        } else {
            error "MISSION0008_PLACE_UNSUPPORTED ref=$ref cell=$cell"
        }
        set bel [mission0008_require_one [lrange $bels 0 0] "placement BEL for $cell"]
        place_cell [list $cell $bel]
        set actual_slr [mission0008_cell_slr $cell]
        set actual_cr [mission0008_cell_cr $cell]
        if {$actual_slr ne [list $expected_slr] || $actual_cr ne [list $clock_region]} {
            error "MISSION0008_PLACE_WRONG_REGION cell=$cell slr=$actual_slr cr=$actual_cr"
        }
        puts $map_handle [join [list [get_property NAME $cell] $ref \
            [get_property NAME $site] [get_property NAME $bel] $expected_slr $clock_region] \t]
    }
}

proc mission0008_place_candidate {candidate out} {
    global mission0008_placed_candidate
    catch {array unset mission0008_placed_candidate}
    array set mission0008_placed_candidate {}
    set map [open [file join $out candidate_site_bel_map.tsv] w]
    puts $map "cell\tref\tsite\tbel\tslr\tclock_region"
    set center_to_right [dict get $candidate center_to_right]
    set replica_near {}
    set replica_far {}
    foreach cell $center_to_right {
        set sinks [llength [mission0008_output_sinks $cell]]
        if {$sinks == 10} {lappend replica_far $cell} else {lappend replica_near $cell}
    }
    if {[llength $replica_far] != 1 || [llength $replica_near] != 2} {
        error "MISSION0008_ATTENTION_REPLICA_SIGNATURE"
    }
    set branch_x1y11 {}
    set branch_x1y12 {}
    set branch_x2y10 {}
    set branch_x2y11 [dict get $candidate branch_return]
    set branch_x2y12 {}
    foreach cell [dict get $candidate branch_local] {
        set ref [get_property REF_NAME $cell]
        set sinks [llength [mission0008_output_sinks $cell]]
        if {$ref eq "LUT1" && $sinks == 12} {
            lappend branch_x1y11 $cell
        } elseif {$ref eq "LUT3" && $sinks == 12} {
            lappend branch_x1y12 $cell
        } elseif {$ref eq "LUT2" && $sinks == 16} {
            lappend branch_x2y10 $cell
        } elseif {$ref eq "LUT2" && $sinks == 124} {
            lappend branch_x2y11 $cell
        } elseif {$ref eq "LUT2" && $sinks in {471 1062}} {
            lappend branch_x2y12 $cell
        } else {
            error "MISSION0008_LOCAL_PLACEMENT_SIGNATURE ref=$ref sinks=$sinks cell=$cell"
        }
    }
    foreach {label value expected} [list x1y11 $branch_x1y11 1 x1y12 $branch_x1y12 1 \
            x2y10 $branch_x2y10 1 x2y11 $branch_x2y11 3 x2y12 $branch_x2y12 3] {
        if {[llength $value] != $expected} {
            error "MISSION0008_CORE_REGION_COUNT region=$label actual=[llength $value] expected=$expected"
        }
    }
    if {[llength [concat $branch_x2y11 $replica_near]] != 5} {
        error "MISSION0008_CORE_REGION_COUNT region=x2y11_combined actual=[llength [concat $branch_x2y11 $replica_near]] expected=5"
    }
    set_property USER_SLR_ASSIGNMENT SLR0 [dict get $candidate parent_state]
    set_property USER_SLR_ASSIGNMENT SLR1 [concat \
        [dict get $candidate branch_foreign] [dict get $candidate branch_mixed]]
    mission0008_place_reserved [dict get $candidate center_mixed] X3Y3 SLR0 $map
    mission0008_place_reserved [list [dict get $candidate row6_copy]] X0Y10 SLR2 $map
    mission0008_place_reserved $branch_x1y11 X1Y11 SLR2 $map
    mission0008_place_reserved $branch_x1y12 X1Y12 SLR2 $map
    mission0008_place_reserved $branch_x2y10 X2Y10 SLR2 $map
    mission0008_place_reserved [concat $branch_x2y11 $replica_near] X2Y11 SLR2 $map
    mission0008_place_reserved $branch_x2y12 X2Y12 SLR2 $map
    mission0008_place_reserved [concat [dict get $candidate attention_right] \
        [list [dict get $candidate center_copy]]] X5Y10 SLR2 $map
    mission0008_place_reserved $replica_far X5Y11 SLR2 $map
    set d0 [dict get $candidate d0]
    mission0008_place_reserved [concat [dict get $d0 AW] [dict get $d0 AR] \
        [dict get $d0 B]] X5Y11 SLR2 $map
    mission0008_place_reserved [dict get $d0 W] X5Y12 SLR2 $map
    mission0008_place_reserved [dict get $d0 R] X5Y13 SLR2 $map
    mission0008_place_reserved [list [dict get $candidate pcie]] X5Y5 SLR1 $map
    close $map
    set retained [mission0008_names [concat [dict get $candidate parent_state] \
        [dict get $candidate branch_foreign] [dict get $candidate branch_mixed]]]
    set expected {}
    foreach name [mission0008_names [concat [dict get $candidate core_all] \
            [dict get $d0 all] [list [dict get $candidate pcie]]]] {
        if {[lsearch -exact $retained $name] < 0} {lappend expected $name}
    }
    set actual [lsort [array names mission0008_placed_candidate]]
    if {[llength $retained] != 6 || [llength $actual] != 1948 || \
            $actual ne [lsort $expected]} {
        error "MISSION0008_PLACEMENT_WHITELIST retained=[llength $retained] placed=[llength $actual] expected=[llength $expected]"
    }
    return $candidate
}

proc mission0008_require_consumer_group {cells class expected_source_slr \
        expected_direct_counts expected_consumer_slrs owner_pattern summary relations failures_name} {
    upvar 1 $failures_name failures
    set observed_counts {}
    foreach cell $cells {
        set name [get_property NAME $cell]
        set source_slr [mission0008_cell_slr $cell]
        set outputs [get_pins -quiet -leaf -of_objects $cell -filter {DIRECTION == OUT}]
        set sinks [mission0008_output_sinks $cell]
        set sink_cells [mission0008_unique [get_cells -quiet -of_objects $sinks]]
        set endpoints [mission0008_unique [all_fanout -flat -endpoints_only -from $outputs]]
        set end_cells [mission0008_unique [get_cells -quiet -of_objects $endpoints]]
        set sink_slrs [mission0008_names [get_slrs -quiet -of_objects $sink_cells]]
        set end_slrs [mission0008_names [get_slrs -quiet -of_objects $end_cells]]
        lappend observed_counts [llength $sinks]
        if {[llength $outputs] != 1} {
            lappend failures "$class output count cell=$name actual=[llength $outputs] expected=1"
        }
        if {$source_slr ne [list $expected_source_slr]} {
            lappend failures "$class source SLR cell=$name actual=$source_slr expected=$expected_source_slr"
        }
        if {[llength $sinks] == 0 || [llength $sink_cells] != [llength $sinks]} {
            lappend failures "$class missing/nonleaf consumer cell=$name pins=[llength $sinks] cells=[llength $sink_cells]"
        }
        if {$sink_slrs ne $expected_consumer_slrs || $end_slrs ne $expected_consumer_slrs} {
            lappend failures "$class consumer SLR cell=$name direct=$sink_slrs end=$end_slrs expected=$expected_consumer_slrs"
        }
        foreach pin $sinks {
            set sink_cell [mission0008_require_one [get_cells -quiet -of_objects $pin] \
                "$class consumer owner"]
            set sink_name [get_property NAME $sink_cell]
            if {$owner_pattern ne "" && ![string match $owner_pattern $sink_name]} {
                lappend failures "$class consumer owner cell=$name sink=$sink_name expected=$owner_pattern"
            }
            puts $relations [join [list $class $name [get_property NAME $outputs] \
                [get_property NAME $pin] $sink_name [mission0008_cell_slr $sink_cell]] \t]
        }
        puts $summary [join [list $class $name [get_property REF_NAME $cell] \
            $source_slr [llength $sinks] [llength $endpoints] \
            [join $sink_slrs ,] [join $end_slrs ,] \
            [expr {$owner_pattern eq "" ? "explicit-boundary" : $owner_pattern}]] \t]
    }
    if {[lsort -integer $observed_counts] ne [lsort -integer $expected_direct_counts]} {
        lappend failures "$class direct counts actual=[lsort -integer $observed_counts] expected=[lsort -integer $expected_direct_counts]"
    }
}

proc mission0008_require_core_connection_partition {candidate out} {
    set failures {}
    set summary [open [file join $out topology_consumer_summary.tsv] w]
    puts $summary "class\tcell\tref\tsource_slr\tdirect_sinks\ttransitive_endpoints\tdirect_slrs\tend_slrs\tconsumer_owner_witness"
    set relations [open [file join $out topology_consumer_relations.tsv] w]
    puts $relations "class\tsource_cell\tsource_pin\tsink_pin\tsink_cell\tsink_slr"
    mission0008_require_consumer_group [dict get $candidate center_mixed] \
        center_local SLR0 {59} {SLR0} */u_array/u_center12/* \
        $summary $relations failures
    mission0008_require_consumer_group [list [dict get $candidate center_copy]] \
        center_right_copy SLR2 {28} {SLR2} */u_array/u_right2/* \
        $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate center_to_right] \
        attention_right_replica SLR2 {2 3 10} {SLR2} */u_array/u_right2/* \
        $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate parent_state] \
        attention_parent_return SLR0 {1 1} {SLR0} "" $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate attention_right] \
        attention_right_local SLR2 {2 4 57} {SLR2} */u_array/u_right2/* \
        $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate branch_local] \
        branch1_local SLR2 {12 12 16 124 471 1062 1062} {SLR2} \
        */u_shared_compute/u_branch1/* $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate branch_return] \
        branch1_producer_return SLR2 {2 4} {SLR1} "" $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate branch_foreign] \
        branch0_foreign_qualification SLR1 {83 84 104} {SLR1} \
        */u_shared_compute/u_branch0/* $summary $relations failures
    mission0008_require_consumer_group [dict get $candidate branch_mixed] \
        branch0_row6_qualification SLR1 {8} {SLR1} \
        */u_shared_compute/u_branch0/* $summary $relations failures
    mission0008_require_consumer_group [list [dict get $candidate row6_copy]] \
        branch1_row6_copy SLR2 {3} {SLR2} */u_shared_compute/u_branch1/* \
        $summary $relations failures
    close $relations
    close $summary

    set center [lindex [dict get $candidate center_mixed] 0]
    set center_copy [dict get $candidate center_copy]
    foreach pin [get_pins -quiet -leaf -of_objects $center -filter {DIRECTION == IN}] {
        set refpin [get_property REF_PIN_NAME $pin]
        set copy_pin [mission0008_require_one [get_pins -quiet -leaf -of_objects \
            $center_copy -filter [format {REF_PIN_NAME == %s} $refpin]] \
            "center copy boundary $refpin"]
        if {[mission0008_pin_driver_records $pin] ne \
                [mission0008_pin_driver_records $copy_pin]} {
            lappend failures "center shared-root input mismatch pin=$refpin"
        }
    }
    foreach cell [dict get $candidate parent_state] {
        set incoming [get_pins -quiet -leaf -of_objects $cell -filter {DIRECTION == IN}]
        set left_witness 0
        foreach pin $incoming {
            foreach source [mission0008_input_driver_cells $pin] {
                if {[string match */u_array/u_left2/* [get_property NAME $source]]} {
                    set left_witness 1
                }
            }
        }
        if {!$left_witness} {
            lappend failures "parent-state incoming left boundary missing cell=[get_property NAME $cell]"
        }
    }
    if {[llength $failures] != 0} {
        error "MISSION0008_CORE_CONNECTION_PARTITION_FAIL findings=[llength $failures] [join $failures {; }]"
    }
}

proc mission0008_require_repaired_clear_partition {candidate} {
    foreach cell [concat [dict get $candidate branch_foreign] \
            [dict get $candidate branch_mixed]] {
        if {[llength [mission0008_clear_input $cell 1]] != 0 || \
                [llength [mission0008_clear_input $cell 0]] != 1} {
            error "MISSION0008_REPAIRED_CLEAR_PARTITION_FAIL branch1 clear retained in repaired branch0 cone: [get_property NAME $cell]"
        }
    }
}

proc mission0008_require_endpoint_topology {candidate out} {
    set failures {}
    set handle [open [file join $out topology_endpoint_witnesses.tsv] w]
    puts $handle "scope\tcells\tinput_pins\tstartpoints\toutput_pins\tdirect_consumers\tendpoints\tsource_slrs\tconsumer_slrs"
    set d0 [dict get $candidate d0]
    set seen {}
    foreach {channel expected_cr} {AW X5Y11 AR X5Y11 B X5Y11 W X5Y12 R X5Y13} {
        set cells [dict get $d0 $channel]
        foreach cell $cells {
            set name [get_property NAME $cell]
            if {[dict exists $seen $name]} {
                lappend failures "D0 overlap cell=$name channels=[dict get $seen $name],$channel"
            }
            dict set seen $name $channel
            if {[mission0008_cell_slr $cell] ne {SLR2} || \
                    [mission0008_cell_cr $cell] ne [list $expected_cr]} {
                lappend failures "D0 placement channel=$channel cell=$name slr=[mission0008_cell_slr $cell] cr=[mission0008_cell_cr $cell]"
            }
        }
        set inputs [get_pins -quiet -leaf -of_objects $cells -filter {DIRECTION == IN}]
        set outputs [get_pins -quiet -leaf -of_objects $cells -filter {DIRECTION == OUT}]
        set fanin [mission0008_chunked_fanin_witnesses $inputs "" \
            endpoint_D0_${channel}_fanin 1]
        set starts [dict get $fanin starts]
        set consumers [mission0008_leaf_peers $outputs IN]
        set fanout [mission0008_chunked_fanout_endpoints $outputs "" \
            endpoint_D0_${channel}_fanout]
        set endpoints [dict get $fanout endpoints]
        if {[llength $inputs] == 0 || [llength $outputs] == 0 || \
                [llength $starts] == 0 || [llength $consumers] == 0 || \
                [llength $endpoints] == 0} {
            lappend failures "D0 consumer witness empty channel=$channel"
        }
        puts $handle [join [list D0_$channel [llength $cells] [llength $inputs] \
            [llength $starts] [llength $outputs] [llength $consumers] \
            [llength $endpoints] \
            [join [mission0008_names [get_slrs -quiet -of_objects \
                [get_cells -quiet -of_objects $starts]]] ,] \
            [join [mission0008_names [get_slrs -quiet -of_objects \
                [get_cells -quiet -of_objects $consumers]]] ,]] \t]
    }
    if {[dict size $seen] != 1929} {
        lappend failures "D0 unique ownership actual=[dict size $seen] expected=1929"
    }
    set pcie [dict get $candidate pcie]
    set pcie_outputs [get_pins -quiet -leaf -of_objects $pcie -filter {DIRECTION == OUT}]
    set pcie_consumers [mission0008_leaf_peers $pcie_outputs IN]
    set destination [mission0008_pcie_destination]
    if {[mission0008_cell_slr $pcie] ne {SLR1} || \
            [mission0008_cell_cr $pcie] ne {X5Y5} || \
            [lsearch -exact [mission0008_names $pcie_consumers] \
                [get_property NAME $destination]] < 0} {
        lappend failures "P0 endpoint/placement witness mismatch"
    }
    set pcie_inputs [get_pins -quiet -leaf -of_objects $pcie -filter {DIRECTION == IN}]
    set pcie_fanin [mission0008_chunked_fanin_witnesses $pcie_inputs "" \
        endpoint_P0_fanin 1]
    set pcie_starts [dict get $pcie_fanin starts]
    puts $handle [join [list P0 1 [llength $pcie_inputs] [llength $pcie_starts] \
        [llength $pcie_outputs] [llength $pcie_consumers] 1 \
        [join [mission0008_names [get_slrs -quiet -of_objects \
            [get_cells -quiet -of_objects $pcie_starts]]] ,] \
        [join [mission0008_names [get_slrs -quiet -of_objects \
            [get_cells -quiet -of_objects $pcie_consumers]]] ,]] \t]
    close $handle
    if {[llength $failures] != 0} {
        error "MISSION0008_ENDPOINT_TOPOLOGY_FAIL findings=[llength $failures] [join $failures {; }]"
    }
}

proc mission0008_add_owner {array_name object owner} {
    upvar 1 $array_name owners
    if {![info exists owners($object)]} {set owners($object) {}}
    if {[lsearch -exact $owners($object) $owner] < 0} {
        lappend owners($object) $owner
        set owners($object) [lsort -unique $owners($object)]
    }
}

proc mission0008_require_leaf_owner_identity {label expected actual} {
    set expected_names [lsort [dict keys $expected]]
    set actual_names [lsort [dict keys $actual]]
    if {$expected_names ne $actual_names} {
        error "MISSION0008_${label}_LEAF_COVERAGE expected=[llength $expected_names] actual=[llength $actual_names] mismatch=[lsort -unique [concat $expected_names $actual_names]]"
    }
    foreach name $expected_names {
        if {[dict get $expected $name] ne [dict get $actual $name]} {
            error "MISSION0008_${label}_CONSUMER_OWNER cell=$name expected=[dict get $expected $name] actual=[dict get $actual $name]"
        }
    }
}

proc mission0008_take_endpoint_sample {objects count} {
    if {[llength $objects] <= $count} {return $objects}
    return [lrange $objects 0 [expr {$count-1}]]
}

proc mission0008_fanin_pilot_groups {domain_pins root_pin_name} {
    set groups [dict create]
    dict for {label pins} $domain_pins {
        dict set groups ${label}_sequential [mission0008_take_endpoint_sample \
            [filter $pins {REF_PIN_NAME =~ D*}] 16]
        dict set groups ${label}_clock [mission0008_take_endpoint_sample \
            [filter $pins {REF_PIN_NAME =~ C* || REF_PIN_NAME =~ CLK*}] 16]
        dict set groups ${label}_reset [mission0008_take_endpoint_sample \
            [filter $pins {REF_PIN_NAME =~ R* || REF_PIN_NAME =~ S* || \
                REF_PIN_NAME =~ PRE* || REF_PIN_NAME =~ CLR*}] 16]
    }

    set reset_pin [get_pins -quiet [list $root_pin_name]]
    if {[llength $reset_pin] == 1} {
        dict set groups shared_reset [mission0008_take_endpoint_sample \
            [mission0008_leaf_peers $reset_pin IN] 16]
    }
    set constant_sources [get_pins -quiet -leaf -of_objects \
        [get_cells -quiet -hier -filter {REF_NAME == VCC || REF_NAME == GND}] \
        -filter {DIRECTION == OUT}]
    if {[llength $constant_sources] != 0} {
        dict set groups present_constants [mission0008_take_endpoint_sample \
            [mission0008_leaf_peers $constant_sources IN] 16]
    }
    set input_ports [get_ports -quiet -filter {DIRECTION == IN}]
    if {[llength $input_ports] != 0} {
        dict set groups present_ports [mission0008_take_endpoint_sample \
            [mission0008_leaf_peers $input_ports IN] 16]
    }
    return $groups
}

proc mission0008_capture_domain_owner_witnesses {candidate out} {
    global mission0008_domain_leaf_owner mission0008_domain_leaf_slr
    global mission0008_domain_leaf_ref mission0008_domain_leaves root_pin_name
    array set owner_slr {}
    dict for {label baseline} [dict get $candidate domain_baseline] {
        set owner_slr($label) [dict get $baseline slr]
    }
    array set selected {}
    foreach cell [dict get $candidate core_original] {
        set selected([get_property NAME $cell]) 1
    }
    array set consumers {}
    array set external_consumers {}
    array set internal_endpoint {}
    array set start_owner_cache {}
    array set endpoint_owner_cache {}
    array set domain_endpoints {}
    array set domain_endpoint_pins {}
    set domain_outputs {}
    set progress [open [file join $out topology_query_progress.tsv] w]
    puts $progress "label\tkind\tevent\tchunk\tchunks\tchunk_roots\ttotal_roots\tunion_objects\telapsed_s\tcumulative_s"
    flush $progress
    set witness_sets [open [file join $out topology_owner_witness_sets.tsv] w]
    puts $witness_sets "owner\tendpoint_cells\tendpoint_pins\tfanin_cells\texternal_startpoints"
    flush $witness_sets
    dict for {label baseline} [dict get $candidate domain_baseline] {
        set names $mission0008_domain_leaves($label)
        set leaves [get_cells -quiet [list {*}$names]]
        if {[llength $leaves] != [llength $names]} {
            close $witness_sets
            close $progress
            error "MISSION0008_DOMAIN_LEAF_REBIND domain=$label actual=[llength $leaves] expected=[llength $names]"
        }
        set endpoints [filter $leaves {REF_NAME =~ FD* || REF_NAME =~ SRL* || REF_NAME =~ RAM* || REF_NAME =~ URAM* || REF_NAME =~ DSP*}]
        set endpoint_pins [get_pins -quiet -leaf -of_objects $endpoints \
            -filter {DIRECTION == IN}]
        if {[llength $endpoints] == 0 || [llength $endpoint_pins] == 0} {
            close $witness_sets
            close $progress
            error "MISSION0008_DOMAIN_OWNER_ENDPOINTS domain=$label cells=[llength $endpoints] pins=[llength $endpoint_pins]"
        }
        foreach pin_name [get_property NAME $endpoint_pins] {
            set internal_endpoint($pin_name) 1
        }
        set domain_endpoints($label) $endpoints
        set domain_endpoint_pins($label) $endpoint_pins
        mission0008_union_named_objects domain_outputs \
            [get_pins -quiet -leaf -of_objects $leaves -filter {DIRECTION == OUT}]
    }
    set pilot_domains [dict create]
    foreach label [array names domain_endpoint_pins] {
        dict set pilot_domains $label $domain_endpoint_pins($label)
    }
    set pilot_groups [mission0008_fanin_pilot_groups $pilot_domains $root_pin_name]
    mission0008_verify_fanin_query_equivalence $pilot_groups $progress $out
    set remaining_endpoints 0
    foreach label [array names domain_endpoint_pins] {
        incr remaining_endpoints [llength $domain_endpoint_pins($label)]
    }
    dict set ::mission0008_query_remaining_total FANIN_ENDPOINT $remaining_endpoints

    dict for {label baseline} [dict get $candidate domain_baseline] {
        set endpoints $domain_endpoints($label)
        set endpoint_pins $domain_endpoint_pins($label)
        set fanin [mission0008_chunked_fanin_witnesses $endpoint_pins $progress \
            domain_${label}_fanin 1]
        set fanin_cells [dict get $fanin cells]
        set fanin_names [lsort -unique [get_property NAME $fanin_cells]]
        set reset_root_pin [get_pins -quiet [list $root_pin_name]]
        set reset_root_cell [get_cells -quiet -of_objects $reset_root_pin]
        if {[llength $reset_root_pin] == 1 && [llength $reset_root_cell] == 1 && \
                [lsearch -exact $fanin_names [get_property NAME $reset_root_cell]] >= 0} {
            mission0008_add_owner external_consumers $root_pin_name $label
        }
        foreach name [lsort -unique [concat $fanin_names [get_property NAME $endpoints]]] {
            if {[info exists mission0008_domain_leaf_owner($name)]} {
                mission0008_add_owner consumers $name $label
            }
        }
        set starts [dict get $fanin starts]
        set external_count 0
        foreach pin $starts {
            set pin_name [get_property NAME $pin]
            if {![info exists start_owner_cache($pin_name)]} {
                set start_owner_cache($pin_name) {}
                foreach cell [get_cells -quiet -of_objects $pin] {
                    set cell_name [get_property NAME $cell]
                    if {[info exists mission0008_domain_leaf_owner($cell_name)]} {
                        lappend start_owner_cache($pin_name) \
                            $cell_name:$mission0008_domain_leaf_owner($cell_name)
                    }
                }
            }
            if {[llength $start_owner_cache($pin_name)] == 0} {
                mission0008_add_owner external_consumers $pin_name $label
                incr external_count
            }
        }
        puts $witness_sets [join [list $label [llength $endpoints] \
            [llength $endpoint_pins] [llength $fanin_names] $external_count] \t]
        flush $witness_sets
    }
    set domain_outputs [mission0008_named_object_values $domain_outputs]
    set fanout [mission0008_chunked_fanout_endpoints $domain_outputs $progress \
        domain_parent_fanout]
    set all_ends [dict get $fanout endpoints]
    set parent_ends {}
    foreach endpoint $all_ends {
        set endpoint_name [get_property NAME $endpoint]
        if {[info exists internal_endpoint($endpoint_name)]} {continue}
        if {![info exists endpoint_owner_cache($endpoint_name)]} {
            set endpoint_owner_cache($endpoint_name) {}
            foreach endpoint_cell [get_cells -quiet -of_objects $endpoint] {
                set cell_name [get_property NAME $endpoint_cell]
                if {[info exists mission0008_domain_leaf_owner($cell_name)]} {
                    lappend endpoint_owner_cache($endpoint_name) \
                        $cell_name:$mission0008_domain_leaf_owner($cell_name)
                }
            }
        }
        if {[llength $endpoint_owner_cache($endpoint_name)] == 0} {
            lappend parent_ends $endpoint
        }
    }
    if {[llength $parent_ends] != 0} {
        set parent_query [mission0008_chunked_fanin_witnesses $parent_ends \
            $progress parent_fanin 0]
        set parent_fanin [dict get $parent_query cells]
        set parent_names [lsort -unique [get_property NAME $parent_fanin]]
        foreach name $parent_names {
            if {[info exists mission0008_domain_leaf_owner($name)]} {
                mission0008_add_owner consumers $name parent
            }
        }
        puts $witness_sets [join [list parent [llength $parent_ends] \
            [llength $parent_ends] [llength $parent_names] 0] \t]
        flush $witness_sets
    }
    close $witness_sets
    close $progress

    set failures {}
    set expected {}
    set actual {}
    set handle [open [file join $out topology_domain_leaf_owner_witnesses.tsv] w]
    puts $handle "cell\tref\tlogical_domain\tclass\tphysical_slr\tallowed_slrs\tconsumer_owner_set\tsource_witness\tconsumer_witness"
    foreach name [lsort [array names mission0008_domain_leaf_owner]] {
        if {[info exists selected($name)]} {continue}
        set logical $mission0008_domain_leaf_owner($name)
        dict set expected $name $logical
        if {![info exists consumers($name)] || [llength $consumers($name)] == 0} {
            lappend failures "unclassified leaf=$name domain=$logical"
            continue
        }
        set owners [lsort -unique $consumers($name)]
        if {[llength $owners] == 1 && [lindex $owners 0] eq $logical} {
            set class local
        } elseif {[llength $owners] == 1} {
            set class boundary
        } else {
            set class shared_root
        }
        set allowed [list $owner_slr($logical)]
        foreach owner $owners {
            if {[info exists owner_slr($owner)]} {lappend allowed $owner_slr($owner)}
        }
        set allowed [lsort -unique $allowed]
        set physical $mission0008_domain_leaf_slr($name)
        if {[llength $physical] != 1 || [lsearch -exact $allowed [lindex $physical 0]] < 0} {
            lappend failures "physical owner cell=$name actual=$physical allowed=$allowed owners=$owners"
        }
        dict set actual $name $logical
        puts $handle [join [list $name $mission0008_domain_leaf_ref($name) $logical \
            $class $physical [join $allowed ,] [join $owners ,] \
            domain:$logical owners:[join $owners ,]] \t]
    }
    close $handle
    set coverage_code [catch {
        mission0008_require_leaf_owner_identity DOMAIN $expected $actual
    } coverage_message]
    if {$coverage_code} {lappend failures $coverage_message}

    set external [open [file join $out topology_parent_shared_root_witnesses.tsv] w]
    puts $external "source_pin\tclass\tconsumer_owner_set\tconsumer_witness"
    foreach pin [lsort [array names external_consumers]] {
        set owners [lsort -unique $external_consumers($pin)]
        set class [expr {[llength $owners] == 1 ? "boundary" : "shared_root"}]
        puts $external [join [list $pin $class [join $owners ,] owners:[join $owners ,]] \t]
    }
    close $external
    if {![info exists external_consumers($root_pin_name)]} {
        lappend failures "global reset root lacks owner witness: $root_pin_name"
    }
    if {[llength $failures] != 0} {
        error "MISSION0008_DOMAIN_OWNER_WITNESS_FAIL findings=[llength $failures] [join $failures {; }]"
    }
    set path [file join $out topology_domain_leaf_owner_witnesses.tsv]
    return [dict create count [dict size $actual] sha256 [mission0008_sha256 $path] \
        path $path external [array size external_consumers]]
}

proc mission0008_write_endpoint_leaf_witnesses {candidate out} {
    set d0 [dict get $candidate d0]
    set cells [concat [dict get $d0 all] [list [dict get $candidate pcie]]]
    set relations [mission0008_cached_net_relations \
        [get_pins -quiet -leaf -of_objects $cells]]
    array set pin_key {}
    array set pin_direction {}
    array set pin_drivers {}
    array set net_sinks {}
    foreach row [dict get $relations pins] {
        set pin_key([lindex $row 0]) [lindex $row 3]
        set pin_direction([lindex $row 0]) [lindex $row 2]
        set pin_drivers([lindex $row 0]) [lindex $row 4]
    }
    foreach row [dict get $relations nets] {
        set net_sinks([lindex $row 0]) [lindex $row 3]
    }
    array set class_by_cell {}
    foreach channel {AW AR W B R} {
        foreach cell [dict get $d0 $channel] {
            set class_by_cell([get_property NAME $cell]) D0_$channel
        }
    }
    set pcie_name [get_property NAME [dict get $candidate pcie]]
    set class_by_cell($pcie_name) P0
    set seen {}
    set failures {}
    set handle [open [file join $out topology_endpoint_leaf_owner_witnesses.tsv] w]
    puts $handle "cell\tref\tclass\tphysical_slr\tinput_driver_pins\toutput_consumer_pins\tconsumer_witness"
    foreach cell $cells {
        set name [get_property NAME $cell]
        if {[dict exists $seen $name]} {
            lappend failures "duplicate endpoint leaf=$name"
            continue
        }
        dict set seen $name $class_by_cell($name)
        set drivers {}
        set sinks {}
        foreach pin [get_pins -quiet -leaf -of_objects $cell] {
            set pin_name [get_property NAME $pin]
            if {$pin_direction($pin_name) eq "IN"} {
                set drivers [concat $drivers [split $pin_drivers($pin_name) ,]]
            } elseif {$pin_direction($pin_name) eq "OUT" && \
                    [info exists net_sinks($pin_key($pin_name))]} {
                set sinks [concat $sinks [split $net_sinks($pin_key($pin_name)) ,]]
            }
        }
        set drivers [lsort -unique $drivers]
        set sinks [lsort -unique $sinks]
        if {[llength $drivers] == 0 || [llength $sinks] == 0} {
            lappend failures "empty endpoint witness cell=$name drivers=[llength $drivers] sinks=[llength $sinks]"
        }
        puts $handle [join [list $name [get_property REF_NAME $cell] \
            $class_by_cell($name) [mission0008_cell_slr $cell] \
            [join $drivers ,] [join $sinks ,] \
            canonical_leaf_pins:[llength $drivers]+[llength $sinks]] \t]
    }
    close $handle
    if {[dict size $seen] != 1930} {
        lappend failures "endpoint leaf coverage actual=[dict size $seen] expected=1930"
    }
    if {[llength $failures] != 0} {
        error "MISSION0008_ENDPOINT_LEAF_WITNESS_FAIL findings=[llength $failures] [join $failures {; }]"
    }
}

proc mission0008_require_topology_partition {candidate out} {
    set failures {}
    set core [dict get $candidate core_all]
    if {[llength [mission0008_unique $core]] != 24} {
        lappend failures "core selected count is not 24"
    }
    set d0 [dict get [dict get $candidate d0] all]
    if {[llength $d0] != 1929} {lappend failures "D0 selected count is not 1929"}
    if {[expr {[llength $core]+[llength $d0]+1}] != 1954} {
        lappend failures "combined selected count is not 1954"
    }
    if {![dict exists $candidate topology_baseline]} {
        lappend failures "per-leaf topology baseline is missing"
    } else {
        set topology_baseline [dict get $candidate topology_baseline]
        set topology_path [dict get $topology_baseline path]
        if {![file isfile $topology_path] || \
                [mission0008_sha256 $topology_path] ne [dict get $topology_baseline sha256]} {
            lappend failures "per-leaf topology baseline identity changed"
        }
    }
    if {[llength [dict get $candidate center_moved_pins]] != 28 || \
            [llength [dict get $candidate row6_moved_pins]] != 3 || \
            [llength [dict get $candidate substitutions]] != 4} {
        lappend failures "ECO connection budget mismatch"
    }
    if {[mission0008_require_clear_equivalence $out] != 12} {
        lappend failures "clear equivalence is not 12 pairs"
    }
    array set selected {}
    foreach cell $core {set selected([get_property NAME $cell]) 1}
    array set covered {}
    set domain_report [open [file join $out topology_domain_coverage.tsv] w]
    puts $domain_report "domain\texpected_slr\tbaseline_leaves\tcurrent_leaves\tbaseline_sequential\tcurrent_sequential\tbaseline_dsp\tcurrent_dsp\tselected\tdefault_owner\toverlap\tdefault_misplaced\toutput_pins\tdirect_consumers\ttransitive_endpoints\tconsumer_slrs"
    dict for {label baseline} [dict get $candidate domain_baseline] {
        set root [mission0008_require_one [get_cells -quiet [list [dict get $baseline root]]] \
            "current domain $label"]
        set root_name [get_property NAME $root]
        set leaves [get_cells -quiet -hier -filter \
            [format {NAME =~ "%s/*" && IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND} $root_name]]
        set sequential [filter $leaves {REF_NAME =~ FD* || REF_NAME =~ SRL*}]
        set dsps [filter $leaves {REF_NAME == DSP48E2}]
        set new_expected [expr {$label in {attention_right mlp_branch1} ? 1 : 0}]
        if {[llength $leaves] != [expr {[dict get $baseline leaves]+$new_expected}]} {
            lappend failures "domain $label leaf delta is not +$new_expected"
        }
        if {[llength $sequential] != [dict get $baseline sequential] || \
                [llength $dsps] != [dict get $baseline dsp]} {
            lappend failures "domain $label sequential/DSP count changed"
        }
        set selected_count 0
        set default_count 0
        set overlap_count 0
        set misplaced_count 0
        foreach cell $leaves {
            set name [get_property NAME $cell]
            if {[info exists covered($name)]} {
                incr overlap_count
                lappend failures "domain ownership overlap cell=$name owners=$covered($name),$label"
            }
            set covered($name) $label
            if {[info exists selected($name)]} {
                incr selected_count
            } else {
                incr default_count
                if {[mission0008_cell_slr $cell] ne [list [dict get $baseline slr]]} {
                    incr misplaced_count
                }
            }
        }
        if {$misplaced_count != 0} {
            lappend failures "domain $label default-owner misplaced=$misplaced_count"
        }
        set outputs [get_pins -quiet -leaf -of_objects $leaves -filter {DIRECTION == OUT}]
        set consumers [mission0008_leaf_peers $outputs IN]
        set fanout [mission0008_chunked_fanout_endpoints $outputs "" \
            topology_${label}_fanout]
        set endpoints [dict get $fanout endpoints]
        set consumer_cells [mission0008_unique [get_cells -quiet -of_objects $consumers]]
        if {[llength $outputs] == 0 || [llength $consumers] == 0 || \
                [llength $endpoints] == 0} {
            lappend failures "domain $label lacks grouped consumer witnesses"
        }
        puts $domain_report [join [list $label [dict get $baseline slr] \
            [dict get $baseline leaves] [llength $leaves] \
            [dict get $baseline sequential] [llength $sequential] \
            [dict get $baseline dsp] [llength $dsps] $selected_count \
            $default_count $overlap_count $misplaced_count [llength $outputs] \
            [llength $consumers] [llength $endpoints] \
            [join [mission0008_names [get_slrs -quiet -of_objects $consumer_cells]] ,]] \t]
    }
    close $domain_report
    foreach cell $core {
        if {![info exists covered([get_property NAME $cell])]} {
            lappend failures "selected core cell lacks domain coverage: [get_property NAME $cell]"
        }
    }
    foreach {cells slr class} [list \
            [concat [dict get $candidate center_mixed] [dict get $candidate parent_state]] SLR0 boundary_slr0 \
            [concat [dict get $candidate center_to_right] [dict get $candidate attention_right] \
                [dict get $candidate branch_local] [dict get $candidate branch_return] \
                [list [dict get $candidate center_copy] [dict get $candidate row6_copy]]] SLR2 local_slr2 \
            [concat [dict get $candidate branch_foreign] [dict get $candidate branch_mixed]] SLR1 foreign_slr1] {
        foreach cell $cells {
            if {[mission0008_cell_slr $cell] ne [list $slr]} {
                lappend failures "$class misplaced: [get_property NAME $cell]"
            }
        }
    }
    set clear_report [open [file join $out topology_clear_sources.tsv] w]
    puts $clear_report "branch\tcell\tslr\tdirect_sinks\tcross_slr_sinks"
    foreach {branch slr} {0 SLR1 1 SLR2} {
        set sources [mission0008_clear_sources $branch]
        if {[llength $sources] != 12} {lappend failures "branch$branch clear count=[llength $sources]"}
        foreach cell $sources {
            set cross 0
            set sinks [mission0008_output_sinks $cell]
            foreach pin $sinks {
                set sink_cell [get_cells -quiet -of_objects $pin]
                if {[mission0008_cell_slr $sink_cell] ne [list $slr]} {incr cross}
            }
            puts $clear_report [join [list $branch [get_property NAME $cell] \
                [mission0008_cell_slr $cell] [llength $sinks] $cross] \t]
            if {$cross != 0} {lappend failures "branch$branch clear cross sinks=$cross cell=$cell"}
        }
    }
    close $clear_report
    set clear_code [catch {mission0008_require_repaired_clear_partition $candidate} clear_message]
    if {$clear_code} {lappend failures $clear_message}
    set core_code [catch {mission0008_require_core_connection_partition $candidate $out} core_message]
    if {$core_code} {lappend failures $core_message}
    set endpoint_code [catch {mission0008_require_endpoint_topology $candidate $out} endpoint_message]
    if {$endpoint_code} {lappend failures $endpoint_message}
    set endpoint_leaf_code [catch {
        mission0008_write_endpoint_leaf_witnesses $candidate $out
    } endpoint_leaf_message]
    if {$endpoint_leaf_code} {lappend failures $endpoint_leaf_message}
    set boundary [open [file join $out topology_boundary_witnesses.tsv] w]
    puts $boundary "class\tcell\tref\tlocation_slr\tconsumer_slrs\tdirect_sinks"
    foreach {class cells expected_source expected_consumers} [list \
            producer_return [dict get $candidate branch_return] SLR2 SLR1 \
            parent_state [dict get $candidate parent_state] SLR0 SLR0 \
            shared_center_inputs [list [dict get $candidate center_copy]] SLR2 SLR2] {
        foreach cell $cells {
            set actual_source [mission0008_cell_slr $cell]
            set actual_consumers [mission0008_output_end_slrs $cell]
            if {$actual_source ne [list $expected_source] || \
                    $actual_consumers ne [list $expected_consumers]} {
                lappend failures "boundary $class cell=[get_property NAME $cell] source=$actual_source/$expected_source consumers=$actual_consumers/$expected_consumers"
            }
            puts $boundary [join [list $class [get_property NAME $cell] \
                [get_property REF_NAME $cell] [mission0008_cell_slr $cell] \
                [join [mission0008_output_end_slrs $cell] ,] \
                [llength [mission0008_output_sinks $cell]]] \t]
        }
    }
    close $boundary
    if {[llength $failures] != 0} {
        error "MISSION0008_TOPOLOGY_PARTITION_FAIL findings=[llength $failures] [join $failures {; }]"
    }
    puts "MISSION0008_TOPOLOGY_PARTITION_PASS core=24 d0=1929 pcie=1 selected=1954 clear=24"
}
