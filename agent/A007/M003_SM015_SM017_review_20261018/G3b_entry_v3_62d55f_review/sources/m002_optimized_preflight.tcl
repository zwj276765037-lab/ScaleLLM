# Installation-only E005 check: no large DCP, synth, optimization or implementation.
set out $::env(HAP_REPORT_DIR)
if {![string match "2025.2*" [version -short]]} {error "Expected Vivado2025.2"}
set_param general.maxThreads 8
create_project m002_directive_probe [file join $out empty_project] -part xcvu9p-flga2104-2L-e
foreach command {place_design phys_opt_design route_design} {
    puts "E005_NATIVE_HELP_BEGIN $command"
    set value [help $command]
    puts "E005_NATIVE_HELP_END $command"
    set h [open [file join $out help_${command}_return.txt] {WRONLY CREAT EXCL}]
    puts $h $value
    close $h
}
set part [get_parts xcvu9p-flga2104-2L-e]
set h [open [file join $out preflight_identity.tsv] {WRONLY CREAT EXCL}]
puts $h "tool\t[version -short]\npart\t[get_property NAME $part]"
foreach property {FAMILY ARCHITECTURE DEVICE} {
    if {![catch {get_property $property $part} value]} {puts $h "$property\t$value"}
}
set run [get_runs impl_1]
if {[llength $run] != 1} {error "Expected one empty implementation run"}
foreach property {FLOW STRATEGY PART} {puts $h "run.$property\t[get_property $property $run]"}
foreach property [list_property [current_project]] {
    if {[regexp -nocase {flow|advanced} $property]} {puts $h "project.$property\t[get_property $property [current_project]]"}
}
foreach {property value} {
    STEPS.PLACE_DESIGN.ARGS.DIRECTIVE SSI_SpreadSLLs
    STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE Default
    STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE Default
} {
    set_property $property $value $run
    if {[get_property $property $run] ne $value} {error "Installed directive property mismatch"}
    puts $h "$property\t[get_property $property $run]"
}
close $h
close_project
puts E005_INSTALLED_DIRECTIVES_ACCEPTED_NO_IMPLEMENTATION
exit 0
