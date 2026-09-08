create_clock -name clk -period 6.667 [get_ports clk]
set_clock_uncertainty 0.150 [get_clocks clk]
set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]
set_input_delay -clock clk 1.000 [get_ports {
    rst_n clear in_valid out_ready activation_s9x8x32[*]
    weights_s4x12x32[*] activation_code_u8x8[*]
    activation_shift_u6x8[*] weight_code_u8x12[*]
    weight_shift_u6x12[*] column_valid_u12[*]}]
set_output_delay -clock clk 1.000 [get_ports {
    in_ready out_valid guard_s36x8x12[*] input_group_count[*]
    output_group_count[*] error}]
