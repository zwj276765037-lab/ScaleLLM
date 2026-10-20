`timescale 1ns / 1ps

// One independently inferred S54 output-lane bank.  Keeping each 256x54 RAM
// in its own module avoids Vivado's 1,000,000-bit single-variable elaboration
// limit and gives the floorplanner one physical BRAM bank per compute lane.
module hap_mlp_down_group_major_s54_bank #(
    parameter integer TILES = 256,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input  wire                       clk,
    input  wire                       read_enable,
    input  wire [TILE_W-1:0]          read_address,
    output reg  signed [53:0]         read_data,
    input  wire                       write_enable,
    input  wire [TILE_W-1:0]          write_address,
    input  wire signed [53:0]         write_data
);

    (* ram_style = "block" *) reg signed [53:0] memory [0:TILES-1];

    always @(posedge clk) begin
        if (read_enable)
            read_data <= memory[read_address];
        if (write_enable)
            memory[write_address] <= write_data;
    end

endmodule

// Group-major down-projection accumulator.
//
// For one product activation group, the A8W4 array walks every output tile
// before the next activation group arrives.  Each of the LANES partial sums
// is held in a local block-RAM bank indexed by output tile.  This changes only
// loop order: the numerical contract is an S54 Q30.24 accumulation over
// GROUPS=448, followed by one round-away-from-zero / 2^8 and S32 saturation.
//
// Compared with storing all 448 activation groups and replaying them for each
// output tile, group-major order permits the down array and DDR W4 reader to
// run during the approximately 835-cycle product-frontend interval.  One
// synchronous read/modify/write request may be accepted each cycle.  Memory
// contents need no reset because in_first_group explicitly overwrites them.
module hap_mlp_down_group_major_accum_s54 #(
    parameter integer LANES = 128,
    parameter integer TILES = 256,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_first_group,
    input  wire                         in_last_group,
    input  wire [TILE_W-1:0]            in_tile_index,
    input  wire signed [LANES*45-1:0]   in_guard_s45,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire [TILE_W-1:0]            out_tile_index,
    output wire signed [LANES*32-1:0]   out_projection_s32,
    output reg  [31:0]                  input_tile_count,
    output reg  [31:0]                  input_group_count,
    output reg  [31:0]                  output_tile_count,
    output wire [31:0]                  saturation_count,
    output reg                          accumulator_overflow,
    output reg                          error
);

    wire signed [53:0] accum_q [0:LANES-1];
    wire signed [LANES*54-1:0] bank_write_data;
    wire signed [LANES*32-1:0] finalized_projection_s32;
    wire [LANES-1:0] finalized_saturation_flags;
    localparam integer CAPTURE_BANKS = 8;
    localparam integer LANES_PER_CAPTURE_BANK = LANES/CAPTURE_BANKS;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [CAPTURE_BANKS-1:0] guard_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [CAPTURE_BANKS-1:0] output_capture_enable;

    // Saturation telemetry is deliberately distributed over one counter per
    // eight lanes.  A procedural 128-lane `increment = increment + 1` loop
    // synthesized to a 123-CARRY8 serial chain in the production combined
    // core.  The local eight-lane popcounts preserve the exact event count,
    // accept one final tile per cycle, and keep the state update shallow.
    localparam integer SATURATION_BLOCKS = LANES/8;
    reg [31:0] saturation_count8_r [0:SATURATION_BLOCKS-1];

    reg pipe_valid_r;
    reg pipe_first_r;
    reg pipe_last_r;
    reg [TILE_W-1:0] pipe_tile_r;
    reg signed [LANES*45-1:0] pipe_guard_r;
    reg [LANES-1:0] overflow_flags_r;
    reg [LANES/8-1:0] overflow_any8_r;
    reg overflow_any_r;
    reg overflow_flags_valid_r;
    reg overflow_any8_valid_r;
    reg overflow_any_valid_r;

    reg out_valid_r;
    reg [TILE_W-1:0] out_tile_r;
    reg signed [LANES*32-1:0] out_projection_r;

    reg [TILE_W-1:0] expected_tile_r;
    reg current_group_first_r;
    reg current_group_last_r;

    wire process_ready = !pipe_valid_r || !pipe_last_r ||
        !out_valid_r || out_ready;
    wire bank_write_enable = process_ready && pipe_valid_r;
    wire output_capture_fire = process_ready && pipe_valid_r && pipe_last_r;
    assign in_ready = rst_n && !clear && process_ready;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_tile_index = out_tile_r;
    assign out_projection_s32 = out_projection_r;

    genvar capture_bank;
    generate
        for (capture_bank = 0; capture_bank < CAPTURE_BANKS;
             capture_bank = capture_bank + 1) begin : gen_guard_capture
            // A V5 bank captures one physical row: 12 lanes x 45 bits.
            // Protecting the net prevents phys_opt from rebuilding the old
            // 3,456-bit common CE after placement.
            (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
            u_guard_capture_enable (
                .I0(in_fire),
                .O(guard_capture_enable[capture_bank])
            );
            // The final projection capture also owns one physical row.  The
            // former common predicate drove 2,304 payload FFs plus out_tile
            // and was promoted to a data BUFG during post-place phys_opt.
            (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
            u_output_capture_enable (
                .I0(output_capture_fire),
                .O(output_capture_enable[capture_bank])
            );

            always @(posedge clk) begin
                if (guard_capture_enable[capture_bank])
                    pipe_guard_r[
                        capture_bank*LANES_PER_CAPTURE_BANK*45 +:
                        LANES_PER_CAPTURE_BANK*45] <= in_guard_s45[
                        capture_bank*LANES_PER_CAPTURE_BANK*45 +:
                        LANES_PER_CAPTURE_BANK*45];
                if (output_capture_enable[capture_bank])
                    out_projection_r[
                        capture_bank*LANES_PER_CAPTURE_BANK*32 +:
                        LANES_PER_CAPTURE_BANK*32] <=
                        finalized_projection_s32[
                        capture_bank*LANES_PER_CAPTURE_BANK*32 +:
                        LANES_PER_CAPTURE_BANK*32];
            end
        end
    endgenerate

    genvar bank_lane;
    generate
        for (bank_lane = 0; bank_lane < LANES;
             bank_lane = bank_lane + 1) begin : gen_accum_bank
            hap_mlp_down_group_major_s54_bank #(
                .TILES(TILES), .TILE_W(TILE_W)
            ) u_bank (
                .clk(clk),
                .read_enable(in_fire),
                .read_address(in_tile_index),
                .read_data(accum_q[bank_lane]),
                .write_enable(bank_write_enable),
                .write_address(pipe_tile_r),
                .write_data(bank_write_data[bank_lane*54 +: 54])
            );
        end
    endgenerate

    function automatic signed [53:0] round_q24_to_q16;
        input signed [53:0] value;
        reg signed [54:0] extended;
        reg [54:0] magnitude;
        begin
            extended = {value[53], value};
            if (!value[53])
                round_q24_to_q16 = (extended + 55'sd128) >>> 8;
            else begin
                magnitude = -extended;
                round_q24_to_q16 =
                    -$signed((magnitude + 55'd128) >> 8);
            end
        end
    endfunction

    function automatic signed [31:0] saturate_s32;
        input signed [53:0] value;
        begin
            if (value > 54'sd2147483647)
                saturate_s32 = 32'sh7fffffff;
            else if (value < -54'sd2147483648)
                saturate_s32 = 32'sh80000000;
            else
                saturate_s32 = value[31:0];
        end
    endfunction

    function automatic did_saturate_s32;
        input signed [53:0] value;
        begin
            did_saturate_s32 = value > 54'sd2147483647 ||
                value < -54'sd2147483648;
        end
    endfunction

    generate
        for (bank_lane = 0; bank_lane < LANES;
             bank_lane = bank_lane + 1) begin : gen_accum_value
            wire signed [54:0] lane_old_ext =
                {accum_q[bank_lane][53], accum_q[bank_lane]};
            wire signed [54:0] lane_guard_ext =
                {{10{pipe_guard_r[bank_lane*45+44]}},
                    pipe_guard_r[bank_lane*45 +: 45]};
            wire signed [54:0] lane_sum_ext =
                pipe_first_r ? lane_guard_ext : lane_old_ext + lane_guard_ext;
            wire signed [53:0] lane_next_accum;
            wire signed [53:0] lane_rounded_accum;

            assign bank_write_data[bank_lane*54 +: 54] =
                lane_sum_ext[53:0];
            assign lane_next_accum =
                $signed(bank_write_data[bank_lane*54 +: 54]);
            assign lane_rounded_accum =
                round_q24_to_q16(lane_next_accum);
            assign finalized_projection_s32[bank_lane*32 +: 32] =
                saturate_s32(lane_rounded_accum);
            assign finalized_saturation_flags[bank_lane] =
                did_saturate_s32(lane_rounded_accum);

            always @(posedge clk) begin
                if (rst_n && !clear && bank_write_enable)
                    overflow_flags_r[bank_lane] <=
                        lane_sum_ext[54] != lane_sum_ext[53];
            end
        end
    endgenerate

    genvar saturation_block;
    generate
        for (saturation_block = 0;
             saturation_block < SATURATION_BLOCKS;
             saturation_block = saturation_block + 1) begin : gen_sat_block
            wire [3:0] increment8 =
                {3'd0, finalized_saturation_flags[saturation_block*8+0]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+1]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+2]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+3]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+4]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+5]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+6]} +
                {3'd0, finalized_saturation_flags[saturation_block*8+7]};

            always @(posedge clk) begin
                if (!rst_n || clear)
                    saturation_count8_r[saturation_block] <= 32'd0;
                else if (process_ready && pipe_valid_r && pipe_last_r)
                    saturation_count8_r[saturation_block] <=
                        saturation_count8_r[saturation_block] + increment8;
            end
        end

        if (SATURATION_BLOCKS == 1) begin : gen_sat_total_8
            assign saturation_count = saturation_count8_r[0];
        end else if (SATURATION_BLOCKS == 12) begin : gen_sat_total_96
            wire [31:0] sum2 [0:5];
            wire [31:0] sum4 [0:2];
            genvar sum_index;
            for (sum_index = 0; sum_index < 6;
                 sum_index = sum_index + 1) begin : gen_sum2
                assign sum2[sum_index] =
                    saturation_count8_r[sum_index*2] +
                    saturation_count8_r[sum_index*2+1];
            end
            for (sum_index = 0; sum_index < 3;
                 sum_index = sum_index + 1) begin : gen_sum4
                assign sum4[sum_index] =
                    sum2[sum_index*2] + sum2[sum_index*2+1];
            end
            assign saturation_count = sum4[0] + sum4[1] + sum4[2];
        end else if (SATURATION_BLOCKS == 16) begin : gen_sat_total_128
            wire [31:0] sum2 [0:7];
            wire [31:0] sum4 [0:3];
            wire [31:0] sum8 [0:1];
            genvar sum_index;
            for (sum_index = 0; sum_index < 8;
                 sum_index = sum_index + 1) begin : gen_sum2
                assign sum2[sum_index] =
                    saturation_count8_r[sum_index*2] +
                    saturation_count8_r[sum_index*2+1];
            end
            for (sum_index = 0; sum_index < 4;
                 sum_index = sum_index + 1) begin : gen_sum4
                assign sum4[sum_index] =
                    sum2[sum_index*2] + sum2[sum_index*2+1];
            end
            for (sum_index = 0; sum_index < 2;
                 sum_index = sum_index + 1) begin : gen_sum8
                assign sum8[sum_index] =
                    sum4[sum_index*2] + sum4[sum_index*2+1];
            end
            assign saturation_count = sum8[0] + sum8[1];
        end else begin : gen_sat_total_unsupported
            assign saturation_count = 32'hffff_ffff;
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n) begin
            pipe_valid_r <= 1'b0;
            out_valid_r <= 1'b0;
            expected_tile_r <= '0;
            current_group_first_r <= 1'b0;
            current_group_last_r <= 1'b0;
            input_tile_count <= 32'd0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            accumulator_overflow <= 1'b0;
            error <= 1'b0;
        end else if (clear) begin
            pipe_valid_r <= 1'b0;
            out_valid_r <= 1'b0;
            expected_tile_r <= '0;
            current_group_first_r <= 1'b0;
            current_group_last_r <= 1'b0;
            input_tile_count <= 32'd0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            overflow_any8_r <= '0;
            overflow_any_r <= 1'b0;
            overflow_flags_valid_r <= 1'b0;
            overflow_any8_valid_r <= 1'b0;
            overflow_any_valid_r <= 1'b0;
            accumulator_overflow <= 1'b0;
            error <= 1'b0;
        end else begin
            overflow_flags_valid_r <= bank_write_enable;
            overflow_any8_valid_r <= overflow_flags_valid_r;
            overflow_any_valid_r <= overflow_any8_valid_r;
            if (overflow_flags_valid_r)
                for (integer overflow_group = 0;
                     overflow_group < LANES/8;
                     overflow_group = overflow_group + 1)
                    overflow_any8_r[overflow_group] <=
                        |overflow_flags_r[overflow_group*8 +: 8];
            if (overflow_any8_valid_r)
                overflow_any_r <= |overflow_any8_r;
            if (overflow_any_valid_r && overflow_any_r) begin
                accumulator_overflow <= 1'b1;
                error <= 1'b1;
            end

            if (out_fire) begin
                out_valid_r <= 1'b0;
                output_tile_count <= output_tile_count + 32'd1;
            end

            if (process_ready) begin
                if (pipe_valid_r) begin
                    if (pipe_last_r) begin
                        out_valid_r <= 1'b1;
                        out_tile_r <= pipe_tile_r;
                    end
                end

                if (in_fire) begin
                    pipe_valid_r <= 1'b1;
                    pipe_first_r <= in_first_group;
                    pipe_last_r <= in_last_group;
                    pipe_tile_r <= in_tile_index;
                end else begin
                    pipe_valid_r <= 1'b0;
                end
            end

            if (in_fire) begin
                input_tile_count <= input_tile_count + 32'd1;
                if (in_tile_index != expected_tile_r ||
                    in_tile_index >= TILES)
                    error <= 1'b1;
                if (in_tile_index == 0) begin
                    current_group_first_r <= in_first_group;
                    current_group_last_r <= in_last_group;
                end else if (in_first_group != current_group_first_r ||
                             in_last_group != current_group_last_r) begin
                    error <= 1'b1;
                end
                if (in_tile_index == TILES-1) begin
                    expected_tile_r <= '0;
                    input_group_count <= input_group_count + 32'd1;
                    if (in_first_group && input_group_count != 0)
                        error <= 1'b1;
                    if (in_last_group && input_group_count != GROUPS-1)
                        error <= 1'b1;
                end else begin
                    expected_tile_r <= expected_tile_r + 1'b1;
                end
            end

            if (input_group_count > GROUPS ||
                output_tile_count > TILES)
                error <= 1'b1;
        end
    end

    initial begin
        if (LANES != 8 && LANES != 96 && LANES != 128)
            $error("group-major accumulator supports LANES=8 test, LANES=96 V5, or LANES=128 V4");
        if ((LANES & 7) != 0)
            $error("group-major accumulator LANES must be divisible by 8");
        if (LANES % CAPTURE_BANKS != 0)
            $error("group-major accumulator capture-bank shape is not integral");
    end

endmodule
