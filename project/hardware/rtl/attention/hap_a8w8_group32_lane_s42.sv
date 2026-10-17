`timescale 1ns / 1ps

module hap_a8w8_group32_lane_s42 #(
    parameter integer FIFO_DEPTH = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [32*8-1:0]       in_act_u8,
    input  wire [32*8-1:0]       in_wgt_s8,
    input  wire [7:0]            in_act_zero_point,
    input  wire [7:0]            in_act_scale_code,
    input  wire [5:0]            in_act_scale_shift,
    input  wire [7:0]            in_wgt_scale_code,
    input  wire [5:0]            in_wgt_scale_shift,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [41:0]    out_guard_s42,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);

    reg high_half_pending_r;
    reg [16*8-1:0] high_act_u8_r;
    reg [16*8-1:0] high_wgt_s8_r;
    reg [7:0] high_zero_point_r;
    reg [6:0] high_total_shift_r;
    (* use_dsp = "no" *) reg [15:0] high_code_product_r;

    reg product_valid_r;
    reg product_high_r;
    reg [6:0] product_total_shift_r;
    reg [15:0] product_code_product_r;
    (* use_dsp = "yes" *) reg signed [15:0] product_r [0:15];

    reg sum2_valid_r;
    reg sum2_high_r;
    reg [6:0] sum2_total_shift_r;
    reg [15:0] sum2_code_product_r;
    (* use_dsp = "no" *) reg signed [16:0] sum2_r [0:7];

    reg sum4_valid_r;
    reg sum4_high_r;
    reg [6:0] sum4_total_shift_r;
    reg [15:0] sum4_code_product_r;
    (* use_dsp = "no" *) reg signed [17:0] sum4_r [0:3];

    reg sum8_valid_r;
    reg sum8_high_r;
    reg [6:0] sum8_total_shift_r;
    reg [15:0] sum8_code_product_r;
    (* use_dsp = "no" *) reg signed [18:0] sum8_r [0:1];

    reg sum16_valid_r;
    reg sum16_high_r;
    reg [6:0] sum16_total_shift_r;
    reg [15:0] sum16_code_product_r;
    (* use_dsp = "no" *) reg signed [19:0] sum16_r;

    reg low_half_valid_r;
    reg signed [19:0] low_half_sum_r;
    reg corr_valid_r;
    reg signed [20:0] corr_s21_r;
    reg [6:0] corr_total_shift_r;
    reg [15:0] corr_code_product_r;

    reg raw_valid_r;
    (* use_dsp = "yes" *) reg signed [36:0] raw_s37_r;
    reg [6:0] raw_total_shift_r;
    reg guard_valid_r;
    reg signed [41:0] guard_s42_r;

    (* ram_style = "distributed" *) reg signed [41:0]
        fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr_r;
    reg [PTR_W-1:0] fifo_rd_ptr_r;
    reg [COUNT_W-1:0] fifo_count_r;
    reg [COUNT_W-1:0] used_count_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire launch_half = high_half_pending_r || in_fire;
    wire launch_high = high_half_pending_r;
    wire [16*8-1:0] launch_act_u8 = high_half_pending_r ?
        high_act_u8_r : in_act_u8[0 +: 16*8];
    wire [16*8-1:0] launch_wgt_s8 = high_half_pending_r ?
        high_wgt_s8_r : in_wgt_s8[0 +: 16*8];
    wire [7:0] launch_zero_point = high_half_pending_r ?
        high_zero_point_r : in_act_zero_point;
    wire [6:0] launch_total_shift = high_half_pending_r ?
        high_total_shift_r :
        ({1'b0, in_act_scale_shift} + {1'b0, in_wgt_scale_shift});
    wire fifo_commit = guard_valid_r &&
        ((fifo_count_r != FIFO_DEPTH) || out_fire);

    assign in_ready = rst_n && !clear && !high_half_pending_r &&
        (used_count_r < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_guard_s42 = fifo_mem[fifo_rd_ptr_r];

    function automatic signed [15:0] centered_product_s16;
        input [7:0] act_u8;
        input [7:0] zero_point;
        input signed [7:0] weight_s8;
        reg signed [8:0] centered_s9;
        reg signed [16:0] full_s17;
        begin
            centered_s9 = $signed({1'b0, act_u8}) -
                $signed({1'b0, zero_point});
            full_s17 = centered_s9 * weight_s8;
            centered_product_s16 = full_s17[15:0];
        end
    endfunction

    integer lane;
    integer reduce_idx;
    always @(posedge clk) begin
        if (in_fire) begin
            high_act_u8_r <= in_act_u8[16*8 +: 16*8];
            high_wgt_s8_r <= in_wgt_s8[16*8 +: 16*8];
            high_zero_point_r <= in_act_zero_point;
            high_total_shift_r <= {1'b0, in_act_scale_shift} +
                {1'b0, in_wgt_scale_shift};
            high_code_product_r <=
                in_act_scale_code * in_wgt_scale_code;
        end

        if (launch_half) begin
            for (lane = 0; lane < 16; lane = lane + 1)
                product_r[lane] <= centered_product_s16(
                    launch_act_u8[lane*8 +: 8], launch_zero_point,
                    $signed(launch_wgt_s8[lane*8 +: 8]));
            product_high_r <= launch_high;
            product_total_shift_r <= launch_total_shift;
            // Only the high half reaches corr_s21_r, so the low-half
            // ScaleCode metadata is a don't-care.  Use the product captured
            // with in_fire for the following high-half launch instead of
            // driving this register directly through another 8x8 multiply.
            // This preserves II=2 and the arithmetic result while removing
            // 128 false low-half multiplier-to-register critical paths.
            product_code_product_r <= launch_high ?
                high_code_product_r : 16'd0;
        end

        if (product_valid_r) begin
            for (reduce_idx = 0; reduce_idx < 8;
                 reduce_idx = reduce_idx + 1)
                sum2_r[reduce_idx] <=
                    $signed(product_r[2*reduce_idx]) +
                    $signed(product_r[2*reduce_idx+1]);
            sum2_high_r <= product_high_r;
            sum2_total_shift_r <= product_total_shift_r;
            sum2_code_product_r <= product_code_product_r;
        end
        if (sum2_valid_r) begin
            for (reduce_idx = 0; reduce_idx < 4;
                 reduce_idx = reduce_idx + 1)
                sum4_r[reduce_idx] <=
                    $signed(sum2_r[2*reduce_idx]) +
                    $signed(sum2_r[2*reduce_idx+1]);
            sum4_high_r <= sum2_high_r;
            sum4_total_shift_r <= sum2_total_shift_r;
            sum4_code_product_r <= sum2_code_product_r;
        end
        if (sum4_valid_r) begin
            for (reduce_idx = 0; reduce_idx < 2;
                 reduce_idx = reduce_idx + 1)
                sum8_r[reduce_idx] <=
                    $signed(sum4_r[2*reduce_idx]) +
                    $signed(sum4_r[2*reduce_idx+1]);
            sum8_high_r <= sum4_high_r;
            sum8_total_shift_r <= sum4_total_shift_r;
            sum8_code_product_r <= sum4_code_product_r;
        end
        if (sum8_valid_r) begin
            sum16_r <= $signed(sum8_r[0]) + $signed(sum8_r[1]);
            sum16_high_r <= sum8_high_r;
            sum16_total_shift_r <= sum8_total_shift_r;
            sum16_code_product_r <= sum8_code_product_r;
        end
        if (sum16_valid_r) begin
            if (sum16_high_r && low_half_valid_r) begin
                corr_s21_r <=
                    $signed({low_half_sum_r[19], low_half_sum_r}) +
                    $signed({sum16_r[19], sum16_r});
                corr_total_shift_r <= sum16_total_shift_r;
                corr_code_product_r <= sum16_code_product_r;
            end else if (!sum16_high_r) begin
                low_half_sum_r <= sum16_r;
            end
        end
        if (corr_valid_r) begin
            raw_s37_r <= corr_s21_r *
                $signed({1'b0, corr_code_product_r});
            raw_total_shift_r <= corr_total_shift_r;
        end
        if (raw_valid_r) begin
            guard_s42_r <= (raw_s37_r == 0) ? 42'sd0 :
                ($signed({{5{raw_s37_r[36]}}, raw_s37_r}) >>>
                    (raw_total_shift_r - 7'd24));
        end
        if (fifo_commit)
            fifo_mem[fifo_wr_ptr_r] <= guard_s42_r;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            high_half_pending_r <= 1'b0;
            product_valid_r <= 1'b0;
            sum2_valid_r <= 1'b0;
            sum4_valid_r <= 1'b0;
            sum8_valid_r <= 1'b0;
            sum16_valid_r <= 1'b0;
            low_half_valid_r <= 1'b0;
            corr_valid_r <= 1'b0;
            raw_valid_r <= 1'b0;
            guard_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            high_half_pending_r <= 1'b0;
            product_valid_r <= 1'b0;
            sum2_valid_r <= 1'b0;
            sum4_valid_r <= 1'b0;
            sum8_valid_r <= 1'b0;
            sum16_valid_r <= 1'b0;
            low_half_valid_r <= 1'b0;
            corr_valid_r <= 1'b0;
            raw_valid_r <= 1'b0;
            guard_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            product_valid_r <= launch_half;
            sum2_valid_r <= product_valid_r;
            sum4_valid_r <= sum2_valid_r;
            sum8_valid_r <= sum4_valid_r;
            sum16_valid_r <= sum8_valid_r;
            corr_valid_r <= sum16_valid_r && sum16_high_r &&
                low_half_valid_r;
            if (sum16_valid_r) begin
                if (sum16_high_r) begin
                    low_half_valid_r <= 1'b0;
                end else begin
                    low_half_valid_r <= 1'b1;
                end
            end
            raw_valid_r <= corr_valid_r;
            guard_valid_r <= raw_valid_r;

            if (high_half_pending_r)
                high_half_pending_r <= 1'b0;
            else if (in_fire)
                high_half_pending_r <= 1'b1;

            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
                if (((in_act_scale_code == 0) &&
                        (in_act_scale_shift != 0)) ||
                    ((in_wgt_scale_code == 0) &&
                        (in_wgt_scale_shift != 0)) ||
                    ((in_act_scale_code != 0) &&
                     (in_wgt_scale_code != 0) &&
                     (({1'b0, in_act_scale_shift} +
                       {1'b0, in_wgt_scale_shift}) < 26 ||
                      ({1'b0, in_act_scale_shift} +
                       {1'b0, in_wgt_scale_shift}) > 47)))
                    error <= 1'b1;
            end

            if (guard_valid_r) begin
                if ((fifo_count_r == FIFO_DEPTH) && !out_fire)
                    error <= 1'b1;
                else
                    fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                output_group_count <= output_group_count + 32'd1;
            end
            case ({fifo_commit, out_fire})
                2'b10: fifo_count_r <= fifo_count_r + 1'b1;
                2'b01: fifo_count_r <= fifo_count_r - 1'b1;
                default: fifo_count_r <= fifo_count_r;
            endcase
            case ({in_fire, out_fire})
                2'b10: used_count_r <= used_count_r + 1'b1;
                2'b01: used_count_r <= used_count_r - 1'b1;
                default: used_count_r <= used_count_r;
            endcase
            if ((used_count_r > FIFO_DEPTH) ||
                (fifo_count_r > FIFO_DEPTH) ||
                (fifo_count_r > used_count_r))
                error <= 1'b1;
        end
    end

    initial begin
        if (FIFO_DEPTH != 16)
            $error("hap_a8w8_group32_lane_s42 production FIFO_DEPTH must be 16");
    end

endmodule
