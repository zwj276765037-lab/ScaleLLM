`timescale 1ns/1ps

module m10_fp_silu_mul_tb #(
    parameter integer CASE_ID = 1,
    parameter string DATA_DIR = "data"
);
    localparam integer VECTOR_COUNT = 512;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg out_ready = 1'b0;
    wire in_ready;
    wire out_valid;
    wire signed [31:0] out_product;
    wire error;
    reg [15:0] gate16 [0:VECTOR_COUNT-1];
    reg [15:0] up16 [0:VECTOR_COUNT-1];
    reg [31:0] gate32 [0:VECTOR_COUNT-1];
    reg [31:0] up32 [0:VECTOR_COUNT-1];
    reg [31:0] expected16 [0:VECTOR_COUNT-1];
    reg [31:0] expected32 [0:VECTOR_COUNT-1];
    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer previous_accept_cycle = -1;
    integer unstalled_accept_interval_max = 0;
    integer mismatch_count = 0;
    integer absolute_error_sum = 0;
    integer absolute_error_max = 0;
    integer difference;
    reg [31:0] held_output;
    reg was_stalled = 1'b0;
    wire in_valid = rst_n && (sent < VECTOR_COUNT);
    wire [31:0] expected = CASE_ID == 1 ?
        expected16[received] : expected32[received];

    always #5 clk = ~clk;
    generate
        if (CASE_ID == 1) begin : fp16_case
            m10_fp16_silu_mul dut (
                .clk(clk),.rst_n(rst_n),.clear(clear),
                .in_valid(in_valid),.in_ready(in_ready),
                .gate_fp(gate16[sent]),.up_fp(up16[sent]),
                .out_valid(out_valid),.out_ready(out_ready),
                .out_product_s32(out_product),.error(error));
        end else begin : fp32_case
            m10_fp32_silu_mul dut (
                .clk(clk),.rst_n(rst_n),.clear(clear),
                .in_valid(in_valid),.in_ready(in_ready),
                .gate_fp(gate32[sent]),.up_fp(up32[sent]),
                .out_valid(out_valid),.out_ready(out_ready),
                .out_product_s32(out_product),.error(error));
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/gate_fp16.mem"},gate16);
        $readmemh({DATA_DIR,"/up_fp16.mem"},up16);
        $readmemh({DATA_DIR,"/gate_fp32.mem"},gate32);
        $readmemh({DATA_DIR,"/up_fp32.mem"},up32);
        $readmemh({DATA_DIR,"/expected_fp16_s32.mem"},expected16);
        $readmemh({DATA_DIR,"/expected_fp32_s32.mem"},expected32);
        repeat(8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (rst_n)
            out_ready <= (received < 256) ? 1'b1 : ((cycle % 11) != 5);
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle <= cycle + 1;
            if (was_stalled && (!out_valid || (out_product !== held_output))) begin
                $display("FAIL: M10 FP output changed under backpressure");
                $finish;
            end
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready)
                held_output <= out_product;
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle = cycle;
                if ((sent < 256) && (previous_accept_cycle >= 0) &&
                    ((cycle-previous_accept_cycle) > unstalled_accept_interval_max))
                    unstalled_accept_interval_max = cycle-previous_accept_cycle;
                previous_accept_cycle = cycle;
                sent <= sent + 1;
            end
            if (error) begin
                $display("FAIL: M10 FP sticky error sent=%0d received=%0d",sent,received);
                $finish;
            end
            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle = cycle;
                difference = $signed(out_product) - $signed(expected);
                if (difference < 0)
                    difference = -difference;
                absolute_error_sum = absolute_error_sum + difference;
                if (difference > absolute_error_max)
                    absolute_error_max = difference;
                if (difference > (CASE_ID == 1 ? 256 : 8)) begin
                    mismatch_count <= mismatch_count + 1;
                    if (mismatch_count < 8)
                        $display("MISMATCH M10 case=%0d idx=%0d got=%h expected=%h diff=%0d",
                            CASE_ID,received,out_product,expected,difference);
                end
                received <= received + 1;
                if (received == VECTOR_COUNT-1) begin
                    if ((mismatch_count == 0) &&
                        (difference <= (CASE_ID == 1 ? 256 : 8)) &&
                        (unstalled_accept_interval_max == 1)) begin
                        $display("M10_FP_SILU_METRIC_JSON: {\"case\":\"%s\",\"vectors\":512,\"tolerance_mismatches\":0,\"mae_s32_lsb\":%0f,\"max_error_s32_lsb\":%0d,\"unstalled_input_ii_max\":%0d,\"first_output_latency\":%0d,\"cycles\":%0d}",
                            CASE_ID==1?"fp16":"fp32",
                            absolute_error_sum/512.0,absolute_error_max,
                            unstalled_accept_interval_max,
                            first_output_cycle-first_input_cycle,
                            cycle-first_input_cycle+1);
                        $display("PASS: M10 FP SiLU multiply");
                    end else begin
                        $display("FAIL: M10 FP final mismatches=%0d maxerr=%0d ii=%0d",
                            mismatch_count,absolute_error_max,unstalled_accept_interval_max);
                    end
                    $finish;
                end
            end
            if (cycle > 10000) begin
                $display("FAIL: M10 FP timeout sent=%0d received=%0d",sent,received);
                $finish;
            end
        end
    end
endmodule
