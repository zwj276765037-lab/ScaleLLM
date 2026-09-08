`timescale 1ns / 1ps

// One physical 8-request x 16-column down-projection slice for group-major
// scheduling.  The S36 kernel output and the 128 independently banked S45
// output accumulators remain in the same hierarchy/SLR.  Only completed S24
// output tiles leave the module.
module hap_mlp_down_group_major_slice8x16_s45 #(
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
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [16*32*4-1:0]    weights_s4x16x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [16*8-1:0]              weight_code_u8x16,
    input  wire [16*6-1:0]              weight_shift_u6x16,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire [TILE_W-1:0]            out_tile_index,
    output wire signed [8*16*24-1:0]    projection_s24x8x16,
    output wire [31:0]                  input_tile_count,
    output wire [31:0]                  input_group_count,
    output wire [31:0]                  output_tile_count,
    output wire [31:0]                  saturation_count,
    output wire                         error
);

    wire kernel_in_ready;
    wire kernel_out_valid;
    wire kernel_out_ready;
    wire signed [8*16*36-1:0] kernel_guard_s36;
    wire [31:0] kernel_input_count;
    wire [31:0] kernel_output_count;
    wire kernel_error;

    reg tag_first_mem [0:31];
    reg tag_last_mem [0:31];
    reg [TILE_W-1:0] tag_tile_mem [0:31];
    reg [4:0] tag_wr_ptr_r;
    reg [4:0] tag_rd_ptr_r;
    reg [5:0] tag_count_r;
    wire tag_full = tag_count_r == 32;
    wire tag_empty = tag_count_r == 0;
    wire kernel_in_fire = in_valid && in_ready;

    wire accum_in_ready;
    wire accum_error;
    wire kernel_out_fire = kernel_out_valid && kernel_out_ready;
    assign in_ready = !tag_full && kernel_in_ready;
    assign kernel_out_ready = !tag_empty && accum_in_ready;

    hap_a8w4_slice8x16_group_s36 u_group_kernel (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && !tag_full), .in_ready(kernel_in_ready),
        .activation_s9x8x32(activation_s9x8x32),
        .weights_s4x16x32(weights_s4x16x32),
        .activation_code_u8x8(activation_code_u8x8),
        .activation_shift_u6x8(activation_shift_u6x8),
        .weight_code_u8x16(weight_code_u8x16),
        .weight_shift_u6x16(weight_shift_u6x16),
        .out_valid(kernel_out_valid), .out_ready(kernel_out_ready),
        .guard_s36x8x16(kernel_guard_s36),
        .input_group_count(kernel_input_count),
        .output_group_count(kernel_output_count),
        .error(kernel_error)
    );

    hap_mlp_down_group_major_accum_s45 #(
        .LANES(128), .TILES(TILES), .GROUPS(GROUPS),
        .TILE_W(TILE_W)
    ) u_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(kernel_out_valid && !tag_empty),
        .in_ready(accum_in_ready),
        .in_first_group(tag_first_mem[tag_rd_ptr_r]),
        .in_last_group(tag_last_mem[tag_rd_ptr_r]),
        .in_tile_index(tag_tile_mem[tag_rd_ptr_r]),
        .in_guard_s36(kernel_guard_s36),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .out_projection_s24(projection_s24x8x16),
        .input_tile_count(input_tile_count),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count),
        .error(accum_error)
    );

    assign error = kernel_error || accum_error;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
        end else begin
            if (kernel_in_fire) begin
                tag_first_mem[tag_wr_ptr_r] <= in_first_group;
                tag_last_mem[tag_wr_ptr_r] <= in_last_group;
                tag_tile_mem[tag_wr_ptr_r] <= in_tile_index;
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
            end
            if (kernel_out_fire)
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
            case ({kernel_in_fire, kernel_out_fire})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && kernel_out_valid && tag_empty)
            $error("group-major down slice output missing tag");
        if (rst_n && !clear && kernel_output_count > kernel_input_count)
            $error("group-major down kernel count ordering error");
    end
`endif

endmodule
