`timescale 1ns / 1ps

module hap_softmax_row_128_tb;
    localparam integer ROW_COUNT = 32;
    localparam integer KEY_COUNT = 128;
    localparam integer VALUE_COUNT = ROW_COUNT * KEY_COUNT;
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
    reg [20:0] input_mem [0:VALUE_COUNT-1];
    reg [15:0] expected_mem [0:VALUE_COUNT-1];
    integer cycle = 0;
    integer send_index = 0;
    integer receive_index = 0;
    integer mismatch_count = 0;
    integer last_row_cycle = 0;
    integer max_row_cycles = 0;
    integer error_send = 0;
    reg error_phase = 1'b0;
    reg [23:0] held_output = '0;
    reg was_stalled = 1'b0;

    always #3.3335 clk = ~clk;
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
        $readmemh("data/softmax_row_128/input.mem", input_mem);
        $readmemh("data/softmax_row_128/expected_prob.mem", expected_mem);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            out_ready <= !(((cycle % 37) >= 27) && ((cycle % 37) <= 31));
            if (!error_phase && (send_index < VALUE_COUNT)) begin
                in_score <= input_mem[send_index][19:0];
                in_mask <= input_mem[send_index][20];
                in_first_key <= ((send_index % KEY_COUNT) == 0);
                in_last_key <= ((send_index % KEY_COUNT) == KEY_COUNT-1);
                in_valid <= ((cycle % 19) != 7);
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
            last_row_cycle <= 0;
            max_row_cycles <= 0;
            error_send <= 0;
            error_phase <= 1'b0;
            was_stalled <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (was_stalled && (!out_valid ||
                ({out_last_key, out_key_index, out_prob} !== held_output))) begin
                $display("FAIL: Softmax row output changed under backpressure cycle=%0d", cycle);
                $finish;
            end
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready)
                held_output <= {out_last_key, out_key_index, out_prob};
            if (in_valid && in_ready) begin
                if (error_phase)
                    error_send <= error_send + 1;
                else
                    send_index <= send_index + 1;
            end
            if (out_valid && out_ready) begin
                if (out_key_index != (receive_index % KEY_COUNT) ||
                    out_last_key != ((receive_index % KEY_COUNT) == KEY_COUNT-1) ||
                    out_prob !== expected_mem[receive_index]) begin
                    mismatch_count <= mismatch_count + 1;
                    $display("MISMATCH row=%0d key=%0d expected=%h got=%h out_index=%0d last=%0d",
                        receive_index / KEY_COUNT, receive_index % KEY_COUNT,
                        expected_mem[receive_index], out_prob,
                        out_key_index, out_last_key);
                end
                receive_index <= receive_index + 1;
                if (out_last_key) begin
                    if ((cycle - last_row_cycle) > max_row_cycles)
                        max_row_cycles <= cycle - last_row_cycle;
                    last_row_cycle <= cycle;
                end
                if (receive_index == VALUE_COUNT-1)
                    error_phase <= 1'b1;
            end
            if (error && !error_phase) begin
                $display("FAIL: Softmax row sticky error before directed all-masked test cycle=%0d", cycle);
                $finish;
            end
            if (error_phase && error) begin
                if ((mismatch_count != 0) ||
                    (input_score_count != VALUE_COUNT + KEY_COUNT) ||
                    (output_prob_count != VALUE_COUNT) ||
                    (row_count != ROW_COUNT)) begin
                    $display("FAIL: Softmax row final mismatch=%0d in=%0d out=%0d rows=%0d",
                        mismatch_count, input_score_count, output_prob_count, row_count);
                end else begin
                    $display("SOFTMAX_ROW_128_METRIC_JSON: {\"rows\":32,\"keys_per_row\":128,\"mismatches\":0,\"max_row_cycles\":%0d,\"all_masked_error\":1,\"cycles\":%0d}",
                        max_row_cycles, cycle);
                    $display("PASS: Softmax row128 matched FixBit v2 golden and rejected all-masked row.");
                end
                $finish;
            end
            if (cycle > 30000) begin
                $display("FAIL: Softmax row timeout send=%0d recv=%0d error_send=%0d state_busy=%0d",
                    send_index, receive_index, error_send, busy);
                $finish;
            end
        end
    end
endmodule
