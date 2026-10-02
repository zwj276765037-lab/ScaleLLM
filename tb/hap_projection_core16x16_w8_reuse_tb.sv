`timescale 1ns / 1ps

module hap_projection_core16x16_w8_reuse_tb;
    localparam integer GROUPS = 128;
    localparam [31:0] REQUEST_ID = 32'h51a8_0037;
    localparam [15:0] COHORT_ID = 16'h001d;
    localparam [5:0] LAYER_ID = 6'd19;
    localparam [2:0] OP_ID = 3'd2;
    localparam [9:0] TILE_ID = 10'd417;
    localparam [6:0] QUERY_START = 7'd48;
    localparam [7:0] VALID_KEY_COUNT = 8'd96;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;

    reg activation_valid = 1'b0;
    wire activation_ready;
    reg activation_wave = 1'b0;
    reg [6143:0] activation_s24 = '0;
    reg [6:0] activation_group = 7'd0;
    wire activation_cached;
    reg activation_release = 1'b0;
    wire activation_release_ready;
    wire activation_released;

    reg project_start = 1'b0;
    wire project_ready;
    wire project_done;
    wire weight_ready;
    reg weight_valid = 1'b0;
    reg [6:0] weight_group = 7'd0;
    reg [4095:0] weight_s8 = '0;
    reg [255:0] weight_meta16 = '0;

    wire out_valid;
    reg out_ready = 1'b0;
    wire out_wave;
    wire [3071:0] out_s24;
    wire [31:0] out_request_id;
    wire [15:0] out_cohort_id;
    wire [5:0] out_layer_id;
    wire [2:0] out_op_id;
    wire [9:0] out_tile_id;
    wire [6:0] out_query_start;
    wire [7:0] out_valid_key_count;
    wire [31:0] accepted_weight_group_count;
    wire [31:0] consumed_wave_group_count;
    wire [31:0] released_weight_group_count;
    wire [31:0] output_wave_tile_count;
    wire [31:0] saturation_count;
    wire [1:0] weight_fifo_high_watermark;
    wire busy;
    wire error;

    reg [6143:0] input_wave0_mem [0:GROUPS-1];
    reg [6143:0] input_wave1_mem [0:GROUPS-1];
    reg [4095:0] weight_mem [0:GROUPS-1];
    reg [255:0] weight_meta_mem [0:GROUPS-1];
    reg [3071:0] expected_mem [0:1];

    integer cycle = 0;
    integer activation_accepts = 0;
    integer weight_accepts = 0;
    integer output_accepts = 0;
    integer project_done_count = 0;
    integer release_done_count = 0;
    integer output_stall_cycles = 0;
    integer stable_output_checks = 0;
    integer stable_weight_checks = 0;
    reg output_phase = 1'b0;
    reg output_was_stalled = 1'b0;
    reg [3071:0] held_output_s24 = '0;
    reg held_output_wave = 1'b0;
    reg weight_was_stalled = 1'b0;
    reg [6:0] held_weight_group = 7'd0;
    reg [4095:0] held_weight_s8 = '0;
    reg [255:0] held_weight_meta16 = '0;

    always #3.3335 clk = ~clk;

    hap_projection_core16x16_w8_reuse dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_wave(activation_wave),
        .activation_s24(activation_s24),
        .activation_group(activation_group),
        .activation_cached(activation_cached),
        .activation_release(activation_release),
        .activation_release_ready(activation_release_ready),
        .activation_released(activation_released),
        .project_start(project_start), .project_ready(project_ready),
        .project_done(project_done),
        .project_request_id(REQUEST_ID),
        .project_cohort_id(COHORT_ID),
        .project_layer_id(LAYER_ID), .project_op_id(OP_ID),
        .project_tile_id(TILE_ID), .project_query_start(QUERY_START),
        .project_valid_key_count(VALID_KEY_COUNT),
        .weight_ready(weight_ready), .weight_valid(weight_valid),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_wave(out_wave), .out_s24(out_s24),
        .out_request_id(out_request_id), .out_cohort_id(out_cohort_id),
        .out_layer_id(out_layer_id), .out_op_id(out_op_id),
        .out_tile_id(out_tile_id), .out_query_start(out_query_start),
        .out_valid_key_count(out_valid_key_count),
        .accepted_weight_group_count(accepted_weight_group_count),
        .consumed_wave_group_count(consumed_wave_group_count),
        .released_weight_group_count(released_weight_group_count),
        .output_wave_tile_count(output_wave_tile_count),
        .saturation_count(saturation_count),
        .weight_fifo_high_watermark(weight_fifo_high_watermark),
        .busy(busy), .error(error)
    );

    task automatic fail;
        input [8*200-1:0] reason;
        begin
            $display("FAIL: %0s cycle=%0d act=%0d weight=%0d output=%0d accepted=%0d consumed=%0d released=%0d",
                reason, cycle, activation_accepts, weight_accepts,
                output_accepts, accepted_weight_group_count,
                consumed_wave_group_count, released_weight_group_count);
            $display("ERROR_SOURCE: core=%0b frontend=%0b array=%0b frontend_control=%0b hadamard=%0b quant=%0h cache=%0b array_control=%0b left=%0b center=%0b right=%0b",
                dut.control_error_r, dut.frontend_error, dut.array_error,
                dut.u_frontend.control_error_r, dut.u_frontend.had_error,
                dut.u_frontend.quant_error, dut.u_frontend.cache_error,
                dut.u_array.control_error_r, dut.u_array.left_error,
                dut.u_array.center_error, dut.u_array.right_error);
            $display("CENTER_SOURCE: region=%0b%0b%0b%0b control=%0b%0b%0b%0b lane=%0h/%0h/%0h/%0h accum=%0b%0b%0b%0b",
                dut.u_array.u_center12.region3_error,
                dut.u_array.u_center12.region2_error,
                dut.u_array.u_center12.region1_error,
                dut.u_array.u_center12.region0_error,
                dut.u_array.u_center12.u_region3_cols12_13.control_error_r,
                dut.u_array.u_center12.u_region2_cols8_11.control_error_r,
                dut.u_array.u_center12.u_region1_cols4_7.control_error_r,
                dut.u_array.u_center12.u_region0_cols2_3.control_error_r,
                dut.u_array.u_center12.u_region3_cols12_13.lane_error,
                dut.u_array.u_center12.u_region2_cols8_11.lane_error,
                dut.u_array.u_center12.u_region1_cols4_7.lane_error,
                dut.u_array.u_center12.u_region0_cols2_3.lane_error,
                dut.u_array.u_center12.u_region3_cols12_13.accum_error,
                dut.u_array.u_center12.u_region2_cols8_11.accum_error,
                dut.u_array.u_center12.u_region1_cols4_7.accum_error,
                dut.u_array.u_center12.u_region0_cols2_3.accum_error);
            $finish;
        end
    endtask

    task automatic send_activation;
        input integer wave;
        input integer group;
        begin
            if (((group + 3*wave) % 11) == 5)
                repeat (2) @(posedge clk);
            @(negedge clk);
            activation_wave = wave[0:0];
            activation_group = group[6:0];
            activation_s24 = wave == 0 ? input_wave0_mem[group] :
                input_wave1_mem[group];
            activation_valid = 1'b1;
            @(posedge clk);
            while (!activation_ready)
                @(posedge clk);
            activation_accepts = activation_accepts + 1;
            @(negedge clk);
            activation_valid = 1'b0;
        end
    endtask

    task automatic send_weight;
        input integer group;
        begin
            if ((group % 13) == 7)
                repeat (3) @(posedge clk);
            @(negedge clk);
            weight_group = group[6:0];
            weight_s8 = weight_mem[group];
            weight_meta16 = weight_meta_mem[group];
            weight_valid = 1'b1;
            @(posedge clk);
            while (!weight_ready)
                @(posedge clk);
            weight_accepts = weight_accepts + 1;
            @(negedge clk);
            weight_valid = 1'b0;
        end
    endtask

    always @(posedge clk) begin
        cycle <= cycle + 1;
        if (rst_n && ((dut.u_array.u_center12.u_region2_cols8_11.launch &&
                       !dut.u_array.u_center12.u_region2_cols8_11.launch_ready) ||
                      (dut.u_array.u_center12.u_region2_cols8_11.lane_in_ready !=
                       {32{dut.u_array.u_center12.u_region2_cols8_11.owner_in_ready}}) ||
                      (dut.u_array.u_center12.u_region2_cols8_11.lane_out_valid !=
                       {32{dut.u_array.u_center12.u_region2_cols8_11.owner_out_valid}}) ||
                      (dut.u_array.u_center12.u_region2_cols8_11.guard_commit &&
                       (!dut.u_array.u_center12.u_region2_cols8_11.guard_valid ||
                        !dut.u_array.u_center12.u_region2_cols8_11.accum_ready)) ||
                      (dut.u_array.u_center12.u_region2_cols8_11.out_ready &&
                       !dut.u_array.u_center12.u_region2_cols8_11.out_valid)))
            $display("REGION2_INVARIANT: cycle=%0d launch=%0b/%0b lane_ready=%0h lane_valid=%0h guard=%0b/%0b/%0b out=%0b/%0b",
                cycle,
                dut.u_array.u_center12.u_region2_cols8_11.launch,
                dut.u_array.u_center12.u_region2_cols8_11.launch_ready,
                dut.u_array.u_center12.u_region2_cols8_11.lane_in_ready,
                dut.u_array.u_center12.u_region2_cols8_11.lane_out_valid,
                dut.u_array.u_center12.u_region2_cols8_11.guard_commit,
                dut.u_array.u_center12.u_region2_cols8_11.guard_valid,
                dut.u_array.u_center12.u_region2_cols8_11.accum_ready,
                dut.u_array.u_center12.u_region2_cols8_11.out_ready,
                dut.u_array.u_center12.u_region2_cols8_11.out_valid);
        if (cycle > 300000)
            fail("timeout");
        if (rst_n && error)
            fail("DUT sticky error asserted");
        if (project_done)
            project_done_count <= project_done_count + 1;
        if (activation_released)
            release_done_count <= release_done_count + 1;

        if (output_was_stalled) begin
            stable_output_checks <= stable_output_checks + 1;
            if (!out_valid || out_s24 !== held_output_s24 ||
                out_wave !== held_output_wave)
                fail("stalled output payload or wave changed");
        end
        output_was_stalled <= out_valid && !out_ready;
        if (out_valid && !out_ready) begin
            held_output_s24 <= out_s24;
            held_output_wave <= out_wave;
            output_stall_cycles <= output_stall_cycles + 1;
        end

        if (weight_was_stalled) begin
            stable_weight_checks <= stable_weight_checks + 1;
            if (!weight_valid || weight_group !== held_weight_group ||
                weight_s8 !== held_weight_s8 ||
                weight_meta16 !== held_weight_meta16)
                fail("stalled weight payload changed");
        end
        weight_was_stalled <= weight_valid && !weight_ready;
        if (weight_valid && !weight_ready) begin
            held_weight_group <= weight_group;
            held_weight_s8 <= weight_s8;
            held_weight_meta16 <= weight_meta16;
        end

        if (out_valid && out_ready) begin
            if (output_accepts >= 2)
                fail("extra output wave");
            if (out_wave !== output_accepts[0:0])
                fail("output wave order mismatch");
            if (out_s24 !== expected_mem[output_accepts])
                fail("cohort16 projection numerical mismatch");
            if (out_request_id !== REQUEST_ID ||
                out_cohort_id !== COHORT_ID || out_layer_id !== LAYER_ID ||
                out_op_id !== OP_ID || out_tile_id !== TILE_ID ||
                out_query_start !== QUERY_START ||
                out_valid_key_count !== VALID_KEY_COUNT)
                fail("output descriptor mismatch");
            output_accepts <= output_accepts + 1;
        end
    end

    always @(negedge clk) begin
        if (!rst_n || !output_phase)
            out_ready <= 1'b0;
        else if (output_stall_cycles < 4)
            out_ready <= 1'b0;
        else
            out_ready <= ((cycle % 9) != 2) && ((cycle % 17) != 6);
    end

    integer group;
    initial begin
        $readmemh("data/projection_core16x16_w8_reuse/input_wave0_s24.mem",
            input_wave0_mem);
        $readmemh("data/projection_core16x16_w8_reuse/input_wave1_s24.mem",
            input_wave1_mem);
        $readmemh("data/projection_core16x16_w8_reuse/weight_s8.mem",
            weight_mem);
        $readmemh("data/projection_core16x16_w8_reuse/weight_meta16.mem",
            weight_meta_mem);
        $readmemh("data/projection_core16x16_w8_reuse/expected_s24.mem",
            expected_mem);

        repeat (8) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        for (group = 0; group < GROUPS; group = group + 1)
            send_activation(0, group);
        for (group = 0; group < GROUPS; group = group + 1)
            send_activation(1, group);

        while (!activation_cached || !project_ready)
            @(posedge clk);
        @(negedge clk);
        project_start = 1'b1;
        @(posedge clk);
        if (!project_ready)
            fail("project_start was not accepted");
        @(negedge clk);
        project_start = 1'b0;
        output_phase = 1'b1;

        for (group = 0; group < GROUPS; group = group + 1)
            send_weight(group);

        while (output_accepts != 2)
            @(posedge clk);
        repeat (4) @(posedge clk);
        output_phase = 1'b0;

        if (activation_accepts != 256)
            fail("activation acceptance count mismatch");
        if (weight_accepts != 128 || accepted_weight_group_count != 128)
            fail("weight was not accepted exactly once per group");
        if (consumed_wave_group_count != 256)
            fail("one weight acceptance did not produce two wave consumes");
        if (dut.array_accumulated_group_count_unused != 256)
            fail("accumulator group count mismatch");
        if (released_weight_group_count != 128)
            fail("weight release count mismatch");
        if (output_wave_tile_count != 2 || output_accepts != 2)
            fail("output wave tile count mismatch");
        if (saturation_count != 0)
            fail("projection saturation count mismatch");
        if (dut.frontend_read_count_unused != 256)
            fail("activation cache read count mismatch");
        if (weight_fifo_high_watermark != 2)
            fail("depth-2 weight ping/pong was not exercised");
        if (project_done_count != 1)
            fail("project_done pulse count mismatch");
        if (output_stall_cycles == 0 || stable_output_checks == 0 ||
            stable_weight_checks == 0)
            fail("randomized backpressure coverage missing");

        while (!activation_release_ready)
            @(posedge clk);
        @(negedge clk);
        activation_release = 1'b1;
        @(posedge clk);
        @(negedge clk);
        activation_release = 1'b0;
        while (release_done_count != 1)
            @(posedge clk);
        repeat (3) @(posedge clk);
        if (activation_cached || project_ready)
            fail("dual activation bank release did not return to fill");

        $display("PROJECTION_CORE16_REUSE_METRIC_JSON: {\"weight_acceptances\":%0d,\"wave_consumptions\":%0d,\"weight_releases\":%0d,\"outputs\":%0d,\"fifo_high_watermark\":%0d,\"output_stall_cycles\":%0d,\"stable_output_checks\":%0d,\"stable_weight_checks\":%0d}",
            accepted_weight_group_count, consumed_wave_group_count,
            released_weight_group_count, output_wave_tile_count,
            weight_fifo_high_watermark, output_stall_cycles,
            stable_output_checks, stable_weight_checks);
        $display("PASS: cohort16 projection accepted 128 W8 groups, consumed 256 wave groups, returned bit-exact wave0/wave1 outputs and released both activation banks");
        $finish;
    end

endmodule
