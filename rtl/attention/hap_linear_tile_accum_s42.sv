`timescale 1ns / 1ps

module hap_linear_tile_accum_s42 #(
    parameter integer LANES = 256
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

    reg signed [41:0] accum_s42_r [0:LANES-1];
    reg [LANES*24-1:0] out_s24_r;
    reg out_valid_r;
    // Keep the last-group add and the S42 -> S24 round/saturate in separate
    // cycles.  Besides shortening the arithmetic chain, finalize_pending_r
    // deliberately blocks one accumulator acceptance cycle so a finalized
    // tile can never overwrite a stalled output.  The array lane itself has
    // II=2, so this does not reduce its steady group acceptance rate.
    reg finalize_pending_r;
    reg [LANES-1:0] saturation_flags_r;
    reg [3:0] saturation_count8_r [0:15];
    reg [5:0] saturation_count32_r [0:3];
    reg [7:0] saturation_total_r;
    reg saturation_flags_valid_r;
    reg saturation_count8_valid_r;
    reg saturation_count32_valid_r;
    reg saturation_total_valid_r;
    // Overflow is diagnostic-only, but the former implementation rebuilt all
    // 128 adders in a second loop and ORed them directly into one sticky FF.
    // That made lane FIFO data cross an SLR and traverse the wide reduction in
    // one cycle.  Capture one flag beside each accumulator lane, then reduce
    // 8 lanes at a time before updating the sticky error.  The arithmetic and
    // valid/ready path are untouched; only error observation is pipelined.
    (* DONT_TOUCH = "yes" *) reg [LANES-1:0] overflow_flags_r;
    reg [LANES/8-1:0] overflow_any8_r;
    reg overflow_any_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    // The old placed netlist merged accumulator write controls into one
    // 4645-load data net (`accum_s42_r[0]`) and promoted it to BUFG.  Give
    // every 42-bit lane one protected combinational enable boundary.  The
    // common in_fire drives 128 LUT inputs rather than thousands of FF pins;
    // each LUT output drives exactly one lane's 42 accumulator bits plus its
    // overflow flag.  This is not a pipeline stage and preserves the group
    // acceptance/finalization schedule.
    wire [LANES-1:0] in_fire_local;
    genvar input_control_lane;
    generate
        for (input_control_lane = 0; input_control_lane < LANES;
             input_control_lane = input_control_lane + 1) begin : g_input_control
            (* DONT_TOUCH = "yes" *)
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

    // Give every lane its own named combinational sum and sequential process.
    // A procedural for-loop with shared temporary regs lets synthesis create a
    // common intermediate driver; in this 128-lane instance that became a
    // 4476-load network.  The generate form makes lane locality structural.
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

    integer lane;
    always @(posedge clk) begin
        if (saturation_flags_valid_r) begin
            for (lane = 0; lane < 16; lane = lane + 1) begin
                saturation_count8_r[lane] <=
                    {3'd0, saturation_flags_r[lane*8+0]} +
                    {3'd0, saturation_flags_r[lane*8+1]} +
                    {3'd0, saturation_flags_r[lane*8+2]} +
                    {3'd0, saturation_flags_r[lane*8+3]} +
                    {3'd0, saturation_flags_r[lane*8+4]} +
                    {3'd0, saturation_flags_r[lane*8+5]} +
                    {3'd0, saturation_flags_r[lane*8+6]} +
                    {3'd0, saturation_flags_r[lane*8+7]};
            end
        end
        if (saturation_count8_valid_r) begin
            for (lane = 0; lane < 4; lane = lane + 1) begin
                saturation_count32_r[lane] <=
                    {2'd0, saturation_count8_r[lane*4+0]} +
                    {2'd0, saturation_count8_r[lane*4+1]} +
                    {2'd0, saturation_count8_r[lane*4+2]} +
                    {2'd0, saturation_count8_r[lane*4+3]};
            end
        end
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
            error <= 1'b0;
        end else if (clear) begin
            out_valid_r <= 1'b0;
            finalize_pending_r <= 1'b0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            error <= 1'b0;
        end else begin
            finalize_pending_r <= in_fire && in_last_group;
            for (overflow_group = 0; overflow_group < LANES/8;
                 overflow_group = overflow_group + 1)
                overflow_any8_r[overflow_group] <=
                    |overflow_flags_r[overflow_group*8 +: 8];
            overflow_any_r <= |overflow_any8_r;
            if (overflow_any_r)
                error <= 1'b1;
            if (out_fire) begin
                out_valid_r <= 1'b0;
                output_tile_count <= output_tile_count + 32'd1;
            end
            if (finalize_pending_r)
                out_valid_r <= 1'b1;
            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
            end
        end
    end

    initial begin
        if (LANES != 128)
            $error("hap_linear_tile_accum_s42 production LANES must be 128");
    end

endmodule
