`timescale 1ns / 1ps

module hap_dual_ddr_weight_group_assembler (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  ddr0_valid,
    output wire                  ddr0_ready,
    input  wire [2047:0]         ddr0_half,
    input  wire                  ddr1_valid,
    output wire                  ddr1_ready,
    input  wire [2047:0]         ddr1_half,
    input  wire                  meta_valid,
    output wire                  meta_ready,
    input  wire [9:0]            meta_tile,
    input  wire [6:0]            meta_group,
    input  wire [255:0]          meta16,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [9:0]            out_tile,
    output wire [6:0]            out_group,
    output wire [4095:0]         out_weight_s8,
    output wire [255:0]          out_meta16,
    output reg  [31:0]           assembled_group_count,
    output reg                   error
);

    reg out_valid_r;
    reg [9:0] out_tile_r;
    reg [6:0] out_group_r;
    reg [4095:0] out_weight_r;
    reg [255:0] out_meta_r;
    wire capacity = !out_valid_r || out_ready;
    wire assemble = capacity && ddr0_valid && ddr1_valid && meta_valid;
    wire out_fire = out_valid && out_ready;

    assign ddr0_ready = assemble;
    assign ddr1_ready = assemble;
    assign meta_ready = assemble;
    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_tile = out_tile_r;
    assign out_group = out_group_r;
    assign out_weight_s8 = out_weight_r;
    assign out_meta16 = out_meta_r;

    always @(posedge clk) begin
        if (assemble) begin
            out_weight_r <= {ddr1_half, ddr0_half};
            out_meta_r <= meta16;
            out_tile_r <= meta_tile;
            out_group_r <= meta_group;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid_r <= 1'b0;
            assembled_group_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            out_valid_r <= 1'b0;
            assembled_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (capacity)
                out_valid_r <= assemble;
            if (out_fire)
                assembled_group_count <= assembled_group_count + 32'd1;
            if ((ddr0_ready != ddr1_ready) ||
                (ddr0_ready != meta_ready))
                error <= 1'b1;
        end
    end

endmodule
