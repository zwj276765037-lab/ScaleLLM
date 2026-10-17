# S0 measured each native width domain wholly within the SLR chosen below.
# Guide only those existing memory/control domains; compute and IP stay free.
create_pblock mission0004_metadata_slr0
resize_pblock [get_pblocks mission0004_metadata_slr0] -add CLOCKREGION_X0Y0:CLOCKREGION_X5Y4
set_property IS_SOFT true [get_pblocks mission0004_metadata_slr0]
add_cells_to_pblock [get_pblocks mission0004_metadata_slr0] [get_cells -hier -regexp {.*u_(gate_bank[01]/g_width\[1\]|down_bank[01]/g_width\[[13]\])\.u_width_local$}]

create_pblock mission0004_metadata_slr1
resize_pblock [get_pblocks mission0004_metadata_slr1] -add CLOCKREGION_X0Y5:CLOCKREGION_X5Y9
set_property IS_SOFT true [get_pblocks mission0004_metadata_slr1]
add_cells_to_pblock [get_pblocks mission0004_metadata_slr1] [get_cells -hier -regexp {.*u_(gate_bank[01]/g_width\[[23]\]|down_bank[01]/g_width\[2\])\.u_width_local$}]

create_pblock mission0004_metadata_slr2
resize_pblock [get_pblocks mission0004_metadata_slr2] -add CLOCKREGION_X0Y10:CLOCKREGION_X5Y14
set_property IS_SOFT true [get_pblocks mission0004_metadata_slr2]
add_cells_to_pblock [get_pblocks mission0004_metadata_slr2] [get_cells -hier -regexp {.*u_(gate|down)_bank[01]/g_width\[0\]\.u_width_local$}]
