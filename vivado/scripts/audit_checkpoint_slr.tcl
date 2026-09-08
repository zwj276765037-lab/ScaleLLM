set checkpoint [file normalize $::env(HAP_CHECKPOINT)]
set output [file normalize $::env(HAP_OUTPUT)]
if {![file exists $checkpoint]} { error "Missing checkpoint: $checkpoint" }
open_checkpoint $checkpoint
set handle [open $output w]
puts $handle "checkpoint=$checkpoint"
foreach slr [get_slrs] {
    set cells [get_cells -quiet -hierarchical -filter \
        "REF_NAME == DSP48E2 && LOC =~ [get_property NAME $slr]*"]
    # LOC names do not contain SLR names.  Count each DSP by testing whether
    # its placed site belongs to the current SLR.
    set count 0
    foreach cell [get_cells -quiet -hierarchical -filter \
        {REF_NAME == DSP48E2}] {
        set site [get_sites -quiet -of_objects $cell]
        if {[llength $site] != 0 &&
            [get_property NAME [get_slrs -quiet -of_objects $site]] eq
            [get_property NAME $slr]} {
            incr count
        }
    }
    puts $handle "[get_property NAME $slr]_dsp48e2=$count"
}
close $handle
close_design
