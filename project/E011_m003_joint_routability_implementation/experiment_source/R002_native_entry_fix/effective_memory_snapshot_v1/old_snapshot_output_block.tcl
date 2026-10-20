    set h [open [file join $out m003_native_${phase}.json] w]
    puts $h "\{\"meta\":[jobject $meta],\"cells\":[jarray $cells],\"ce_edges\":[jarray $edges],\"master_inputs\":[jarray $inputs],\"memory_pins\":[jarray $pins],\"meta_ref_cells\":[jarray $controller],\"pblocks\":[jarray $pblocks],\"target_sites\":[jobject $target_sites],\"helper_pins\":[jarray $helper_pins],\"uram_configs\":[jarray $configs],\"control_sources\":[jobject $control_sources],\"boundaries\":[jarray $boundaries]\}"
    close $h
