`timescale 1ns / 1ps

module hap_projection_core8x16_capture_fanout_tb;
    localparam integer GROUPS = 128;
    localparam integer COLS = 16;
    localparam integer TILES = 2;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg activation_valid = 1'b0;
    wire activation_ready;
    reg [6143:0] activation_s24 = '0;
    reg [6:0] activation_group = '0;
    wire activation_cached;
    reg activation_release = 1'b0;
    reg project_start = 1'b0;
    wire weight_ready;
    reg weight_valid = 1'b0;
    reg [6:0] weight_group = '0;
    reg [4095:0] weight_s8 = '0;
    reg [255:0] weight_meta16 = '0;
    wire out_valid;
    reg out_ready = 1'b0;
    wire [3071:0] out_s24;
    wire [31:0] accepted_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;

    reg [6143:0] activation_mem [0:GROUPS-1];
    reg [255:0] weight_col_mem [0:TILES*GROUPS*COLS-1];
    reg [15:0] weight_meta_mem [0:TILES*GROUPS*COLS-1];
    reg [3071:0] expected_mem [0:TILES-1];

    integer cycle = 0;
    integer checks = 0;
    integer activation_send = 0;
    integer weight_send = 0;
    integer tile_receive = 0;
    integer col;
    integer shard_row;
    integer shard_col;
    integer expected_weight_index;
    integer last_capture_cycle = -1000;
    integer capture_count = 0;
    integer wrong_group_stall_cycles = 0;
    integer source_bubble_cycles = 0;
    integer output_stall_cycles = 0;
    integer clear_count = 0;
    integer clear_hold_cycles = 0;
    integer phase = 0;
    reg project_started = 1'b0;
    reg wrong_group_tested = 1'b0;
    reg [3071:0] held_output = '0;
    reg was_stalled = 1'b0;
    reg [8191:0] expected_array_act_u8 = '0;
    reg [1023:0] expected_array_zero = '0;
    reg [127:0] expected_array_act_code = '0;
    reg [95:0] expected_array_act_shift = '0;
    reg [4095:0] expected_array_weight = '0;
    reg [127:0] expected_array_weight_code = '0;
    reg [95:0] expected_array_weight_shift = '0;
    integer array_compare_pending = 0;

    always #3.3335 clk = ~clk;

    hap_projection_core8x16 dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_s24(activation_s24),
        .activation_group(activation_group),
        .activation_cached(activation_cached),
        .activation_release(activation_release),
        .project_start(project_start), .weight_ready(weight_ready),
        .weight_valid(weight_valid), .weight_group(weight_group),
        .weight_s8(weight_s8), .weight_meta16(weight_meta16),
        .out_valid(out_valid), .out_ready(out_ready), .out_s24(out_s24),
        .accepted_group_count(accepted_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    task automatic fail;
        input [8*180-1:0] reason;
        begin
            $display("FAIL: %0s cycle=%0d phase=%0d act=%0d weight=%0d capture=%0d accepted=%0d output=%0d",
                reason, cycle, phase, activation_send, weight_send,
                capture_count, accepted_group_count, output_tile_count);
            $finish;
        end
    endtask

    task automatic load_weight_payload;
        input integer linear_group;
        integer local_col;
        begin
            for (local_col = 0; local_col < COLS;
                 local_col = local_col + 1) begin
                weight_s8[local_col*256 +: 256] = weight_col_mem[
                    (((linear_group % GROUPS)*TILES) +
                     (linear_group/GROUPS))*COLS + local_col];
                weight_meta16[local_col*16 +: 16] = weight_meta_mem[
                    (((linear_group % GROUPS)*TILES) +
                     (linear_group/GROUPS))*COLS + local_col];
            end
        end
    endtask

    initial begin
        $readmemh("data/projection_core8x16/input_s24.mem",
            activation_mem);
        $readmemh("data/projection_core8x16/weight_s8.mem",
            weight_col_mem);
        $readmemh("data/projection_core8x16/weight_meta16.mem",
            weight_meta_mem);
        $readmemh("data/projection_core8x16/expected_s24.mem",
            expected_mem);
        repeat (8) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
    end

    // Driver deliberately misaligns producer valid, legal group readiness
    // and downstream output readiness.  In particular, the first projection
    // presents an illegal group for five cycles; ready must stay low without
    // setting the sticky error or disturbing the later golden transaction.
    always @(negedge clk) begin
        if (!rst_n || clear) begin
            activation_valid = 1'b0;
            project_start = 1'b0;
            activation_release = 1'b0;
            weight_valid = 1'b0;
            out_ready = 1'b0;
        end else begin
            project_start = 1'b0;
            activation_release = 1'b0;
            out_ready = !(((cycle % 41) >= 23) && ((cycle % 41) <= 32));

            if (activation_send < GROUPS) begin
                activation_group = activation_send[6:0];
                activation_s24 = activation_mem[activation_send];
                activation_valid = ((cycle % 13) != 4) &&
                    ((cycle % 13) != 5);
            end else begin
                activation_valid = 1'b0;
            end

            if ((!project_started || (tile_receive > 0)) &&
                (tile_receive < TILES) && activation_cached &&
                (weight_send == tile_receive*GROUPS))
                project_start = 1'b1;

            if (project_started && (weight_send < TILES*GROUPS)) begin
                if (!wrong_group_tested && (weight_send == 0) &&
                    (wrong_group_stall_cycles < 5)) begin
                    weight_group = 7'd1;
                    load_weight_payload(1);
                    weight_valid = 1'b1;
                end else if (((cycle + weight_send) % 17) == 6 ||
                    ((cycle + weight_send) % 17) == 7) begin
                    weight_valid = 1'b0;
                    source_bubble_cycles = source_bubble_cycles + 1;
                end else begin
                    weight_group = weight_send[6:0];
                    load_weight_payload(weight_send);
                    weight_valid = 1'b1;
                end
            end else begin
                weight_valid = 1'b0;
            end

            if ((tile_receive == TILES) && activation_cached)
                activation_release = 1'b1;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            cycle <= 0;
            activation_send <= 0;
            weight_send <= 0;
            tile_receive <= 0;
            project_started <= 1'b0;
            wrong_group_tested <= 1'b0;
            wrong_group_stall_cycles <= 0;
            source_bubble_cycles <= 0;
            output_stall_cycles <= 0;
            capture_count <= 0;
            last_capture_cycle <= -1000;
            was_stalled <= 1'b0;
            phase <= 0;
            clear_count <= 0;
            clear_hold_cycles <= 0;
        end else begin
            cycle <= cycle + 1;

            if (phase == 0) begin
                // Exercise clear while an activation payload is being held;
                // no partial cache fill may survive.  The fresh golden run
                // starts only after this reset-like protocol flush.
                if ((activation_send == 3) && !clear) begin
                    clear <= 1'b1;
                    clear_hold_cycles <= 2;
                end
                if (clear) begin
                    if (clear_hold_cycles == 1) begin
                        clear <= 1'b0;
                        clear_hold_cycles <= 0;
                        clear_count <= clear_count + 1;
                        activation_send <= 0;
                        phase <= 1;
                    end else begin
                        clear_hold_cycles <= clear_hold_cycles - 1;
                    end
                end else if (activation_valid && activation_ready) begin
                    activation_send <= activation_send + 1;
                end
            end else if (activation_valid && activation_ready) begin
                activation_send <= activation_send + 1;
            end

            if (project_start)
                project_started <= 1'b1;

            if (weight_valid && !weight_ready && !wrong_group_tested &&
                (weight_send == 0) && (weight_group == 1)) begin
                wrong_group_stall_cycles <= wrong_group_stall_cycles + 1;
                if (wrong_group_stall_cycles == 4)
                    wrong_group_tested <= 1'b1;
                checks <= checks + 1;
            end
            if (weight_valid && weight_ready) begin
                weight_send <= weight_send + 1;
                checks <= checks + 1;
            end

            if (dut.capture_group) begin
                if (dut.capture_group_local !== {52{1'b1}})
                    fail("capture-group LUT replicas were not lockstep high");
                if ((last_capture_cycle >= 0) &&
                    ((cycle - last_capture_cycle) < 2))
                    fail("capture-group interval violated array II=2");
                if (dut.frontend_rd_rsp_group !== dut.weight_buffer_group_r)
                    fail("frontend/weight tags mismatched on capture");
                last_capture_cycle <= cycle;
                capture_count <= capture_count + 1;
                checks <= checks + 3;
            end else if (dut.capture_group_local !== 52'd0) begin
                fail("capture-group LUT replicas were not lockstep low");
            end

            // One delta after the capture edge, every payload bank must equal
            // the two source buffers that participated in that transaction.
            if (dut.capture_group) begin
                expected_weight_index = dut.weight_buffer_group_r;
                #1;
                if (dut.group_stage_group_r !== expected_weight_index[6:0])
                    fail("captured group tag mismatch");
                if (dut.group_stage_act_meta_r !== dut.frontend_rd_rsp_meta)
                    fail("captured activation metadata mismatch");
                for (col=0; col<32; col=col+1)
                    if (dut.group_stage_act_u8_region_r[col*256 +: 256] !==
                        dut.frontend_rd_rsp_u8[(col/4)*256 +: 256])
                        fail("captured activation region mismatch");
                for (col=0; col<16; col=col+1)
                    if (dut.group_stage_weight_s8_r[col*256 +: 256] !==
                        dut.weight_buffer_s8_r[col*256 +: 256])
                        fail("captured weight column mismatch");
                if (dut.group_stage_weight_meta16_r !==
                    dut.weight_buffer_meta16_r)
                    fail("captured weight metadata mismatch");
                checks <= checks + 51;
            end

            if (dut.u_frontend.input_fire) begin
                if (dut.u_frontend.input_fire_local !== {24{1'b1}})
                    fail("frontend input-fire LUT replicas were not high");
                #1;
                if (dut.u_frontend.input_buffer_s24_r !== activation_s24)
                    fail("frontend input banks did not capture bit exactly");
                checks <= checks + 25;
            end else if (dut.u_frontend.input_fire_local !== 24'd0) begin
                fail("frontend input-fire LUT replicas were not low");
            end

            if ({dut.u_array.u_left2.u_shard.capture_fire,
                 dut.u_array.u_center12.u_region0_cols2_3.capture_fire,
                 dut.u_array.u_center12.u_region1_cols4_7.capture_fire,
                 dut.u_array.u_center12.u_region2_cols8_11.capture_fire,
                 dut.u_array.u_center12.u_region3_cols12_13.capture_fire,
                 dut.u_array.u_right2.u_shard.capture_fire} !==
                {6{dut.u_array.input_fire}})
                fail("array shard captures were not atomic");
            if ((dut.u_array.u_left2.u_shard.stage_valid_r !==
                 dut.u_array.u_center12.u_region0_cols2_3.stage_valid_r) ||
                (dut.u_array.u_left2.u_shard.stage_valid_r !==
                 dut.u_array.u_center12.u_region1_cols4_7.stage_valid_r) ||
                (dut.u_array.u_left2.u_shard.stage_valid_r !==
                 dut.u_array.u_center12.u_region2_cols8_11.stage_valid_r) ||
                (dut.u_array.u_left2.u_shard.stage_valid_r !==
                 dut.u_array.u_center12.u_region3_cols12_13.stage_valid_r) ||
                (dut.u_array.u_left2.u_shard.stage_valid_r !==
                 dut.u_array.u_right2.u_shard.stage_valid_r))
                fail("array shard input stages lost lockstep");

            if (dut.u_array.input_fire) begin
                if (!(dut.u_array.left_capture_ready &&
                      dut.u_array.center_capture_ready &&
                      dut.u_array.right_capture_ready))
                    fail("array input fired without all shard ready");
                expected_array_act_u8 = dut.u_array.region_act_u8;
                expected_array_zero = dut.u_array.lane_act_zero_point;
                expected_array_act_code = dut.u_array.row_act_scale_code;
                expected_array_act_shift = dut.u_array.row_act_scale_shift;
                expected_array_weight = dut.u_array.col_wgt_s8;
                expected_array_weight_code = dut.u_array.col_wgt_scale_code;
                expected_array_weight_shift = dut.u_array.col_wgt_scale_shift;
                array_compare_pending = 2;
            end
            if (array_compare_pending != 0) begin
                array_compare_pending = array_compare_pending - 1;
                if (array_compare_pending == 0) begin
                    for (shard_row=0; shard_row<8;
                         shard_row=shard_row+1) begin
                        if (dut.u_array.u_left2.u_shard.stage_act_u8_r[
                                shard_row*256 +: 256] !==
                            expected_array_act_u8[
                                (shard_row*4+0)*256 +: 256])
                            fail("left shard activation mapping mismatch");
                        if (dut.u_array.u_right2.u_shard.stage_act_u8_r[
                                shard_row*256 +: 256] !==
                            expected_array_act_u8[
                                (shard_row*4+3)*256 +: 256])
                            fail("right shard activation mapping mismatch");
                        if (dut.u_array.u_center12.u_region0_cols2_3.
                                stage_act_u8_r[shard_row*256 +: 256] !==
                            expected_array_act_u8[
                                (shard_row*4+0)*256 +: 256])
                            fail("center region0 activation mapping mismatch");
                        if (dut.u_array.u_center12.u_region1_cols4_7.
                                stage_act_u8_r[shard_row*256 +: 256] !==
                            expected_array_act_u8[
                                (shard_row*4+1)*256 +: 256])
                            fail("center region1 activation mapping mismatch");
                        if (dut.u_array.u_center12.u_region2_cols8_11.
                                stage_act_u8_r[shard_row*256 +: 256] !==
                            expected_array_act_u8[
                                (shard_row*4+2)*256 +: 256])
                            fail("center region2 activation mapping mismatch");
                        if (dut.u_array.u_center12.u_region3_cols12_13.
                                stage_act_u8_r[shard_row*256 +: 256] !==
                            expected_array_act_u8[
                                (shard_row*4+3)*256 +: 256])
                            fail("center region3 activation mapping mismatch");
                        for (shard_col=0; shard_col<2;
                             shard_col=shard_col+1) begin
                            if (dut.u_array.u_left2.u_shard.
                                    stage_act_zero_point_r[
                                        (shard_row*2+shard_col)*8 +: 8] !==
                                expected_array_zero[
                                    (shard_row*16+shard_col)*8 +: 8])
                                fail("left shard zero-point mapping mismatch");
                            if (dut.u_array.u_right2.u_shard.
                                    stage_act_zero_point_r[
                                        (shard_row*2+shard_col)*8 +: 8] !==
                                expected_array_zero[
                                    (shard_row*16+14+shard_col)*8 +: 8])
                                fail("right shard zero-point mapping mismatch");
                        end
                        for (shard_col=0; shard_col<2;
                             shard_col=shard_col+1) begin
                            if (dut.u_array.u_center12.u_region0_cols2_3.
                                    stage_act_zero_point_r[
                                        (shard_row*2+shard_col)*8 +: 8] !==
                                expected_array_zero[
                                    (shard_row*16+2+shard_col)*8 +: 8])
                                fail("center region0 zero-point mismatch");
                            if (dut.u_array.u_center12.u_region3_cols12_13.
                                    stage_act_zero_point_r[
                                        (shard_row*2+shard_col)*8 +: 8] !==
                                expected_array_zero[
                                    (shard_row*16+12+shard_col)*8 +: 8])
                                fail("center region3 zero-point mismatch");
                        end
                        for (shard_col=0; shard_col<4;
                             shard_col=shard_col+1) begin
                            if (dut.u_array.u_center12.u_region1_cols4_7.
                                    stage_act_zero_point_r[
                                        (shard_row*4+shard_col)*8 +: 8] !==
                                expected_array_zero[
                                    (shard_row*16+4+shard_col)*8 +: 8])
                                fail("center region1 zero-point mismatch");
                            if (dut.u_array.u_center12.u_region2_cols8_11.
                                    stage_act_zero_point_r[
                                        (shard_row*4+shard_col)*8 +: 8] !==
                                expected_array_zero[
                                    (shard_row*16+8+shard_col)*8 +: 8])
                                fail("center region2 zero-point mismatch");
                        end
                    end
                    if ((dut.u_array.u_left2.u_shard.
                            stage_act_scale_code_r !==
                         expected_array_act_code[63:0]) ||
                        (dut.u_array.u_center12.u_region0_cols2_3.
                            stage_act_scale_code_r !==
                         expected_array_act_code[63:0]) ||
                        (dut.u_array.u_center12.u_region1_cols4_7.
                            stage_act_scale_code_r !==
                         expected_array_act_code[63:0]) ||
                        (dut.u_array.u_center12.u_region2_cols8_11.
                            stage_act_scale_code_r !==
                         expected_array_act_code[63:0]) ||
                        (dut.u_array.u_center12.u_region3_cols12_13.
                            stage_act_scale_code_r !==
                         expected_array_act_code[63:0]) ||
                        (dut.u_array.u_right2.u_shard.
                            stage_act_scale_code_r !==
                         expected_array_act_code[63:0]) ||
                        (dut.u_array.u_left2.u_shard.
                            stage_act_scale_shift_r !==
                         expected_array_act_shift[47:0]) ||
                        (dut.u_array.u_center12.u_region0_cols2_3.
                            stage_act_scale_shift_r !==
                         expected_array_act_shift[47:0]) ||
                        (dut.u_array.u_center12.u_region1_cols4_7.
                            stage_act_scale_shift_r !==
                         expected_array_act_shift[47:0]) ||
                        (dut.u_array.u_center12.u_region2_cols8_11.
                            stage_act_scale_shift_r !==
                         expected_array_act_shift[47:0]) ||
                        (dut.u_array.u_center12.u_region3_cols12_13.
                            stage_act_scale_shift_r !==
                         expected_array_act_shift[47:0]) ||
                        (dut.u_array.u_right2.u_shard.
                            stage_act_scale_shift_r !==
                         expected_array_act_shift[47:0]))
                        fail("array shard activation metadata mismatch");
                    if ((dut.u_array.u_left2.u_shard.stage_wgt_s8_r !==
                         expected_array_weight[0 +: 512]) ||
                        (dut.u_array.u_center12.u_region0_cols2_3.
                            stage_wgt_s8_r !==
                         expected_array_weight[2*256 +: 2*256]) ||
                        (dut.u_array.u_center12.u_region1_cols4_7.
                            stage_wgt_s8_r !==
                         expected_array_weight[4*256 +: 4*256]) ||
                        (dut.u_array.u_center12.u_region2_cols8_11.
                            stage_wgt_s8_r !==
                         expected_array_weight[8*256 +: 4*256]) ||
                        (dut.u_array.u_center12.u_region3_cols12_13.
                            stage_wgt_s8_r !==
                         expected_array_weight[12*256 +: 2*256]) ||
                        (dut.u_array.u_right2.u_shard.stage_wgt_s8_r !==
                         expected_array_weight[14*256 +: 512]) ||
                        (dut.u_array.u_left2.u_shard.
                            stage_wgt_scale_code_r !==
                         expected_array_weight_code[0 +: 16]) ||
                        (dut.u_array.u_center12.u_region0_cols2_3.
                            stage_wgt_scale_code_r !==
                         expected_array_weight_code[2*8 +: 2*8]) ||
                        (dut.u_array.u_center12.u_region1_cols4_7.
                            stage_wgt_scale_code_r !==
                         expected_array_weight_code[4*8 +: 4*8]) ||
                        (dut.u_array.u_center12.u_region2_cols8_11.
                            stage_wgt_scale_code_r !==
                         expected_array_weight_code[8*8 +: 4*8]) ||
                        (dut.u_array.u_center12.u_region3_cols12_13.
                            stage_wgt_scale_code_r !==
                         expected_array_weight_code[12*8 +: 2*8]) ||
                        (dut.u_array.u_right2.u_shard.
                            stage_wgt_scale_code_r !==
                         expected_array_weight_code[14*8 +: 16]) ||
                        (dut.u_array.u_left2.u_shard.
                            stage_wgt_scale_shift_r !==
                         expected_array_weight_shift[0 +: 12]) ||
                        (dut.u_array.u_center12.u_region0_cols2_3.
                            stage_wgt_scale_shift_r !==
                         expected_array_weight_shift[2*6 +: 2*6]) ||
                        (dut.u_array.u_center12.u_region1_cols4_7.
                            stage_wgt_scale_shift_r !==
                         expected_array_weight_shift[4*6 +: 4*6]) ||
                        (dut.u_array.u_center12.u_region2_cols8_11.
                            stage_wgt_scale_shift_r !==
                         expected_array_weight_shift[8*6 +: 4*6]) ||
                        (dut.u_array.u_center12.u_region3_cols12_13.
                            stage_wgt_scale_shift_r !==
                         expected_array_weight_shift[12*6 +: 2*6]) ||
                        (dut.u_array.u_right2.u_shard.
                            stage_wgt_scale_shift_r !==
                         expected_array_weight_shift[14*6 +: 12]))
                        fail("array shard weight payload mapping mismatch");
                    checks <= checks + 196;
                end
            end

            if (dut.u_array.launch &&
                !(dut.u_array.left_launch_ready &&
                  dut.u_array.center_launch_ready &&
                  dut.u_array.right_launch_ready))
                fail("array shard launches were not lockstep");

            if (dut.u_array.guard_commit) begin
                if (!(dut.u_array.u_left2.u_shard.g_single_accumulator.
                          u_accumulator.in_fire &&
                      dut.u_array.u_center12.u_region0_cols2_3.
                          g_single_accumulator.u_accumulator.in_fire &&
                      dut.u_array.u_center12.u_region1_cols4_7.
                          g_single_accumulator.u_accumulator.in_fire &&
                      dut.u_array.u_center12.u_region2_cols8_11.
                          g_single_accumulator.u_accumulator.in_fire &&
                      dut.u_array.u_center12.u_region3_cols12_13.
                          g_single_accumulator.u_accumulator.in_fire &&
                      dut.u_array.u_right2.u_shard.g_single_accumulator.
                          u_accumulator.in_fire))
                    fail("array shard accumulator commits were not atomic");
                if ((dut.u_array.u_left2.u_shard.g_single_accumulator.
                        u_accumulator.
                        in_fire_local !== {16{1'b1}}) ||
                    (dut.u_array.u_center12.u_region0_cols2_3.
                        g_single_accumulator.u_accumulator.in_fire_local !==
                        {16{1'b1}}) ||
                    (dut.u_array.u_center12.u_region1_cols4_7.
                        g_single_accumulator.u_accumulator.in_fire_local !==
                        {32{1'b1}}) ||
                    (dut.u_array.u_center12.u_region2_cols8_11.
                        g_single_accumulator.u_accumulator.in_fire_local !==
                        {32{1'b1}}) ||
                    (dut.u_array.u_center12.u_region3_cols12_13.
                        g_single_accumulator.u_accumulator.in_fire_local !==
                        {16{1'b1}}) ||
                    (dut.u_array.u_right2.u_shard.g_single_accumulator.
                        u_accumulator.
                        in_fire_local !== {16{1'b1}}))
                    fail("array shard accumulator lane enables were not high");
                checks <= checks + 128;
            end else if ((dut.u_array.u_left2.u_shard.
                            g_single_accumulator.u_accumulator.
                            in_fire_local !== 16'd0) ||
                         (dut.u_array.u_center12.u_region0_cols2_3.
                            g_single_accumulator.u_accumulator.
                            in_fire_local !== 16'd0) ||
                         (dut.u_array.u_center12.u_region1_cols4_7.
                            g_single_accumulator.u_accumulator.
                            in_fire_local !== 32'd0) ||
                         (dut.u_array.u_center12.u_region2_cols8_11.
                            g_single_accumulator.u_accumulator.
                            in_fire_local !== 32'd0) ||
                         (dut.u_array.u_center12.u_region3_cols12_13.
                            g_single_accumulator.u_accumulator.
                            in_fire_local !== 16'd0) ||
                         (dut.u_array.u_right2.u_shard.
                            g_single_accumulator.u_accumulator.
                            in_fire_local !== 16'd0)) begin
                fail("array shard accumulator lane enables were not low");
            end

            if (was_stalled && (!out_valid || out_s24 !== held_output))
                fail("output changed under backpressure");
            was_stalled <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                held_output <= out_s24;
                output_stall_cycles <= output_stall_cycles + 1;
            end

            if (!clear && error)
                fail("projection core asserted sticky error");

            if (out_valid && out_ready) begin
                if (out_s24 !== expected_mem[tile_receive])
                    fail("A8W8 output was not bit exact");
                if (activation_send != GROUPS ||
                    weight_send != (tile_receive+1)*GROUPS ||
                    accepted_group_count != (tile_receive+1)*GROUPS ||
                    output_tile_count != tile_receive ||
                    saturation_count != 0)
                    fail("projection counters/tags did not match tile boundary");
                checks <= checks + 6;
                if (tile_receive == TILES-1) begin
                    tile_receive <= tile_receive + 1;
                    $display("PROJECTION_CAPTURE_FANOUT_METRIC_JSON: {\"activation_groups\":128,\"weight_groups\":256,\"projection_tiles\":2,\"mismatches\":0,\"array_ii\":2,\"captures\":%0d,\"wrong_group_stalls\":%0d,\"source_bubbles\":%0d,\"output_stalls\":%0d,\"clears\":%0d,\"cycles\":%0d}",
                        capture_count, wrong_group_stall_cycles,
                        source_bubble_cycles, output_stall_cycles,
                        clear_count, cycle);
                    $display("PASS: projection capture fanout kept 128-group A8W8 bit exact, II=2, tags, backpressure and clear (%0d checks)", checks);
                    $finish;
                end else begin
                    tile_receive <= tile_receive + 1;
                    project_started <= 1'b0;
                end
            end

            if (cycle > 50000)
                fail("global timeout");
        end
    end
endmodule
