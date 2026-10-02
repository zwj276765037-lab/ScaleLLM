set scopes [get_scopes -quiet -r *]
puts "M09_SCOPE_COUNT: [llength $scopes]"
foreach scope $scopes {
    set name [get_property NAME $scope]
    if {[regexp {dut$|u_wrapper$|u_core$|u_lane$} $name]} {
        current_scope $name
        set direct [get_objects -quiet *]
        puts "M09_SCOPE: $name DIRECT_OBJECTS=[llength $direct]"
    }
}
set shown 0
foreach scope $scopes {
    set name [get_property NAME $scope]
    if {$shown < 120 && [regexp {g_row\[0\].*g_pair\[0\]} $name]} {
        puts "M09_ROW0_PAIR0_SCOPE: $name"
        incr shown
    }
}
exit
