`timescale 1ns / 1ps

module m13_recovery_array_tb #(
    parameter integer CASE_ID = 0,
    parameter integer VECTORS = 4096,
    parameter string DATA_DIR = "data"
);
    localparam integer LANES = 96;
    localparam integer CONTRIBUTIONS_PER_CYCLE = 192;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;

    reg [LANES*17-1:0] dot0_mem [0:VECTORS-1];
    reg [LANES*17-1:0] dot1_mem [0:VECTORS-1];
    reg [LANES*14-1:0] activation_sc_mem [0:VECTORS-1];
    reg [LANES*14-1:0] weight0_sc_mem [0:VECTORS-1];
    reg [LANES*14-1:0] weight1_sc_mem [0:VECTORS-1];
    reg [LANES*16-1:0] activation_fp16_mem [0:VECTORS-1];
    reg [LANES*16-1:0] weight0_fp16_mem [0:VECTORS-1];
    reg [LANES*16-1:0] weight1_fp16_mem [0:VECTORS-1];
    reg [LANES*32-1:0] activation_fp32_mem [0:VECTORS-1];
    reg [LANES*32-1:0] weight0_fp32_mem [0:VECTORS-1];
    reg [LANES*32-1:0] weight1_fp32_mem [0:VECTORS-1];
    reg [LANES*36-1:0] expected0_mem [0:VECTORS-1];
    reg [LANES*36-1:0] expected1_mem [0:VECTORS-1];

    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer first_accept = -1;
    integer first_output = -1;
    integer previous_accept = -1;
    integer previous_output = -1;
    integer input_ii_min = 999999;
    integer input_ii_max = 0;
    integer output_ii_min = 999999;
    integer output_ii_max = 0;
    integer interval;
    integer lane;

    wire [31:0] source_index = sent < VECTORS ? sent : VECTORS-1;
    wire in_valid = rst_n && sent < VECTORS;
    wire in_ready;
    wire out_valid;
    wire signed [LANES*36-1:0] contribution0;
    wire signed [LANES*36-1:0] contribution1;
    wire error;

    generate
        if (CASE_ID == 0) begin : g_sc
            m13_sc_recovery_array96 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .dot0_s17x96(dot0_mem[source_index]),
                .dot1_s17x96(dot1_mem[source_index]),
                .activation_code_u8x96(
                    activation_sc_mem[source_index][0 +: LANES*8]),
                .activation_shift_u6x96(
                    activation_sc_mem[source_index][LANES*8 +: LANES*6]),
                .weight0_code_u8x96(
                    weight0_sc_mem[source_index][0 +: LANES*8]),
                .weight0_shift_u6x96(
                    weight0_sc_mem[source_index][LANES*8 +: LANES*6]),
                .weight1_code_u8x96(
                    weight1_sc_mem[source_index][0 +: LANES*8]),
                .weight1_shift_u6x96(
                    weight1_sc_mem[source_index][LANES*8 +: LANES*6]),
                .out_valid(out_valid),
                .contribution0_s36_q24x96(contribution0),
                .contribution1_s36_q24x96(contribution1), .error(error));
        end else if (CASE_ID == 3) begin : g_sc_auto
            m13_sc_recovery_array96_auto dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .dot0_s17x96(dot0_mem[source_index]),
                .dot1_s17x96(dot1_mem[source_index]),
                .activation_code_u8x96(
                    activation_sc_mem[source_index][0 +: LANES*8]),
                .activation_shift_u6x96(
                    activation_sc_mem[source_index][LANES*8 +: LANES*6]),
                .weight0_code_u8x96(
                    weight0_sc_mem[source_index][0 +: LANES*8]),
                .weight0_shift_u6x96(
                    weight0_sc_mem[source_index][LANES*8 +: LANES*6]),
                .weight1_code_u8x96(
                    weight1_sc_mem[source_index][0 +: LANES*8]),
                .weight1_shift_u6x96(
                    weight1_sc_mem[source_index][LANES*8 +: LANES*6]),
                .out_valid(out_valid),
                .contribution0_s36_q24x96(contribution0),
                .contribution1_s36_q24x96(contribution1), .error(error));
        end else if (CASE_ID == 1) begin : g_fp16
            m13_fp16_recovery_array96 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .dot0_s17x96(dot0_mem[source_index]),
                .dot1_s17x96(dot1_mem[source_index]),
                .activation_scale_fpx96(activation_fp16_mem[source_index]),
                .weight0_scale_fpx96(weight0_fp16_mem[source_index]),
                .weight1_scale_fpx96(weight1_fp16_mem[source_index]),
                .out_valid(out_valid),
                .contribution0_s36_q24x96(contribution0),
                .contribution1_s36_q24x96(contribution1), .error(error));
        end else begin : g_fp32
            m13_fp32_recovery_array96 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .dot0_s17x96(dot0_mem[source_index]),
                .dot1_s17x96(dot1_mem[source_index]),
                .activation_scale_fpx96(activation_fp32_mem[source_index]),
                .weight0_scale_fpx96(weight0_fp32_mem[source_index]),
                .weight1_scale_fpx96(weight1_fp32_mem[source_index]),
                .out_valid(out_valid),
                .contribution0_s36_q24x96(contribution0),
                .contribution1_s36_q24x96(contribution1), .error(error));
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/dot0_s17x96.mem"}, dot0_mem);
        $readmemh({DATA_DIR,"/dot1_s17x96.mem"}, dot1_mem);
        if (CASE_ID == 0 || CASE_ID == 3) begin
            $readmemh({DATA_DIR,"/activation_meta_sc_u1344.mem"},
                activation_sc_mem);
            $readmemh({DATA_DIR,"/weight0_meta_sc_u1344.mem"},
                weight0_sc_mem);
            $readmemh({DATA_DIR,"/weight1_meta_sc_u1344.mem"},
                weight1_sc_mem);
            $readmemh({DATA_DIR,"/expected_sc0_s36x96.mem"}, expected0_mem);
            $readmemh({DATA_DIR,"/expected_sc1_s36x96.mem"}, expected1_mem);
        end else if (CASE_ID == 1) begin
            $readmemh({DATA_DIR,"/activation_scale_fp16x96.mem"},
                activation_fp16_mem);
            $readmemh({DATA_DIR,"/weight0_scale_fp16x96.mem"},
                weight0_fp16_mem);
            $readmemh({DATA_DIR,"/weight1_scale_fp16x96.mem"},
                weight1_fp16_mem);
            $readmemh({DATA_DIR,"/expected_fp16_0_s36x96.mem"}, expected0_mem);
            $readmemh({DATA_DIR,"/expected_fp16_1_s36x96.mem"}, expected1_mem);
        end else begin
            $readmemh({DATA_DIR,"/activation_scale_fp32x96.mem"},
                activation_fp32_mem);
            $readmemh({DATA_DIR,"/weight0_scale_fp32x96.mem"},
                weight0_fp32_mem);
            $readmemh({DATA_DIR,"/weight1_scale_fp32x96.mem"},
                weight1_fp32_mem);
            $readmemh({DATA_DIR,"/expected_fp32_0_s36x96.mem"}, expected0_mem);
            $readmemh({DATA_DIR,"/expected_fp32_1_s36x96.mem"}, expected1_mem);
        end
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                if (first_accept < 0)
                    first_accept = cycle;
                if (previous_accept >= 0) begin
                    interval = cycle-previous_accept;
                    if (interval < input_ii_min) input_ii_min = interval;
                    if (interval > input_ii_max) input_ii_max = interval;
                end
                previous_accept = cycle;
                sent <= sent + 1;
            end
            if (error) begin
                $display("FAIL: M13 sticky error case=%0d cycle=%0d", CASE_ID, cycle);
                $finish;
            end
            if (out_valid) begin
                if (first_output < 0)
                    first_output = cycle;
                if (previous_output >= 0) begin
                    interval = cycle-previous_output;
                    if (interval < output_ii_min) output_ii_min = interval;
                    if (interval > output_ii_max) output_ii_max = interval;
                end
                previous_output = cycle;
                if (contribution0 !== expected0_mem[received] ||
                    contribution1 !== expected1_mem[received]) begin
                    $display("FAIL: M13 mismatch case=%0d vector=%0d", CASE_ID, received);
                    for (lane = 0; lane < LANES; lane = lane + 1) begin
                        if (contribution0[lane*36 +: 36] !==
                            expected0_mem[received][lane*36 +: 36])
                            $display("M13_MISMATCH vector=%0d lane=%0d output=0 expected=%h got=%h",
                                received, lane,
                                expected0_mem[received][lane*36 +: 36],
                                contribution0[lane*36 +: 36]);
                        if (contribution1[lane*36 +: 36] !==
                            expected1_mem[received][lane*36 +: 36])
                            $display("M13_MISMATCH vector=%0d lane=%0d output=1 expected=%h got=%h",
                                received, lane,
                                expected1_mem[received][lane*36 +: 36],
                                contribution1[lane*36 +: 36]);
                    end
                    $finish;
                end
                received <= received + 1;
                if (received == VECTORS-1) begin
                    if (sent != VECTORS) begin
                        $display("FAIL: M13 output completed before all inputs sent case=%0d sent=%0d",
                            CASE_ID, sent);
                        $finish;
                    end
                    $display("M13_METRIC_JSON: {\"case_id\":%0d,\"vectors\":%0d,\"lanes\":%0d,\"outputs_per_lane\":2,\"accepted_contributions\":%0d,\"mismatches\":0,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"output_ii_min\":%0d,\"output_ii_max\":%0d,\"first_output_latency\":%0d,\"total_cycles\":%0d,\"contributions_per_cycle\":%0d}",
                        CASE_ID, VECTORS, LANES,
                        VECTORS*CONTRIBUTIONS_PER_CYCLE,
                        input_ii_min, input_ii_max, output_ii_min,
                        output_ii_max, first_output-first_accept,
                        cycle-first_accept+1, CONTRIBUTIONS_PER_CYCLE);
                    $display("PASS: M13 recovery-only array case=%0d", CASE_ID);
                    $finish;
                end
            end
            if (cycle > VECTORS+256) begin
                $display("FAIL: M13 timeout case=%0d sent=%0d received=%0d",
                    CASE_ID, sent, received);
                $finish;
            end
        end
    end
endmodule
