`timescale 1ns / 1ps

// Force each signed reduction adder into LUT/carry fabric.  Separate narrow
// hierarchy prevents Vivado from using additional DSP48E2 ALUs at scale.
(* use_dsp = "no", keep_hierarchy = "yes" *)
module hap_a8w4_add2_lut #(
    parameter integer IN_W = 12
) (
    input  wire signed [IN_W-1:0] lhs,
    input  wire signed [IN_W-1:0] rhs,
    output wire signed [IN_W:0]   sum
);
    (* use_dsp = "no" *) wire signed [IN_W:0] sum_lut =
        $signed({lhs[IN_W-1], lhs}) + $signed({rhs[IN_W-1], rhs});
    assign sum = sum_lut;
endmodule

// One group32 produces exact S17 dots for two output columns every cycle.
module hap_a8w4_group32_pack2_s17 (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire signed [32*9-1:0]       activation_s9x32,
    input  wire signed [32*4-1:0]       weight0_s4x32,
    input  wire signed [32*4-1:0]       weight1_s4x32,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [16:0]           dot0_s17,
    output wire signed [16:0]           dot1_s17
);

    wire [31:0] leaf_in_ready;
    wire [31:0] leaf_out_valid;
    wire signed [32*12-1:0] product0_s12x32;
    wire signed [32*12-1:0] product1_s12x32;
    wire all_leaf_out_valid = &leaf_out_valid;

    reg s0_valid_r;
    reg signed [16*13-1:0] s0_sum0_s13x16_r;
    reg signed [16*13-1:0] s0_sum1_s13x16_r;
    reg s1_valid_r;
    reg signed [8*14-1:0] s1_sum0_s14x8_r;
    reg signed [8*14-1:0] s1_sum1_s14x8_r;
    reg s2_valid_r;
    reg signed [4*15-1:0] s2_sum0_s15x4_r;
    reg signed [4*15-1:0] s2_sum1_s15x4_r;
    reg s3_valid_r;
    reg signed [2*16-1:0] s3_sum0_s16x2_r;
    reg signed [2*16-1:0] s3_sum1_s16x2_r;
    reg s4_valid_r;
    reg signed [16:0] s4_sum0_s17_r;
    reg signed [16:0] s4_sum1_s17_r;

    // The former single final output slot is replaced by this two-entry FF
    // ring.  Credit depends only on registered occupancy, so out_ready cannot
    // feed back through the reduction pipeline in the same cycle.
    (* ram_style = "registers", shreg_extract = "no" *)
    reg signed [16:0] dot0_q [0:1];
    (* ram_style = "registers", shreg_extract = "no" *)
    reg signed [16:0] dot1_q [0:1];
    reg dot_q_wr_ptr_r;
    reg dot_q_rd_ptr_r;
    reg [1:0] dot_q_count_r;

    wire dot_q_ready = dot_q_count_r < 2;
    wire dot_q_empty = dot_q_count_r == 0;
    wire dot_q_push = s4_valid_r && dot_q_ready;
    wire dot_q_pop = !dot_q_empty && out_ready;
    wire s4_ready = !s4_valid_r || dot_q_ready;
    wire s3_ready = !s3_valid_r || s4_ready;
    wire s2_ready = !s2_valid_r || s3_ready;
    wire s1_ready = !s1_valid_r || s2_ready;
    wire s0_ready = !s0_valid_r || s1_ready;
    wire leaf_output_fire = all_leaf_out_valid && s0_ready;
    wire group_input_ready = &leaf_in_ready;
    wire group_input_fire = in_valid && in_ready;

    wire signed [16*13-1:0] s0_sum0_next;
    wire signed [16*13-1:0] s0_sum1_next;
    wire signed [8*14-1:0] s1_sum0_next;
    wire signed [8*14-1:0] s1_sum1_next;
    wire signed [4*15-1:0] s2_sum0_next;
    wire signed [4*15-1:0] s2_sum1_next;
    wire signed [2*16-1:0] s3_sum0_next;
    wire signed [2*16-1:0] s3_sum1_next;
    wire signed [16:0] s4_sum0_next;
    wire signed [16:0] s4_sum1_next;

    assign in_ready = rst_n && !clear && group_input_ready;
    assign out_valid = !dot_q_empty;
    assign dot0_s17 = dot0_q[dot_q_rd_ptr_r];
    assign dot1_s17 = dot1_q[dot_q_rd_ptr_r];

    genvar lane;
    generate
        for (lane = 0; lane < 32; lane = lane + 1) begin : gen_leaf
            hap_a8w4_pack2_dsp u_leaf (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid && in_ready),
                .in_ready(leaf_in_ready[lane]),
                .activation_s9(activation_s9x32[lane*9 +: 9]),
                .weight0_s4(weight0_s4x32[lane*4 +: 4]),
                .weight1_s4(weight1_s4x32[lane*4 +: 4]),
                .out_valid(leaf_out_valid[lane]),
                .out_ready(s0_ready),
                .product0_s12(product0_s12x32[lane*12 +: 12]),
                .product1_s12(product1_s12x32[lane*12 +: 12])
            );
        end

        for (lane = 0; lane < 16; lane = lane + 1) begin : gen_reduce_s0
            hap_a8w4_add2_lut #(.IN_W(12)) u_add0 (
                .lhs(product0_s12x32[(2*lane)*12 +: 12]),
                .rhs(product0_s12x32[(2*lane+1)*12 +: 12]),
                .sum(s0_sum0_next[lane*13 +: 13])
            );
            hap_a8w4_add2_lut #(.IN_W(12)) u_add1 (
                .lhs(product1_s12x32[(2*lane)*12 +: 12]),
                .rhs(product1_s12x32[(2*lane+1)*12 +: 12]),
                .sum(s0_sum1_next[lane*13 +: 13])
            );
        end

        for (lane = 0; lane < 8; lane = lane + 1) begin : gen_reduce_s1
            hap_a8w4_add2_lut #(.IN_W(13)) u_add0 (
                .lhs(s0_sum0_s13x16_r[(2*lane)*13 +: 13]),
                .rhs(s0_sum0_s13x16_r[(2*lane+1)*13 +: 13]),
                .sum(s1_sum0_next[lane*14 +: 14])
            );
            hap_a8w4_add2_lut #(.IN_W(13)) u_add1 (
                .lhs(s0_sum1_s13x16_r[(2*lane)*13 +: 13]),
                .rhs(s0_sum1_s13x16_r[(2*lane+1)*13 +: 13]),
                .sum(s1_sum1_next[lane*14 +: 14])
            );
        end

        for (lane = 0; lane < 4; lane = lane + 1) begin : gen_reduce_s2
            hap_a8w4_add2_lut #(.IN_W(14)) u_add0 (
                .lhs(s1_sum0_s14x8_r[(2*lane)*14 +: 14]),
                .rhs(s1_sum0_s14x8_r[(2*lane+1)*14 +: 14]),
                .sum(s2_sum0_next[lane*15 +: 15])
            );
            hap_a8w4_add2_lut #(.IN_W(14)) u_add1 (
                .lhs(s1_sum1_s14x8_r[(2*lane)*14 +: 14]),
                .rhs(s1_sum1_s14x8_r[(2*lane+1)*14 +: 14]),
                .sum(s2_sum1_next[lane*15 +: 15])
            );
        end

        for (lane = 0; lane < 2; lane = lane + 1) begin : gen_reduce_s3
            hap_a8w4_add2_lut #(.IN_W(15)) u_add0 (
                .lhs(s2_sum0_s15x4_r[(2*lane)*15 +: 15]),
                .rhs(s2_sum0_s15x4_r[(2*lane+1)*15 +: 15]),
                .sum(s3_sum0_next[lane*16 +: 16])
            );
            hap_a8w4_add2_lut #(.IN_W(15)) u_add1 (
                .lhs(s2_sum1_s15x4_r[(2*lane)*15 +: 15]),
                .rhs(s2_sum1_s15x4_r[(2*lane+1)*15 +: 15]),
                .sum(s3_sum1_next[lane*16 +: 16])
            );
        end
    endgenerate

    hap_a8w4_add2_lut #(.IN_W(16)) u_reduce_s4_col0 (
        .lhs(s3_sum0_s16x2_r[0 +: 16]),
        .rhs(s3_sum0_s16x2_r[16 +: 16]), .sum(s4_sum0_next));
    hap_a8w4_add2_lut #(.IN_W(16)) u_reduce_s4_col1 (
        .lhs(s3_sum1_s16x2_r[0 +: 16]),
        .rhs(s3_sum1_s16x2_r[16 +: 16]), .sum(s4_sum1_next));

    always @(posedge clk) begin
        if (!rst_n) begin
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            s2_valid_r <= 1'b0;
            s3_valid_r <= 1'b0;
            s4_valid_r <= 1'b0;
            dot_q_wr_ptr_r <= 1'b0;
            dot_q_rd_ptr_r <= 1'b0;
            dot_q_count_r <= 2'd0;
            dot0_q[0] <= '0;
            dot0_q[1] <= '0;
            dot1_q[0] <= '0;
            dot1_q[1] <= '0;
        end else if (clear) begin
            s0_valid_r <= 1'b0;
            s1_valid_r <= 1'b0;
            s2_valid_r <= 1'b0;
            s3_valid_r <= 1'b0;
            s4_valid_r <= 1'b0;
            dot_q_wr_ptr_r <= 1'b0;
            dot_q_rd_ptr_r <= 1'b0;
            dot_q_count_r <= 2'd0;
        end else begin
            if (dot_q_push) begin
                dot0_q[dot_q_wr_ptr_r] <= s4_sum0_s17_r;
                dot1_q[dot_q_wr_ptr_r] <= s4_sum1_s17_r;
                dot_q_wr_ptr_r <= dot_q_wr_ptr_r + 1'b1;
            end
            if (dot_q_pop)
                dot_q_rd_ptr_r <= dot_q_rd_ptr_r + 1'b1;
            case ({dot_q_push, dot_q_pop})
                2'b10: dot_q_count_r <= dot_q_count_r + 1'b1;
                2'b01: dot_q_count_r <= dot_q_count_r - 1'b1;
                default: dot_q_count_r <= dot_q_count_r;
            endcase
            if (s4_ready) begin
                s4_valid_r <= s3_valid_r;
                if (s3_valid_r) begin
                    s4_sum0_s17_r <= s4_sum0_next;
                    s4_sum1_s17_r <= s4_sum1_next;
                end
            end
            if (s3_ready) begin
                s3_valid_r <= s2_valid_r;
                if (s2_valid_r) begin
                    s3_sum0_s16x2_r <= s3_sum0_next;
                    s3_sum1_s16x2_r <= s3_sum1_next;
                end
            end
            if (s2_ready) begin
                s2_valid_r <= s1_valid_r;
                if (s1_valid_r) begin
                    s2_sum0_s15x4_r <= s2_sum0_next;
                    s2_sum1_s15x4_r <= s2_sum1_next;
                end
            end
            if (s1_ready) begin
                s1_valid_r <= s0_valid_r;
                if (s0_valid_r) begin
                    s1_sum0_s14x8_r <= s1_sum0_next;
                    s1_sum1_s14x8_r <= s1_sum1_next;
                end
            end
            if (s0_ready) begin
                s0_valid_r <= leaf_output_fire;
                if (leaf_output_fire) begin
                    s0_sum0_s13x16_r <= s0_sum0_next;
                    s0_sum1_s13x16_r <= s0_sum1_next;
                end
            end
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && (leaf_out_valid != {32{leaf_out_valid[0]}}))
            $error("hap_a8w4_group32_pack2_s17 leaf valid divergence");
        if (rst_n && !clear && group_input_fire &&
            (leaf_in_ready != {32{leaf_in_ready[0]}}))
            $error("hap_a8w4_group32_pack2_s17 leaf ready divergence");
        if (rst_n && !clear && dot_q_count_r > 2)
            $error("hap_a8w4_group32_pack2_s17 output queue overflow");
    end
`endif

endmodule
