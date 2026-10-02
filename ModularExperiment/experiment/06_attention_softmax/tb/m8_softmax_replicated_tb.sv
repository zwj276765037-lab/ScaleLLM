`timescale 1ns/1ps

module m8_softmax_replicated_tb #(
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
    wire out_last_key;
    wire error;
    wire [15:0] out_prob;
    wire [6:0] out_key_index;
    wire [31:0] input_score_count;
    wire [31:0] output_prob_count;
    wire [31:0] row_count;
    reg [15:0] score16 [0:SOURCE_VALUES-1];
    reg [31:0] score32 [0:SOURCE_VALUES-1];
    reg [15:0] expected16 [0:SOURCE_VALUES-1];
    reg [15:0] expected32 [0:SOURCE_VALUES-1];
    reg mask [0:SOURCE_VALUES-1];
    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer protocol_mismatches = 0;
    integer numeric_error_sum = 0;
    integer numeric_error_max = 0;
    integer difference;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer previous_row_cycle = -1;
    integer row_interval_min = 999999;
    integer row_interval_max = 0;
    integer row_interval_sum = 0;
    integer interval;
    integer source_input_index = 0;
    integer source_output_index = 0;
    wire [15:0] expected = CASE_ID == 1 ?
        expected16[source_output_index] : expected32[source_output_index];

    always #5 clk = ~clk;
    always @* begin
        source_input_index = sent % SOURCE_VALUES;
        source_output_index = received % SOURCE_VALUES;
    end

    generate
        if (CASE_ID == 1) begin : fp16_case
            m8_fp16_softmax_x22 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key((sent % KEYS) == 0),
                .in_last_key((sent % KEYS) == KEYS-1),
                .in_mask(mask[source_input_index]),
                .in_score(score16[source_input_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(input_score_count),
                .output_prob_count(output_prob_count), .row_count(row_count),
                .error(error)
            );
            always @(posedge clk) begin
                if (rst_n && error)
                    $display("M8_DEBUG_ERROR: protocol=%0b core_error=%h",
                        dut.u.protocol_error, dut.u.core_error);
            end
        end else begin : fp32_case
            m8_fp32_softmax_x26 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key((sent % KEYS) == 0),
                .in_last_key((sent % KEYS) == KEYS-1),
                .in_mask(mask[source_input_index]),
                .in_score(score32[source_input_index]),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(input_score_count),
                .output_prob_count(output_prob_count), .row_count(row_count),
                .error(error)
            );
            always @(posedge clk) begin
                if (rst_n && error)
                    $display("M8_DEBUG_ERROR: protocol=%0b core_error=%h",
                        dut.u.protocol_error, dut.u.core_error);
            end
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/score_fp16.mem"}, score16);
        $readmemh({DATA_DIR,"/score_fp32.mem"}, score32);
        $readmemh({DATA_DIR,"/expected_fp16.mem"}, expected16);
        $readmemh({DATA_DIR,"/expected_fp32.mem"}, expected32);
        $readmemh({DATA_DIR,"/mask.mem"}, mask);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            in_valid <= sent < TEST_VALUES;
            out_ready <= !(((cycle % 37) >= 27) && ((cycle % 37) <= 31));
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
                $display("FAIL: replicated M8 sticky error cycle=%0d sent=%0d received=%0d",
                    cycle, sent, received);
                $finish;
            end
            if (out_valid && out_ready) begin
                difference = $signed({1'b0,out_prob}) - $signed({1'b0,expected});
                if (difference < 0)
                    difference = -difference;
                numeric_error_sum = numeric_error_sum + difference;
                if (difference > numeric_error_max)
                    numeric_error_max = difference;
                if ((out_key_index != (received % KEYS)) ||
                    (out_last_key !== ((received % KEYS) == KEYS-1)) ||
                    ((CASE_ID == 2) && (difference != 0))) begin
                    if (protocol_mismatches < 8)
                        $display("MISMATCH replicated M8 idx=%0d expected=%h got=%h key=%0d last=%0d",
                            received, expected, out_prob, out_key_index, out_last_key);
                    protocol_mismatches <= protocol_mismatches + 1;
                end
                if (first_output_cycle < 0)
                    first_output_cycle = cycle;
                if (out_last_key) begin
                    if (previous_row_cycle >= 0) begin
                        interval = cycle - previous_row_cycle;
                        if (interval < row_interval_min)
                            row_interval_min = interval;
                        if (interval > row_interval_max)
                            row_interval_max = interval;
                        row_interval_sum = row_interval_sum + interval;
                    end
                    previous_row_cycle = cycle;
                end
                received <= received + 1;
                if (received == TEST_VALUES-1) begin
                    if ((protocol_mismatches == 0) &&
                        !((CASE_ID == 2) && (difference != 0)) &&
                        (input_score_count == TEST_VALUES) &&
                        (output_prob_count == TEST_VALUES-1) &&
                        (row_count == TEST_ROWS-1)) begin
                        $display("M8_REPLICATED_METRIC_JSON: {\"case\":\"%s\",\"cores\":%0d,\"rows\":%0d,\"keys\":%0d,\"protocol_mismatches\":0,\"numeric_mae_u16\":%0f,\"numeric_max_u16\":%0d,\"first_output_latency\":%0d,\"row_interval_min\":%0d,\"row_interval_mean\":%0f,\"row_interval_max\":%0d,\"cycles\":%0d}",
                            CASE_ID==1 ? "fp16" : "fp32",
                            CASE_ID==1 ? 22 : 26, TEST_ROWS, TEST_VALUES,
                            numeric_error_sum/real'(TEST_VALUES),
                            numeric_error_max,
                            first_output_cycle-first_input_cycle,
                            row_interval_min,
                            row_interval_sum/real'(TEST_ROWS-1),
                            row_interval_max, cycle-first_input_cycle+1);
                        $display("PASS: M8 replicated equal-throughput scheduler");
                    end else begin
                        $display("FAIL: replicated M8 final protocol=%0d in=%0d out=%0d rows=%0d",
                            protocol_mismatches, input_score_count,
                            output_prob_count, row_count);
                    end
                    $finish;
                end
            end
            if (cycle > 250000) begin
                $display("FAIL: replicated M8 timeout sent=%0d received=%0d", sent, received);
                $finish;
            end
        end
    end
endmodule
