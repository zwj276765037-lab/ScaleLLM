set dcp [file normalize [lindex $argv 0]]
open_checkpoint $dcp
puts "M7_DCP_NONPRIMITIVE_BEGIN"
foreach c [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE == 0}] {
    set n [get_property NAME $c]
    set r [get_property REF_NAME $c]
    set o [get_property ORIG_REF_NAME $c]
    if {[string match -nocase "*qk*" $n] ||
        [string match -nocase "*qk*" $r] ||
        [string match -nocase "*qk*" $o]} {
        puts "M7_DCP_CELL NAME=$n REF=$r ORIG=$o"
    }
}
puts "M7_DCP_NONPRIMITIVE_END"
close_design
exit
