`timescale 1ns / 1ps

// Minimal V5 shared-compute closure for one physical 8x12 slice.
//
// This is deliberately an independent leaf boundary.  It proves that the
// 96-lane S36 bus maps to row-major `row*12+column` S43/S45 accumulation
// without changing the V4 production wrapper before the 48-column scheduler
// contract is integrated.
module hap_mlp_shared_slice8x12_s43_s45 (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_down,
    input  wire                         in_first,
    input  wire                         in_last,
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [12*32*4-1:0]    weights_s4x12x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [12*8-1:0]              weight_code_u8x12,
    input  wire [12*6-1:0]              weight_shift_u6x12,
    input  wire [11:0]                  column_valid_u12,
    output wire                         gate_valid,
    input  wire                         gate_ready,
    output wire signed [8*12*24-1:0]    gate_s24x8x12,
    output wire                         down_valid,
    input  wire                         down_ready,
    output wire signed [8*12*24-1:0]    down_s24x8x12,
    output wire [31:0]                  gate_saturation,
    output wire [31:0]                  down_saturation,
    output wire                         error
);

    localparam integer LANES = 8*12;
    reg tag_mode [0:31];
    reg tag_first [0:31];
    reg tag_last [0:31];
    reg [4:0] tag_wr_ptr_r;
    reg [4:0] tag_rd_ptr_r;
    reg [5:0] tag_count_r;
    wire tag_full = tag_count_r == 32;
    wire tag_empty = tag_count_r == 0;
    wire kernel_ready;
    wire kernel_valid;
    wire gate_accum_ready;
    wire down_accum_ready;
    wire selected_ready = tag_mode[tag_rd_ptr_r] ?
        down_accum_ready : gate_accum_ready;
    wire kernel_fire = kernel_valid && !tag_empty && selected_ready;
    wire input_fire = in_valid && in_ready;
    wire signed [LANES*36-1:0] guard_s36;
    wire kernel_error;
    wire gate_error;
    wire down_error;

    assign in_ready = rst_n && !clear && !tag_full && kernel_ready;

    hap_a8w4_slice8x12_group_s36 u_kernel (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && !tag_full), .in_ready(kernel_ready),
        .activation_s9x8x32(activation_s9x8x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x8(activation_code_u8x8),
        .activation_shift_u6x8(activation_shift_u6x8),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .out_valid(kernel_valid),
        .out_ready(!tag_empty && selected_ready),
        .guard_s36x8x12(guard_s36),
        .input_group_count(), .output_group_count(), .error(kernel_error)
    );

    hap_mlp_tile_accum_s36 #(
        .LANES(LANES), .ACC_W(43), .GROUPS(128),
        .ALLOW_V5_96_LANES(1)
    ) u_gate_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(kernel_valid && !tag_empty && !tag_mode[tag_rd_ptr_r]),
        .in_ready(gate_accum_ready),
        .in_first_group(tag_first[tag_rd_ptr_r]),
        .in_last_group(tag_last[tag_rd_ptr_r]),
        .in_guard_s36(guard_s36),
        .out_valid(gate_valid), .out_ready(gate_ready),
        .out_projection_s24(gate_s24x8x12),
        .input_group_count(), .output_tile_count(),
        .saturation_count(gate_saturation), .error(gate_error)
    );

    hap_mlp_tile_accum_s36 #(
        .LANES(LANES), .ACC_W(45), .GROUPS(448),
        .ALLOW_V5_96_LANES(1)
    ) u_down_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(kernel_valid && !tag_empty && tag_mode[tag_rd_ptr_r]),
        .in_ready(down_accum_ready),
        .in_first_group(tag_first[tag_rd_ptr_r]),
        .in_last_group(tag_last[tag_rd_ptr_r]),
        .in_guard_s36(guard_s36),
        .out_valid(down_valid), .out_ready(down_ready),
        .out_projection_s24(down_s24x8x12),
        .input_group_count(), .output_tile_count(),
        .saturation_count(down_saturation), .error(down_error)
    );

    assign error = kernel_error || gate_error || down_error;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
        end else begin
            if (input_fire) begin
                tag_mode[tag_wr_ptr_r] <= in_down;
                tag_first[tag_wr_ptr_r] <= in_first;
                tag_last[tag_wr_ptr_r] <= in_last;
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
            end
            if (kernel_fire)
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
            case ({input_fire, kernel_fire})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
        end
    end

endmodule
