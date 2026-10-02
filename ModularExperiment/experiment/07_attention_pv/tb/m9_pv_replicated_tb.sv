`timescale 1ns/1ps

module m9_pv_replicated_tb #(
    parameter integer CASE_ID = 1,
    parameter string DATA_DIR = "data"
);
    localparam integer SOURCE_ROWS = 32;
    localparam integer TEST_ROWS = 96;
    localparam integer KEYS = 128;
    localparam integer SOURCE_VALUES = SOURCE_ROWS * KEYS;
    localparam integer TEST_VALUES = TEST_ROWS * KEYS;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    reg out_ready = 1'b0;
    wire in_ready;
    wire out_valid;
    wire error;
    wire [383:0] out_context;
    wire [31:0] input_key_count;
    wire [31:0] output_row_count;
    wire [31:0] saturation_count;
    reg [15:0] prob16 [0:SOURCE_VALUES-1];
    reg [31:0] prob32 [0:SOURCE_VALUES-1];
    reg [255:0] value16 [0:SOURCE_VALUES-1];
    reg [511:0] value32 [0:SOURCE_VALUES-1];
    reg [383:0] expected16 [0:SOURCE_ROWS-1];
    reg [383:0] expected32 [0:SOURCE_ROWS-1];
    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer mismatch_count = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer previous_output_cycle = -1;
    integer row_interval_min = 999999;
    integer row_interval_max = 0;
    integer row_interval_sum = 0;
    integer interval;
    integer source_input_index = 0;
    integer source_output_index = 0;
    wire [383:0] expected = CASE_ID == 1 ?
        expected16[source_output_index] : expected32[source_output_index];

    always #5 clk = ~clk;
    always @* begin
        source_input_index = sent % SOURCE_VALUES;
        source_output_index = received % SOURCE_ROWS;
    end

    generate
        if (CASE_ID == 1) begin : fp16_case
            m9_fp16_pv_x19 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key((sent % KEYS) == 0),
                .in_last_key((sent % KEYS) == KEYS-1),
                .in_prob(prob16[source_input_index]),
                .in_v(value16[source_input_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context),
                .input_key_count(input_key_count),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count), .error(error)
            );
        end else begin : fp32_case
            m9_fp32_pv_x21 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key((sent % KEYS) == 0),
                .in_last_key((sent % KEYS) == KEYS-1),
                .in_prob(prob32[source_input_index]),
                .in_v(value32[source_input_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_context16_s24(out_context),
                .input_key_count(input_key_count),
                .output_row_count(output_row_count),
                .saturation_count(saturation_count), .error(error)
            );
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/prob16.mem"}, prob16);
        $readmemh({DATA_DIR,"/prob32.mem"}, prob32);
        $readmemh({DATA_DIR,"/v16.mem"}, value16);
        $readmemh({DATA_DIR,"/v32.mem"}, value32);
        $readmemh({DATA_DIR,"/e16.mem"}, expected16);
        $readmemh({DATA_DIR,"/e32.mem"}, expected32);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            in_valid <= sent < TEST_VALUES;
            out_ready <= !(((cycle % 31) >= 21) && ((cycle % 31) <= 25));
        end
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle <= cycle + 1;
            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle = cycle;
                sent <= sent + 1;
            end
            if (error) begin
                $display("FAIL: replicated M9 sticky error cycle=%0d sent=%0d received=%0d",
                    cycle, sent, received);
                $finish;
            end
            if (out_valid && out_ready) begin
                if (out_context !== expected) begin
                    mismatch_count <= mismatch_count + 1;
                    if (mismatch_count < 8)
                        $display("MISMATCH replicated M9 row=%0d expected=%h got=%h",
                            received, expected, out_context);
                end
                if (first_output_cycle < 0)
                    first_output_cycle = cycle;
                if (previous_output_cycle >= 0) begin
                    interval = cycle - previous_output_cycle;
                    if (interval < row_interval_min)
                        row_interval_min = interval;
                    if (interval > row_interval_max)
                        row_interval_max = interval;
                    row_interval_sum = row_interval_sum + interval;
                end
                previous_output_cycle = cycle;
                received <= received + 1;
                if (received == TEST_ROWS-1) begin
                    if ((mismatch_count == 0) && (out_context === expected) &&
                        (input_key_count == TEST_VALUES) &&
                        (output_row_count == TEST_ROWS-1)) begin
                        $display("M9_REPLICATED_METRIC_JSON: {\"case\":\"%s\",\"cores\":%0d,\"rows\":%0d,\"keys\":%0d,\"row_mismatches\":0,\"first_output_latency\":%0d,\"row_interval_min\":%0d,\"row_interval_mean\":%0f,\"row_interval_max\":%0d,\"saturation_count_before_last\":%0d,\"cycles\":%0d}",
                            CASE_ID==1 ? "fp16" : "fp32",
                            CASE_ID==1 ? 19 : 21, TEST_ROWS, TEST_VALUES,
                            first_output_cycle-first_input_cycle,
                            row_interval_min,
                            row_interval_sum/real'(TEST_ROWS-1),
                            row_interval_max,
                            saturation_count, cycle-first_input_cycle+1);
                        $display("PASS: M9 buffered replicated equal-throughput scheduler");
                    end else begin
                        $display("FAIL: replicated M9 final mismatch=%0d in=%0d out=%0d",
                            mismatch_count, input_key_count, output_row_count);
                    end
                    $finish;
                end
            end
            if (cycle > 250000) begin
                $display("FAIL: replicated M9 timeout sent=%0d received=%0d", sent, received);
                $finish;
            end
        end
    end
endmodule
