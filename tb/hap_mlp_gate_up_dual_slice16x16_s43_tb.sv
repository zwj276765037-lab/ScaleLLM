`timescale 1ns / 1ps

module hap_mlp_gate_up_dual_slice16x16_s43_tb;
    localparam integer GROUPS = 128;
    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire signed [4607:0] activation_s9x16x32;
    wire signed [2047:0] weights_s4x16x32;
    wire [127:0] activation_code_u8x16;
    wire [95:0] activation_shift_u6x16;
    wire [127:0] weight_code_u8x16;
    wire [95:0] weight_shift_u6x16;
    wire out_valid;
    reg out_ready = 1'b1;
    wire signed [6143:0] projection_s24x16x16;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [4607:0] activation_mem [0:GROUPS-1];
    reg [2047:0] weights_mem [0:GROUPS-1];
    reg [223:0] activation_meta_mem [0:GROUPS-1];
    reg [223:0] weight_meta_mem [0:GROUPS-1];
    reg [6143:0] expected_mem [0:0];
    integer send_index = 0;
    integer cycle_count = 0;
    integer last_accept_cycle = -1;
    integer within_tile_interval_max = 0;
    integer finish_countdown = -1;
    integer mismatch_count = 0;
    wire [6:0] source_index = send_index < GROUPS ? send_index : GROUPS-1;

    assign in_valid = send_index < GROUPS;
    assign activation_s9x16x32 = activation_mem[source_index];
    assign weights_s4x16x32 = weights_mem[source_index];
    assign activation_code_u8x16 = activation_meta_mem[source_index][127:0];
    assign activation_shift_u6x16 = activation_meta_mem[source_index][223:128];
    assign weight_code_u8x16 = weight_meta_mem[source_index][127:0];
    assign weight_shift_u6x16 = weight_meta_mem[source_index][223:128];

    hap_mlp_gate_up_dual_slice16x16_s43 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_group(send_index == 0),
        .in_last_group(send_index == GROUPS-1),
        .activation_s9x16x32(activation_s9x16x32),
        .weights_s4x16x32(weights_s4x16x32),
        .activation_code_u8x16(activation_code_u8x16),
        .activation_shift_u6x16(activation_shift_u6x16),
        .weight_code_u8x16(weight_code_u8x16),
        .weight_shift_u6x16(weight_shift_u6x16),
        .out_valid(out_valid), .out_ready(out_ready),
        .projection_s24x16x16(projection_s24x16x16),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        $readmemh("data/mlp_gate_up_dual_slice_s43/activation_s9x16x32.mem",
            activation_mem);
        $readmemh("data/mlp_gate_up_dual_slice_s43/weights_s4x16x32.mem",
            weights_mem);
        $readmemh("data/mlp_gate_up_dual_slice_s43/activation_meta_u224.mem",
            activation_meta_mem);
        $readmemh("data/mlp_gate_up_dual_slice_s43/weight_meta_u224.mem",
            weight_meta_mem);
        $readmemh("data/mlp_gate_up_dual_slice_s43/expected_s24x16x16.mem",
            expected_mem);
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_ready <= 1'b1;
            send_index <= 0;
            cycle_count <= 0;
            last_accept_cycle <= -1;
            within_tile_interval_max <= 0;
            finish_countdown <= -1;
            mismatch_count <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            out_ready <= ((cycle_count % 7) != 3 &&
                          (cycle_count % 11) != 5);
            if (in_valid && in_ready) begin
                send_index <= send_index + 1;
                if (send_index != 0 && last_accept_cycle >= 0 &&
                    cycle_count-last_accept_cycle >
                    within_tile_interval_max)
                    within_tile_interval_max <=
                        cycle_count-last_accept_cycle;
                last_accept_cycle <= cycle_count;
            end
            if (out_valid && out_ready) begin
                if (projection_s24x16x16 !== expected_mem[0]) begin
                    $display("MISMATCH dual-slice tile");
                    mismatch_count <= mismatch_count + 1;
                end
                finish_countdown <= 8;
            end
            if (finish_countdown >= 0) begin
                finish_countdown <= finish_countdown - 1;
                if (finish_countdown == 0) begin
                    if (mismatch_count == 0 && !error &&
                        within_tile_interval_max <= 1 &&
                        input_group_count == GROUPS &&
                        output_tile_count == 1 &&
                        saturation_count == 0) begin
                        $display("PASS: hap_mlp_gate_up_dual_slice16x16_s43 tiles=1 groups=%0d cycles=%0d mismatches=0 within_tile_ii=%0d",
                            GROUPS, cycle_count, within_tile_interval_max);
                        $finish;
                    end else begin
                        $fatal(1,
                            "FAIL: mismatch=%0d error=%0d ii=%0d in=%0d out=%0d sat=%0d",
                            mismatch_count, error,
                            within_tile_interval_max,
                            input_group_count, output_tile_count,
                            saturation_count);
                    end
                end
            end
            if (cycle_count > 1000)
                $fatal(1, "FAIL: timeout send=%0d error=%0d",
                    send_index, error);
        end
    end
endmodule
