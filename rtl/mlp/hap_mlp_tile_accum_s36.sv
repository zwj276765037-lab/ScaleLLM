`timescale 1ns / 1ps

// Local projection accumulator for one physical 8x16 slice.
//
// The production configurations are:
//   gate/up: ACC_W=43, GROUPS=128, S43 Q19.24
//   down:    ACC_W=45, GROUPS=448, S45 Q21.24
//
// Contributions remain S36 Q12.24 and are accumulated without per-group
// rounding or saturation.  Only a completed tile is rounded half away from
// zero by 2^8 and saturated to the S24 Q8.16 projection boundary.
module hap_mlp_tile_accum_s36 #(
    parameter integer LANES = 128,
    parameter integer ACC_W = 43,
    parameter integer GROUPS = 128,
    // The production V4 contract remains 128 lanes.  V5's independently
    // verified 8x12 leaf has 96 row-major lanes; only its explicit wrapper
    // enables this parameter while the 48-column scheduler is integrated.
    parameter integer ALLOW_V5_96_LANES = 0
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_first_group,
    input  wire                         in_last_group,
    input  wire signed [LANES*36-1:0]   in_guard_s36,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [LANES*24-1:0]   out_projection_s24,
    output reg  [31:0]                  input_group_count,
    output reg  [31:0]                  output_tile_count,
    output reg  [31:0]                  saturation_count,
    output reg                          error
);

    localparam integer GROUP_INDEX_W = $clog2(GROUPS);
    localparam integer CONTROL_BANKS =
        (LANES == 192) ? 16 : 8;
    localparam integer LANES_PER_CONTROL_BANK = LANES/CONTROL_BANKS;
    reg signed [ACC_W-1:0] accum_r [0:LANES-1];
    reg signed [LANES*24-1:0] out_projection_s24_r;
    reg out_valid_r;
    // Functional row/bank-local finalize owners.  The old single pending bit
    // updated all LANES*24 projection registers and became two data-BUFG
    // trees in each V5 branch.  These cycle-aligned protocol bits limit each
    // finalization predicate to one physical row (288 bits for LANES=96).
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [CONTROL_BANKS-1:0] finalize_pending_bank_r;
    reg [GROUP_INDEX_W-1:0] group_index_r;
    reg [LANES-1:0] overflow_flags_r;
    reg [LANES-1:0] saturation_flags_r;
    reg [LANES/8-1:0] overflow_any8_r;
    reg overflow_any_r;
    // overflow_flags_r is resetless telemetry payload, just like accum_r.
    // Explicit validity stages prevent its retained/unknown contents from
    // leaking back into sticky error after reset or a maintenance clear.
    reg overflow_flags_valid_r;
    reg overflow_any8_valid_r;
    reg overflow_any_valid_r;
    localparam integer SAT8_BLOCKS = LANES/8;
    localparam integer SAT32_BLOCKS = LANES/32;
    reg [3:0] saturation_count8_r [0:SAT8_BLOCKS-1];
    reg [5:0] saturation_count32_r [0:SAT32_BLOCKS-1];
    reg [7:0] saturation_total_r;
    reg saturation_flags_valid_r;
    reg saturation_count8_valid_r;
    reg saturation_count32_valid_r;
    reg saturation_total_valid_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [CONTROL_BANKS-1:0] accum_write_enable;
    assign in_ready = rst_n && !clear &&
        !(|finalize_pending_bank_r) &&
        (!out_valid_r || out_ready);
    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_projection_s24 = out_projection_s24_r;

    function automatic signed [23:0] round_sat_acc_to_s24;
        input signed [ACC_W-1:0] value;
        reg signed [ACC_W:0] extended;
        reg [ACC_W:0] magnitude;
        reg signed [ACC_W:0] rounded;
        begin
            extended = {value[ACC_W-1], value};
            if (value < 0) begin
                magnitude = -extended;
                rounded = -$signed((magnitude + 128) >> 8);
            end else begin
                rounded = (extended + 128) >>> 8;
            end
            if (rounded > 8388607)
                round_sat_acc_to_s24 = 24'sh7f_ffff;
            else if (rounded < -8388608)
                round_sat_acc_to_s24 = -24'sd8388608;
            else
                round_sat_acc_to_s24 = rounded[23:0];
        end
    endfunction

    function automatic acc_to_s24_saturates;
        input signed [ACC_W-1:0] value;
        reg signed [ACC_W:0] extended;
        reg [ACC_W:0] magnitude;
        reg signed [ACC_W:0] rounded;
        begin
            extended = {value[ACC_W-1], value};
            if (value < 0) begin
                magnitude = -extended;
                rounded = -$signed((magnitude + 128) >> 8);
            end else begin
                rounded = (extended + 128) >>> 8;
            end
            acc_to_s24_saturates =
                (rounded > 8388607) || (rounded < -8388608);
        end
    endfunction

    genvar control_bank;
    generate
        for (control_bank = 0; control_bank < CONTROL_BANKS;
             control_bank = control_bank + 1) begin : gen_write_control
            // Protect the output net as well as the LUT.  Each bank owns one
            // physical row of accumulator state (516 FFs for a V5 8x12 leaf).
            (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
            u_accum_write_enable (
                .I0(in_fire),
                .O(accum_write_enable[control_bank])
            );
        end
    endgenerate

    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin : gen_lane
            localparam integer CONTROL_BANK =
                lane/LANES_PER_CONTROL_BANK;
            wire signed [ACC_W:0] lane_acc_ext =
                $signed({accum_r[lane][ACC_W-1], accum_r[lane]});
            wire signed [ACC_W:0] lane_guard_ext =
                $signed({{(ACC_W-35){in_guard_s36[lane*36+35]}},
                    in_guard_s36[lane*36 +: 36]});
            wire signed [ACC_W:0] lane_sum_ext =
                (in_first_group ? '0 : lane_acc_ext) + lane_guard_ext;

            always @(posedge clk) begin
                if (rst_n && !clear) begin
                    if (accum_write_enable[CONTROL_BANK]) begin
                        accum_r[lane] <= lane_sum_ext[ACC_W-1:0];
                        overflow_flags_r[lane] <=
                            lane_sum_ext[ACC_W] != lane_sum_ext[ACC_W-1];
                    end
                    if (finalize_pending_bank_r[CONTROL_BANK]) begin
                        out_projection_s24_r[lane*24 +: 24] <=
                            round_sat_acc_to_s24(accum_r[lane]);
                        saturation_flags_r[lane] <=
                            acc_to_s24_saturates(accum_r[lane]);
                    end
                end
            end
        end
    endgenerate

    integer group8;
    integer sat_group;
    always @(posedge clk) begin
        if (saturation_flags_valid_r) begin
            for (sat_group = 0; sat_group < SAT8_BLOCKS;
                 sat_group = sat_group + 1)
                saturation_count8_r[sat_group] <=
                    {3'd0, saturation_flags_r[sat_group*8+0]} +
                    {3'd0, saturation_flags_r[sat_group*8+1]} +
                    {3'd0, saturation_flags_r[sat_group*8+2]} +
                    {3'd0, saturation_flags_r[sat_group*8+3]} +
                    {3'd0, saturation_flags_r[sat_group*8+4]} +
                    {3'd0, saturation_flags_r[sat_group*8+5]} +
                    {3'd0, saturation_flags_r[sat_group*8+6]} +
                    {3'd0, saturation_flags_r[sat_group*8+7]};
        end
        if (saturation_count8_valid_r) begin
            for (sat_group = 0; sat_group < SAT32_BLOCKS;
                 sat_group = sat_group + 1)
                saturation_count32_r[sat_group] <=
                    {2'd0, saturation_count8_r[sat_group*4+0]} +
                    {2'd0, saturation_count8_r[sat_group*4+1]} +
                    {2'd0, saturation_count8_r[sat_group*4+2]} +
                    {2'd0, saturation_count8_r[sat_group*4+3]};
        end
        if (saturation_count32_valid_r)
            if (LANES == 96)
                saturation_total_r <=
                    {2'd0, saturation_count32_r[0]} +
                    {2'd0, saturation_count32_r[1]} +
                    {2'd0, saturation_count32_r[2]};
            else if (LANES == 192)
                saturation_total_r <=
                    {2'd0, saturation_count32_r[0]} +
                    {2'd0, saturation_count32_r[1]} +
                    {2'd0, saturation_count32_r[2]} +
                    {2'd0, saturation_count32_r[3]} +
                    {2'd0, saturation_count32_r[4]} +
                    {2'd0, saturation_count32_r[5]};
            else
                saturation_total_r <=
                    {2'd0, saturation_count32_r[0]} +
                    {2'd0, saturation_count32_r[1]} +
                    {2'd0, saturation_count32_r[2]} +
                    {2'd0, saturation_count32_r[3]};
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            out_valid_r <= 1'b0;
            finalize_pending_bank_r <= '0;
            group_index_r <= '0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            saturation_count <= 32'd0;
            saturation_flags_valid_r <= 1'b0;
            saturation_count8_valid_r <= 1'b0;
            saturation_count32_valid_r <= 1'b0;
            saturation_total_valid_r <= 1'b0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            error <= 1'b0;
        end else if (clear) begin
            out_valid_r <= 1'b0;
            finalize_pending_bank_r <= '0;
            group_index_r <= '0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            saturation_count <= 32'd0;
            saturation_flags_valid_r <= 1'b0;
            saturation_count8_valid_r <= 1'b0;
            saturation_count32_valid_r <= 1'b0;
            saturation_total_valid_r <= 1'b0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            error <= 1'b0;
        end else begin
            finalize_pending_bank_r <=
                {CONTROL_BANKS{in_fire && in_last_group}};
            saturation_flags_valid_r <= finalize_pending_bank_r[0];
            saturation_count8_valid_r <= saturation_flags_valid_r;
            saturation_count32_valid_r <= saturation_count8_valid_r;
            saturation_total_valid_r <= saturation_count32_valid_r;
            if (out_fire) begin
                out_valid_r <= 1'b0;
                output_tile_count <= output_tile_count + 32'd1;
            end
            if (finalize_pending_bank_r[0])
                out_valid_r <= 1'b1;
            if (saturation_total_valid_r)
                saturation_count <= saturation_count +
                    saturation_total_r;

            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
                if (in_first_group != (group_index_r == 0) ||
                    in_last_group != (group_index_r == GROUPS-1))
                    error <= 1'b1;
                if (in_last_group)
                    group_index_r <= '0;
                else
                    group_index_r <= group_index_r + 1'b1;
            end

            overflow_flags_valid_r <= in_fire;
            overflow_any8_valid_r <= overflow_flags_valid_r;
            overflow_any_valid_r <= overflow_any8_valid_r;
            if (overflow_flags_valid_r)
                for (group8 = 0; group8 < LANES/8; group8 = group8 + 1)
                    overflow_any8_r[group8] <=
                        |overflow_flags_r[group8*8 +: 8];
            if (overflow_any8_valid_r)
                overflow_any_r <= |overflow_any8_r;
            if (overflow_any_valid_r && overflow_any_r)
                error <= 1'b1;
        end
    end

    initial begin
        if (LANES != 128 &&
            !(ALLOW_V5_96_LANES == 1 && LANES == 96) &&
            !(ALLOW_V5_96_LANES == 2 && LANES == 192))
            $error("hap_mlp_tile_accum_s36 requires production 128 lanes or explicit V5 96/192 lanes");
        if (!((ACC_W == 43 && GROUPS == 128) ||
              (ACC_W == 45 && GROUPS == 448)))
            $error("unsupported MLP accumulator width/group contract");
        if (LANES % CONTROL_BANKS != 0)
            $error("MLP accumulator control-bank shape is not integral");
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear &&
            finalize_pending_bank_r !=
            {CONTROL_BANKS{finalize_pending_bank_r[0]}})
            $error("MLP accumulator finalize banks diverged");
    end
`endif

endmodule
