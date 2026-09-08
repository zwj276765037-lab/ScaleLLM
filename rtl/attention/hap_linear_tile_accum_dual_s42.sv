`timescale 1ns / 1ps

// Two local accumulator banks share one add/round/saturation datapath.  The
// banks accept alternating wave0/wave1 groups and retain independent S42
// state, while completed outputs retire in deterministic wave0 then wave1
// order.  No projection DSP lane is duplicated.
module hap_linear_tile_accum_dual_s42 #(
    parameter integer LANES = 16
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_wave,
    input  wire                         in_first_group,
    input  wire                         in_last_group,
    input  wire signed [LANES*42-1:0]   in_guard_s42,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire                         out_wave,
    output wire [LANES*24-1:0]          out_s24,
    output reg  [31:0]                  input_group_count,
    output reg  [31:0]                  output_tile_count,
    output reg  [31:0]                  saturation_count,
    output wire                         error
);

    localparam integer COUNT8_GROUPS = LANES / 8;
    localparam integer COUNT32_GROUPS = (LANES + 31) / 32;
    localparam integer PAD8_GROUPS = COUNT32_GROUPS * 4;
    localparam integer PAD32_GROUPS = 4;
    localparam integer FINALIZE_LANES = 8;
    // Production 16- and 32-lane shards finish in the same four cycles so
    // every physical shard remains lockstep. The legacy 96-lane shape uses
    // all twelve natural groups.
    localparam integer FINALIZE_GROUPS =
        (LANES <= 32) ? 4 : (LANES / FINALIZE_LANES);
    localparam integer FINALIZE_GROUP_W = $clog2(FINALIZE_GROUPS);

    reg signed [41:0] wave0_accum_s42_r [0:LANES-1];
    reg signed [41:0] wave1_accum_s42_r [0:LANES-1];
    reg [LANES*24-1:0] wave0_out_s24_r;
    reg [LANES*24-1:0] wave1_out_s24_r;
    reg wave0_out_valid_r;
    reg wave1_out_valid_r;

    reg expected_input_wave_r;
    reg expected_output_wave_r;
    reg finalize_active_r;
    reg [FINALIZE_GROUP_W-1:0] finalize_group_r;
    reg finalize_wave_r;
    reg control_error_r;

    reg [LANES-1:0] saturation_flags_r;
    reg [3:0] saturation_count8_r [0:PAD8_GROUPS-1];
    reg [5:0] saturation_count32_r [0:PAD32_GROUPS-1];
    reg [7:0] saturation_total_r;
    reg saturation_flags_valid_r;
    reg saturation_count8_valid_r;
    reg saturation_count32_valid_r;
    reg saturation_total_valid_r;

    (* DONT_TOUCH = "yes" *) reg [LANES-1:0] overflow_flags_r;
    reg [COUNT8_GROUPS-1:0] overflow_any8_r;
    reg overflow_any_r;
    reg overflow_flags_valid_r;
    reg overflow_any8_valid_r;
    reg overflow_any_valid_r;

    wire input_sequence_legal = in_wave == expected_input_wave_r;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire selected_output_slot_empty = in_wave ?
        !wave1_out_valid_r : !wave0_out_valid_r;
    wire selected_output_slot_retires = out_fire &&
        (expected_output_wave_r == in_wave);
    wire selected_context_available =
        selected_output_slot_empty || selected_output_slot_retires;

    assign in_ready = rst_n && !clear && !control_error_r &&
        !finalize_active_r && input_sequence_legal &&
        selected_context_available;
    assign out_valid = rst_n && !clear &&
        (expected_output_wave_r ? wave1_out_valid_r : wave0_out_valid_r);
    assign out_wave = expected_output_wave_r;
    assign out_s24 = expected_output_wave_r ?
        wave1_out_s24_r : wave0_out_s24_r;
    assign error = control_error_r;

    function automatic signed [42:0] round_guard_s42_to_s43;
        input signed [41:0] value;
        reg [42:0] magnitude;
        reg [42:0] rounded_magnitude;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[41], value});
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                round_guard_s42_to_s43 = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                round_guard_s42_to_s43 = $signed(rounded_magnitude);
            end
        end
    endfunction

    genvar accum_lane;
    generate
        for (accum_lane = 0; accum_lane < LANES;
             accum_lane = accum_lane + 1) begin : g_accum_lane
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            wire wave0_write_enable;
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            wire wave1_write_enable;

            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT2 #(.INIT(4'h2)) u_wave0_write_enable (
                .I0(in_fire), .I1(in_wave), .O(wave0_write_enable)
            );
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT2 #(.INIT(4'h8)) u_wave1_write_enable (
                .I0(in_fire), .I1(in_wave), .O(wave1_write_enable)
            );

            wire signed [41:0] selected_accum_s42 =
                wave1_write_enable ?
                wave1_accum_s42_r[accum_lane] :
                wave0_accum_s42_r[accum_lane];
            wire signed [42:0] lane_sum_ext =
                (in_first_group ? 43'sd0 :
                    $signed({selected_accum_s42[41],
                             selected_accum_s42})) +
                $signed({in_guard_s42[accum_lane*42+41],
                         in_guard_s42[accum_lane*42 +: 42]});
            wire signed [41:0] lane_sum_s42 = lane_sum_ext[41:0];

            always @(posedge clk) begin
                if (!rst_n || clear) begin
                    overflow_flags_r[accum_lane] <= 1'b0;
                end else if (wave0_write_enable ||
                             wave1_write_enable) begin
                    if (wave1_write_enable)
                        wave1_accum_s42_r[accum_lane] <= lane_sum_s42;
                    else
                        wave0_accum_s42_r[accum_lane] <= lane_sum_s42;
                    overflow_flags_r[accum_lane] <=
                        lane_sum_ext[42] != lane_sum_ext[41];
                end
            end
        end
    endgenerate

    // Finalization is cold relative to the group pipeline: it runs once per
    // 128 groups. The production 16-lane shards use eight static lanes and
    // the 32-lane shards use sixteen static lanes. Both finish useful work in
    // two cycles and retain two idle cycles so every shard stays lockstep.
    genvar finalize_slot16;
    genvar finalize_slot32;
    genvar finalize_slot96;
    generate
        if (LANES == 16) begin : g_finalize_lanes16
            for (finalize_slot16 = 0;
                 finalize_slot16 < FINALIZE_LANES;
                 finalize_slot16 = finalize_slot16 + 1) begin : g_slot
                wire signed [41:0] selected_finalize_accum_s42 =
                    finalize_wave_r ?
                    (finalize_group_r[0] ?
                        wave1_accum_s42_r[finalize_slot16+8] :
                        wave1_accum_s42_r[finalize_slot16]) :
                    (finalize_group_r[0] ?
                        wave0_accum_s42_r[finalize_slot16+8] :
                        wave0_accum_s42_r[finalize_slot16]);
                wire signed [42:0] rounded_s43 =
                    round_guard_s42_to_s43(selected_finalize_accum_s42);
                wire saturates = (rounded_s43 > 43'sd8388607) ||
                    (rounded_s43 < -43'sd8388608);
                wire signed [23:0] rounded_s24 =
                    (rounded_s43 > 43'sd8388607) ? 24'sh7f_ffff :
                    (rounded_s43 < -43'sd8388608) ?
                        -24'sd8388608 : rounded_s43[23:0];

                always @(posedge clk) begin
                    if (finalize_active_r && finalize_group_r == 0) begin
                        if (finalize_wave_r)
                            wave1_out_s24_r[finalize_slot16*24 +: 24] <=
                                rounded_s24;
                        else
                            wave0_out_s24_r[finalize_slot16*24 +: 24] <=
                                rounded_s24;
                        saturation_flags_r[finalize_slot16] <= saturates;
                    end else if (finalize_active_r &&
                                 finalize_group_r == 1) begin
                        if (finalize_wave_r)
                            wave1_out_s24_r[(finalize_slot16+8)*24 +: 24] <=
                                rounded_s24;
                        else
                            wave0_out_s24_r[(finalize_slot16+8)*24 +: 24] <=
                                rounded_s24;
                        saturation_flags_r[finalize_slot16+8] <= saturates;
                    end
                end
            end
        end else if (LANES == 32) begin : g_finalize_lanes32
            for (finalize_slot32 = 0; finalize_slot32 < 16;
                 finalize_slot32 = finalize_slot32 + 1) begin : g_slot
                wire signed [41:0] selected_finalize_accum_s42 =
                    finalize_wave_r ?
                    (finalize_group_r[0] ?
                        wave1_accum_s42_r[finalize_slot32+16] :
                        wave1_accum_s42_r[finalize_slot32]) :
                    (finalize_group_r[0] ?
                        wave0_accum_s42_r[finalize_slot32+16] :
                        wave0_accum_s42_r[finalize_slot32]);
                wire signed [42:0] rounded_s43 =
                    round_guard_s42_to_s43(selected_finalize_accum_s42);
                wire saturates = (rounded_s43 > 43'sd8388607) ||
                    (rounded_s43 < -43'sd8388608);
                wire signed [23:0] rounded_s24 =
                    (rounded_s43 > 43'sd8388607) ? 24'sh7f_ffff :
                    (rounded_s43 < -43'sd8388608) ?
                        -24'sd8388608 : rounded_s43[23:0];

                always @(posedge clk) begin
                    if (finalize_active_r && finalize_group_r == 0) begin
                        if (finalize_wave_r)
                            wave1_out_s24_r[finalize_slot32*24 +: 24] <=
                                rounded_s24;
                        else
                            wave0_out_s24_r[finalize_slot32*24 +: 24] <=
                                rounded_s24;
                        saturation_flags_r[finalize_slot32] <= saturates;
                    end else if (finalize_active_r &&
                                 finalize_group_r == 1) begin
                        if (finalize_wave_r)
                            wave1_out_s24_r[(finalize_slot32+16)*24 +: 24] <=
                                rounded_s24;
                        else
                            wave0_out_s24_r[(finalize_slot32+16)*24 +: 24] <=
                                rounded_s24;
                        saturation_flags_r[finalize_slot32+16] <= saturates;
                    end
                end
            end
        end else begin : g_finalize_lanes96
            for (finalize_slot96 = 0;
                 finalize_slot96 < FINALIZE_LANES;
                 finalize_slot96 = finalize_slot96 + 1) begin : g_slot
                wire [FINALIZE_GROUP_W+2:0] finalize_lane =
                    {finalize_group_r, 3'b000} + finalize_slot96;
                wire signed [41:0] selected_finalize_accum_s42 =
                    finalize_wave_r ? wave1_accum_s42_r[finalize_lane] :
                        wave0_accum_s42_r[finalize_lane];
                wire signed [42:0] rounded_s43 =
                    round_guard_s42_to_s43(selected_finalize_accum_s42);
                wire saturates = (rounded_s43 > 43'sd8388607) ||
                    (rounded_s43 < -43'sd8388608);
                wire signed [23:0] rounded_s24 =
                    (rounded_s43 > 43'sd8388607) ? 24'sh7f_ffff :
                    (rounded_s43 < -43'sd8388608) ?
                        -24'sd8388608 : rounded_s43[23:0];

                always @(posedge clk) begin
                    if (finalize_active_r) begin
                        if (finalize_wave_r)
                            wave1_out_s24_r[finalize_lane*24 +: 24] <=
                                rounded_s24;
                        else
                            wave0_out_s24_r[finalize_lane*24 +: 24] <=
                                rounded_s24;
                        saturation_flags_r[finalize_lane] <= saturates;
                    end
                end
            end
        end
    endgenerate

    genvar count8_group;
    generate
        for (count8_group = 0; count8_group < PAD8_GROUPS;
             count8_group = count8_group + 1) begin : g_count8
            if (count8_group < COUNT8_GROUPS) begin : g_active
                always @(posedge clk) begin
                    if (saturation_flags_valid_r)
                        saturation_count8_r[count8_group] <=
                            {3'd0, saturation_flags_r[count8_group*8+0]} +
                            {3'd0, saturation_flags_r[count8_group*8+1]} +
                            {3'd0, saturation_flags_r[count8_group*8+2]} +
                            {3'd0, saturation_flags_r[count8_group*8+3]} +
                            {3'd0, saturation_flags_r[count8_group*8+4]} +
                            {3'd0, saturation_flags_r[count8_group*8+5]} +
                            {3'd0, saturation_flags_r[count8_group*8+6]} +
                            {3'd0, saturation_flags_r[count8_group*8+7]};
                end
            end else begin : g_padding
                always @(posedge clk)
                    if (saturation_flags_valid_r)
                        saturation_count8_r[count8_group] <= 4'd0;
            end
        end
    endgenerate

    genvar count32_group;
    generate
        for (count32_group = 0; count32_group < PAD32_GROUPS;
             count32_group = count32_group + 1) begin : g_count32
            if (count32_group < COUNT32_GROUPS) begin : g_active
                always @(posedge clk) begin
                    if (saturation_count8_valid_r)
                        saturation_count32_r[count32_group] <=
                            {2'd0, saturation_count8_r[
                                count32_group*4+0]} +
                            {2'd0, saturation_count8_r[
                                count32_group*4+1]} +
                            {2'd0, saturation_count8_r[
                                count32_group*4+2]} +
                            {2'd0, saturation_count8_r[
                                count32_group*4+3]};
                end
            end else begin : g_padding
                always @(posedge clk)
                    if (saturation_count8_valid_r)
                        saturation_count32_r[count32_group] <= 6'd0;
            end
        end
    endgenerate

    always @(posedge clk) begin
        if (saturation_count32_valid_r)
            saturation_total_r <=
                {2'd0, saturation_count32_r[0]} +
                {2'd0, saturation_count32_r[1]} +
                {2'd0, saturation_count32_r[2]} +
                {2'd0, saturation_count32_r[3]};
    end

    integer overflow_group;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            saturation_flags_valid_r <= 1'b0;
            saturation_count8_valid_r <= 1'b0;
            saturation_count32_valid_r <= 1'b0;
            saturation_total_valid_r <= 1'b0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            saturation_count <= 32'd0;
        end else if (clear) begin
            saturation_flags_valid_r <= 1'b0;
            saturation_count8_valid_r <= 1'b0;
            saturation_count32_valid_r <= 1'b0;
            saturation_total_valid_r <= 1'b0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            saturation_count <= 32'd0;
        end else begin
            saturation_flags_valid_r <= finalize_active_r &&
                (finalize_group_r == FINALIZE_GROUPS-1);
            saturation_count8_valid_r <= saturation_flags_valid_r;
            saturation_count32_valid_r <= saturation_count8_valid_r;
            saturation_total_valid_r <= saturation_count32_valid_r;
            if (saturation_total_valid_r)
                saturation_count <= saturation_count + saturation_total_r;

            overflow_flags_valid_r <= in_fire;
            overflow_any8_valid_r <= overflow_flags_valid_r;
            overflow_any_valid_r <= overflow_any8_valid_r;
            if (overflow_flags_valid_r)
                for (overflow_group = 0;
                     overflow_group < COUNT8_GROUPS;
                     overflow_group = overflow_group + 1)
                    overflow_any8_r[overflow_group] <=
                        |overflow_flags_r[overflow_group*8 +: 8];
            if (overflow_any8_valid_r)
                overflow_any_r <= |overflow_any8_r;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            expected_input_wave_r <= 1'b0;
            expected_output_wave_r <= 1'b0;
            finalize_active_r <= 1'b0;
            finalize_group_r <= '0;
            finalize_wave_r <= 1'b0;
            wave0_out_valid_r <= 1'b0;
            wave1_out_valid_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            expected_input_wave_r <= 1'b0;
            expected_output_wave_r <= 1'b0;
            finalize_active_r <= 1'b0;
            finalize_group_r <= '0;
            finalize_wave_r <= 1'b0;
            wave0_out_valid_r <= 1'b0;
            wave1_out_valid_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (in_fire) begin
                expected_input_wave_r <= ~expected_input_wave_r;
                input_group_count <= input_group_count + 32'd1;
                if (in_last_group) begin
                    finalize_active_r <= 1'b1;
                    finalize_group_r <= '0;
                    finalize_wave_r <= in_wave;
                end
            end else if (finalize_active_r) begin
                if (finalize_group_r == FINALIZE_GROUPS-1)
                    finalize_active_r <= 1'b0;
                else
                    finalize_group_r <= finalize_group_r + 1'b1;
            end

            if (out_fire) begin
                if (expected_output_wave_r)
                    wave1_out_valid_r <= 1'b0;
                else
                    wave0_out_valid_r <= 1'b0;
                expected_output_wave_r <= ~expected_output_wave_r;
                output_tile_count <= output_tile_count + 32'd1;
            end

            if (finalize_active_r &&
                finalize_group_r == FINALIZE_GROUPS-1) begin
                if (finalize_wave_r) begin
                    if (wave1_out_valid_r &&
                        !(out_fire && expected_output_wave_r))
                        control_error_r <= 1'b1;
                    wave1_out_valid_r <= 1'b1;
                end else begin
                    if (wave0_out_valid_r &&
                        !(out_fire && !expected_output_wave_r))
                        control_error_r <= 1'b1;
                    wave0_out_valid_r <= 1'b1;
                end
            end

            if (in_valid && !input_sequence_legal)
                control_error_r <= 1'b1;
            if (overflow_any_valid_r && overflow_any_r)
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if (LANES != 16 && LANES != 32 && LANES != 96)
            $error("hap_linear_tile_accum_dual_s42 illegal LANES");
        if ((LANES % 8) != 0)
            $error("hap_linear_tile_accum_dual_s42 LANES must divide by 8");
    end

endmodule
