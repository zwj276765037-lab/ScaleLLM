`timescale 1ns / 1ps

// One column shard of the Attention Wo/QKV tile accumulator.  Lanes never
// interact arithmetically, so partitioning the original 128-lane accumulator
// preserves the exact per-lane add order.  All three production shards are
// committed by one global event in hap_a8w8_array_16x16_s42_col3.
module hap_linear_tile_accum_shard_s42 #(
    parameter integer LANES = 16
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_first_group,
    input  wire                         in_last_group,
    input  wire signed [LANES*42-1:0]   in_guard_s42,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire [LANES*24-1:0]          out_s24,
    output reg  [31:0]                  input_group_count,
    output reg  [31:0]                  output_tile_count,
    output reg  [31:0]                  saturation_count,
    output reg                          error
);

    localparam integer COUNT8_GROUPS = LANES / 8;
    localparam integer COUNT32_GROUPS = (LANES + 31) / 32;
    // Four entries keep the final reduction identical in depth for the
    // 16/96/16 production shards.  Unused entries are tied to zero.
    localparam integer PAD8_GROUPS = COUNT32_GROUPS * 4;
    localparam integer PAD32_GROUPS = 4;

    reg signed [41:0] accum_s42_r [0:LANES-1];
    reg [LANES*24-1:0] out_s24_r;
    reg out_valid_r;
    reg finalize_pending_r;
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

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [LANES-1:0] in_fire_local;

    genvar input_control_lane;
    generate
        for (input_control_lane = 0; input_control_lane < LANES;
             input_control_lane = input_control_lane + 1) begin : g_input_control
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(in_fire),
                .O(in_fire_local[input_control_lane])
            );
        end
    endgenerate

    assign in_ready = rst_n && !clear && !finalize_pending_r &&
        (!out_valid_r || out_ready);
    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_s24 = out_s24_r;

    function automatic signed [23:0] round_sat_guard_s42_to_s24;
        input signed [41:0] value;
        reg [42:0] magnitude;
        reg [42:0] rounded_magnitude;
        reg signed [42:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[41], value});
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = $signed(rounded_magnitude);
            end
            if (rounded_value > 43'sd8388607)
                round_sat_guard_s42_to_s24 = 24'sh7f_ffff;
            else if (rounded_value < -43'sd8388608)
                round_sat_guard_s42_to_s24 = -24'sd8388608;
            else
                round_sat_guard_s42_to_s24 = rounded_value[23:0];
        end
    endfunction

    function automatic guard_s42_to_s24_saturates;
        input signed [41:0] value;
        reg [42:0] magnitude;
        reg [42:0] rounded_magnitude;
        reg signed [42:0] rounded_value;
        begin
            if (value < 0) begin
                magnitude = -$signed({value[41], value});
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = -$signed(rounded_magnitude);
            end else begin
                magnitude = {1'b0, value};
                rounded_magnitude = (magnitude + 43'd128) >> 8;
                rounded_value = $signed(rounded_magnitude);
            end
            guard_s42_to_s24_saturates =
                (rounded_value > 43'sd8388607) ||
                (rounded_value < -43'sd8388608);
        end
    endfunction

    genvar accum_lane;
    generate
        for (accum_lane = 0; accum_lane < LANES;
             accum_lane = accum_lane + 1) begin : g_accum_lane
            wire signed [42:0] lane_sum_ext =
                (in_first_group ? 43'sd0 :
                    $signed({accum_s42_r[accum_lane][41],
                             accum_s42_r[accum_lane]})) +
                $signed({in_guard_s42[accum_lane*42+41],
                         in_guard_s42[accum_lane*42 +: 42]});
            wire signed [41:0] lane_sum_s42 = lane_sum_ext[41:0];

            always @(posedge clk) begin
                if (!rst_n || clear) begin
                    overflow_flags_r[accum_lane] <= 1'b0;
                end else if (in_fire_local[accum_lane]) begin
                    accum_s42_r[accum_lane] <= lane_sum_s42;
                    overflow_flags_r[accum_lane] <=
                        lane_sum_ext[42] != lane_sum_ext[41];
                end
                if (finalize_pending_r) begin
                    out_s24_r[accum_lane*24 +: 24] <=
                        round_sat_guard_s42_to_s24(
                            accum_s42_r[accum_lane]);
                    saturation_flags_r[accum_lane] <=
                        guard_s42_to_s24_saturates(
                            accum_s42_r[accum_lane]);
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
                            {2'd0, saturation_count8_r[count32_group*4+0]} +
                            {2'd0, saturation_count8_r[count32_group*4+1]} +
                            {2'd0, saturation_count8_r[count32_group*4+2]} +
                            {2'd0, saturation_count8_r[count32_group*4+3]};
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

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            saturation_flags_valid_r <= 1'b0;
            saturation_count8_valid_r <= 1'b0;
            saturation_count32_valid_r <= 1'b0;
            saturation_total_valid_r <= 1'b0;
            saturation_count <= 32'd0;
        end else if (clear) begin
            saturation_flags_valid_r <= 1'b0;
            saturation_count8_valid_r <= 1'b0;
            saturation_count32_valid_r <= 1'b0;
            saturation_total_valid_r <= 1'b0;
            saturation_count <= 32'd0;
        end else begin
            saturation_flags_valid_r <= finalize_pending_r;
            saturation_count8_valid_r <= saturation_flags_valid_r;
            saturation_count32_valid_r <= saturation_count8_valid_r;
            saturation_total_valid_r <= saturation_count32_valid_r;
            if (saturation_total_valid_r)
                saturation_count <= saturation_count + saturation_total_r;
        end
    end

    integer overflow_group;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid_r <= 1'b0;
            finalize_pending_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            error <= 1'b0;
        end else if (clear) begin
            out_valid_r <= 1'b0;
            finalize_pending_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            error <= 1'b0;
        end else begin
            finalize_pending_r <= in_fire && in_last_group;
            // overflow_flags_r is written on the in_fire edge.  Qualify both
            // reduction stages so reset-like clear cannot replay stale flag
            // contents into the sticky error pipeline on later idle cycles.
            overflow_flags_valid_r <= in_fire;
            overflow_any8_valid_r <= overflow_flags_valid_r;
            overflow_any_valid_r <= overflow_any8_valid_r;
            if (overflow_flags_valid_r)
                for (overflow_group = 0; overflow_group < COUNT8_GROUPS;
                     overflow_group = overflow_group + 1)
                    overflow_any8_r[overflow_group] <=
                        |overflow_flags_r[overflow_group*8 +: 8];
            if (overflow_any8_valid_r)
                overflow_any_r <= |overflow_any8_r;
            if (overflow_any_valid_r && overflow_any_r)
                error <= 1'b1;
            if (out_fire) begin
                out_valid_r <= 1'b0;
                output_tile_count <= output_tile_count + 32'd1;
            end
            if (finalize_pending_r)
                out_valid_r <= 1'b1;
            if (in_fire)
                input_group_count <= input_group_count + 32'd1;
        end
    end

    initial begin
        if (LANES != 16 && LANES != 32 && LANES != 96)
            $error("hap_linear_tile_accum_shard_s42 LANES must be 16, 32, or 96");
        if ((LANES % 8) != 0)
            $error("hap_linear_tile_accum_shard_s42 LANES must divide into groups of 8");
    end

endmodule
