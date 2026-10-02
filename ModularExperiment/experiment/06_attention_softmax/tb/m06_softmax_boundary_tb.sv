`timescale 1ns / 1ps

module m06_softmax_boundary_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data_boundary"
);
    localparam integer ROWS = 72;
    localparam integer SCORES = 4236;
    // Frozen before the first boundary XSIM.  The previous N=128 hardware
    // workload observed 96 U16 LSB max error; 128 keeps a small integer margin
    // while still rejecting probability errors larger than 1/512.
    localparam integer FP16_TOLERANCE_U16 = 128;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    reg out_ready = 1'b0;
    wire in_ready;
    wire out_valid;
    wire [15:0] out_prob_u16;
    wire [6:0] out_key_index;
    wire out_last_key;
    wire [31:0] input_score_count;
    wire [31:0] conversion_score_count;
    wire [31:0] core_input_score_count;
    wire [31:0] output_prob_count;
    wire [31:0] row_count;
    wire error;

    reg signed [19:0] score_mem [0:SCORES-1];
    reg [0:0] mask_mem [0:SCORES-1];
    reg [7:0] row_length_mem [0:ROWS-1];
    reg [15:0] expected_sc_mem [0:SCORES-1];
    reg [15:0] expected_fp16_mem [0:SCORES-1];
    reg [15:0] expected_fp32_mem [0:SCORES-1];

    integer cycle = 0;
    integer sent = 0;
    integer received = 0;
    integer send_row = 0;
    integer send_key = 0;
    integer receive_row = 0;
    integer receive_key = 0;
    integer protocol_mismatches = 0;
    integer numeric_excesses = 0;
    integer difference = 0;
    integer numeric_error_max = 0;
    longint numeric_error_sum = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer last_output_cycle = -1;
    integer previous_row_cycle = -1;
    integer row_interval_min = 32'h7fffffff;
    integer row_interval_max = 0;
    longint row_interval_sum = 0;
    integer interval = 0;
    reg done_pending = 1'b0;
    reg was_stalled = 1'b0;
    reg [23:0] held_output = '0;

    wire [7:0] current_send_length =
        send_row < ROWS ? row_length_mem[send_row] : 8'd1;
    wire [7:0] current_receive_length =
        receive_row < ROWS ? row_length_mem[receive_row] : 8'd1;
    wire input_first_key = send_key == 0;
    wire input_last_key = send_key == current_send_length-1;
    wire signed [19:0] input_score_value =
        sent < SCORES ? score_mem[sent] : 20'sd0;
    wire input_mask_value = sent < SCORES ? mask_mem[sent] : 1'b0;
    wire [15:0] expected_probability =
        received >= SCORES ? 16'd0 :
        CASE_ID == 0 ? expected_sc_mem[received] :
        CASE_ID == 1 ? expected_fp16_mem[received] :
                       expected_fp32_mem[received];
    wire expected_last_key = receive_key == current_receive_length-1;
    wire [15:0] numeric_tolerance =
        CASE_ID == 1 ? FP16_TOLERANCE_U16 : 16'd0;

    generate
        if (CASE_ID == 0) begin : g_sc
            m06_sc_softmax_boundary dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(input_first_key),
                .in_last_key(input_last_key),
                .in_mask(input_mask_value),
                .in_score_s20(input_score_value),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob_u16),
                .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(input_score_count),
                .conversion_score_count(conversion_score_count),
                .core_input_score_count(core_input_score_count),
                .output_prob_count(output_prob_count),
                .row_count(row_count), .error(error));
        end else if (CASE_ID == 1) begin : g_fp16
            m06_fp16_softmax_boundary dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(input_first_key),
                .in_last_key(input_last_key),
                .in_mask(input_mask_value),
                .in_score_s20(input_score_value),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob_u16),
                .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(input_score_count),
                .conversion_score_count(conversion_score_count),
                .core_input_score_count(core_input_score_count),
                .output_prob_count(output_prob_count),
                .row_count(row_count), .error(error));
        end else begin : g_fp32
            m06_fp32_softmax_boundary dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(input_first_key),
                .in_last_key(input_last_key),
                .in_mask(input_mask_value),
                .in_score_s20(input_score_value),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_prob_u16(out_prob_u16),
                .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_score_count(input_score_count),
                .conversion_score_count(conversion_score_count),
                .core_input_score_count(core_input_score_count),
                .output_prob_count(output_prob_count),
                .row_count(row_count), .error(error));
        end
    endgenerate

    always #5 clk = ~clk;

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M06 boundary CASE_ID must be 0, 1, or 2");
        if (BACKPRESSURE != 0 && BACKPRESSURE != 1)
            $error("M06 boundary BACKPRESSURE must be 0 or 1");
        $readmemh({DATA_DIR,"/score_s20.mem"}, score_mem);
        $readmemh({DATA_DIR,"/mask.mem"}, mask_mem);
        $readmemh({DATA_DIR,"/row_key_count_u8.mem"}, row_length_mem);
        $readmemh({DATA_DIR,"/expected_sc_u16.mem"}, expected_sc_mem);
        $readmemh({DATA_DIR,"/expected_fp16_u16.mem"}, expected_fp16_mem);
        $readmemh({DATA_DIR,"/expected_fp32_u16.mem"}, expected_fp32_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            in_valid <= sent < SCORES;
            if (BACKPRESSURE == 0)
                out_ready <= 1'b1;
            else
                out_ready <= !(((cycle % 41) >= 29) &&
                    ((cycle % 41) <= 34));
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            sent <= 0;
            received <= 0;
            send_row <= 0;
            send_key <= 0;
            receive_row <= 0;
            receive_key <= 0;
            protocol_mismatches = 0;
            numeric_excesses = 0;
            numeric_error_max = 0;
            numeric_error_sum = 0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            last_output_cycle <= -1;
            previous_row_cycle <= -1;
            row_interval_min = 32'h7fffffff;
            row_interval_max = 0;
            row_interval_sum = 0;
            done_pending <= 1'b0;
            was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;

            if (was_stalled && (!out_valid ||
                    {out_last_key,out_key_index,out_prob_u16} !== held_output)) begin
                $display("FAIL: M06 boundary output changed under backpressure cycle=%0d",
                    cycle);
                $finish;
            end
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready)
                held_output <= {out_last_key,out_key_index,out_prob_u16};

            if (error) begin
                $display("FAIL: M06 boundary sticky error case=%0d cycle=%0d sent=%0d received=%0d",
                    CASE_ID, cycle, sent, received);
                $finish;
            end

            if (in_valid && in_ready) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                sent <= sent + 1;
                if (input_last_key) begin
                    send_row <= send_row + 1;
                    send_key <= 0;
                end else begin
                    send_key <= send_key + 1;
                end
            end

            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                difference = $signed({1'b0,out_prob_u16}) -
                    $signed({1'b0,expected_probability});
                if (difference < 0)
                    difference = -difference;
                numeric_error_sum = numeric_error_sum + difference;
                if (difference > numeric_error_max)
                    numeric_error_max = difference;
                if (difference > numeric_tolerance) begin
                    if (numeric_excesses < 8)
                        $display("MISMATCH: M06 boundary numeric idx=%0d expected=%h got=%h diff=%0d tolerance=%0d",
                            received, expected_probability, out_prob_u16,
                            difference, numeric_tolerance);
                    numeric_excesses = numeric_excesses + 1;
                end
                if (out_key_index != receive_key ||
                        out_last_key !== expected_last_key) begin
                    if (protocol_mismatches < 8)
                        $display("MISMATCH: M06 boundary protocol idx=%0d row=%0d key=%0d got_key=%0d expected_last=%0d got_last=%0d",
                            received, receive_row, receive_key,
                            out_key_index, expected_last_key, out_last_key);
                    protocol_mismatches = protocol_mismatches + 1;
                end

                received <= received + 1;
                if (expected_last_key) begin
                    if (previous_row_cycle >= 0) begin
                        interval = cycle - previous_row_cycle;
                        row_interval_sum = row_interval_sum + interval;
                        if (interval < row_interval_min)
                            row_interval_min = interval;
                        if (interval > row_interval_max)
                            row_interval_max = interval;
                    end
                    previous_row_cycle <= cycle;
                    receive_row <= receive_row + 1;
                    receive_key <= 0;
                end else begin
                    receive_key <= receive_key + 1;
                end
                if (received == SCORES-1) begin
                    last_output_cycle <= cycle;
                    done_pending <= 1'b1;
                end
            end

            if (done_pending) begin
                if (protocol_mismatches != 0 || numeric_excesses != 0 ||
                        input_score_count != SCORES ||
                        conversion_score_count != SCORES ||
                        core_input_score_count != SCORES ||
                        output_prob_count != SCORES ||
                        row_count != ROWS ||
                        send_row != ROWS || receive_row != ROWS) begin
                    $display("FAIL: M06 boundary final case=%0d protocol=%0d numeric=%0d input=%0d conversion=%0d core=%0d output=%0d rows=%0d send_rows=%0d receive_rows=%0d",
                        CASE_ID, protocol_mismatches, numeric_excesses,
                        input_score_count, conversion_score_count,
                        core_input_score_count, output_prob_count, row_count,
                        send_row, receive_row);
                end else begin
                    $display("M06_BOUNDARY_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"rows\":72,\"scores\":4236,\"protocol_mismatches\":0,\"numeric_excesses\":0,\"numeric_mae_u16\":%0f,\"numeric_max_u16\":%0d,\"first_output_latency\":%0d,\"row_interval_min\":%0d,\"row_interval_mean\":%0f,\"row_interval_max\":%0d,\"cycles\":%0d}",
                        CASE_ID, BACKPRESSURE,
                        numeric_error_sum/real'(SCORES),
                        numeric_error_max,
                        first_output_cycle-first_input_cycle,
                        row_interval_min,
                        row_interval_sum/real'(ROWS-1),
                        row_interval_max,
                        last_output_cycle-first_input_cycle+1);
                    $display("PASS: M06 boundary-inclusive Softmax");
                end
                $finish;
            end

            if (cycle > 500000) begin
                $display("FAIL: M06 boundary timeout case=%0d sent=%0d received=%0d rows=%0d",
                    CASE_ID, sent, received, row_count);
                $finish;
            end
        end
    end
endmodule
