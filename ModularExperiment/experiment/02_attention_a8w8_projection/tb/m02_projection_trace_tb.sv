`timescale 1ns / 1ps

module m02_projection_trace_tb #(
    parameter integer CASE_ID = 0,
    parameter integer BACKPRESSURE = 0,
    parameter integer TILES = 18,
    parameter string DATA_DIR = "data_trace"
);
    localparam integer GROUPS = 128;
    localparam integer TRANSACTIONS = TILES * GROUPS;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg out_ready = 1'b0;
    integer cycle = 0;
    integer sent = 0;
    integer tile_accept_count = 0;
    integer tile_output_count = 0;
    integer mismatch_count = 0;
    integer wait_input_cycles = 0;
    integer wait_output_cycles = 0;
    integer first_accept_cycle = -1;
    integer last_output_cycle = -1;
    integer previous_accept_cycle = -1;
    integer input_ii_min = 999999;
    integer input_ii_max = 0;
    integer interval;
    integer lane;
    integer drain_cycles = 0;

    reg [2047:0] act_mem [0:TRANSACTIONS-1];
    reg [4095:0] weight_mem [0:TRANSACTIONS-1];
    reg [63:0] zp_mem [0:TRANSACTIONS-1];
    reg [383:0] meta16_mem [0:TRANSACTIONS-1];
    reg [767:0] meta32_mem [0:TRANSACTIONS-1];
    reg [3071:0] expected_mem [0:TILES-1];
    wire [31:0] bounded_input_index =
        (sent < TRANSACTIONS) ? sent : 0;
    wire in_valid = rst_n && !clear && drain_cycles == 0 &&
        sent < TRANSACTIONS;
    wire in_ready;
    wire out_valid;
    wire [3071:0] out_s24;
    wire [31:0] accepted_groups;
    wire [31:0] accumulated_groups;
    wire [31:0] output_tiles;
    wire [31:0] saturations;
    wire error;

    always #5 clk = ~clk;

    m4_matched_tile #(.CASE_ID(CASE_ID)) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_act_u8(act_mem[bounded_input_index]),
        .in_wgt_s8(weight_mem[bounded_input_index]),
        .in_zp_rows(zp_mem[bounded_input_index]),
        .in_meta16(meta16_mem[bounded_input_index]),
        .in_meta32(meta32_mem[bounded_input_index]),
        .out_valid(out_valid), .out_ready(out_ready), .out_s24(out_s24),
        .accepted_group_count(accepted_groups),
        .accumulated_group_count(accumulated_groups),
        .output_tile_count(output_tiles), .saturation_count(saturations),
        .error(error));

    initial begin
        $readmemh({DATA_DIR,"/act_u8.mem"}, act_mem);
        $readmemh({DATA_DIR,"/weight_s8.mem"}, weight_mem);
        $readmemh({DATA_DIR,"/zp_rows.mem"}, zp_mem);
        if (CASE_ID == 1)
            $readmemh({DATA_DIR,"/scalecode_meta.mem"}, meta16_mem);
        else if (CASE_ID == 2)
            $readmemh({DATA_DIR,"/fp16_meta.mem"}, meta16_mem);
        else
            meta16_mem = '{default:'0};
        if (CASE_ID == 3)
            $readmemh({DATA_DIR,"/fp32_meta.mem"}, meta32_mem);
        else
            meta32_mem = '{default:'0};
        if (CASE_ID == 1)
            $readmemh({DATA_DIR,"/expected_scalecode_s24.mem"}, expected_mem);
        else if (CASE_ID == 2)
            $readmemh({DATA_DIR,"/expected_fp16_s24.mem"}, expected_mem);
        else if (CASE_ID == 3)
            $readmemh({DATA_DIR,"/expected_fp32_s24.mem"}, expected_mem);
        else begin
            $display("FAIL: M02 trace does not define a MAC-only case");
            $fatal(1);
        end
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
    end

    always @(negedge clk) begin
        if (!rst_n)
            out_ready <= 1'b0;
        else if (BACKPRESSURE == 0)
            out_ready <= 1'b1;
        else
            out_ready <= !((cycle % 37) >= 27 && (cycle % 37) <= 31);
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
        end else begin
            cycle <= cycle + 1;
            if (clear) begin
                clear <= 1'b0;
            end else if (drain_cycles > 0) begin
                drain_cycles <= drain_cycles - 1;
                if (drain_cycles == 1) begin
                    if (tile_output_count == TILES) begin
                        if (mismatch_count == 0 && sent == TRANSACTIONS &&
                                input_ii_min == 2 && input_ii_max == 2) begin
                            $display("M02_TRACE_METRIC_JSON: {\"case_id\":%0d,\"backpressure\":%0d,\"tiles\":%0d,\"groups\":%0d,\"lanes_per_tile\":128,\"mismatches\":0,\"input_ii_min\":%0d,\"input_ii_max\":%0d,\"first_input_to_last_output_cycles\":%0d,\"wait_input_cycles\":%0d,\"wait_output_cycles\":%0d}",
                                CASE_ID, BACKPRESSURE, TILES, TRANSACTIONS,
                                input_ii_min, input_ii_max,
                                last_output_cycle-first_accept_cycle+1,
                                wait_input_cycles, wait_output_cycles);
                            $display("PASS: M02 real projection trace");
                            $finish;
                        end
                        $display("FAIL: M02 trace final case=%0d sent=%0d tiles=%0d mismatch=%0d ii=%0d/%0d",
                            CASE_ID, sent, tile_output_count, mismatch_count,
                            input_ii_min, input_ii_max);
                        $fatal(1);
                    end else begin
                        clear <= 1'b1;
                    end
                end
            end

            if (in_valid && in_ready) begin
                if (first_accept_cycle < 0)
                    first_accept_cycle = cycle;
                if (previous_accept_cycle >= 0) begin
                    interval = cycle - previous_accept_cycle;
                    if (interval < input_ii_min)
                        input_ii_min = interval;
                    if (interval > input_ii_max)
                        input_ii_max = interval;
                end
                previous_accept_cycle = cycle;
                tile_accept_count = tile_accept_count + 1;
                sent <= sent + 1;
            end else if (in_valid) begin
                wait_input_cycles = wait_input_cycles + 1;
            end
            if (out_valid && !out_ready)
                wait_output_cycles = wait_output_cycles + 1;

            if (error) begin
                $display("FAIL: M02 trace DUT error case=%0d cycle=%0d sent=%0d tile=%0d accepted=%0d accumulated=%0d",
                    CASE_ID, cycle, sent, tile_output_count,
                    accepted_groups, accumulated_groups);
                $fatal(1);
            end

            if (out_valid && out_ready) begin
                if (tile_accept_count != GROUPS || accepted_groups != GROUPS ||
                        accumulated_groups != GROUPS || output_tiles != 0) begin
                    $display("FAIL: M02 trace counters case=%0d tile=%0d local=%0d accepted=%0d accumulated=%0d outputs=%0d",
                        CASE_ID, tile_output_count, tile_accept_count,
                        accepted_groups, accumulated_groups, output_tiles);
                    $fatal(1);
                end
                if (out_s24 !== expected_mem[tile_output_count]) begin
                    mismatch_count = mismatch_count + 1;
                    $display("M02_TRACE_TILE_MISMATCH case=%0d tile=%0d",
                        CASE_ID, tile_output_count);
                    for (lane = 0; lane < 128; lane = lane + 1)
                        if (out_s24[lane*24 +: 24] !==
                                expected_mem[tile_output_count][lane*24 +: 24])
                            $display("M02_TRACE_LANE_MISMATCH case=%0d tile=%0d lane=%0d expected=%h got=%h",
                                CASE_ID, tile_output_count, lane,
                                expected_mem[tile_output_count][lane*24 +: 24],
                                out_s24[lane*24 +: 24]);
                end
                tile_output_count = tile_output_count + 1;
                tile_accept_count = 0;
                previous_accept_cycle = -1;
                last_output_cycle = cycle;
                // Keep the tile alive long enough for the pipelined overflow
                // diagnostic to surface before clear resets the sticky error.
                drain_cycles <= 8;
            end

            if (cycle > 200000) begin
                $display("FAIL: M02 trace timeout case=%0d sent=%0d tiles=%0d",
                    CASE_ID, sent, tile_output_count);
                $fatal(1);
            end
        end
    end
endmodule
