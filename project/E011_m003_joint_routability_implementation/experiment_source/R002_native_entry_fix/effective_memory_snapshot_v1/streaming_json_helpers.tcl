
# Serialize one row at a time; preserve the existing JSON schema and bytes.
proc m003::write_jarray {handle rows} {
    puts -nonewline $handle \[
    set separator {}
    foreach row $rows {
        puts -nonewline $handle $separator
        puts -nonewline $handle [jobject $row]
        set separator ,
    }
    puts -nonewline $handle \]
}
proc m003::write_snapshot_json {handle parts} {
    puts -nonewline $handle \{
    set separator {}
    foreach {key type} {meta object cells array ce_edges array master_inputs array memory_pins array meta_ref_cells array pblocks array target_sites object helper_pins array uram_configs array control_sources object boundaries array} {
        puts -nonewline $handle "$separator[jq $key]:"
        if {$type eq {object}} {
            puts -nonewline $handle [jobject [dict get $parts $key]]
        } else {write_jarray $handle [dict get $parts $key]}
        set separator ,
    }
    puts $handle \}
}
proc m003::write_snapshot_file {path parts} {
    set partial $path.partial
    if {[file exists $path] || [file exists $partial]} {error "M003 snapshot output already exists: $path"}
    set handle [open $partial {WRONLY CREAT EXCL}]
    set code [catch {
        write_snapshot_json $handle $parts
        close $handle
        set handle {}
        file rename $partial $path
    } message options]
    if {$code} {
        if {$handle ne {}} {catch {close $handle}}
        return -options $options $message
    }
}
