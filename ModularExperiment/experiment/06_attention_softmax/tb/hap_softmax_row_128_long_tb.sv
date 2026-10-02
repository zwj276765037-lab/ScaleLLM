`timescale 1ns / 1ps

module hap_softmax_row_128_long_tb #(
    parameter string DATA_DIR = "data/softmax_row_128"
);
    localparam integer SOURCE_ROWS = 32;
    localparam integer TEST_ROWS = 96;
    localparam integer KEY_COUNT = 128;
    localparam integer SOURCE_VALUES = SOURCE_ROWS * KEY_COUNT;
    localparam integer TEST_VALUES = TEST_ROWS * KEY_COUNT;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg in_valid = 1'b0;
    wire in_ready;
    reg in_first_key = 1'b0;
    reg in_last_key = 1'b0;
    reg in_mask = 1'b0;
    reg signed [19:0] in_score = '0;
    wire out_valid;
    reg out_ready = 1'b0;
    wire [15:0] out_prob;
    wire [6:0] out_key_index;
    wire out_last_key;
    wire busy;
    wire [31:0] input_score_count;
    wire [31:0] output_prob_count;
    wire [31:0] row_count;
    wire error;
    reg [20:0] input_mem [0:SOURCE_VALUES-1];
    reg [15:0] expected_mem [0:SOURCE_VALUES-1];
    integer cycle = 0;
    integer send_index = 0;
    integer receive_index = 0;
    integer mismatch_count = 0;
    integer error_send = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer previous_row_cycle = -1;
    integer row_interval_min = 999999;
    integer row_interval_max = 0;
    integer row_interval_sum = 0;
    integer row_interval;
    integer batch_end_cycle = -1;
    reg error_phase = 1'b0;
    reg [23:0] held_output = '0;
    reg was_stalled = 1'b0;

    always #5 clk = ~clk;
    hap_softmax_row_128 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_mask(in_mask), .in_score_q14_s20(in_score),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_prob_u16(out_prob), .out_key_index(out_key_index),
        .out_last_key(out_last_key), .busy(busy),
        .input_score_count(input_score_count),
        .output_prob_count(output_prob_count), .row_count(row_count),
        .error(error)
    );

    initial begin
        $readmemh({DATA_DIR,"/input.mem"}, input_mem);
        $readmemh({DATA_DIR,"/expected_prob.mem"}, expected_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            out_ready <= !(((cycle % 37) >= 27) && ((cycle % 37) <= 31));
            if (!error_phase && (send_index < TEST_VALUES)) begin
                in_score <= input_mem[send_index % SOURCE_VALUES][19:0];
                in_mask <= input_mem[send_index % SOURCE_VALUES][20];
                in_first_key <= ((send_index % KEY_COUNT) == 0);
                in_last_key <= ((send_index % KEY_COUNT) == KEY_COUNT-1);
                in_valid <= 1'b1;
            end else if (error_phase && (error_send < KEY_COUNT)) begin
                in_score <= 20'sd0;
                in_mask <= 1'b1;
                in_first_key <= (error_send == 0);
                in_last_key <= (error_send == KEY_COUNT-1);
                in_valid <= 1'b1;
            end else begin
                in_valid <= 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_index <= 0;
            receive_index <= 0;
            mismatch_count <= 0;
            error_send <= 0;
            error_phase <= 1'b0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            previous_row_cycle <= -1;
            row_interval_min <= 999999;
            row_interval_max <= 0;
            row_interval_sum = 0;
            batch_end_cycle <= -1;
            was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (was_stalled && (!out_valid ||
                    ({out_last_key,out_key_index,out_prob} !== held_output))) begin
                $display("FAIL: long Softmax output changed under backpressure cycle=%0d", cycle);
                $finish;
            end
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready)
                held_output <= {out_last_key,out_key_index,out_prob};

            if (in_valid && in_ready) begin
                if (error_phase) begin
                    error_send <= error_send + 1;
                end else begin
                    if (first_input_cycle < 0)
                        first_input_cycle <= cycle;
                    send_index <= send_index + 1;
                end
            end

            if (out_valid && out_ready) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                if ((out_key_index != (receive_index % KEY_COUNT)) ||
                    (out_last_key !==
                        ((receive_index % KEY_COUNT) == KEY_COUNT-1)) ||
                    (out_prob !==
                        expected_mem[receive_index % SOURCE_VALUES])) begin
                    mismatch_count <= mismatch_count + 1;
                    if (mismatch_count < 8)
                        $display("MISMATCH long Softmax idx=%0d expected=%h got=%h key=%0d last=%0d",
                            receive_index,
                            expected_mem[receive_index % SOURCE_VALUES],
                            out_prob, out_key_index, out_last_key);
                end
                if (out_last_key) begin
                    if (previous_row_cycle >= 0) begin
                        row_interval = cycle - previous_row_cycle;
                        if (row_interval < row_interval_min)
                            row_interval_min <= row_interval;
                        if (row_interval > row_interval_max)
                            row_interval_max <= row_interval;
                        row_interval_sum = row_interval_sum + row_interval;
                    end
                    previous_row_cycle <= cycle;
                end
                receive_index <= receive_index + 1;
                if (receive_index == TEST_VALUES-1) begin
                    batch_end_cycle <= cycle;
                    error_phase <= 1'b1;
                end
            end

            if (error && !error_phase) begin
                $display("FAIL: long Softmax sticky error before all-masked test cycle=%0d", cycle);
                $finish;
            end
            if (error_phase && error) begin
                if ((mismatch_count != 0) ||
                    (input_score_count != TEST_VALUES + KEY_COUNT) ||
                    (output_prob_count != TEST_VALUES) ||
                    (row_count != TEST_ROWS)) begin
                    $display("FAIL: long Softmax final mismatch=%0d in=%0d out=%0d rows=%0d",
                        mismatch_count, input_score_count,
                        output_prob_count, row_count);
                end else begin
                    $display("SOFTMAX_ROW_128_LONG_METRIC_JSON: {\"rows\":96,\"keys\":12288,\"mismatches\":0,\"first_output_latency\":%0d,\"row_interval_min\":%0d,\"row_interval_mean\":%0f,\"row_interval_max\":%0d,\"all_masked_error\":1,\"cycles\":%0d}",
                        first_output_cycle-first_input_cycle,
                        row_interval_min,
                        row_interval_sum/real'(TEST_ROWS-1),
                        row_interval_max,
                        batch_end_cycle-first_input_cycle+1);
                    $display("PASS: long Softmax row128 matched FixBit v2 golden.");
                end
                $finish;
            end
            if (cycle > 60000) begin
                $display("FAIL: long Softmax timeout send=%0d recv=%0d error_send=%0d busy=%0d",
                    send_index, receive_index, error_send, busy);
                $finish;
            end
        end
    end
endmodule
