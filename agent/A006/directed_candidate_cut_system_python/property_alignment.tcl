# Native property columns: retain the vector fast path; recover alignment by
# actual per-object queries, preserving empty optional values and rejecting
# missing required fields. This file performs no query when sourced.
namespace eval propertyalign {}
proc propertyalign::values {objects property allow_empty context audit_file} {
    set count [llength $objects]
    if {!$count} {return [list]}
    set vector [get_property -quiet $property $objects]
    set vector_count [llength $vector]
    if {$vector_count == $count} {
        if {!$allow_empty} {
            foreach value $vector {if {$value eq ""} {error "Required native property empty: $context/$property"}}
        }
        return $vector
    }
    set aligned [list];set empty 0
    foreach object $objects {
        set name [get_property -quiet NAME $object]
        if {$name eq "" || $name ne $object} {error "Exact native object identity unavailable during property fallback: $context/$property/$object"}
        # A failed native scalar query propagates. Empty is an observed value,
        # not a substituted object or a guessed LOC/BEL/clock/policy identity.
        set value [get_property -quiet $property $object]
        if {$value eq ""} {
            incr empty
            if {!$allow_empty} {error "Required native scalar property empty: $context/$property/$name"}
        }
        lappend aligned $value
    }
    if {[llength $aligned] != $count} {error "Native scalar fallback did not preserve object count: $context/$property"}
    if {![file exists $audit_file]} {
        set h [open $audit_file {WRONLY CREAT EXCL}]
        puts $h "context\tproperty\tobject_count\tnative_vector_list_length\tscalar_queries\tscalar_empty_values\tscalar_result_count\tfirst_object\tlast_object"
    } else {set h [open $audit_file a]}
    puts $h "$context\t$property\t$count\t$vector_count\t$count\t$empty\t[llength $aligned]\t[list [lindex $objects 0]]\t[list [lindex $objects end]]"
    close $h
    return $aligned
}
