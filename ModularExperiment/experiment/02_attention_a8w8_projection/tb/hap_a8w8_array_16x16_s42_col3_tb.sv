`timescale 1ns / 1ps

// Functional equivalence and protocol test for the three-column-shard
// Attention projection array.  The production monolithic array is the golden
// reference: both arrays accept exactly the same two 128-group tiles, and
// their complete 16x16 S24 payloads are compared under randomized output
// backpressure.  Directed side probes cover atomic shard capture and the
// clear-after-overflow diagnostic contract.
module hap_a8w8_array_16x16_s42_col3_tb;
    localparam integer GROUPS_PER_TILE = 128;
    localparam integer TILES = 2;
    localparam integer TOTAL_GROUPS = GROUPS_PER_TILE * TILES;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg run_enable = 1'b0;

    reg [8191:0] region_act_u8 = '0;
    reg [1023:0] lane_act_zero_point = '0;
    reg [127:0] row_act_scale_code = '0;
    reg [95:0] row_act_scale_shift = '0;
    reg [4095:0] col_wgt_s8 = '0;
    reg [127:0] col_wgt_scale_code = '0;
    reg [95:0] col_wgt_scale_shift = '0;
    integer send_index = 0;

    wire ref_in_ready;
    wire dut_in_ready;
    wire source_valid = run_enable && (send_index < TOTAL_GROUPS) &&
        ref_in_ready && dut_in_ready;
    wire source_first = (send_index % GROUPS_PER_TILE) == 0;
    wire source_last = (send_index % GROUPS_PER_TILE) ==
        (GROUPS_PER_TILE - 1);
    wire source_fire = source_valid && ref_in_ready && dut_in_ready;

    wire ref_out_valid;
    wire dut_out_valid;
    wire [6143:0] ref_out_s24;
    wire [6143:0] dut_out_s24;
    reg [15:0] ready_lfsr_r = 16'h1ace;
    wire random_ready = ready_lfsr_r[0] ^ ready_lfsr_r[2] ^
        ready_lfsr_r[5];
    wire common_out_ready = random_ready && ref_out_valid && dut_out_valid;
    wire output_fire = common_out_ready && ref_out_valid && dut_out_valid;

    wire [31:0] ref_accepted_count;
    wire [31:0] ref_accumulated_count;
    wire [31:0] ref_output_count;
    wire [31:0] ref_saturation_count;
    wire ref_error;
    wire [31:0] dut_accepted_count;
    wire [31:0] dut_accumulated_count;
    wire [31:0] dut_output_count;
    wire [31:0] dut_saturation_count;
    wire dut_error;

    integer cycle = 0;
    integer receive_index = 0;
    integer capture_events = 0;
    integer launch_events = 0;
    integer commit_events = 0;
    integer output_stall_cycles = 0;
    integer last_capture_cycle = -1000;
    integer max_capture_interval = 0;
    reg final_epoch_r = 1'b0;
    reg ref_was_stalled_r = 1'b0;
    reg dut_was_stalled_r = 1'b0;
    reg [6143:0] ref_held_output_r = '0;
    reg [6143:0] dut_held_output_r = '0;

    // Standalone shard probe for an illegal owner event while !capture_ready.
    // Unlike an external ready/valid port, capture_valid is explicitly an
    // owner-issued lockstep event in hap_a8w8_col_shard_s42.  The shard must
    // preserve A, raise its sticky diagnostic for B, and recover on clear.
    reg probe_clear = 1'b0;
    reg probe_capture_valid = 1'b0;
    wire probe_capture_ready;
    reg [2047:0] probe_act_u8 = '0;
    reg [127:0] probe_zero = '0;
    reg [63:0] probe_act_code = '0;
    reg [47:0] probe_act_shift = '0;
    reg [511:0] probe_wgt = '0;
    reg [15:0] probe_wgt_code = '0;
    reg [11:0] probe_wgt_shift = '0;
    wire probe_launch_ready;
    wire probe_guard_valid;
    wire signed [671:0] probe_guard;
    wire probe_accum_ready;
    wire probe_out_valid;
    wire [383:0] probe_out;
    wire probe_error;

    // Standalone accumulator probe for stale-overflow replay after clear.
    reg overflow_clear = 1'b0;
    reg overflow_in_valid = 1'b0;
    wire overflow_in_ready;
    reg overflow_first = 1'b0;
    reg overflow_last = 1'b0;
    reg signed [671:0] overflow_guard = '0;
    wire overflow_out_valid;
    wire [383:0] overflow_out;
    wire overflow_error;

    always #3.3335 clk = ~clk;

    hap_a8w8_array_16x16_s42 u_reference (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(source_valid), .in_ready(ref_in_ready),
        .in_first_group(source_first), .in_last_group(source_last),
        .region_act_u8(region_act_u8),
        .lane_act_zero_point(lane_act_zero_point),
        .row_act_scale_code(row_act_scale_code),
        .row_act_scale_shift(row_act_scale_shift),
        .col_wgt_s8(col_wgt_s8),
        .col_wgt_scale_code(col_wgt_scale_code),
        .col_wgt_scale_shift(col_wgt_scale_shift),
        .out_valid(ref_out_valid), .out_ready(common_out_ready),
        .out_s24(ref_out_s24),
        .accepted_group_count(ref_accepted_count),
        .accumulated_group_count(ref_accumulated_count),
        .output_tile_count(ref_output_count),
        .saturation_count(ref_saturation_count), .error(ref_error)
    );

    hap_a8w8_array_16x16_s42_col3 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(source_valid), .in_ready(dut_in_ready),
        .in_first_group(source_first), .in_last_group(source_last),
        .in_wave(1'b0),
        .region_act_u8(region_act_u8),
        .lane_act_zero_point(lane_act_zero_point),
        .row_act_scale_code(row_act_scale_code),
        .row_act_scale_shift(row_act_scale_shift),
        .col_wgt_s8(col_wgt_s8),
        .col_wgt_scale_code(col_wgt_scale_code),
        .col_wgt_scale_shift(col_wgt_scale_shift),
        .out_valid(dut_out_valid), .out_ready(common_out_ready), .out_wave(),
        .out_s24(dut_out_s24),
        .accepted_group_count(dut_accepted_count),
        .accumulated_group_count(dut_accumulated_count),
        .output_tile_count(dut_output_count),
        .saturation_count(dut_saturation_count), .error(dut_error)
    );

    hap_a8w8_col_shard_left2_s42 u_capture_probe (
        .clk(clk), .rst_n(rst_n), .clear(probe_clear),
        .capture_valid(probe_capture_valid),
        .capture_ready(probe_capture_ready),
        .capture_act_u8(probe_act_u8),
        .capture_act_zero_point(probe_zero),
        .capture_act_scale_code(probe_act_code),
        .capture_act_scale_shift(probe_act_shift),
        .capture_wgt_s8(probe_wgt),
        .capture_wgt_scale_code(probe_wgt_code),
        .capture_wgt_scale_shift(probe_wgt_shift),
        .launch_ready(probe_launch_ready), .launch(1'b0),
        .guard_valid(probe_guard_valid), .guard_s42(probe_guard),
        .accum_ready(probe_accum_ready), .guard_commit(1'b0),
        .guard_wave(1'b0), .guard_first(1'b0), .guard_last(1'b0),
        .out_valid(probe_out_valid), .out_ready(1'b0),
        .out_wave(), .out_s24(probe_out), .accumulated_group_count(),
        .output_tile_count(), .saturation_count(), .error(probe_error)
    );

    hap_linear_tile_accum_shard_s42 #(.LANES(16)) u_overflow_probe (
        .clk(clk), .rst_n(rst_n), .clear(overflow_clear),
        .in_valid(overflow_in_valid), .in_ready(overflow_in_ready),
        .in_first_group(overflow_first), .in_last_group(overflow_last),
        .in_guard_s42(overflow_guard), .out_valid(overflow_out_valid),
        .out_ready(1'b0), .out_s24(overflow_out),
        .input_group_count(), .output_tile_count(), .saturation_count(),
        .error(overflow_error)
    );

    task automatic fail;
        input [8*180-1:0] reason;
        begin
            $display("FAIL: %0s cycle=%0d send=%0d receive=%0d capture=%0d launch=%0d commit=%0d",
                reason, cycle, send_index, receive_index, capture_events,
                launch_events, commit_events);
            $finish;
        end
    endtask

    // All four activation regions and all sixteen columns deliberately carry
    // distinct data.  This catches a local-column mapping that accidentally
    // treats center columns 2:13 as only two equal-width regions.
    task automatic load_group;
        input integer linear_group;
        integer tile;
        integer group;
        integer row;
        integer region;
        integer col;
        integer elem;
        integer delta;
        integer weight_value;
        begin
            tile = linear_group / GROUPS_PER_TILE;
            group = linear_group % GROUPS_PER_TILE;
            region_act_u8 = '0;
            lane_act_zero_point = '0;
            row_act_scale_code = '0;
            row_act_scale_shift = '0;
            col_wgt_s8 = '0;
            col_wgt_scale_code = '0;
            col_wgt_scale_shift = '0;
            for (row = 0; row < 8; row = row + 1) begin
                row_act_scale_code[row*8 +: 8] = 8'(row + 1);
                row_act_scale_shift[row*6 +: 6] = 6'd13;
                for (region = 0; region < 4; region = region + 1) begin
                    for (elem = 0; elem < 32; elem = elem + 1) begin
                        delta = ((group*3 + row*5 + region*7 + elem +
                            tile*11) % 9) - 4;
                        region_act_u8[
                            ((row*4+region)*32+elem)*8 +: 8] =
                            8'(80 + row + region + delta);
                    end
                end
                for (col = 0; col < 16; col = col + 1)
                    lane_act_zero_point[(row*16+col)*8 +: 8] =
                        8'(80 + row + (col/4));
            end
            for (col = 0; col < 16; col = col + 1) begin
                col_wgt_scale_code[col*8 +: 8] = 8'(col + 2);
                col_wgt_scale_shift[col*6 +: 6] = 6'd13;
                for (elem = 0; elem < 32; elem = elem + 1) begin
                    weight_value = ((group + col*3 + elem*5 + tile*7) %
                        9) - 4;
                    col_wgt_s8[(col*32+elem)*8 +: 8] =
                        weight_value[7:0];
                end
            end
        end
    endtask

    task automatic send_overflow_group;
        input first;
        input signed [41:0] lane0_value;
        begin
            @(negedge clk);
            while (!overflow_in_ready)
                @(negedge clk);
            overflow_guard = '0;
            overflow_guard[41:0] = lane0_value;
            overflow_first = first;
            overflow_last = 1'b0;
            overflow_in_valid = 1'b1;
            @(negedge clk);
            overflow_in_valid = 1'b0;
        end
    endtask

    // Keep the source payload stable for the complete ready-to-ready cycle.
    always @(negedge clk) begin
        if (run_enable && (send_index < TOTAL_GROUPS))
            load_group(send_index);
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            send_index <= 0;
            receive_index <= 0;
            ready_lfsr_r <= 16'h1ace;
            capture_events <= 0;
            launch_events <= 0;
            commit_events <= 0;
            output_stall_cycles <= 0;
            last_capture_cycle <= -1000;
            max_capture_interval <= 0;
            ref_was_stalled_r <= 1'b0;
            dut_was_stalled_r <= 1'b0;
        end else begin
            cycle <= cycle + 1;
            ready_lfsr_r <= {ready_lfsr_r[14:0],
                ready_lfsr_r[15] ^ ready_lfsr_r[13] ^
                ready_lfsr_r[12] ^ ready_lfsr_r[10]};

            if (clear) begin
                send_index <= 0;
                receive_index <= 0;
                capture_events <= 0;
                launch_events <= 0;
                commit_events <= 0;
                output_stall_cycles <= 0;
                last_capture_cycle <= -1000;
                max_capture_interval <= 0;
                ref_was_stalled_r <= 1'b0;
                dut_was_stalled_r <= 1'b0;
            end else begin
                if (source_fire)
                    send_index <= send_index + 1;

                if (dut.input_fire) begin
                    if (!(dut.left_capture_ready &&
                          dut.center_capture_ready &&
                          dut.right_capture_ready))
                        fail("capture was not a three-shard atomic handshake");
                    // Tile retirement/finalization deliberately inserts a
                    // boundary bubble.  II=2 is the within-tile requirement,
                    // so start a fresh interval epoch on each first group.
                    if (final_epoch_r && !source_first &&
                        (last_capture_cycle >= 0)) begin
                        if ((cycle - last_capture_cycle) < 2)
                            fail("column-shard input interval violated II=2");
                        if ((cycle - last_capture_cycle) >
                            max_capture_interval)
                            max_capture_interval <=
                                cycle - last_capture_cycle;
                    end
                    last_capture_cycle <= cycle;
                    capture_events <= capture_events + 1;
                end
                if (dut.launch) begin
                    if (!(dut.left_launch_ready &&
                          dut.center_launch_ready &&
                          dut.right_launch_ready))
                        fail("launch was not lockstep across all shards");
                    launch_events <= launch_events + 1;
                end
                if (dut.guard_commit) begin
                    if (!(dut.left_guard_valid &&
                          dut.center_guard_valid &&
                          dut.right_guard_valid &&
                          dut.left_accum_ready &&
                          dut.center_accum_ready &&
                          dut.right_accum_ready))
                        fail("guard/accumulator commit was not atomic");
                    if (!(dut.u_left2.u_shard.g_single_accumulator.u_accumulator.in_fire &&
                          dut.u_center12.u_region0_cols2_3.g_single_accumulator.u_accumulator.in_fire &&
                          dut.u_center12.u_region1_cols4_7.g_single_accumulator.u_accumulator.in_fire &&
                          dut.u_center12.u_region2_cols8_11.g_single_accumulator.u_accumulator.in_fire &&
                          dut.u_center12.u_region3_cols12_13.g_single_accumulator.u_accumulator.in_fire &&
                          dut.u_right2.u_shard.g_single_accumulator.u_accumulator.in_fire))
                        fail("one shard missed the global accumulator commit");
                    commit_events <= commit_events + 1;
                end

                if ((dut.u_left2.u_shard.stage_valid_r !==
                     dut.u_center12.u_region1_cols4_7.stage_valid_r) ||
                    (dut.u_center12.u_region0_cols2_3.stage_valid_r !==
                     dut.u_center12.u_region1_cols4_7.stage_valid_r) ||
                    (dut.u_center12.u_region2_cols8_11.stage_valid_r !==
                     dut.u_center12.u_region1_cols4_7.stage_valid_r) ||
                    (dut.u_center12.u_region3_cols12_13.stage_valid_r !==
                     dut.u_center12.u_region1_cols4_7.stage_valid_r) ||
                    (dut.u_left2.u_shard.stage_valid_r !==
                     dut.u_right2.u_shard.stage_valid_r) ||
                    (dut.left_guard_valid !== dut.center_guard_valid) ||
                    (dut.left_guard_valid !== dut.right_guard_valid) ||
                    (dut.left_out_valid !== dut.center_out_valid) ||
                    (dut.left_out_valid !== dut.right_out_valid) ||
                    (dut.left_accumulated_count !==
                     dut.center_accumulated_count) ||
                    (dut.left_accumulated_count !==
                     dut.right_accumulated_count) ||
                    (dut.left_output_count !== dut.center_output_count) ||
                    (dut.left_output_count !== dut.right_output_count))
                    fail("three shard control/counters lost lockstep");

                if (ref_was_stalled_r &&
                    (!ref_out_valid || (ref_out_s24 !== ref_held_output_r)))
                    fail("reference output changed under backpressure");
                if (dut_was_stalled_r &&
                    (!dut_out_valid || (dut_out_s24 !== dut_held_output_r)))
                    fail("sharded output changed under backpressure");
                ref_was_stalled_r <= ref_out_valid && !common_out_ready;
                dut_was_stalled_r <= dut_out_valid && !common_out_ready;
                if (ref_out_valid && !common_out_ready)
                    ref_held_output_r <= ref_out_s24;
                if (dut_out_valid && !common_out_ready) begin
                    dut_held_output_r <= dut_out_s24;
                    output_stall_cycles <= output_stall_cycles + 1;
                end

                if (output_fire) begin
                    if (dut_out_s24 !== ref_out_s24)
                        fail("column-shard output differed from golden array");
                    if ((dut_accepted_count !=
                         (receive_index+1)*GROUPS_PER_TILE) ||
                        (dut_accumulated_count !=
                         (receive_index+1)*GROUPS_PER_TILE) ||
                        (ref_accepted_count !=
                         (receive_index+1)*GROUPS_PER_TILE) ||
                        (ref_accumulated_count !=
                         (receive_index+1)*GROUPS_PER_TILE))
                        fail("group counters mismatched at tile retirement");
                    receive_index <= receive_index + 1;
                end

                if (final_epoch_r && (ref_error || dut_error))
                    fail("golden or sharded array asserted sticky error");
            end

            if (cycle > 10000)
                fail("global timeout");
        end
    end

    initial begin : main_test
        integer wait_cycles;
        reg [2047:0] captured_probe_act;
        repeat (8) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        load_group(0);
        run_enable = 1'b1;

        // Clear a partially populated tag/lane pipeline, then start the
        // measured two-tile equivalence epoch from a clean state.
        wait (send_index == 5);
        @(negedge clk);
        run_enable = 1'b0;
        clear = 1'b1;
        repeat (2) @(negedge clk);
        clear = 1'b0;
        load_group(0);
        final_epoch_r = 1'b1;
        run_enable = 1'b1;

        wait (receive_index == TILES);
        @(negedge clk);
        run_enable = 1'b0;
        if (send_index != TOTAL_GROUPS || capture_events != TOTAL_GROUPS ||
            launch_events != TOTAL_GROUPS || commit_events != TOTAL_GROUPS)
            fail("two-tile event totals were incomplete");
        if (output_stall_cycles == 0)
            fail("randomized output backpressure was not exercised");
        if (max_capture_interval > 2)
            fail("unstalled within-tile input throughput was below II=2");
        if (dut_output_count != TILES || ref_output_count != TILES)
            fail("tile counters were incomplete");
        if (dut_saturation_count != ref_saturation_count)
            fail("cumulative saturation counters differed");

        // Capture A, then illegally issue capture_valid with payload B while
        // the shard stage is full.  B must not overwrite A and must raise the
        // fail-closed diagnostic required by the internal owner-event contract.
        probe_act_u8 = {256{8'ha5}};
        probe_zero = {16{8'h21}};
        probe_act_code = {8{8'd1}};
        probe_act_shift = {8{6'd13}};
        probe_wgt = {64{8'h03}};
        probe_wgt_code = {2{8'd1}};
        probe_wgt_shift = {2{6'd13}};
        probe_capture_valid = 1'b1;
        @(posedge clk);
        #1;
        if (probe_capture_ready)
            fail("capture probe did not fill its one-entry stage");
        captured_probe_act = u_capture_probe.u_shard.stage_act_u8_r;
        @(negedge clk);
        probe_act_u8 = {256{8'h5a}};
        repeat (3) begin
            @(posedge clk);
            #1;
            if (u_capture_probe.u_shard.stage_act_u8_r !==
                captured_probe_act)
                fail("capture payload was overwritten while !ready");
            if (!probe_error)
                fail("illegal capture event did not raise shard error");
        end
        @(negedge clk);
        probe_capture_valid = 1'b0;
        probe_clear = 1'b1;
        @(negedge clk);
        probe_clear = 1'b0;

        // Overflow S42 on lane zero, observe the sticky diagnostic, clear it,
        // and remain idle long enough for every reduction-valid stage to
        // drain.  A stale flag must never reassert error.
        send_overflow_group(1'b1, {1'b0, {41{1'b1}}});
        send_overflow_group(1'b0, 42'sd1);
        wait_cycles = 0;
        while (!overflow_error && (wait_cycles < 20)) begin
            @(posedge clk);
            wait_cycles = wait_cycles + 1;
        end
        if (!overflow_error)
            fail("directed S42 overflow was not reported");
        @(negedge clk);
        overflow_clear = 1'b1;
        repeat (2) @(negedge clk);
        overflow_clear = 1'b0;
        repeat (24) begin
            @(posedge clk);
            #1;
            if (overflow_error)
                fail("stale overflow flag reasserted after clear");
        end

        $display("COL3_ARRAY_METRIC_JSON: {\"tiles\":2,\"groups\":256,\"mismatches\":0,\"input_ii\":2,\"capture_events\":%0d,\"launch_events\":%0d,\"commit_events\":%0d,\"output_stall_cycles\":%0d,\"clear_after_overflow\":1,\"cycles\":%0d}",
            capture_events, launch_events, commit_events,
            output_stall_cycles, cycle);
        $display("PASS: col3 array matched monolithic golden for two tiles; lockstep, II=2, randomized backpressure, atomic capture and overflow clear passed");
        $finish;
    end
endmodule
