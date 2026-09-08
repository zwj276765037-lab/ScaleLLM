set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set out [file normalize $::env(HAP_REPORT_DIR)]
file mkdir $out

if {![file exists $input_dcp]} {
    error "missing input DCP $input_dcp"
}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

proc pin_names {objects} {
    set names {}
    foreach object $objects {
        lappend names [get_property NAME $object]
    }
    return [lsort -dictionary -unique $names]
}

open_checkpoint $input_dcp
set leaves [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/*/u_leaf && REF_NAME == LUT1}]]
if {[llength $leaves] != 816} {
    error "capture leaf LUT1 count mismatch expected=816 actual=[llength $leaves]"
}

set detail [open [file join $out capture_leaf_connectivity.tsv] w]
puts $detail "index\tleaf\tlocal_nets\tsegment_nets\tlocal_ce\tsegment_ce\tfanout_ce\tfanout_d\tfanout_other\tfanout_total"

set index 0
set local_ce_total 0
set segment_ce_total 0
set fanout_ce_total 0
set fanout_d_total 0
set fanout_other_total 0
set min_fanout_ce 1000000000
set max_fanout_ce 0
set min_fanout_d 1000000000
set max_fanout_d 0
set fanout_ce_leaves 0
set fanout_d_leaves 0

foreach leaf $leaves {
    set output [get_pins -quiet -of_objects $leaf -filter {DIRECTION == OUT}]
    if {[llength $output] != 1} {
        error "capture leaf output mismatch leaf=$leaf actual=[llength $output]"
    }
    set local_nets [get_nets -quiet -of_objects $output]
    set segment_nets [get_nets -quiet -segments -of_objects $output]
    set local_ce [get_pins -quiet -leaf -of_objects $local_nets -filter {
        DIRECTION == IN && REF_PIN_NAME == CE}]
    set segment_ce [get_pins -quiet -leaf -of_objects $segment_nets -filter {
        DIRECTION == IN && REF_PIN_NAME == CE}]
    set fanout [all_fanout -quiet -flat -endpoints_only -from $output]
    set fanout_ce [filter $fanout {IS_LEAF && REF_PIN_NAME == CE}]
    set fanout_d [filter $fanout {IS_LEAF && REF_PIN_NAME == D}]
    set fanout_other {}
    foreach endpoint $fanout {
        set ref_pin [get_property REF_PIN_NAME $endpoint]
        if {$ref_pin ne "CE" && $ref_pin ne "D"} {
            lappend fanout_other $endpoint
        }
    }

    set local_ce_count [llength $local_ce]
    set segment_ce_count [llength $segment_ce]
    set fanout_ce_count [llength $fanout_ce]
    set fanout_d_count [llength $fanout_d]
    set fanout_other_count [llength $fanout_other]
    incr local_ce_total $local_ce_count
    incr segment_ce_total $segment_ce_count
    incr fanout_ce_total $fanout_ce_count
    incr fanout_d_total $fanout_d_count
    incr fanout_other_total $fanout_other_count
    if {$fanout_ce_count != 0} {incr fanout_ce_leaves}
    if {$fanout_d_count != 0} {incr fanout_d_leaves}
    if {$fanout_ce_count < $min_fanout_ce} {set min_fanout_ce $fanout_ce_count}
    if {$fanout_ce_count > $max_fanout_ce} {set max_fanout_ce $fanout_ce_count}
    if {$fanout_d_count < $min_fanout_d} {set min_fanout_d $fanout_d_count}
    if {$fanout_d_count > $max_fanout_d} {set max_fanout_d $fanout_d_count}

    puts $detail [join [list $index [get_property NAME $leaf] \
        [join [pin_names $local_nets] ,] \
        [join [pin_names $segment_nets] ,] $local_ce_count \
        $segment_ce_count $fanout_ce_count $fanout_d_count \
        $fanout_other_count [llength $fanout]] "\t"]
    if {$index < 3} {
        set sample [open [file join $out sample_${index}_endpoints.txt] w]
        foreach endpoint $fanout {
            set cell [get_cells -quiet -of_objects $endpoint]
            puts $sample [join [list [get_property NAME $endpoint] \
                [get_property REF_PIN_NAME $endpoint] \
                [get_property NAME $cell] [get_property REF_NAME $cell]] "\t"]
        }
        close $sample
    }
    incr index
}
close $detail

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] input_dcp $input_dcp \
    capture_leaf_lut1 [llength $leaves] local_ce_total $local_ce_total \
    segment_ce_total $segment_ce_total fanout_ce_total $fanout_ce_total \
    fanout_d_total $fanout_d_total fanout_other_total $fanout_other_total \
    fanout_ce_leaves $fanout_ce_leaves fanout_d_leaves $fanout_d_leaves \
    min_fanout_ce $min_fanout_ce max_fanout_ce $max_fanout_ce \
    min_fanout_d $min_fanout_d max_fanout_d $max_fanout_d] {
    puts $summary "$key=$value"
}
close $summary
close_design
puts "MLP_CAPTURE_LEAF_DIAG leaves=[llength $leaves] fanout_ce=$fanout_ce_total fanout_d=$fanout_d_total"
