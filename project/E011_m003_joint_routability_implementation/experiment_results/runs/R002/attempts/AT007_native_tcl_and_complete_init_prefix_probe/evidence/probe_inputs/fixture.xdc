if {![info exists ::env(HAP_PROBE_HELPER)]} {error "explicit helper binding missing"}
source $::env(HAP_PROBE_HELPER)
constraint_probe::apply
