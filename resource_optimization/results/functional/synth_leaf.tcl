set_param general.maxThreads 4
set run_dir [file normalize [lindex $argv 0]]
set source [file normalize [lindex $argv 1]]
set top hap_a8w4_scalecode_recover2_lut
set part xcvu9p-flga2104-2L-e
if {![file isfile $source]} {error "Missing candidate source: $source"}
puts "LEAF_SYNTH_IDENTITY source=$source top=$top part=$part tool=[version -short]"
create_project -in_memory -part $part
read_verilog -sv $source
synth_design -top $top -part $part -mode out_of_context -flatten_hierarchy none
report_utilization -file [file join $run_dir utilization_synth.rpt]
set dsps [get_cells -hierarchical -quiet -filter {REF_NAME == DSP48E2}]
set inventory [open [file join $run_dir dsp_inventory.tsv] w]
puts $inventory "cell\tref_name\tuse_mult\tareg\tbreg\tadreg\tdreg\tmreg\tpreg"
foreach dsp [lsort $dsps] {
    set fields [list [get_property NAME $dsp] [get_property REF_NAME $dsp]]
    foreach property {USE_MULT AREG BREG ADREG DREG MREG PREG} {
        set value ""
        catch {set value [get_property $property $dsp]}
        lappend fields $value
    }
    puts $inventory [join $fields "\t"]
}
close $inventory
write_checkpoint -force [file join $run_dir post_synth.dcp]
write_verilog -force -mode funcsim [file join $run_dir post_synth_funcsim.v]
puts "LEAF_POST_SYNTH_EXPORT_PASS dsp48e2_count=[llength $dsps]"
close_project
