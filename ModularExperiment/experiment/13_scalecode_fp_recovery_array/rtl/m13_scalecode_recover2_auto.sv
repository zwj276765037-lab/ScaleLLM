`timescale 1ns / 1ps

// Unforced-mapping ScaleCode recovery leaf for the fair M13 comparison.
//
// Arithmetic and pipeline behavior intentionally match the production
// hap_a8w4_scalecode_recover2_lut leaf:
//   raw = dot_s17 * activation_code_u8 * weight_code_u8
//
// Unlike the production LUT-budgeting implementation, this reference carries
// no use_dsp/mult_style synthesis attribute.  Vivado must apply its default
// mapping policy, exactly as it does for the FP reference paths.
module m13_scalecode_recover2_auto (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire signed [16:0]   dot0_s17,
    input  wire signed [16:0]   dot1_s17,
    input  wire [7:0]           activation_code_u8,
    input  wire [7:0]           weight0_code_u8,
    input  wire [7:0]           weight1_code_u8,
    output reg                  out_valid,
    input  wire                 out_ready,
    output reg signed [32:0]    raw0_s33,
    output reg signed [32:0]    raw1_s33
);

    reg s0_valid_r;
    reg [15:0] s0_code_product0_u16_r;
    reg [15:0] s0_code_product1_u16_r;
    reg signed [16:0] s0_dot0_s17_r;
    reg signed [16:0] s0_dot1_s17_r;

    reg s1_valid_r;
    reg signed [32:0] s1_raw0_s33_r;
    reg signed [32:0] s1_raw1_s33_r;

    wire out_stage_ready = !out_valid || out_ready;
    wire s1_ready = !s1_valid_r || out_stage_ready;
    wire s0_ready = !s0_valid_r || s1_ready;
    wire in_fire = in_valid && in_ready;
    assign in_ready = rst_n && !clear && s0_ready;

    always @(posedge clk) begin
        if (!rst_n) begin
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            out_valid <= 1'b0;
            s0_code_product0_u16_r <= '0;
            s0_code_product1_u16_r <= '0;
            s0_dot0_s17_r <= '0;
            s0_dot1_s17_r <= '0;
            s1_raw0_s33_r <= '0;
            s1_raw1_s33_r <= '0;
            raw0_s33 <= '0;
            raw1_s33 <= '0;
        end else if (clear) begin
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            out_valid <= 1'b0;
        end else begin
            if (out_stage_ready) begin
                out_valid <= s1_valid_r;
                if (s1_valid_r) begin
                    raw0_s33 <= s1_raw0_s33_r;
                    raw1_s33 <= s1_raw1_s33_r;
                end
            end
            if (s1_ready) begin
                s1_valid_r <= s0_valid_r;
                if (s0_valid_r) begin
                    s1_raw0_s33_r <= s0_dot0_s17_r *
                        $signed({1'b0, s0_code_product0_u16_r});
                    s1_raw1_s33_r <= s0_dot1_s17_r *
                        $signed({1'b0, s0_code_product1_u16_r});
                end
            end
            if (s0_ready) begin
                s0_valid_r <= in_fire;
                if (in_fire) begin
                    s0_code_product0_u16_r <= activation_code_u8 *
                        weight0_code_u8;
                    s0_code_product1_u16_r <= activation_code_u8 *
                        weight1_code_u8;
                    s0_dot0_s17_r <= dot0_s17;
                    s0_dot1_s17_r <= dot1_s17;
                end
            end
        end
    end
endmodule
