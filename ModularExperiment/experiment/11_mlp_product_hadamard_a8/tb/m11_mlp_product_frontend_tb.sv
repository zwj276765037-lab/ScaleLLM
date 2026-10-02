`timescale 1ns/1ps

module m11_mlp_product_frontend_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 0,
    parameter DATA_DIR = "/tmp"
);
    localparam integer GROUPS = 448;
    localparam integer INPUT_W = 16*32*32;
    localparam integer DATA_W = 16*32*8;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    wire in_valid;
    wire in_ready;
    wire [INPUT_W-1:0] product_s32;
    wire out_valid;
    wire out_ready;
    wire [DATA_W-1:0] activation_u8;
    wire [383:0] activation_meta_narrow;
    wire [639:0] activation_meta_wide;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire [31:0] busy_cycle_count;
    wire error;

    reg [INPUT_W-1:0] input_mem [0:GROUPS-1];
    reg [DATA_W-1:0] expected_sc_u8_mem [0:GROUPS-1];
    reg [383:0] expected_sc_meta_mem [0:GROUPS-1];
    reg [DATA_W-1:0] expected_fp_u8_mem [0:GROUPS-1];
    reg [383:0] expected_fp16_meta_mem [0:GROUPS-1];
    reg [639:0] expected_fp32_meta_mem [0:GROUPS-1];

    integer cycle = 0;
    integer send_index = 0;
    integer receive_index = 0;
    integer mismatch_count = 0;
    integer nonfinite_scale_count = 0;
    integer previous_input_cycle = -1;
    integer previous_output_cycle = -1;
    integer input_ii_min = 32'h7fff_ffff;
    integer input_ii_max = 0;
    integer output_ii_min = 32'h7fff_ffff;
    integer output_ii_max = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer last_output_cycle = -1;
    integer input_stall_cycles = 0;
    integer output_stall_cycles = 0;
    integer delta;
    reg output_was_stalled = 1'b0;
    reg [DATA_W-1:0] stalled_u8;
    reg [383:0] stalled_meta_narrow;
    reg [639:0] stalled_meta_wide;
    reg response_mismatch;

    always #5 clk = ~clk;
    assign in_valid = rst_n && send_index < GROUPS;
    assign product_s32 = input_mem[
        send_index < GROUPS ? send_index : GROUPS-1];
    assign out_ready = rst_n &&
        ((BACKPRESSURE == 0) || ((cycle % 29) < 21));

    initial begin
        $readmemh({DATA_DIR, "/input_s32.mem"}, input_mem);
        $readmemh({DATA_DIR, "/expected_sc_u8.mem"}, expected_sc_u8_mem);
        $readmemh({DATA_DIR, "/expected_sc_meta.mem"}, expected_sc_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp_u8.mem"}, expected_fp_u8_mem);
        $readmemh({DATA_DIR, "/expected_fp16_meta.mem"},
            expected_fp16_meta_mem);
        $readmemh({DATA_DIR, "/expected_fp32_meta.mem"},
            expected_fp32_meta_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    generate
        if (CASE_ID == 0) begin : g_sc
            assign activation_meta_wide = 640'd0;
            hap_mlp_product_frontend16_q4 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .product_s32x16x32(product_s32),
                .out_valid(out_valid), .out_ready(out_ready),
                .activation_u8x16x32(activation_u8),
                .activation_meta_u24x16(activation_meta_narrow),
                .input_group_count(input_group_count),
                .output_group_count(output_group_count),
                .busy_cycle_count(busy_cycle_count), .error(error)
            );
        end else if (CASE_ID == 1) begin : g_fp16
            assign activation_meta_wide = 640'd0;
            m11_fp16_mlp_product_frontend16_q4 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .product_s32x16x32(product_s32),
                .out_valid(out_valid), .out_ready(out_ready),
                .activation_u8x16x32(activation_u8),
                .activation_meta(activation_meta_narrow),
                .input_group_count(input_group_count),
                .output_group_count(output_group_count),
                .busy_cycle_count(busy_cycle_count), .error(error)
            );
        end else begin : g_fp32
            assign activation_meta_narrow = 384'd0;
            m11_fp32_mlp_product_frontend16_q4 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .product_s32x16x32(product_s32),
                .out_valid(out_valid), .out_ready(out_ready),
                .activation_u8x16x32(activation_u8),
                .activation_meta(activation_meta_wide),
                .input_group_count(input_group_count),
                .output_group_count(output_group_count),
                .busy_cycle_count(busy_cycle_count), .error(error)
            );
        end
    endgenerate

    function automatic narrow_meta_nonfinite;
        input [383:0] metadata;
        integer row;
        reg invalid;
        begin
            invalid = 1'b0;
            for (row = 0; row < 16; row = row + 1)
                if (&metadata[row*24 + 18 +: 5])
                    invalid = 1'b1;
            narrow_meta_nonfinite = invalid;
        end
    endfunction

    function automatic wide_meta_nonfinite;
        input [639:0] metadata;
        integer row;
        reg invalid;
        begin
            invalid = 1'b0;
            for (row = 0; row < 16; row = row + 1)
                if (&metadata[row*40 + 31 +: 8])
                    invalid = 1'b1;
            wide_meta_nonfinite = invalid;
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_index <= 0;
            receive_index <= 0;
            mismatch_count <= 0;
            nonfinite_scale_count <= 0;
            previous_input_cycle <= -1;
            previous_output_cycle <= -1;
            input_ii_min <= 32'h7fff_ffff;
            input_ii_max <= 0;
            output_ii_min <= 32'h7fff_ffff;
            output_ii_max <= 0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            last_output_cycle <= -1;
            input_stall_cycles <= 0;
            output_stall_cycles <= 0;
            output_was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                if (previous_input_cycle >= 0) begin
                    delta = cycle - previous_input_cycle;
                    if (delta < input_ii_min)
                        input_ii_min <= delta;
                    if (delta > input_ii_max)
                        input_ii_max <= delta;
                end
                previous_input_cycle <= cycle;
                send_index <= send_index + 1;
            end else if (in_valid)
                input_stall_cycles <= input_stall_cycles + 1;

            if (out_valid && !out_ready)
                output_stall_cycles <= output_stall_cycles + 1;
            if (output_was_stalled) begin
                if (!out_valid || activation_u8 !== stalled_u8 ||
                        (CASE_ID != 2 &&
                         activation_meta_narrow !== stalled_meta_narrow) ||
                        (CASE_ID == 2 &&
                         activation_meta_wide !== stalled_meta_wide)) begin
                    $display("FAIL: M11 output changed under stall case=%0d",
                        CASE_ID);
                    $finish;
                end
            end
            output_was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                stalled_u8 <= activation_u8;
                stalled_meta_narrow <= activation_meta_narrow;
                stalled_meta_wide <= activation_meta_wide;
            end

            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                if (previous_output_cycle >= 0) begin
                    delta = cycle - previous_output_cycle;
                    if (delta < output_ii_min)
                        output_ii_min <= delta;
                    if (delta > output_ii_max)
                        output_ii_max <= delta;
                end
                previous_output_cycle <= cycle;
                last_output_cycle <= cycle;
                response_mismatch = 1'b0;
                if (CASE_ID == 0) begin
                    if (activation_u8 !== expected_sc_u8_mem[receive_index] ||
                            activation_meta_narrow !==
                            expected_sc_meta_mem[receive_index])
                        response_mismatch = 1'b1;
                end else if (CASE_ID == 1) begin
                    if (activation_u8 !== expected_fp_u8_mem[receive_index] ||
                            activation_meta_narrow !==
                            expected_fp16_meta_mem[receive_index])
                        response_mismatch = 1'b1;
                    if (narrow_meta_nonfinite(activation_meta_narrow))
                        nonfinite_scale_count <= nonfinite_scale_count + 1;
                end else begin
                    if (activation_u8 !== expected_fp_u8_mem[receive_index] ||
                            activation_meta_wide !==
                            expected_fp32_meta_mem[receive_index])
                        response_mismatch = 1'b1;
                    if (wide_meta_nonfinite(activation_meta_wide))
                        nonfinite_scale_count <= nonfinite_scale_count + 1;
                end
                if (response_mismatch) begin
                    mismatch_count <= mismatch_count + 1;
                    if (mismatch_count < 12)
                        $display("M11_MISMATCH case=%0d group=%0d",
                            CASE_ID, receive_index);
                end
                receive_index <= receive_index + 1;
                if (receive_index == GROUPS-1) begin
                    if (mismatch_count == 0 &&
                            input_group_count == GROUPS &&
                            output_group_count + 1 == GROUPS &&
                            nonfinite_scale_count == 0 && !error) begin
                        $display("M11_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"groups\":%0d,\"rows\":16,\"mismatches\":0,\"nonfinite_scales\":0,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"output_ii_min\":%0d,\"output_ii_max\":%0d,\"first_output_latency\":%0d,\"first_input_to_last_output_cycles\":%0d,\"input_stall_cycles\":%0d,\"output_stall_cycles\":%0d,\"busy_cycles\":%0d,\"cycles\":%0d}",
                            CASE_ID, BACKPRESSURE, GROUPS, input_ii_min,
                            input_ii_max, output_ii_min, output_ii_max,
                            first_output_cycle-first_input_cycle+1,
                            cycle-first_input_cycle+1, input_stall_cycles,
                            output_stall_cycles, busy_cycle_count, cycle+1);
                        $display("PASS: M11 MLP product frontend native-scale boundary");
                    end else begin
                        $display("FAIL: M11 final case=%0d mismatch=%0d nonfinite=%0d input=%0d output=%0d error=%b",
                            CASE_ID, mismatch_count, nonfinite_scale_count,
                            input_group_count, output_group_count+1, error);
                    end
                    $finish;
                end
            end
            if (error) begin
                $display("FAIL: M11 DUT error case=%0d cycle=%0d",
                    CASE_ID, cycle);
                $finish;
            end
            if (cycle > 1000000) begin
                $display("FAIL: M11 timeout case=%0d send=%0d receive=%0d",
                    CASE_ID, send_index, receive_index);
                $finish;
            end
        end
    end

    initial begin
        if ((CASE_ID < 0) || (CASE_ID > 2) ||
                ((BACKPRESSURE != 0) && (BACKPRESSURE != 1)))
            $error("invalid M11 test parameters");
    end
endmodule
