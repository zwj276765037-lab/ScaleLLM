# Native M003 role resolution and constraints. No EDA runs are launched here.
set m003_scripts [file dirname [file normalize [info script]]]
source [file join $m003_scripts ../constraints/m003_joint_locality_data.tcl]
namespace eval m003 {
    variable scripts $::m003_scripts
    variable cache [dict create]
    variable resolved [dict create]
    variable ancestor_pblocks [dict create]
}
proc m003::require_project {{context registry}} {
    variable scripts
    exec /usr/bin/python3 [file join $scripts m003_entry.py] check-sources
    if {[info exists ::m003_restored]} {
        if {![info exists ::m003_restore_registry_verified] || $::m003_restore_registry_verified ne "1"} {error "M003 restore missing actual candidate registration qualification"}
        return
    }
    if {$context eq "runtime"} {
        exec /usr/bin/python3 [file join $scripts m003_entry.py] check-runtime --report $::env(HAP_REPORT_DIR)
        return
    }
    set path [file normalize [file join $scripts ../constraints/m003_joint_locality.xdc]]
    set files [get_files -quiet -of_objects [get_filesets constrs_1] $path]
    exact_count $files 1 "formal overlay registration"
    set f [lindex $files 0]
    if {[yes [prop $f USED_IN_SYNTHESIS]] || ![yes [prop $f USED_IN_IMPLEMENTATION]] || ![yes [prop $f IS_ENABLED]] ||
        [prop $f PROCESSING_ORDER] ne "LATE" || [prop $f SCOPED_TO_REF] ne "" ||
        [prop $f SCOPED_TO_CELLS] ne ""} {error "M003 overlay must be global implementation-only LATE"}
    set row [dict create NAME $path source_manifest_sha256 [lindex [exec sha256sum -- [file join $scripts ../constraints/m003_entry_manifest.json]] 0] overlay_sha256 [lindex [exec sha256sum -- $path] 0]]
    foreach property {USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED PROCESSING_ORDER SCOPED_TO_REF SCOPED_TO_CELLS} {dict set row $property [prop $f $property]}
    set receipt [file join $::env(HAP_REPORT_DIR) m003_candidate_registration.json]
    set content [jobject $row]
    if {[file exists $receipt]} {
        set h [open $receipt r];set previous [string trimright [read $h] "\n"];close $h
        if {$previous ne $content} {error "M003 candidate registration changed within stage"}
    } else {set h [open $receipt {WRONLY CREAT EXCL}];puts $h $content;close $h}
}
proc m003::one {command name} {
    set objects [$command -quiet -hier -filter [format {NAME == "%s"} $name]]
    if {[llength $objects] != 1 || [get_property NAME $objects] ne $name} {error "M003 exact identity mismatch: $command/$name"}
    return [lindex $objects 0]
}
proc m003::yes {value} {expr {[string tolower $value] in {1 true yes}}}
proc m003::prop {object name} {
    if {$name ni [list_property $object]} {return NOT_SUPPORTED}
    return [get_property -quiet $name $object]
}
proc m003::prefix {value root} {expr {[string first ${root}/ $value] == 0}}
proc m003::exact_count {objects n label} {
    if {[llength $objects] != $n || [llength [lsort -unique $objects]] != $n} {error "M003 $label count/duplicate mismatch: [llength $objects], expected $n"}
}
proc m003::init_value {value} {
    if {![regexp -nocase {^[0-9]+'([hb])([0-9a-f]+)$} $value -> base digits]} {error "M003 unknown LUT INIT encoding: $value"}
    if {[string tolower $base] eq "h"} {return [scan $digits %x]}
    set value 0
    foreach bit [split $digits {}] {
        if {$bit ni {0 1}} {error "M003 nonbinary INIT: $digits"}
        set value [expr {2*$value+$bit}]
    }
    return $value
}
proc m003::physical {cell} {
    set ref [get_property REF_NAME $cell]
    if {[string match DSP* $ref] && $ref ne "DSP48E2"} {
        set name [get_property NAME $cell]
        while {[file dirname $name] ni {. /}} {
            set name [file dirname $name];set object [one get_cells $name]
            if {[get_property REF_NAME $object] eq "DSP48E2"} {return $object}
        }
        error "M003 unresolved DSP physical parent: $cell"
    }
    return $cell
}
proc m003::primitive_scope {root} {
    set broad $root;set i [string first {[} $broad]
    if {$i >= 0} {set broad [string range $broad 0 [expr {$i-1}]]}
    set result [list]
    foreach object [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s*"} $broad]] {
        set name [get_property NAME $object]
        if {[prefix $name $root] && [get_property REF_NAME $object] ni {GND VCC}} {lappend result [physical $object]}
    }
    return [lsort -unique $result]
}
proc m003::resolve {} {
    variable parent_scope;variable meta_scope;variable core_meta_scope;variable c01_root
    variable resolved;variable groups
    set resolved [dict create]
    foreach root [list $parent_scope $meta_scope $core_meta_scope $c01_root] {one get_cells $root}
    set family_bits [dict create];set buffers [dict create]
    # Bounded name filters avoid iterating the complete shared-compute subtree.
    set selected [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*parent_*_r_reg*"} $parent_scope]]
    foreach cell $selected {
        set name [get_property NAME $cell]
        if {![regexp {parent_(head|tail)_r_reg\[([0-9]+)\]$} $name -> family bit]} {error "M003 unresolved/replicated payload origin: $name"}
        if {[get_property REF_NAME $cell] ni {FDRE FDCE FDSE FDPE} || $bit>=6560 || [dict exists $family_bits $family $bit]} {error "M003 invalid payload member: $name"}
        dict set family_bits $family $bit $cell
    }
    foreach family {head tail} {
        if {![dict exists $family_bits $family] || [dict size [dict get $family_bits $family]] != 6560} {error "M003 $family production payload incomplete"}
    }
    foreach cell [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*u_ce_buffer"} $parent_scope]] {
        set name [get_property NAME $cell]
        if {![regexp {g_(head|tail)_ce\[([0-9]+)\].*u_ce_buffer$} $name -> family index]} {error "M003 buffer origin unknown: $name"}
        if {[get_property REF_NAME $cell] ne "LUT1" || ![yes [get_property DONT_TOUCH $cell]] || [init_value [get_property INIT $cell]] != 2 || [dict exists $buffers $family $index]} {error "M003 buffer primitive/protection mismatch: $cell"}
        dict set buffers $family $index $cell
    }
    foreach {family n} {head 42 tail 39} {
        if {![dict exists $buffers $family] || [dict size [dict get $buffers $family]] != $n} {error "M003 $family production buffer count mismatch"}
    }
    dict set resolved payload $family_bits;dict set resolved buffers $buffers
    set original_address [dict create]
    foreach cell [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*meta_read_addr_r_reg*"} $core_meta_scope]] {
        set name [get_property NAME $cell]
        if {![regexp {meta_read_addr_r_reg\[([0-9]+)\]$} $name -> bit] || $bit>=17 || [dict exists $original_address $bit]} {error "M003 original core address role unresolved"}
        dict set original_address $bit $cell
    }
    if {[dict size $original_address]!=17} {error "M003 original core address17 missing"}
    dict set resolved core_address $original_address
    set meta [primitive_scope $meta_scope];set memory [dict create];set addresses [dict create];set helpers [dict create]
    foreach cell $meta {
        set name [get_property NAME $cell];set ref [get_property REF_NAME $cell]
        if {[string match URAM* $ref]} {
            if {![regexp {g_slice\[([01])\]} $name -> index]} {error "M003 URAM not in selected slice: $name"}
            dict lappend memory $index $cell
        }
        if {[regexp {g_slice\[([01])\].*u_addr/} $name -> index]} {
            dict lappend helpers $index $cell
            if {[regexp {address_r_reg\[([0-9]+)\]$} $name -> bit]} {
                if {$ref ni {FDCE FDRE} || $bit>=17 || ![yes [get_property DONT_TOUCH $cell]] || [dict exists $addresses $index $bit]} {error "M003 address FF/protection/origin mismatch: $name"}
                dict set addresses $index $bit $cell
            }
        }
    }
    foreach index {0 1} {
        exact_count [dict get $memory $index] 40 "slice$index URAM"
        if {[dict size [dict get $addresses $index]] != 17} {error "M003 address state count mismatch: $index"}
        foreach {suffix ref value} {u_local_ce LUT3 254 u_local_increment LUT2 2} {
            set matches [list]
            foreach cell [dict get $helpers $index] {if {[file tail $cell] eq $suffix} {lappend matches $cell}}
            exact_count $matches 1 "slice$index/$suffix";set cell [lindex $matches 0]
            if {[get_property REF_NAME $cell] ne $ref || [init_value [get_property INIT $cell]] != $value || ![yes [get_property DONT_TOUCH $cell]]} {error "M003 local control primitive/protection mismatch: $cell"}
        }
    }
    dict set resolved meta_all $meta;dict set resolved memory $memory;dict set resolved addresses $addresses;dict set resolved helpers $helpers
    dict set resolved c01 [primitive_scope $c01_root]
    if {![llength [dict get $resolved c01]]} {error "M003 C01 physical membership empty"}
    return $resolved
}
proc m003::hard_pblock {name sites cells} {
    variable ancestor_pblocks
    # Refuse unknown fixed or macro restrictions before assigning new bounds.
    foreach cell $cells {
        foreach property {IS_LOC_FIXED IS_BEL_FIXED} {
            set value [prop $cell $property]
            if {$value eq "NOT_SUPPORTED"} {error "M003 unknown fixed-resource policy: $cell/$property"}
        }
        set macro [prop $cell MACRO_NAME]
        if {$macro ni {{} NOT_SUPPORTED}} {error "M003 native macro requires explicit compatibility qualification: $cell/$macro"}
        foreach relative {RLOC RLOC_ORIGIN} {
            set restriction [prop $cell $relative]
            if {$restriction ni {{} NOT_SUPPORTED}} {error "M003 relative placement restriction requires explicit qualification: $cell/$relative=$restriction"}
        }
        set existing [get_pblocks -quiet -of_objects $cell]
        set ancestor [file dirname $cell]
        while {$ancestor ni {. /}} {
            if {![dict exists $ancestor_pblocks $ancestor]} {
                set object [one get_cells $ancestor]
                dict set ancestor_pblocks $ancestor [get_pblocks -quiet -of_objects $object]
            }
            set existing [concat $existing [dict get $ancestor_pblocks $ancestor]]
            set ancestor [file dirname $ancestor]
        }
        foreach other $existing {
            if {$other ne $name && ![yes [prop $other IS_SOFT]]} {
                error "M003 incompatible pre-existing hard pblock: $cell/$other versus $name"
            }
        }
        if {[yes [prop $cell IS_LOC_FIXED]]} {
            set loc [prop $cell LOC]
            set allowed [get_sites -quiet $sites]
            if {[get_sites -quiet $loc] ni $allowed} {error "M003 fixed LOC outside target pool: $cell/$loc"}
        }
    }
    set pb [get_pblocks -quiet $name]
    if {[llength $pb] > 1} {error "M003 duplicate pblock: $name"}
    if {![llength $pb]} {create_pblock $name;set pb [get_pblocks $name]}
    foreach property {IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING} {set_property $property 0 $pb}
    resize_pblock $pb -add $sites
    add_cells_to_pblock $pb $cells
    return $pb
}
proc m003::apply {} {
    variable groups;variable regions;variable meta_pools;variable c01_protected
    # Native implementation child reads sources in a temporary run project;
    # preserve original XPR policy in the parent-native registration receipt.
    require_project runtime
    variable ancestor_pblocks;set ancestor_pblocks [dict create]
    set r [resolve];set by_cr [dict create]
    foreach g $groups {
        set family [dict get $g family];set index [dict get $g index];set cr [dict get $g clock_region]
        dict lappend by_cr $cr [dict get $r buffers $family $index]
        foreach bit [dict get $g bits] {dict lappend by_cr $cr [dict get $r payload $family $bit]}
    }
    dict for {cr expected} $regions {
        set object [get_clock_regions -quiet $cr]
        if {[llength $object]!=1} {set object [get_clock_regions -quiet CLOCKREGION_$cr]}
        if {[llength $object]!=1} {error "M003 native CR absent: $cr"}
        set sites [get_sites -quiet -of_objects $object -filter {SITE_TYPE =~ SLICE*}]
        exact_count $sites $expected "native slices $cr"
        hard_pblock m003_parent_$cr $sites [dict get $by_cr $cr]
    }
    foreach pool $meta_pools {
        set index [dict get $pool index];set us [dict get $pool uram_sites];set cs [dict get $pool clb_sites]
        exact_count [get_sites -quiet $us] 40 "native slice$index URAM pool"
        exact_count [get_sites -quiet $cs] 3480 "native slice$index address CLB pool"
        hard_pblock m003_meta_slice${index}_uram $us [dict get $r memory $index]
        hard_pblock m003_meta_slice${index}_address $cs [dict get $r helpers $index]
    }
    if {[llength [get_slrs -quiet SLR2]] != 1} {error "M003 native SLR2 absent"}
    hard_pblock m002_exact_hotspot_SLR2 CLOCKREGION_X0Y10:CLOCKREGION_X5Y14 [dict get $r c01]
    foreach name $c01_protected {
        set cell [one get_cells $name]
        if {![yes [get_property DONT_TOUCH $cell]]} {error "M003 C01 original protection lost: $name"}
    }
    puts "M003_OVERLAY_APPLIED head42 tail39 URAM40+40 address34 C01_retained"
}
proc m003::jq {s} {
    return \"[string map [list \\ \\\\ \" \\\" \n \\n \r \\r \t \\t] $s]\"
}
proc m003::jobject {d} {
    set fields [list];dict for {k v} $d {lappend fields "[jq $k]:[jq $v]"};return \{[join $fields ,]\}
}
proc m003::jarray {rows} {set values [list];foreach row $rows {lappend values [jobject $row]};return \[[join $values ,]\]}
proc m003::cell_row {cell role extra} {
    set d [dict create role $role NAME [get_property NAME $cell] REF_NAME [get_property REF_NAME $cell]]
    foreach p {LOC BEL IS_LOC_FIXED IS_BEL_FIXED RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH ORIG_CELL_NAME ORIG_REF_NAME USER_SLR_ASSIGNMENT} {dict set d $p [prop $cell $p]}
    dict set d PBLOCKS [get_property NAME [get_pblocks -quiet -of_objects $cell]]
    set loc [dict get $d LOC]
    if {$loc ne "" && $loc ne "NOT_SUPPORTED"} {
        set site [get_sites -quiet $loc]
        dict set d SLR [get_property NAME [get_slrs -quiet -of_objects $site]]
        dict set d clock_region [get_property NAME [get_clock_regions -quiet -of_objects $site]]
    } else {dict set d SLR UNPLACED;dict set d clock_region UNPLACED}
    return [dict merge $d $extra]
}
proc m003::pin_net {cell terminal} {
    set pin [get_pins -quiet -of_objects $cell -filter [format {REF_PIN_NAME == "%s"} $terminal]]
    exact_count $pin 1 "$cell/$terminal"
    set nets [get_nets -quiet -segments -of_objects $pin]
    if {![llength $nets]} {error "M003 disconnected pin: $cell/$terminal"}
    return $nets
}
proc m003::snapshot {phase out} {
    variable groups;variable spec_path;variable scripts;variable parent_scope;variable core_meta_scope
    require_project
    set r [resolve];set cells [list];set edges [list];set inputs [list];set pins [list];set controller [list];set pblocks [list];set boundaries [list];set target_sites [dict create];set helper_pins [list];set configs [list];set control_sources [dict create]
    dict for {bit cell} [dict get $r core_address] {
        lappend cells [cell_row $cell core_address [dict create bit $bit C_nets [pin_net $cell C] CLR_nets [pin_net $cell CLR]]]
    }
    foreach family {head tail} {
        dict for {bit cell} [dict get $r payload $family] {
            set nets [dict create]
            foreach terminal {D Q C CE R} {
                set ps [get_pins -quiet -of_objects $cell -filter [format {REF_PIN_NAME == "%s"} $terminal]]
                if {[llength $ps]} {dict set nets ${terminal}_nets [get_property NAME [get_nets -quiet -segments -of_objects $ps]]}
            }
            set dp [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
            set qp [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == Q}]
            dict set nets D_drivers [get_property NAME [get_pins -quiet -leaf -of_objects [get_nets -quiet -segments -of_objects $dp] -filter {DIRECTION == OUT}]]
            dict set nets Q_loads [get_property NAME [get_pins -quiet -leaf -of_objects [get_nets -quiet -segments -of_objects $qp] -filter {DIRECTION == IN}]]
            lappend cells [cell_row $cell payload [dict merge [dict create family $family bit $bit] $nets]]
        }
    }
    foreach g $groups {
        set family [dict get $g family];set index [dict get $g index];set cell [dict get $r buffers $family $index]
        lappend cells [cell_row $cell buffer [dict create group [dict get $g id] INIT [get_property INIT $cell]]]
        set nets [pin_net $cell O]
        foreach pin [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == IN}] {
            set owner [get_cells -quiet -of_objects $pin]
            lappend edges [dict create group [dict get $g id] source $cell load [get_property NAME $owner] pin [get_property REF_PIN_NAME $pin]]
        }
        set inet [pin_net $cell I0]
        set drivers [get_pins -quiet -leaf -of_objects $inet -filter {DIRECTION == OUT}]
        exact_count $drivers 1 "master driver $family/$index"
        set all_loads [get_pins -quiet -leaf -of_objects $inet -filter {DIRECTION == IN}]
        lappend inputs [dict create group [dict get $g id] family $family driver [get_property NAME $drivers] load_pins [get_property NAME $all_loads]]
    }
    foreach index {0 1} {
        dict for {bit cell} [dict get $r addresses $index] {
            set dp [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
            set fanin [all_fanin -quiet -flat -startpoints_only -to $dp]
            set cen [pin_net $cell CE]
            set ce_driver [get_pins -quiet -leaf -of_objects $cen -filter {DIRECTION == OUT}]
            lappend cells [cell_row $cell address [dict create slice $index bit $bit D_startpoints [get_property NAME $fanin] CE_nets $cen CE_drivers [get_property NAME $ce_driver] C_nets [pin_net $cell C] CLR_nets [pin_net $cell CLR]]]

        }
        foreach cell [dict get $r helpers $index] {
            if {$cell in [dict values [dict get $r addresses $index]]} {continue}
            set extra [dict create slice $index]
            if {[string match LUT* [get_property REF_NAME $cell]]} {dict set extra INIT [get_property INIT $cell]}
            lappend cells [cell_row $cell address_logic $extra]
        }
        foreach cell [dict get $r helpers $index] {
            foreach pin [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN}] {
                set nets [get_nets -quiet -segments -of_objects $pin]
                set drivers [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}]
                lappend helper_pins [dict create slice $index cell $cell pin [get_property REF_PIN_NAME $pin] nets [get_property NAME $nets] drivers [get_property NAME $drivers]]
            }
        }
        foreach cell [dict get $r memory $index] {
            lappend cells [cell_row $cell memory [dict create slice $index]]
            foreach pin [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN}] {
                set terminal [get_property REF_PIN_NAME $pin]
                if {![string match ADDR* $terminal] && ![string match *EN* $terminal] && ![string match *WE* $terminal] && ![string match *CLK* $terminal] && ![string match *RDB_WR* $terminal] && ![string match CAS* $terminal]} {continue}
                set nets [get_nets -quiet -segments -of_objects $pin]
                set driver [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}]
                set startpoints [list]
                if {[string match ADDR* $terminal]} {set startpoints [all_fanin -quiet -flat -startpoints_only -to $pin]}
                set refs [list]
                foreach object $driver {lappend refs [get_property REF_NAME [get_cells -quiet -of_objects $object]]}
                lappend pins [dict create slice $index cell $cell pin $terminal drivers [get_property NAME $driver] driver_refs $refs startpoints [get_property NAME $startpoints] nets [get_property NAME $nets]]
            }
            set props [open [file join $out m003_uram_properties_${phase}_[string map {/ _ . _ \[ _ \] _} $cell].tsv] w]
            set config [dict create NAME $cell slice $index]
            foreach property [lsort [list_property $cell]] {
                set value [get_property -quiet $property $cell]
                puts $props "$property\t[list $value]"
                if {[string match CONFIG.* $property] || [regexp {CASCADE|OREG|IREG|WRITE|READ|BWE|CLOCK} $property]} {dict set config $property $value}
            }
            lappend configs $config;close $props
        }
    }
    variable meta_scope
    foreach {tag terminal} {S addr_system_clear L addr_launch clock clk reset rst_n} {
        set pin [get_pins -quiet ${meta_scope}/$terminal]
        exact_count $pin 1 "selected metadata boundary $tag"
        set nets [get_nets -quiet -segments -of_objects $pin]
        if {![llength $nets]} {error "M003 empty metadata boundary signal: $tag"}
        dict set control_sources $tag [get_property NAME $nets]
    }
    set event [get_nets -quiet -hier -filter [format {NAME == "%s/rsp_fire"} $meta_scope]]
    if {![llength $event]} {error "M003 local response event unresolved"}
    dict set control_sources R [get_property NAME [get_nets -quiet -segments -of_objects $event]]
    foreach cell [dict get $r c01] {lappend cells [cell_row $cell c01 [dict create]]}
    foreach cell [dict get $r meta_all] {lappend controller [dict create NAME $cell REF_NAME [get_property REF_NAME $cell]]}
    foreach pb [get_pblocks -quiet -filter {NAME =~ m003_* || NAME == m002_exact_hotspot_SLR2}] {
        set d [dict create NAME $pb]
        foreach p {IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING GRID_RANGES} {dict set d $p [prop $pb $p]}
        dict set d actual_sites [get_property NAME [get_sites -quiet -of_objects $pb]]
        lappend pblocks $d
    }
    variable regions
    dict for {region count} $regions {
        set object [get_clock_regions -quiet $region]
        if {[llength $object]!=1} {set object [get_clock_regions -quiet CLOCKREGION_$region]}
        exact_count $object 1 "target CR $region"
        dict set target_sites m003_parent_$region [get_property NAME [get_sites -quiet -of_objects $object -filter {SITE_TYPE =~ SLICE*}]]
    }
    exact_count [get_slrs -quiet SLR2] 1 "target SLR2"
    dict set target_sites m002_exact_hotspot_SLR2 [get_property NAME [get_sites -quiet -of_objects [get_slrs SLR2]]]
    variable core_meta_scope
    set base [file dirname $core_meta_scope]
    foreach {tag scope suffix ref count width} [list \
        input $base/u_attention/u_input_buffer u_capture_decode LUT6 48 256 \
        gate $base/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack u_output_payload_ce LUT1 16 384 \
        down $base/u_mlp/u_serial_command/u_down_scheduler/u_projection_repack u_output_payload_ce LUT1 16 512] {
        set objects [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*%s" && REF_NAME == "%s"} $scope $suffix $ref]]
        exact_count $objects $count "preserved $tag boundary"
        foreach object $objects {
            set ns [pin_net $object O]
            set loads [get_pins -quiet -leaf -of_objects $ns -filter {DIRECTION == IN}]
            lappend boundaries [dict create NAME $object tag $tag REF_NAME $ref DONT_TOUCH [get_property DONT_TOUCH $object] load_count [llength $loads] load_terminals [get_property REF_PIN_NAME $loads] expected_width $width]
        }
    }
    set meta [dict create phase $phase kind native fixture false spec_sha256 [lindex [exec sha256sum -- $spec_path] 0] part [get_property PART [current_design]] source_manifest_sha256 [lindex [exec sha256sum -- [file join $scripts ../constraints/m003_entry_manifest.json]] 0]]
    set h [open [file join $out m003_native_${phase}.json] w]
    puts $h "\{\"meta\":[jobject $meta],\"cells\":[jarray $cells],\"ce_edges\":[jarray $edges],\"master_inputs\":[jarray $inputs],\"memory_pins\":[jarray $pins],\"meta_ref_cells\":[jarray $controller],\"pblocks\":[jarray $pblocks],\"target_sites\":[jobject $target_sites],\"helper_pins\":[jarray $helper_pins],\"uram_configs\":[jarray $configs],\"control_sources\":[jobject $control_sources],\"boundaries\":[jarray $boundaries]\}"
    close $h
    exec /usr/bin/python3 [file join $scripts m003_joint_evidence.py] --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]
}
