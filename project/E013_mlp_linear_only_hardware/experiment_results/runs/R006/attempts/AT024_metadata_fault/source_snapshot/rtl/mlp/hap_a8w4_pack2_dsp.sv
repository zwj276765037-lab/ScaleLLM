`timescale 1ns / 1ps

// One centered A8 activation times two signed W4 output-column weights.
// Direct signed packing removes the old per-column activation-bias correction:
//
//   packed_w_s16 = {weight1_s4, sign_extend(weight0_s4 to 12 bits)}
//   P            = activation_s9 * packed_w_s16
//   product0     = signed(P[11:0])
//   product1     = signed(P[24:12]) - (weight0<0 ? activation : 0) + P[11]
//
// The final two terms undo the sign extension of the low 12-bit field and the
// arithmetic-floor carry when product0 is negative.  Exhaustive 511x16x16
// analysis proves exact recovery for the legal A8/W4 ranges.  The S9xS16
// product remains one DSP48E2 and still emits both columns every cycle.
module hap_a8w4_pack2_dsp (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire signed [8:0]    activation_s9,
    input  wire signed [3:0]    weight0_s4,
    input  wire signed [3:0]    weight1_s4,
    output reg                  out_valid,
    input  wire                 out_ready,
    output reg signed [11:0]    product0_s12,
    output reg signed [11:0]    product1_s12
);

    reg                  s0_valid_r;
    reg signed [8:0]     s0_activation_s9_r;
    reg signed [15:0]    s0_packed_weight_s16_r;
    reg                  s0_low_weight_negative_r;

    reg                  s1_valid_r;
    (* use_dsp = "yes", dont_touch = "yes" *) reg signed [24:0]
        s1_dsp_product_s25_r;
    reg signed [8:0]     s1_activation_s9_r;
    reg                  s1_low_weight_negative_r;

    wire out_stage_ready = !out_valid || out_ready;
    wire s1_ready = !s1_valid_r || out_stage_ready;
    wire s0_ready = !s0_valid_r || s1_ready;
    wire input_fire = in_valid && in_ready;
    wire signed [11:0] product0_comb = s1_dsp_product_s25_r[11:0];
    (* use_dsp = "no" *) wire signed [13:0] product1_comb =
        $signed({s1_dsp_product_s25_r[24],
            s1_dsp_product_s25_r[24:12]}) -
        (s1_low_weight_negative_r ?
            $signed({{5{s1_activation_s9_r[8]}},s1_activation_s9_r}) :
            14'sd0) +
        $signed({13'd0,s1_dsp_product_s25_r[11]});

    assign in_ready = rst_n && !clear && s0_ready;

    always @(posedge clk) begin
        if (!rst_n) begin
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            out_valid <= 1'b0;
            s0_activation_s9_r <= '0;
            s0_packed_weight_s16_r <= '0;
            s0_low_weight_negative_r <= 1'b0;
            s1_dsp_product_s25_r <= '0;
            s1_activation_s9_r <= '0;
            s1_low_weight_negative_r <= 1'b0;
            product0_s12 <= '0;
            product1_s12 <= '0;
        end else if (clear) begin
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            out_valid <= 1'b0;
        end else begin
            if (out_stage_ready) begin
                out_valid <= s1_valid_r;
                if (s1_valid_r) begin
                    product0_s12 <= product0_comb;
                    product1_s12 <= product1_comb[11:0];
                end
            end

            if (s1_ready) begin
                s1_valid_r <= s0_valid_r;
                if (s0_valid_r) begin
                    s1_dsp_product_s25_r <= s0_activation_s9_r *
                        s0_packed_weight_s16_r;
                    s1_activation_s9_r <= s0_activation_s9_r;
                    s1_low_weight_negative_r <=
                        s0_low_weight_negative_r;
                end
            end

            if (s0_ready) begin
                s0_valid_r <= input_fire;
                if (input_fire) begin
                    s0_activation_s9_r <= activation_s9;
                    s0_packed_weight_s16_r <= {weight1_s4,
                        {8{weight0_s4[3]}},weight0_s4};
                    s0_low_weight_negative_r <= weight0_s4[3];
                end
            end
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && input_fire &&
            ((activation_s9 < -9'sd255) || (activation_s9 > 9'sd255)))
            $error("hap_a8w4_pack2_dsp activation outside [-255,255]");
        if (rst_n && !clear && out_stage_ready && s1_valid_r &&
            ((product1_comb < -14'sd2048) ||
             (product1_comb > 14'sd2047)))
            $error("hap_a8w4_pack2_dsp correction escaped S12");
    end
`endif

endmodule
