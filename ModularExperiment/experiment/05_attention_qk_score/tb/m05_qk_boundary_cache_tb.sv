`timescale 1ns / 1ps

module m05_qk_boundary_cache_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 1,
    parameter string DATA_DIR = "data_boundary"
);
    localparam integer ROWS = 72;
    localparam integer QUERY_GROUPS = ROWS*4;
    localparam integer SCORES = 4236;
    localparam integer KEY_GROUPS = SCORES*4;
    localparam integer TB_QUERY = 0;
    localparam integer TB_KEY = 1;
    localparam integer TB_START = 2;
    localparam integer TB_OUTPUT = 3;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg out_ready = 1'b0;
    integer tb_state = TB_QUERY;
    integer cycle = 0;
    integer row_index = 0;
    integer query_in_row = 0;
    integer key_group_in_row = 0;
    integer output_in_row = 0;
    integer key_group_base = 0;
    integer score_base = 0;
    integer rows_started = 0;
    integer mismatches = 0;
    integer first_input_cycle = -1;
    integer first_output_cycle = -1;
    integer previous_load_cycle = -1;
    integer load_ii_min = 999999;
    integer load_ii_max = 0;
    integer interval;
    integer output_stall_cycles = 0;
    integer stability_checks = 0;
    reg stalled_last_cycle = 1'b0;
    reg signed [19:0] stalled_score;
    reg stalled_mask;
    reg [6:0] stalled_index;
    reg stalled_last;

    reg [7:0] row_key_count_mem [0:ROWS-1];
    reg [767:0] query_s24_mem [0:QUERY_GROUPS-1];
    reg [383:0] key_s12_mem [0:KEY_GROUPS-1];
    reg [15:0] key_meta_mem [0:KEY_GROUPS-1];
    reg [15:0] key_scale16_mem [0:KEY_GROUPS-1];
    reg [31:0] key_scale32_mem [0:KEY_GROUPS-1];
    reg mask_mem [0:SCORES-1];
    reg [19:0] expected_sc_mem [0:SCORES-1];
    reg [19:0] expected_fp16_mem [0:SCORES-1];
    reg [19:0] expected_fp32_mem [0:SCORES-1];
    reg [31:0] expected_clip_sc [0:0];
    reg [31:0] expected_clip_fp16 [0:0];
    reg [31:0] expected_clip_fp32 [0:0];

    wire [7:0] row_key_count = row_key_count_mem[
        row_index < ROWS ? row_index : ROWS-1];
    wire [31:0] row_key_groups = row_key_count*4;
    wire query_load_valid = rst_n && tb_state == TB_QUERY;
    wire query_load_ready;
    wire [1:0] query_load_group = query_in_row[1:0];
    wire [767:0] query_load_s24 = query_s24_mem[
        (row_index < ROWS ? row_index : ROWS-1)*4 + query_in_row];
    wire key_load_valid = rst_n && tb_state == TB_KEY;
    wire key_load_ready;
    wire [6:0] key_load_index = key_group_in_row[8:2];
    wire [1:0] key_load_group = key_group_in_row[1:0];
    wire [31:0] bounded_key_record = key_group_base+key_group_in_row <
        KEY_GROUPS ? key_group_base+key_group_in_row : KEY_GROUPS-1;
    wire [383:0] key_load_s12 = key_s12_mem[bounded_key_record];
    wire [15:0] key_load_meta16 = key_meta_mem[bounded_key_record];
    wire [15:0] key_load_scale16 = key_scale16_mem[bounded_key_record];
    wire [31:0] key_load_scale32 = key_scale32_mem[bounded_key_record];
    wire key_load_mask = mask_mem[score_base+key_load_index];
    wire key_load_last = key_group_in_row+1 == row_key_groups;
    wire start_valid = rst_n && tb_state == TB_START;
    wire start_ready;
    wire out_valid;
    wire signed [19:0] out_score_q14_s20;
    wire out_mask;
    wire [6:0] out_key_index;
    wire out_last_key;
    wire [31:0] input_group_count;
    wire [31:0] output_score_count;
    wire [31:0] clip_count;
    wire [31:0] query_cache_write_count;
    wire [31:0] key_cache_write_count;
    wire frontend_idle;
    wire error;
    wire query_load_fire = query_load_valid && query_load_ready;
    wire key_load_fire = key_load_valid && key_load_ready;
    wire output_fire = out_valid && out_ready;

    function automatic signed [19:0] expected_score;
        input integer index;
        begin
            case (CASE_ID)
                0: expected_score = expected_sc_mem[index];
                1: expected_score = expected_fp16_mem[index];
                default: expected_score = expected_fp32_mem[index];
            endcase
        end
    endfunction

    function automatic [31:0] expected_clip_count;
        begin
            case (CASE_ID)
                0: expected_clip_count = expected_clip_sc[0];
                1: expected_clip_count = expected_clip_fp16[0];
                default: expected_clip_count = expected_clip_fp32[0];
            endcase
        end
    endfunction

    generate
        if (CASE_ID == 0) begin : g_sc
            assign frontend_idle = 1'b1;
            m05_sc_qk_boundary_cache dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(query_load_group),
                .query_load_s24(query_load_s24),
                .key_load_valid(key_load_valid),
                .key_load_ready(key_load_ready),
                .key_load_index(key_load_index),
                .key_load_group(key_load_group),
                .key_load_s12(key_load_s12),
                .key_load_meta16(key_load_meta16),
                .key_load_mask(key_load_mask),
                .key_load_last(key_load_last),
                .start_valid(start_valid), .start_ready(start_ready),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_score_q14_s20(out_score_q14_s20),
                .out_mask(out_mask), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count),
                .query_cache_write_count(query_cache_write_count),
                .key_cache_write_count(key_cache_write_count), .error(error));
        end else if (CASE_ID == 1) begin : g_fp16
            m05_fp16_qk_boundary_cache dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(query_load_group),
                .query_load_s24(query_load_s24),
                .key_load_valid(key_load_valid),
                .key_load_ready(key_load_ready),
                .key_load_index(key_load_index),
                .key_load_group(key_load_group),
                .key_load_s12(key_load_s12),
                .key_load_scale_fp(key_load_scale16),
                .key_load_mask(key_load_mask),
                .key_load_last(key_load_last),
                .start_valid(start_valid), .start_ready(start_ready),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_score_q14_s20(out_score_q14_s20),
                .out_mask(out_mask), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count),
                .query_cache_write_count(query_cache_write_count),
                .key_cache_write_count(key_cache_write_count),
                .frontend_idle(frontend_idle), .error(error));
        end else begin : g_fp32
            m05_fp32_qk_boundary_cache dut (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(query_load_group),
                .query_load_s24(query_load_s24),
                .key_load_valid(key_load_valid),
                .key_load_ready(key_load_ready),
                .key_load_index(key_load_index),
                .key_load_group(key_load_group),
                .key_load_s12(key_load_s12),
                .key_load_scale_fp(key_load_scale32),
                .key_load_mask(key_load_mask),
                .key_load_last(key_load_last),
                .start_valid(start_valid), .start_ready(start_ready),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_score_q14_s20(out_score_q14_s20),
                .out_mask(out_mask), .out_key_index(out_key_index),
                .out_last_key(out_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count),
                .query_cache_write_count(query_cache_write_count),
                .key_cache_write_count(key_cache_write_count),
                .frontend_idle(frontend_idle), .error(error));
        end
    endgenerate

    initial begin
        $readmemh({DATA_DIR,"/row_key_count_u8.mem"}, row_key_count_mem);
        $readmemh({DATA_DIR,"/query_group_s24.mem"}, query_s24_mem);
        $readmemh({DATA_DIR,"/key_group_s12.mem"}, key_s12_mem);
        $readmemh({DATA_DIR,"/key_meta_sc_u16.mem"}, key_meta_mem);
        $readmemh({DATA_DIR,"/key_scale_fp16.mem"}, key_scale16_mem);
        $readmemh({DATA_DIR,"/key_scale_fp32.mem"}, key_scale32_mem);
        $readmemh({DATA_DIR,"/mask.mem"}, mask_mem);
        $readmemh({DATA_DIR,"/expected_sc.mem"}, expected_sc_mem);
        $readmemh({DATA_DIR,"/expected_fp16.mem"}, expected_fp16_mem);
        $readmemh({DATA_DIR,"/expected_fp32.mem"}, expected_fp32_mem);
        $readmemh({DATA_DIR,"/clip_count_sc.mem"}, expected_clip_sc);
        $readmemh({DATA_DIR,"/clip_count_fp16.mem"}, expected_clip_fp16);
        $readmemh({DATA_DIR,"/clip_count_fp32.mem"}, expected_clip_fp32);
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n)
            out_ready <= 1'b0;
        else if (BACKPRESSURE == 0)
            out_ready <= 1'b1;
        else if (BACKPRESSURE == 1)
            out_ready <= !((cycle % 37) >= 25 && (cycle % 37) <= 30);
        else
            out_ready <= !((cycle * 17 + 5) % 43 < 9);
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            tb_state <= TB_QUERY;
            cycle <= 0;
            row_index <= 0;
            query_in_row <= 0;
            key_group_in_row <= 0;
            output_in_row <= 0;
            key_group_base <= 0;
            score_base <= 0;
            rows_started <= 0;
            mismatches <= 0;
            first_input_cycle <= -1;
            first_output_cycle <= -1;
            previous_load_cycle <= -1;
            load_ii_min <= 999999;
            load_ii_max <= 0;
            output_stall_cycles <= 0;
            stability_checks <= 0;
            stalled_last_cycle <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            if (error) begin
                $display("FAIL: M05 boundary cache sticky error case=%0d cycle=%0d row=%0d q=%0d k=%0d out=%0d",
                    CASE_ID, cycle, row_index, query_in_row,
                    key_group_in_row, output_in_row);
                $finish;
            end

            if (query_load_fire || key_load_fire) begin
                if (first_input_cycle < 0)
                    first_input_cycle <= cycle;
                if (previous_load_cycle >= 0) begin
                    interval = cycle-previous_load_cycle;
                    if (interval < load_ii_min)
                        load_ii_min <= interval;
                    if (interval > load_ii_max)
                        load_ii_max <= interval;
                end
                previous_load_cycle <= cycle;
            end

            if (query_load_fire) begin
                query_in_row <= query_in_row + 1;
                if (query_in_row + 1 == 4) begin
                    query_in_row <= 0;
                    key_group_in_row <= 0;
                    previous_load_cycle <= -1;
                    tb_state <= TB_KEY;
                end
            end
            if (key_load_fire) begin
                key_group_in_row <= key_group_in_row + 1;
                if (key_group_in_row + 1 == row_key_groups) begin
                    previous_load_cycle <= -1;
                    tb_state <= TB_START;
                end
            end
            if (start_valid && start_ready) begin
                rows_started <= rows_started + 1;
                output_in_row <= 0;
                tb_state <= TB_OUTPUT;
            end

            if (stalled_last_cycle) begin
                stability_checks <= stability_checks + 1;
                if (!out_valid || out_score_q14_s20 !== stalled_score ||
                    out_mask !== stalled_mask ||
                    out_key_index !== stalled_index ||
                    out_last_key !== stalled_last) begin
                    $display("FAIL: M05 boundary output changed under backpressure case=%0d cycle=%0d",
                        CASE_ID, cycle);
                    $finish;
                end
            end
            stalled_last_cycle <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                stalled_score <= out_score_q14_s20;
                stalled_mask <= out_mask;
                stalled_index <= out_key_index;
                stalled_last <= out_last_key;
                output_stall_cycles <= output_stall_cycles + 1;
            end

            if (output_fire) begin
                if (first_output_cycle < 0)
                    first_output_cycle <= cycle;
                if (out_score_q14_s20 !==
                        expected_score(score_base+output_in_row) ||
                    out_mask !== mask_mem[score_base+output_in_row] ||
                    out_key_index !== output_in_row[6:0] ||
                    out_last_key !== (output_in_row+1 == row_key_count)) begin
                    mismatches <= mismatches + 1;
                    $display("M05_BOUNDARY_MISMATCH case=%0d row=%0d key=%0d actual=%05x expected=%05x mask=%0d/%0d index=%0d last=%0d",
                        CASE_ID, row_index, output_in_row,
                        out_score_q14_s20,
                        expected_score(score_base+output_in_row),
                        out_mask, mask_mem[score_base+output_in_row],
                        out_key_index, out_last_key);
                end
                output_in_row <= output_in_row + 1;
                if (output_in_row + 1 == row_key_count) begin
                    if (!out_last_key)
                        mismatches <= mismatches + 1;
                    if (row_index + 1 == ROWS) begin
                        if (mismatches == 0 &&
                            out_score_q14_s20 ===
                                expected_score(score_base+output_in_row) &&
                            out_mask === mask_mem[score_base+output_in_row] &&
                            out_key_index === output_in_row[6:0] &&
                            out_last_key === 1'b1 &&
                            input_group_count == KEY_GROUPS &&
                            output_score_count + 1 == SCORES &&
                            query_cache_write_count == QUERY_GROUPS &&
                            key_cache_write_count == KEY_GROUPS &&
                            rows_started == ROWS &&
                            clip_count == expected_clip_count() &&
                            load_ii_min == 2 && load_ii_max == 2) begin
                            $display("M05_BOUNDARY_METRIC_JSON: {\"case_id\":%0d,\"rows\":72,\"scores\":4236,\"key_groups\":16944,\"query_groups\":288,\"mismatches\":0,\"load_ii_min\":%0d,\"load_ii_max\":%0d,\"first_output_latency\":%0d,\"total_cycles\":%0d,\"output_stall_cycles\":%0d,\"stability_checks\":%0d,\"clip_count\":%0d}",
                                CASE_ID, load_ii_min, load_ii_max,
                                first_output_cycle-first_input_cycle,
                                cycle-first_input_cycle+1,
                                output_stall_cycles, stability_checks,
                                clip_count);
                            $display("PASS: M05 QK boundary cache full workload case=%0d backpressure=%0d",
                                CASE_ID, BACKPRESSURE);
                        end else begin
                            $display("FAIL: M05 boundary final gate case=%0d mismatch=%0d groups=%0d/%0d scores=%0d/%0d qcache=%0d kcache=%0d rows=%0d clip=%0d/%0d ii=%0d/%0d",
                                CASE_ID, mismatches, input_group_count,
                                KEY_GROUPS, output_score_count+1, SCORES,
                                query_cache_write_count,
                                key_cache_write_count, rows_started,
                                clip_count, expected_clip_count(),
                                load_ii_min, load_ii_max);
                        end
                        $finish;
                    end else begin
                        key_group_base <= key_group_base + row_key_groups;
                        score_base <= score_base + row_key_count;
                        row_index <= row_index + 1;
                        query_in_row <= 0;
                        key_group_in_row <= 0;
                        output_in_row <= 0;
                        previous_load_cycle <= -1;
                        tb_state <= TB_QUERY;
                    end
                end
            end
            if (cycle > 2000000) begin
                $display("FAIL: M05 boundary timeout case=%0d row=%0d groups=%0d scores=%0d",
                    CASE_ID, row_index, input_group_count,
                    output_score_count);
                $finish;
            end
        end
    end

    initial begin
        if (CASE_ID < 0 || CASE_ID > 2)
            $error("M05 boundary CASE_ID must be 0, 1, or 2");
        if (BACKPRESSURE < 0 || BACKPRESSURE > 2)
            $error("M05 boundary BACKPRESSURE must be 0, 1, or 2");
    end
endmodule
