# Complete domains receive SLR ownership; soft regions retain placement freedom.
# Existing capture, guard feedback and output stages move with their compute.
set_property USER_SLR_ASSIGNMENT SLR0 [get_cells -hier -regexp {.*u_array$}]
set_property USER_SLR_ASSIGNMENT SLR0 [get_cells -hier -regexp {.*u_array/u_center12$}]
set_property USER_SLR_ASSIGNMENT SLR1 [get_cells -hier -regexp {.*u_array/u_left2$}]
set_property USER_SLR_ASSIGNMENT SLR2 [get_cells -hier -regexp {.*u_array/u_right2$}]
set_property USER_SLR_ASSIGNMENT SLR1 [get_cells -hier -regexp {.*u_shared_compute/u_branch0$}]
set_property USER_SLR_ASSIGNMENT SLR2 [get_cells -hier -regexp {.*u_shared_compute/u_branch1$}]

create_pblock mission0005_attention_cols2_3
resize_pblock [get_pblocks mission0005_attention_cols2_3] -add CLOCKREGION_X0Y0:CLOCKREGION_X2Y1
set_property IS_SOFT true [get_pblocks mission0005_attention_cols2_3]
add_cells_to_pblock [get_pblocks mission0005_attention_cols2_3] [get_cells -hier -regexp {.*u_array/u_center12/u_region0_cols2_3$}]

create_pblock mission0005_attention_cols4_7
resize_pblock [get_pblocks mission0005_attention_cols4_7] -add CLOCKREGION_X0Y2:CLOCKREGION_X2Y4
set_property IS_SOFT true [get_pblocks mission0005_attention_cols4_7]
add_cells_to_pblock [get_pblocks mission0005_attention_cols4_7] [get_cells -hier -regexp {.*u_array/u_center12/u_region1_cols4_7$}]

create_pblock mission0005_attention_cols8_11
resize_pblock [get_pblocks mission0005_attention_cols8_11] -add CLOCKREGION_X3Y1:CLOCKREGION_X5Y4
set_property IS_SOFT true [get_pblocks mission0005_attention_cols8_11]
add_cells_to_pblock [get_pblocks mission0005_attention_cols8_11] [get_cells -hier -regexp {.*u_array/u_center12/u_region2_cols8_11$}]

create_pblock mission0005_attention_cols12_13
resize_pblock [get_pblocks mission0005_attention_cols12_13] -add CLOCKREGION_X3Y0:CLOCKREGION_X5Y2
set_property IS_SOFT true [get_pblocks mission0005_attention_cols12_13]
add_cells_to_pblock [get_pblocks mission0005_attention_cols12_13] [get_cells -hier -regexp {.*u_array/u_center12/u_region3_cols12_13$}]

create_pblock mission0005_attention_left
resize_pblock [get_pblocks mission0005_attention_left] -add CLOCKREGION_X3Y5:CLOCKREGION_X5Y6
set_property IS_SOFT true [get_pblocks mission0005_attention_left]
add_cells_to_pblock [get_pblocks mission0005_attention_left] [get_cells -hier -regexp {.*u_array/u_left2$}]

create_pblock mission0005_attention_right
resize_pblock [get_pblocks mission0005_attention_right] -add CLOCKREGION_X3Y10:CLOCKREGION_X5Y11
set_property IS_SOFT true [get_pblocks mission0005_attention_right]
add_cells_to_pblock [get_pblocks mission0005_attention_right] [get_cells -hier -regexp {.*u_array/u_right2$}]

create_pblock mission0005_mlp_body0
resize_pblock [get_pblocks mission0005_mlp_body0] -add CLOCKREGION_X0Y5:CLOCKREGION_X4Y9
set_property IS_SOFT true [get_pblocks mission0005_mlp_body0]
add_cells_to_pblock [get_pblocks mission0005_mlp_body0] [get_cells -hier -regexp {.*u_shared_compute/u_branch0/u_(kernel|gate_accum|down_accum|down_output_queue)$}]

create_pblock mission0005_mlp_body1
resize_pblock [get_pblocks mission0005_mlp_body1] -add CLOCKREGION_X0Y10:CLOCKREGION_X4Y14
set_property IS_SOFT true [get_pblocks mission0005_mlp_body1]
add_cells_to_pblock [get_pblocks mission0005_mlp_body1] [get_cells -hier -regexp {.*u_shared_compute/u_branch1/u_(kernel|gate_accum|down_accum|down_output_queue)$}]

# Branch-root ingress/tag/clear and output-slot endpoints have no added stage.
create_pblock mission0005_mlp_endpoints0
resize_pblock [get_pblocks mission0005_mlp_endpoints0] -add CLOCKREGION_X3Y5:CLOCKREGION_X5Y7
set_property IS_SOFT true [get_pblocks mission0005_mlp_endpoints0]
set mission0007_branch0_root [get_cells -hier -regexp {.*u_shared_compute/u_branch0/[^/]+$} \
    -filter {IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND && NAME !~ ".*clear_.*"}]
add_cells_to_pblock [get_pblocks mission0005_mlp_endpoints0] $mission0007_branch0_root

create_pblock mission0005_mlp_endpoints1
resize_pblock [get_pblocks mission0005_mlp_endpoints1] -add CLOCKREGION_X1Y11:CLOCKREGION_X3Y13
set_property IS_SOFT true [get_pblocks mission0005_mlp_endpoints1]
set mission0007_branch1_root [get_cells -hier -regexp {.*u_shared_compute/u_branch1/[^/]+$} \
    -filter {IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND && NAME !~ ".*clear_.*"}]
add_cells_to_pblock [get_pblocks mission0005_mlp_endpoints1] $mission0007_branch1_root

# The eleven compute/result replicas and the separate ingress clear in each
# branch are hard-bounded inside their consumer SLR. Larger endpoint/body
# regions remain soft.
create_pblock mission0007_mlp_controls0
resize_pblock [get_pblocks mission0007_mlp_controls0] -add CLOCKREGION_X0Y5:CLOCKREGION_X4Y9
set_property IS_SOFT false [get_pblocks mission0007_mlp_controls0]
set mission0007_branch0_controls [get_cells -hier -regexp {.*u_shared_compute/u_branch0/clear_(kernel_row|gate_accum|down_accum|result_queues)_r_reg.*} \
    -filter {IS_PRIMITIVE == 1}]
add_cells_to_pblock [get_pblocks mission0007_mlp_controls0] $mission0007_branch0_controls

create_pblock mission0007_mlp_controls1
resize_pblock [get_pblocks mission0007_mlp_controls1] -add CLOCKREGION_X0Y10:CLOCKREGION_X4Y14
set_property IS_SOFT false [get_pblocks mission0007_mlp_controls1]
set mission0007_branch1_controls [get_cells -hier -regexp {.*u_shared_compute/u_branch1/clear_(kernel_row|gate_accum|down_accum|result_queues)_r_reg.*} \
    -filter {IS_PRIMITIVE == 1}]
add_cells_to_pblock [get_pblocks mission0007_mlp_controls1] $mission0007_branch1_controls

create_pblock mission0007_mlp_ingress_clear0
resize_pblock [get_pblocks mission0007_mlp_ingress_clear0] -add CLOCKREGION_X3Y5:CLOCKREGION_X5Y7
set_property IS_SOFT false [get_pblocks mission0007_mlp_ingress_clear0]
set mission0007_ingress_clear0 [get_cells -hier -regexp {.*u_shared_compute/u_branch0/clear_ingress_tag_r_reg.*} \
    -filter {IS_PRIMITIVE == 1}]
add_cells_to_pblock [get_pblocks mission0007_mlp_ingress_clear0] $mission0007_ingress_clear0

create_pblock mission0007_mlp_ingress_clear1
resize_pblock [get_pblocks mission0007_mlp_ingress_clear1] -add CLOCKREGION_X1Y11:CLOCKREGION_X3Y13
set_property IS_SOFT false [get_pblocks mission0007_mlp_ingress_clear1]
set mission0007_ingress_clear1 [get_cells -hier -regexp {.*u_shared_compute/u_branch1/clear_ingress_tag_r_reg.*} \
    -filter {IS_PRIMITIVE == 1}]
add_cells_to_pblock [get_pblocks mission0007_mlp_ingress_clear1] $mission0007_ingress_clear1

# Preserve width-local URAM ownership and collect the existing 224-bit returns
# beside the scheduler and parent ingress, rather than through Attention's body.
set_property USER_SLR_ASSIGNMENT SLR0 [get_cells -hier -regexp {.*u_(gate_bank[01]/g_width\[1\]|down_bank[01]/g_width\[[13]\])\.u_width_local$}]
set_property USER_SLR_ASSIGNMENT SLR1 [get_cells -hier -regexp {.*u_(gate_bank[01]/g_width\[[23]\]|down_bank[01]/g_width\[2\])\.u_width_local$}]
set_property USER_SLR_ASSIGNMENT SLR2 [get_cells -hier -regexp {.*u_(gate|down)_bank[01]/g_width\[0\]\.u_width_local$}]

create_pblock mission0005_metadata_returns
resize_pblock [get_pblocks mission0005_metadata_returns] -add CLOCKREGION_X0Y7:CLOCKREGION_X2Y9
set_property IS_SOFT true [get_pblocks mission0005_metadata_returns]
add_cells_to_pblock [get_pblocks mission0005_metadata_returns] [get_cells -hier -regexp {.*u_meta_sched$}]
add_cells_to_pblock [get_pblocks mission0005_metadata_returns] [get_cells -hier -regexp {.*u_meta_bank/u_(gate|down)_bank[01]/[^/]+$} -filter {IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND}]
add_cells_to_pblock [get_pblocks mission0005_metadata_returns] [get_cells -hier -regexp {.*u_shared_compute/[^/]+$} -filter {IS_PRIMITIVE == 1 && REF_NAME != VCC && REF_NAME != GND}]
set_property USER_SLR_ASSIGNMENT SLR1 [get_cells -hier -regexp {.*u_(meta_bank|meta_sched|shared_compute)$}]
