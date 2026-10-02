`timescale 1ns / 1ps

// Common two-cycle, 16-DSP producer used by every M3 case.
module m3_precenter_mac_group32 #(
    parameter integer META_W = 64
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  allow_input,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [255:0]          in_act_u8,
    input  wire [255:0]          in_wgt_s8,
    input  wire [7:0]            in_zero_point,
    input  wire [META_W-1:0]     in_meta,
    output reg                   out_valid,
    output reg signed [20:0]     out_corr_s21,
    output reg [META_W-1:0]      out_meta
);
    reg high_pending_r;
    reg [127:0] high_act_r;
    reg [127:0] high_wgt_r;
    reg [7:0] high_zp_r;
    reg [META_W-1:0] high_meta_r;
    reg product_valid_r, product_high_r;
    reg [META_W-1:0] product_meta_r;
    (* use_dsp = "yes" *) reg signed [15:0] product_r [0:15];
    reg sum2_valid_r, sum2_high_r;
    reg [META_W-1:0] sum2_meta_r;
    (* use_dsp = "no" *) reg signed [16:0] sum2_r [0:7];
    reg sum4_valid_r, sum4_high_r;
    reg [META_W-1:0] sum4_meta_r;
    (* use_dsp = "no" *) reg signed [17:0] sum4_r [0:3];
    reg sum8_valid_r, sum8_high_r;
    reg [META_W-1:0] sum8_meta_r;
    (* use_dsp = "no" *) reg signed [18:0] sum8_r [0:1];
    reg sum16_valid_r, sum16_high_r;
    reg [META_W-1:0] sum16_meta_r;
    (* use_dsp = "no" *) reg signed [19:0] sum16_r;
    reg low_valid_r;
    reg signed [19:0] low_sum_r;

    wire in_fire = in_valid && in_ready;
    wire launch = high_pending_r || in_fire;
    wire launch_high = high_pending_r;
    wire [127:0] launch_act = high_pending_r ? high_act_r : in_act_u8[127:0];
    wire [127:0] launch_wgt = high_pending_r ? high_wgt_r : in_wgt_s8[127:0];
    wire [7:0] launch_zp = high_pending_r ? high_zp_r : in_zero_point;
    wire [META_W-1:0] launch_meta = high_pending_r ? high_meta_r : in_meta;
    assign in_ready = rst_n && !clear && allow_input && !high_pending_r;

    function automatic signed [15:0] centered_product;
        input [7:0] act;
        input [7:0] zp;
        input signed [7:0] weight;
        reg signed [8:0] centered;
        reg signed [16:0] full;
        begin
            centered = $signed({1'b0, act}) - $signed({1'b0, zp});
            full = centered * weight;
            centered_product = full[15:0];
        end
    endfunction

    integer lane, idx;
    always @(posedge clk) begin
        if (in_fire) begin
            high_act_r <= in_act_u8[255:128];
            high_wgt_r <= in_wgt_s8[255:128];
            high_zp_r <= in_zero_point;
            high_meta_r <= in_meta;
        end
        if (launch) begin
            for (lane=0; lane<16; lane=lane+1)
                product_r[lane] <= centered_product(
                    launch_act[lane*8 +: 8], launch_zp,
                    $signed(launch_wgt[lane*8 +: 8]));
            product_high_r <= launch_high;
            product_meta_r <= launch_meta;
        end
        if (product_valid_r) begin
            for (idx=0; idx<8; idx=idx+1)
                sum2_r[idx] <= $signed(product_r[2*idx]) +
                    $signed(product_r[2*idx+1]);
            sum2_high_r <= product_high_r; sum2_meta_r <= product_meta_r;
        end
        if (sum2_valid_r) begin
            for (idx=0; idx<4; idx=idx+1)
                sum4_r[idx] <= $signed(sum2_r[2*idx]) +
                    $signed(sum2_r[2*idx+1]);
            sum4_high_r <= sum2_high_r; sum4_meta_r <= sum2_meta_r;
        end
        if (sum4_valid_r) begin
            for (idx=0; idx<2; idx=idx+1)
                sum8_r[idx] <= $signed(sum4_r[2*idx]) +
                    $signed(sum4_r[2*idx+1]);
            sum8_high_r <= sum4_high_r; sum8_meta_r <= sum4_meta_r;
        end
        if (sum8_valid_r) begin
            sum16_r <= $signed(sum8_r[0]) + $signed(sum8_r[1]);
            sum16_high_r <= sum8_high_r; sum16_meta_r <= sum8_meta_r;
        end
        if (sum16_valid_r) begin
            if (sum16_high_r && low_valid_r) begin
                out_corr_s21 <= $signed({low_sum_r[19],low_sum_r}) +
                    $signed({sum16_r[19],sum16_r});
                out_meta <= sum16_meta_r;
            end else if (!sum16_high_r) low_sum_r <= sum16_r;
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            high_pending_r<=0; product_valid_r<=0; sum2_valid_r<=0;
            sum4_valid_r<=0; sum8_valid_r<=0; sum16_valid_r<=0;
            low_valid_r<=0; out_valid<=0;
        end else if (clear) begin
            high_pending_r<=0; product_valid_r<=0; sum2_valid_r<=0;
            sum4_valid_r<=0; sum8_valid_r<=0; sum16_valid_r<=0;
            low_valid_r<=0; out_valid<=0;
        end else begin
            product_valid_r <= launch;
            sum2_valid_r <= product_valid_r;
            sum4_valid_r <= sum2_valid_r;
            sum8_valid_r <= sum4_valid_r;
            sum16_valid_r <= sum8_valid_r;
            out_valid <= sum16_valid_r && sum16_high_r && low_valid_r;
            if (sum16_valid_r)
                low_valid_r <= !sum16_high_r;
            if (high_pending_r) high_pending_r <= 0;
            else if (in_fire) high_pending_r <= 1;
        end
    end
endmodule
