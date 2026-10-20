set raw {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_shared_compute/parent_head_r[0]}
set seg [lsort -unique [list $raw]]
puts [list raw $raw sorted_list $seg string_ne [expr {$raw ne $seg}] lengths [list [llength $raw] [llength $seg]] element_equal [expr {[lindex $raw 0] eq [lindex $seg 0]}]]
