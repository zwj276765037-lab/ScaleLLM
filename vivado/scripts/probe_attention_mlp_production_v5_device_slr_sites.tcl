# Device-only validation of the Vivado 2025.2 SLR/site relationship API.
# No design or checkpoint is opened and no implementation command is run.

set out [file normalize $::env(HAP_V5_DEVICE_SLR_PROBE_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $out

proc hap_v5_device_probe_stage {out stage} {
    set fp [open [file join $out stage.txt] w]
    puts $fp "stage=$stage"
    close $fp
}

hap_v5_device_probe_stage $out startup

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
hap_v5_device_probe_stage $out create_in_memory_project
create_project -in_memory -part $part
set actual_part [get_property PART [current_project]]
if {$actual_part ne $part} {
    error "V5 device SLR probe part mismatch: $actual_part"
}

# Device geometry collections are populated only after a design is linked in
# Vivado 2025.2.  Synthesize a one-output disposable top into the in-memory
# project.  The source exists only in this probe artifact and is never added to
# the production project or written as a checkpoint.
hap_v5_device_probe_stage $out synthesize_disposable_top
set disposable_rtl [file join $out hap_v5_device_probe_top.sv]
set rtl_fp [open $disposable_rtl w]
puts $rtl_fp {module hap_v5_device_probe_top(output logic probe_o);}
puts $rtl_fp {  assign probe_o = 1'b0;}
puts $rtl_fp {endmodule}
close $rtl_fp
read_verilog -sv $disposable_rtl
synth_design -top hap_v5_device_probe_top -part $part \
    -flatten_hierarchy none
if {[llength [get_designs -quiet]] != 1} {
    error "V5 device SLR probe did not create exactly one linked design"
}

hap_v5_device_probe_stage $out query_slr_site_relationships
set slrs [get_slrs -quiet]
set slr_names [lsort -dictionary -unique [get_property NAME $slrs]]
if {$slr_names ne {SLR0 SLR1 SLR2}} {
    error "V5 device SLR set mismatch: $slr_names"
}

set site_to_slr [dict create]
set slr_site_counts {}
set reverse_relation_ok 1
set site_has_slr_index_property 0
set detail [open [file join $out device_slr_site_probe.txt] w]
puts $detail "status=V5_DEVICE_SLR_SITE_PROBE_DETAIL"
puts $detail "part=$actual_part"

for {set index 0} {$index < 3} {incr index} {
    set expected_name SLR${index}
    set slr [get_slrs -quiet $expected_name]
    if {[llength $slr] != 1} {
        error "V5 device SLR identity is not unique: $expected_name"
    }

    # One bulk query per SLR is the API contract used by the production audit.
    set slr_sites [get_sites -quiet -of_objects $slr]
    set names [get_property NAME $slr_sites]
    if {[llength $slr_sites] == 0 ||
        [llength $names] != [llength $slr_sites]} {
        error "V5 device SLR/site query failed: slr=$expected_name sites=[llength $slr_sites] names=[llength $names]"
    }
    set unique_names [lsort -dictionary -unique $names]
    if {[llength $unique_names] != [llength $names]} {
        error "V5 device SLR contains duplicate site names: $expected_name"
    }

    # Validate the reverse relationship in one bulk query, never per site.
    set reverse_names [lsort -dictionary -unique [get_property NAME \
        [get_slrs -quiet -of_objects $slr_sites]]]
    if {$reverse_names ne [list $expected_name]} {
        set reverse_relation_ok 0
        error "V5 bulk site-to-SLR relationship mismatch: expected=$expected_name actual=$reverse_names"
    }

    set sample [lindex $slr_sites 0]
    set sample_properties [list_property $sample]
    if {[lsearch -exact $sample_properties SLR_INDEX] >= 0} {
        set site_has_slr_index_property 1
    }
    puts $detail "slr${index}_site_count=[llength $unique_names]"
    puts $detail "slr${index}_sample_site=[get_property NAME $sample]"
    puts $detail "slr${index}_reverse_relation=$reverse_names"

    foreach name $unique_names {
        if {[dict exists $site_to_slr $name]} {
            error "V5 device site belongs to multiple SLR sets: site=$name old=[dict get $site_to_slr $name] new=$index"
        }
        dict set site_to_slr $name $index
    }
    lappend slr_site_counts [llength $unique_names]
}

set all_sites [get_sites -quiet]
set all_site_names [lsort -dictionary -unique [get_property NAME $all_sites]]
set mapped_site_names [lsort -dictionary [dict keys $site_to_slr]]
set site_union_exact [expr {$mapped_site_names eq $all_site_names}]
puts $detail "all_site_count=[llength $all_site_names]"
puts $detail "mapped_site_count=[llength $mapped_site_names]"
puts $detail "site_union_exact=$site_union_exact"
puts $detail "site_has_slr_index_property=$site_has_slr_index_property"
close $detail

set status [expr {$site_union_exact && $reverse_relation_ok &&
    !$site_has_slr_index_property ?
    "V5_DEVICE_SLR_SITE_API_PROBE_PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] evidence_class V5_DEVICE_ONLY_SLR_SITE_API_PROBE \
    part $actual_part slr_count [llength $slr_names] \
    slr0_site_count [lindex $slr_site_counts 0] \
    slr1_site_count [lindex $slr_site_counts 1] \
    slr2_site_count [lindex $slr_site_counts 2] \
    all_site_count [llength $all_site_names] \
    mapped_site_count [llength $mapped_site_names] \
    site_union_exact $site_union_exact \
    cross_slr_site_overlap 0 reverse_relation_ok $reverse_relation_ok \
    site_has_slr_index_property $site_has_slr_index_property \
    synthesis_run 1 disposable_probe_top 1 \
    checkpoint_opened 0 implementation_commands_run 0 \
    checkpoint_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
hap_v5_device_probe_stage $out complete
close_project
if {$status ne "V5_DEVICE_SLR_SITE_API_PROBE_PASS"} {
    error "V5 device SLR/site API probe failed"
}
