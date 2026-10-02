`timescale 1ns/1ps

// Native floating-scale counterpart of hap_mlp_product_frontend16_q4.
// The shared II=1 S32 Hadamard engine and four-quantizer round-robin schedule
// match production; only ScaleCode generation is replaced by affine U8 plus
// an IEEE FP16/FP32 scale.
module m11_fp_mlp_product_frontend16_q4 #(
    parameter integer FP_W = 16
) (
    input  wire                           clk,
    input  wire                           rst_n,
    input  wire                           clear,
    input  wire                           in_valid,
    output wire                           in_ready,
    input  wire signed [16*32*32-1:0]     product_s32x16x32,
    output wire                           out_valid,
    input  wire                           out_ready,
    output wire [16*32*8-1:0]             activation_u8x16x32,
    output wire [16*(FP_W+8)-1:0]         activation_meta,
    output reg  [31:0]                    input_group_count,
    output reg  [31:0]                    output_group_count,
    output reg  [31:0]                    busy_cycle_count,
    output reg                            error
);
    localparam integer META_PER_ROW = FP_W + 8;

    reg active_r;
    reg out_valid_r;
    reg signed [16*32*32-1:0] product_buffer_r;
    (* DONT_TOUCH = "yes" *) reg [63:0] product_capture_open_bank_r;
    reg [4:0] source_row_r;
    reg [4:0] dispatch_row_r;
    reg [2:0] quant_output_wave_r [0:3];
    reg [5:0] completed_row_count_r;
    reg [16*32*8-1:0] activation_u8_r;
    reg [16*META_PER_ROW-1:0] activation_meta_r;

    wire hadamard_in_valid = active_r && source_row_r < 16;
    wire hadamard_in_ready;
    wire hadamard_in_fire = hadamard_in_valid && hadamard_in_ready;
    wire [32*32-1:0] hadamard_in_s32 =
        product_buffer_r[source_row_r*32*32 +: 32*32];
    wire hadamard_out_valid;
    wire hadamard_out_ready;
    wire [32*35-1:0] hadamard_out_s35;
    wire hadamard_error;

    wire [3:0] quant_in_ready;
    wire [3:0] quant_out_valid;
    wire [3:0] quant_out_ready;
    wire [4*32*8-1:0] quant_out_u8;
    wire [4*META_PER_ROW-1:0] quant_out_meta;
    wire [3:0] quant_error;
    wire [1:0] dispatch_quantizer = dispatch_row_r[1:0];
    wire hadamard_out_fire = hadamard_out_valid && hadamard_out_ready;
    wire [3:0] quant_out_fire = quant_out_valid & quant_out_ready;
    wire [2:0] quant_fire_count =
        {2'd0, quant_out_fire[0]} + {2'd0, quant_out_fire[1]} +
        {2'd0, quant_out_fire[2]} + {2'd0, quant_out_fire[3]};
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && !active_r && !out_valid_r;
    assign out_valid = rst_n && !clear && out_valid_r;
    assign activation_u8x16x32 = activation_u8_r;
    assign activation_meta = activation_meta_r;
    assign hadamard_out_ready = quant_in_ready[dispatch_quantizer];

    integer capture_bank;
    always @(posedge clk) begin
        for (capture_bank = 0; capture_bank < 64;
             capture_bank = capture_bank + 1)
            if (product_capture_open_bank_r[capture_bank] && in_valid)
                product_buffer_r[capture_bank*256 +: 256] <=
                    product_s32x16x32[capture_bank*256 +: 256];
    end

    hap_mlp_hadamard32_s32_norm_stream u_hadamard (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(hadamard_in_valid), .in_ready(hadamard_in_ready),
        .in_s32(hadamard_in_s32),
        .out_valid(hadamard_out_valid), .out_ready(hadamard_out_ready),
        .out_s35(hadamard_out_s35), .input_group_count(),
        .output_group_count(), .saturation_count(), .error(hadamard_error)
    );

    genvar quantizer;
    generate
        for (quantizer = 0; quantizer < 4;
             quantizer = quantizer + 1) begin : g_quantizer
            m11_native_fp_a8_quantizer_s35 #(.FP_W(FP_W)) u_quantizer (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(hadamard_out_valid &&
                    dispatch_quantizer == quantizer[1:0]),
                .in_ready(quant_in_ready[quantizer]),
                .in_s35(hadamard_out_s35),
                .out_valid(quant_out_valid[quantizer]),
                .out_ready(quant_out_ready[quantizer]),
                .out_u8(quant_out_u8[quantizer*32*8 +: 32*8]),
                .out_meta(quant_out_meta[
                    quantizer*META_PER_ROW +: META_PER_ROW]),
                .input_group_count(), .output_group_count(), .cycle_count(),
                .error(quant_error[quantizer])
            );
            assign quant_out_ready[quantizer] = active_r &&
                quant_output_wave_r[quantizer] < 4;
        end
    endgenerate

    integer q;
    integer output_row;
    always @(posedge clk) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            out_valid_r <= 1'b0;
            product_capture_open_bank_r <= {64{1'b1}};
            source_row_r <= '0;
            dispatch_row_r <= '0;
            completed_row_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            busy_cycle_count <= 32'd0;
            error <= 1'b0;
            for (q = 0; q < 4; q = q + 1)
                quant_output_wave_r[q] <= '0;
        end else if (clear) begin
            active_r <= 1'b0;
            out_valid_r <= 1'b0;
            product_capture_open_bank_r <= {64{1'b1}};
            source_row_r <= '0;
            dispatch_row_r <= '0;
            completed_row_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            busy_cycle_count <= 32'd0;
            error <= 1'b0;
            for (q = 0; q < 4; q = q + 1)
                quant_output_wave_r[q] <= '0;
        end else begin
            if (active_r)
                busy_cycle_count <= busy_cycle_count + 32'd1;
            if (in_fire) begin
                active_r <= 1'b1;
                product_capture_open_bank_r <= 64'd0;
                source_row_r <= '0;
                dispatch_row_r <= '0;
                completed_row_count_r <= '0;
                input_group_count <= input_group_count + 32'd1;
                for (q = 0; q < 4; q = q + 1)
                    quant_output_wave_r[q] <= '0;
            end
            if (hadamard_in_fire)
                source_row_r <= source_row_r + 1'b1;
            if (hadamard_out_fire)
                dispatch_row_r <= dispatch_row_r + 1'b1;
            for (q = 0; q < 4; q = q + 1) begin
                if (quant_out_fire[q]) begin
                    output_row = q + 4*quant_output_wave_r[q];
                    activation_u8_r[output_row*32*8 +: 32*8] <=
                        quant_out_u8[q*32*8 +: 32*8];
                    activation_meta_r[
                        output_row*META_PER_ROW +: META_PER_ROW] <=
                        quant_out_meta[q*META_PER_ROW +: META_PER_ROW];
                    quant_output_wave_r[q] <=
                        quant_output_wave_r[q] + 1'b1;
                end
            end
            if (quant_fire_count != 0) begin
                completed_row_count_r <=
                    completed_row_count_r + quant_fire_count;
                if (completed_row_count_r + quant_fire_count == 16)
                    out_valid_r <= 1'b1;
            end
            if (out_fire) begin
                out_valid_r <= 1'b0;
                active_r <= 1'b0;
                product_capture_open_bank_r <= {64{1'b1}};
                output_group_count <= output_group_count + 32'd1;
            end
            if (hadamard_error || (|quant_error) || source_row_r > 16 ||
                    dispatch_row_r > 16 || completed_row_count_r > 16)
                error <= 1'b1;
        end
    end

    initial begin
        if ((FP_W != 16) && (FP_W != 32))
            $error("M11 FP_W must be 16 or 32");
    end
endmodule

module m11_fp16_mlp_product_frontend16_q4 (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire signed [16383:0] product_s32x16x32,
    output wire out_valid,
    input wire out_ready,
    output wire [4095:0] activation_u8x16x32,
    output wire [383:0] activation_meta,
    output wire [31:0] input_group_count, output_group_count,
    output wire [31:0] busy_cycle_count,
    output wire error
);
    m11_fp_mlp_product_frontend16_q4 #(.FP_W(16)) u_frontend (.*);
endmodule

module m11_fp32_mlp_product_frontend16_q4 (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire signed [16383:0] product_s32x16x32,
    output wire out_valid,
    input wire out_ready,
    output wire [4095:0] activation_u8x16x32,
    output wire [639:0] activation_meta,
    output wire [31:0] input_group_count, output_group_count,
    output wire [31:0] busy_cycle_count,
    output wire error
);
    m11_fp_mlp_product_frontend16_q4 #(.FP_W(32)) u_frontend (.*);
endmodule
