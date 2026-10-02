`timescale 1ns/1ps

module m5_qk_matched_tb;
    parameter integer CASE_ID = 0;
    parameter integer BACKPRESSURE = 0;
    parameter DATA_DIR = "data";

    localparam integer ROWS = 6;
    localparam integer TOTAL_SCORES = 353;
    localparam integer TOTAL_GROUPS = 1412;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg query_load_valid = 1'b0;
    reg [1:0] query_load_group = 2'd0;
    reg [767:0] query_group_fixed = 768'd0;
    reg [511:0] query_group_fp16 = 512'd0;
    reg [1023:0] query_group_fp32 = 1024'd0;
    reg in_valid = 1'b0;
    reg in_first_key = 1'b0;
    reg in_last_key = 1'b0;
    reg [1:0] in_group = 2'd0;
    reg in_mask = 1'b0;
    reg [383:0] key_group_fixed = 384'd0;
    reg [15:0] key_meta_fixed = 16'd0;
    reg [511:0] key_group_fp16 = 512'd0;
    reg [1023:0] key_group_fp32 = 1024'd0;
    reg out_ready = 1'b0;

    wire query_load_ready;
    wire query_ready;
    wire in_ready;
    wire out_valid;
    wire signed [19:0] out_score_q14_s20;
    wire out_mask;
    wire [6:0] out_key_index;
    wire out_last_key;
    wire [31:0] input_group_count;
    wire [31:0] output_score_count;
    wire [31:0] clip_count;
    wire error;

    reg [767:0] query_fixed_mem [0:ROWS*4-1];
    reg [511:0] query_fp16_mem [0:ROWS*4-1];
    reg [1023:0] query_fp32_mem [0:ROWS*4-1];
    reg [383:0] key_fixed_mem [0:TOTAL_GROUPS-1];
    reg [15:0] key_meta_mem [0:TOTAL_GROUPS-1];
    reg [511:0] key_fp16_mem [0:TOTAL_GROUPS-1];
    reg [1023:0] key_fp32_mem [0:TOTAL_GROUPS-1];
    reg [19:0] expected_sc_mem [0:TOTAL_SCORES-1];
    reg [19:0] expected_fp16_mem [0:TOTAL_SCORES-1];
    reg [19:0] expected_fp32_mem [0:TOTAL_SCORES-1];
    reg mask_mem [0:TOTAL_SCORES-1];
    reg [31:0] clip_sc_mem [0:0];
    reg [31:0] clip_fp16_mem [0:0];
    reg [31:0] clip_fp32_mem [0:0];

    integer shape [0:ROWS-1];
    integer cycle = 0;
    integer row = 0;
    integer query_sent = 0;
    integer row_group_sent = 0;
    integer total_group_sent = 0;
    integer row_score_received = 0;
    integer total_score_received = 0;
    integer mismatch_count = 0;
    integer input_stall_cycles = 0;
    integer output_stall_cycles = 0;
    integer first_query_cycle = -1;
    integer row_query_start_cycle = -1;
    integer row_key_start_cycle = -1;
    integer row_last_input_cycle = -1;
    integer row_first_output_cycle = -1;
    integer row_last_input_fire_cycle = -1;
    integer row_last_output_fire_cycle = -1;
    integer input_ii_min = 1000000;
    integer input_ii_max = 0;
    integer output_ii_min = 1000000;
    integer output_ii_max = 0;
    integer delta;
    integer expected_clip_count;
    integer done_pending = 0;
    integer watchdog_cycles = 20000;

    generate
        if (CASE_ID == 0) begin : g_sc
            hap_qk_score_row_128 dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(query_load_group),
                .query_load_s24(query_group_fixed), .query_ready(query_ready),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(in_first_key), .in_last_key(in_last_key),
                .in_group(in_group), .in_mask(in_mask),
                .in_key_s12(key_group_fixed),
                .in_key_meta16(key_meta_fixed), .out_valid(out_valid),
                .out_ready(out_ready), .out_score_q14_s20(out_score_q14_s20),
                .out_mask(out_mask), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count), .error(error)
            );
        end else if (CASE_ID == 1) begin : g_fp16
            m5_fp16_qk_top dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(query_load_group),
                .query_group_fp(query_group_fp16), .query_ready(query_ready),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(in_first_key), .in_last_key(in_last_key),
                .in_group(in_group), .in_mask(in_mask),
                .key_group_fp(key_group_fp16), .out_valid(out_valid),
                .out_ready(out_ready), .out_score_q14_s20(out_score_q14_s20),
                .out_mask(out_mask), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count), .error(error)
            );
        end else begin : g_fp32
            m5_fp32_qk_top dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(query_load_group),
                .query_group_fp(query_group_fp32), .query_ready(query_ready),
                .in_valid(in_valid), .in_ready(in_ready),
                .in_first_key(in_first_key), .in_last_key(in_last_key),
                .in_group(in_group), .in_mask(in_mask),
                .key_group_fp(key_group_fp32), .out_valid(out_valid),
                .out_ready(out_ready), .out_score_q14_s20(out_score_q14_s20),
                .out_mask(out_mask), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count), .error(error)
            );
        end
    endgenerate

    always #5 clk = ~clk;

    initial begin
        shape[0] = 128;
        shape[1] = 112;
        shape[2] = 64;
        shape[3] = 32;
        shape[4] = 16;
        shape[5] = 1;
        $readmemh({DATA_DIR, "/query_group_fixed.mem"}, query_fixed_mem);
        $readmemh({DATA_DIR, "/query_group_fp16.mem"}, query_fp16_mem);
        $readmemh({DATA_DIR, "/query_group_fp32.mem"}, query_fp32_mem);
        $readmemh({DATA_DIR, "/key_group_fixed.mem"}, key_fixed_mem);
        $readmemh({DATA_DIR, "/key_meta_fixed.mem"}, key_meta_mem);
        $readmemh({DATA_DIR, "/key_group_fp16.mem"}, key_fp16_mem);
        $readmemh({DATA_DIR, "/key_group_fp32.mem"}, key_fp32_mem);
        $readmemh({DATA_DIR, "/expected_sc.mem"}, expected_sc_mem);
        $readmemh({DATA_DIR, "/expected_fp16.mem"}, expected_fp16_mem);
        $readmemh({DATA_DIR, "/expected_fp32.mem"}, expected_fp32_mem);
        $readmemh({DATA_DIR, "/mask.mem"}, mask_mem);
        $readmemh({DATA_DIR, "/clip_count_sc.mem"}, clip_sc_mem);
        $readmemh({DATA_DIR, "/clip_count_fp16.mem"}, clip_fp16_mem);
        $readmemh({DATA_DIR, "/clip_count_fp32.mem"}, clip_fp32_mem);
        expected_clip_count = CASE_ID == 0 ? clip_sc_mem[0] :
            (CASE_ID == 1 ? clip_fp16_mem[0] : clip_fp32_mem[0]);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            query_load_valid <= 1'b0;
            in_valid <= 1'b0;
            out_ready <= 1'b0;
        end else begin
            out_ready <= (BACKPRESSURE == 0) ||
                !((cycle % 37 >= 25) && (cycle % 37 <= 30));
            query_load_valid <= 1'b0;
            in_valid <= 1'b0;
            if (!done_pending && row < ROWS) begin
                if (query_sent < 4) begin
                    query_load_valid <= 1'b1;
                    query_load_group <= query_sent[1:0];
                    query_group_fixed <= query_fixed_mem[row*4 + query_sent];
                    query_group_fp16 <= query_fp16_mem[row*4 + query_sent];
                    query_group_fp32 <= query_fp32_mem[row*4 + query_sent];
                end else if (row_group_sent < shape[row]*4) begin
                    in_valid <= 1'b1;
                    in_group <= row_group_sent[1:0];
                    in_first_key <= row_group_sent == 0;
                    in_last_key <= (row_group_sent == shape[row]*4-1);
                    in_mask <= mask_mem[total_score_received +
                        (row_group_sent >> 2) - row_score_received];
                    key_group_fixed <= key_fixed_mem[total_group_sent];
                    key_meta_fixed <= key_meta_mem[total_group_sent];
                    key_group_fp16 <= key_fp16_mem[total_group_sent];
                    key_group_fp32 <= key_fp32_mem[total_group_sent];
                end
            end
        end
    end

    always @(posedge clk) begin
        if (rst_n) begin
            cycle = cycle + 1;
            if (query_load_valid && query_load_ready) begin
                if (query_sent == 0) begin
                    row_query_start_cycle = cycle;
                    if (first_query_cycle < 0)
                        first_query_cycle = cycle;
                end
                query_sent = query_sent + 1;
            end
            if (in_valid && !in_ready)
                input_stall_cycles = input_stall_cycles + 1;
            if (out_valid && !out_ready)
                output_stall_cycles = output_stall_cycles + 1;
            if (in_valid && in_ready) begin
                if (row_group_sent == 0) begin
                    row_key_start_cycle = cycle;
                    row_last_input_fire_cycle = cycle;
                end else begin
                    delta = cycle - row_last_input_fire_cycle;
                    if (delta < input_ii_min)
                        input_ii_min = delta;
                    if (delta > input_ii_max)
                        input_ii_max = delta;
                    row_last_input_fire_cycle = cycle;
                end
                if (row_group_sent == shape[row]*4-1)
                    row_last_input_cycle = cycle;
                row_group_sent = row_group_sent + 1;
                total_group_sent = total_group_sent + 1;
            end
            if (error) begin
                $display("FAIL: M5 DUT error case=%0d bp=%0d row=%0d q=%0d group=%0d score=%0d",
                    CASE_ID, BACKPRESSURE, row, query_sent,
                    total_group_sent, total_score_received);
                $finish;
            end
            if (out_valid && out_ready) begin
                if (row_score_received == 0)
                    row_first_output_cycle = cycle;
                else begin
                    delta = cycle - row_last_output_fire_cycle;
                    if (delta < output_ii_min)
                        output_ii_min = delta;
                    if (delta > output_ii_max)
                        output_ii_max = delta;
                end
                row_last_output_fire_cycle = cycle;
                if ((out_score_q14_s20 !==
                        (CASE_ID == 0 ? expected_sc_mem[total_score_received] :
                         (CASE_ID == 1 ? expected_fp16_mem[total_score_received] :
                                         expected_fp32_mem[total_score_received]))) ||
                        (out_mask !== mask_mem[total_score_received]) ||
                        (out_key_index !== row_score_received[6:0]) ||
                        (out_last_key !== (row_score_received == shape[row]-1))) begin
                    if (mismatch_count < 12)
                        $display("M5_QK_MISMATCH case=%0d bp=%0d row=%0d key=%0d expected=%h got=%h mask=%0d/%0d index=%0d last=%0d",
                            CASE_ID, BACKPRESSURE, row, row_score_received,
                            CASE_ID == 0 ? expected_sc_mem[total_score_received] :
                            (CASE_ID == 1 ? expected_fp16_mem[total_score_received] :
                                            expected_fp32_mem[total_score_received]),
                            out_score_q14_s20, mask_mem[total_score_received],
                            out_mask, out_key_index, out_last_key);
                    mismatch_count = mismatch_count + 1;
                end
                row_score_received = row_score_received + 1;
                total_score_received = total_score_received + 1;
                if (out_last_key) begin
                    $display("M5_QK_SHAPE_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"n\":%0d,\"scores\":%0d,\"query_to_last_cycles\":%0d,\"key_to_first_cycles\":%0d,\"key_to_last_cycles\":%0d,\"last_input_to_last_output_cycles\":%0d}",
                        CASE_ID, BACKPRESSURE, shape[row], row_score_received,
                        cycle-row_query_start_cycle+1,
                        row_first_output_cycle-row_key_start_cycle,
                        cycle-row_key_start_cycle+1,
                        cycle-row_last_input_cycle);
                    row = row + 1;
                    query_sent = 0;
                    row_group_sent = 0;
                    row_score_received = 0;
                    row_query_start_cycle = -1;
                    row_key_start_cycle = -1;
                    row_last_input_cycle = -1;
                    row_first_output_cycle = -1;
                    row_last_input_fire_cycle = -1;
                    row_last_output_fire_cycle = -1;
                    if (total_score_received == TOTAL_SCORES)
                        done_pending = 1;
                end
            end
            if (done_pending == 1) begin
                done_pending = 2;
            end else if (done_pending == 2) begin
                if ((mismatch_count == 0) &&
                        (total_group_sent == TOTAL_GROUPS) &&
                        (total_score_received == TOTAL_SCORES) &&
                        (input_group_count == TOTAL_GROUPS) &&
                        (output_score_count == TOTAL_SCORES) &&
                        (clip_count == expected_clip_count) &&
                        ((BACKPRESSURE != 0) ||
                         ((input_ii_min == 2) && (input_ii_max == 2) &&
                          (output_ii_min == 8) && (output_ii_max == 8)))) begin
                    $display("M5_QK_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"shapes\":6,\"scores\":%0d,\"groups\":%0d,\"mismatches\":%0d,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"output_ii_min\":%0d,\"output_ii_max\":%0d,\"input_stall_cycles\":%0d,\"output_stall_cycles\":%0d,\"clip_count\":%0d,\"cycles\":%0d}",
                        CASE_ID, BACKPRESSURE, total_score_received,
                        total_group_sent, mismatch_count, input_ii_min,
                        input_ii_max, output_ii_min, output_ii_max,
                        input_stall_cycles, output_stall_cycles, clip_count,
                        cycle-first_query_cycle+1);
                    $display("PASS: M5 matched QK");
                end else begin
                    $display("FAIL: M5 final case=%0d bp=%0d mis=%0d groups=%0d/%0d scores=%0d/%0d dut_groups=%0d dut_scores=%0d clips=%0d/%0d in_ii=%0d/%0d out_ii=%0d/%0d",
                        CASE_ID, BACKPRESSURE, mismatch_count,
                        total_group_sent, TOTAL_GROUPS,
                        total_score_received, TOTAL_SCORES,
                        input_group_count, output_score_count,
                        clip_count, expected_clip_count,
                        input_ii_min, input_ii_max,
                        output_ii_min, output_ii_max);
                end
                $finish;
            end
            if (cycle > watchdog_cycles) begin
                $display("FAIL: M5 timeout case=%0d bp=%0d row=%0d q=%0d row_group=%0d total_group=%0d row_score=%0d total_score=%0d",
                    CASE_ID, BACKPRESSURE, row, query_sent, row_group_sent,
                    total_group_sent, row_score_received, total_score_received);
                $finish;
            end
        end
    end

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("CASE_ID must be 0, 1, or 2");
        if (BACKPRESSURE < 0 || BACKPRESSURE > 1)
            $error("BACKPRESSURE must be 0 or 1");
    end
endmodule
