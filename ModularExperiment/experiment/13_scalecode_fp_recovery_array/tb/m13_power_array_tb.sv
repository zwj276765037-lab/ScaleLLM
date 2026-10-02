`timescale 1ns / 1ps

// Post-route timing-netlist activity driver. Inputs change on falling edges so
// the routed clock insertion delay cannot turn testbench stimulus changes into
// artificial input hold violations.
module m13_power_array_tb;
    localparam integer LANES = 96;
    localparam integer VECTORS = 4096;
    localparam integer ACTIVE_CYCLES = 65536;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    integer sent = 0;
    integer accepted = 0;
    integer produced = 0;
    integer vector_index = 0;

    reg [LANES*17-1:0] dot0_mem [0:VECTORS-1];
    reg [LANES*17-1:0] dot1_mem [0:VECTORS-1];
    wire in_ready;
    wire out_valid;
    wire signed [LANES*36-1:0] contribution0;
    wire signed [LANES*36-1:0] contribution1;
    wire error;

`ifdef M13_POWER_SC
    reg [LANES*14-1:0] activation_meta_mem [0:VECTORS-1];
    reg [LANES*14-1:0] weight0_meta_mem [0:VECTORS-1];
    reg [LANES*14-1:0] weight1_meta_mem [0:VECTORS-1];
    m13_sc_recovery_array96 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .dot0_s17x96(dot0_mem[vector_index]),
        .dot1_s17x96(dot1_mem[vector_index]),
        .activation_code_u8x96(
            activation_meta_mem[vector_index][0 +: LANES*8]),
        .activation_shift_u6x96(
            activation_meta_mem[vector_index][LANES*8 +: LANES*6]),
        .weight0_code_u8x96(
            weight0_meta_mem[vector_index][0 +: LANES*8]),
        .weight0_shift_u6x96(
            weight0_meta_mem[vector_index][LANES*8 +: LANES*6]),
        .weight1_code_u8x96(
            weight1_meta_mem[vector_index][0 +: LANES*8]),
        .weight1_shift_u6x96(
            weight1_meta_mem[vector_index][LANES*8 +: LANES*6]),
        .out_valid(out_valid),
        .contribution0_s36_q24x96(contribution0),
        .contribution1_s36_q24x96(contribution1), .error(error));
`elsif M13_POWER_SC_AUTO
    reg [LANES*14-1:0] activation_meta_mem [0:VECTORS-1];
    reg [LANES*14-1:0] weight0_meta_mem [0:VECTORS-1];
    reg [LANES*14-1:0] weight1_meta_mem [0:VECTORS-1];
    m13_sc_recovery_array96_auto dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .dot0_s17x96(dot0_mem[vector_index]),
        .dot1_s17x96(dot1_mem[vector_index]),
        .activation_code_u8x96(
            activation_meta_mem[vector_index][0 +: LANES*8]),
        .activation_shift_u6x96(
            activation_meta_mem[vector_index][LANES*8 +: LANES*6]),
        .weight0_code_u8x96(
            weight0_meta_mem[vector_index][0 +: LANES*8]),
        .weight0_shift_u6x96(
            weight0_meta_mem[vector_index][LANES*8 +: LANES*6]),
        .weight1_code_u8x96(
            weight1_meta_mem[vector_index][0 +: LANES*8]),
        .weight1_shift_u6x96(
            weight1_meta_mem[vector_index][LANES*8 +: LANES*6]),
        .out_valid(out_valid),
        .contribution0_s36_q24x96(contribution0),
        .contribution1_s36_q24x96(contribution1), .error(error));
`elsif M13_POWER_FP16
    reg [LANES*16-1:0] activation_scale_mem [0:VECTORS-1];
    reg [LANES*16-1:0] weight0_scale_mem [0:VECTORS-1];
    reg [LANES*16-1:0] weight1_scale_mem [0:VECTORS-1];
    m13_fp16_recovery_array96 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .dot0_s17x96(dot0_mem[vector_index]),
        .dot1_s17x96(dot1_mem[vector_index]),
        .activation_scale_fpx96(activation_scale_mem[vector_index]),
        .weight0_scale_fpx96(weight0_scale_mem[vector_index]),
        .weight1_scale_fpx96(weight1_scale_mem[vector_index]),
        .out_valid(out_valid),
        .contribution0_s36_q24x96(contribution0),
        .contribution1_s36_q24x96(contribution1), .error(error));
`elsif M13_POWER_FP32
    reg [LANES*32-1:0] activation_scale_mem [0:VECTORS-1];
    reg [LANES*32-1:0] weight0_scale_mem [0:VECTORS-1];
    reg [LANES*32-1:0] weight1_scale_mem [0:VECTORS-1];
    m13_fp32_recovery_array96 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .dot0_s17x96(dot0_mem[vector_index]),
        .dot1_s17x96(dot1_mem[vector_index]),
        .activation_scale_fpx96(activation_scale_mem[vector_index]),
        .weight0_scale_fpx96(weight0_scale_mem[vector_index]),
        .weight1_scale_fpx96(weight1_scale_mem[vector_index]),
        .out_valid(out_valid),
        .contribution0_s36_q24x96(contribution0),
        .contribution1_s36_q24x96(contribution1), .error(error));
`else
    initial $error("define exactly one M13_POWER_SC/SC_AUTO/FP16/FP32 variant");
`endif

    initial begin
        $readmemh({`M13_POWER_DATA_DIR,"/dot0_s17x96.mem"}, dot0_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/dot1_s17x96.mem"}, dot1_mem);
`ifdef M13_POWER_SC
        $readmemh({`M13_POWER_DATA_DIR,"/activation_meta_sc_u1344.mem"},
            activation_meta_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight0_meta_sc_u1344.mem"},
            weight0_meta_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight1_meta_sc_u1344.mem"},
            weight1_meta_mem);
`elsif M13_POWER_SC_AUTO
        $readmemh({`M13_POWER_DATA_DIR,"/activation_meta_sc_u1344.mem"},
            activation_meta_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight0_meta_sc_u1344.mem"},
            weight0_meta_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight1_meta_sc_u1344.mem"},
            weight1_meta_mem);
`elsif M13_POWER_FP16
        $readmemh({`M13_POWER_DATA_DIR,"/activation_scale_fp16x96.mem"},
            activation_scale_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight0_scale_fp16x96.mem"},
            weight0_scale_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight1_scale_fp16x96.mem"},
            weight1_scale_mem);
`elsif M13_POWER_FP32
        $readmemh({`M13_POWER_DATA_DIR,"/activation_scale_fp32x96.mem"},
            activation_scale_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight0_scale_fp32x96.mem"},
            weight0_scale_mem);
        $readmemh({`M13_POWER_DATA_DIR,"/weight1_scale_fp32x96.mem"},
            weight1_scale_mem);
`endif
        repeat (10) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
    end

    always @(negedge clk) begin
        if (rst_n) begin
            if (sent < ACTIVE_CYCLES) begin
                vector_index = sent & (VECTORS-1);
                in_valid = 1'b1;
                sent = sent + 1;
            end else begin
                in_valid = 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if (rst_n) begin
            if (in_valid && in_ready)
                accepted = accepted + 1;
            if (out_valid)
                produced = produced + 1;
            if (error) begin
                $display("FAIL: M13 power workload DUT error sent=%0d accepted=%0d produced=%0d",
                    sent, accepted, produced);
                $finish;
            end
        end
    end

    initial begin
        wait(rst_n);
        wait(produced == ACTIVE_CYCLES);
        repeat (16) @(posedge clk);
        if (accepted != ACTIVE_CYCLES || sent != ACTIVE_CYCLES) begin
            $display("FAIL: M13 power workload counters sent=%0d accepted=%0d produced=%0d",
                sent, accepted, produced);
            $finish;
        end
        $display("M13_POWER_METRIC_JSON: {\"active_cycles\":%0d,\"lanes\":96,\"contributions_per_cycle\":192,\"accepted_contributions\":%0d}",
            ACTIVE_CYCLES, ACTIVE_CYCLES*192);
        $display("PASS: M13 post-route power workload");
        $finish;
    end

    initial begin
        #(10*(ACTIVE_CYCLES+1024));
        $display("FAIL: M13 power workload timeout sent=%0d accepted=%0d produced=%0d",
            sent, accepted, produced);
        $finish;
    end
endmodule
