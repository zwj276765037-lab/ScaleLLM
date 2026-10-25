`timescale 1ns / 1ps

module hap_softmax_prob_u16 #(
    parameter integer FIFO_DEPTH = 16
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          clear,
    input  wire          in_valid,
    output wire          in_ready,
    input  wire [16:0]   in_exp_u17,
    input  wire [16:0]   in_recip_u17,
    output wire          out_valid,
    input  wire          out_ready,
    output wire [15:0]   out_prob_u16,
    output reg  [31:0]   clamp_count,
    output reg            error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);
    reg product_valid_r;
    (* use_dsp = "yes" *) reg [32:0] product_u33_r;
    reg result_valid_r;
    reg [15:0] result_u16_r;
    reg result_clamped_r;
    (* ram_style = "distributed" *) reg [16:0] fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr_r;
    reg [PTR_W-1:0] fifo_rd_ptr_r;
    reg [COUNT_W-1:0] fifo_count_r;
    reg [COUNT_W-1:0] used_count_r;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire fifo_commit = result_valid_r &&
        ((fifo_count_r != FIFO_DEPTH) || out_fire);
    wire [33:0] rounded_product = {1'b0, product_u33_r} + 34'd32768;
    wire [17:0] rounded_u18 = rounded_product >> 16;

    assign in_ready = rst_n && !clear && (used_count_r < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_prob_u16 = fifo_mem[fifo_rd_ptr_r][15:0];

    always @(posedge clk) begin
        if (in_fire)
            product_u33_r <= in_exp_u17 * in_recip_u17;
        if (product_valid_r) begin
            result_clamped_r <= rounded_u18 > 65535;
            result_u16_r <= (rounded_u18 > 65535) ? 16'hffff :
                rounded_u18[15:0];
        end
        if (fifo_commit)
            fifo_mem[fifo_wr_ptr_r] <= {result_clamped_r, result_u16_r};
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            product_valid_r <= 1'b0;
            result_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            clamp_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            product_valid_r <= 1'b0;
            result_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            clamp_count <= 32'd0;
            error <= 1'b0;
        end else begin
            product_valid_r <= in_fire;
            result_valid_r <= product_valid_r;
            if (in_fire && ((in_exp_u17 > 17'd65536) ||
                (in_recip_u17 > 17'd65536)))
                error <= 1'b1;
            if (result_valid_r) begin
                if ((fifo_count_r == FIFO_DEPTH) && !out_fire)
                    error <= 1'b1;
                else
                    fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                if (fifo_mem[fifo_rd_ptr_r][16])
                    clamp_count <= clamp_count + 32'd1;
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
        end
    end
endmodule
