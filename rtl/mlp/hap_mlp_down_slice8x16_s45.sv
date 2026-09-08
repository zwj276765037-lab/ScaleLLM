`timescale 1ns / 1ps

// One physical down-projection slice: A8W4 group kernel followed by a local
// 128-lane, 448-group S45 accumulator.  The 4,608-bit S36 boundary remains
// inside the slice SLR and only completed S24 tiles leave this hierarchy.
module hap_mlp_down_slice8x16_s45 (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_first_group,
    input  wire                         in_last_group,
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [16*32*4-1:0]    weights_s4x16x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [16*8-1:0]              weight_code_u8x16,
    input  wire [16*6-1:0]              weight_shift_u6x16,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [8*16*24-1:0]    projection_s24x8x16,
    output wire [31:0]                  input_group_count,
    output wire [31:0]                  output_tile_count,
    output wire [31:0]                  saturation_count,
    output wire                         error
);

    wire group_kernel_ready;
    wire group_valid;
    wire accum_in_ready;
    wire signed [8*16*36-1:0] group_guard_s36;
    wire [31:0] kernel_input_count;
    wire [31:0] kernel_output_count;
    wire kernel_error;
    wire accum_error;

    reg tag_first_mem [0:31];
    reg tag_last_mem [0:31];
    reg [4:0] tag_wr_ptr_r;
    reg [4:0] tag_rd_ptr_r;
    reg [5:0] tag_count_r;
    wire tag_full = tag_count_r == 32;
    wire tag_empty = tag_count_r == 0;
    wire kernel_in_fire = in_valid && in_ready;
    wire kernel_out_fire = group_valid && accum_in_ready && !tag_empty;

    assign in_ready = !tag_full && group_kernel_ready;

    hap_a8w4_slice8x16_group_s36 u_group_kernel (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && !tag_full), .in_ready(group_kernel_ready),
        .activation_s9x8x32(activation_s9x8x32),
        .weights_s4x16x32(weights_s4x16x32),
        .activation_code_u8x8(activation_code_u8x8),
        .activation_shift_u6x8(activation_shift_u6x8),
        .weight_code_u8x16(weight_code_u8x16),
        .weight_shift_u6x16(weight_shift_u6x16),
        .out_valid(group_valid), .out_ready(accum_in_ready && !tag_empty),
        .guard_s36x8x16(group_guard_s36),
        .input_group_count(kernel_input_count),
        .output_group_count(kernel_output_count), .error(kernel_error)
    );

    hap_mlp_tile_accum_s36 #(
        .LANES(128), .ACC_W(45), .GROUPS(448)
    ) u_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(group_valid && !tag_empty), .in_ready(accum_in_ready),
        .in_first_group(tag_first_mem[tag_rd_ptr_r]),
        .in_last_group(tag_last_mem[tag_rd_ptr_r]),
        .in_guard_s36(group_guard_s36),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_projection_s24(projection_s24x8x16),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(accum_error)
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
        if (rst_n && !clear && group_valid && tag_empty)
            $error("down slice produced a group without a matching tag");
        if (rst_n && !clear && kernel_output_count > kernel_input_count)
            $error("down slice kernel count ordering error");
    end
`endif

endmodule
