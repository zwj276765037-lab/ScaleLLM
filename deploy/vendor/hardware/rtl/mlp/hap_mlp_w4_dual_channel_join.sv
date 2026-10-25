`timescale 1ns / 1ps

// Atomic join of two eight-column W4 halves and one 16-column ScaleCode meta
// transaction.  Output payload is the native 16 columns x group32 x W4.
module hap_mlp_w4_dual_channel_join (
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   clear,
    input  wire                   half0_valid,
    output wire                   half0_ready,
    input  wire [1023:0]          half0_data,
    input  wire                   half1_valid,
    output wire                   half1_ready,
    input  wire [1023:0]          half1_data,
    input  wire                   meta_valid,
    output wire                   meta_ready,
    input  wire [223:0]           meta_u224,
    output wire                   out_valid,
    input  wire                   out_ready,
    output wire [2047:0]          weights_s4x16x32,
    output wire [223:0]           weight_meta_u224,
    output reg  [31:0]            useful_group_count,
    output reg  [63:0]            useful_weight_byte_count,
    output reg                    error
);

    reg out_valid_r;
    reg [2047:0] weights_r;
    reg [223:0] meta_r;
    wire capacity = !out_valid_r || out_ready;
    wire assemble = capacity && half0_valid && half1_valid && meta_valid;
    wire out_fire = out_valid && out_ready;

    assign half0_ready = assemble;
    assign half1_ready = assemble;
    assign meta_ready = assemble;
    assign out_valid = rst_n && !clear && out_valid_r;
    assign weights_s4x16x32 = weights_r;
    assign weight_meta_u224 = meta_r;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            out_valid_r <= 1'b0;
            useful_group_count <= 32'd0;
            useful_weight_byte_count <= 64'd0;
            error <= 1'b0;
        end else begin
            if (capacity)
                out_valid_r <= assemble;
            if (assemble) begin
                weights_r <= {half1_data, half0_data};
                meta_r <= meta_u224;
            end
            if (out_fire) begin
                useful_group_count <= useful_group_count + 32'd1;
                useful_weight_byte_count <=
                    useful_weight_byte_count + 64'd256;
            end
            if (half0_ready != half1_ready ||
                half0_ready != meta_ready)
                error <= 1'b1;
        end
    end

endmodule
