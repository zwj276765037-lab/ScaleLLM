`timescale 1ns/1ps

module m1_fp_attention_frontend_8row #(
    parameter integer FP_W = 16
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_bank,
    input  wire [6:0]                    in_group,
    input  wire [8*32*24-1:0]            in_s24,
    input  wire                          rd_req_valid,
    output wire                          rd_req_ready,
    input  wire                          rd_req_bank,
    input  wire [6:0]                    rd_req_group,
    output wire                          rd_rsp_valid,
    input  wire                          rd_rsp_ready,
    output wire                          rd_rsp_bank,
    output wire [6:0]                    rd_rsp_group,
    output wire [8*32*8-1:0]             rd_rsp_u8,
    output wire [8*(FP_W+8)-1:0]         rd_rsp_meta,
    input  wire                          release_valid,
    output wire                          release_ready,
    input  wire                          release_bank,
    output wire [1:0]                    bank_ready,
    output reg  [31:0]                   input_group_count,
    output wire [31:0]                   cache_write_count,
    output wire [31:0]                   cache_read_count,
    output wire [31:0]                   cache_release_count,
    output wire [31:0]                   hadamard_saturation_count,
    output wire [31:0]                   format_error_count,
    output wire                          error
);
    localparam integer ROWS = 8;
    localparam integer GROUP_SIZE = 32;
    localparam integer ROW_W = 3;
    localparam integer META_W = ROWS * (FP_W + 8);

    reg input_buffer_valid_r;
    reg input_buffer_bank_r;
    reg [6:0] input_buffer_group_r;
    reg [ROWS*GROUP_SIZE*24-1:0] input_buffer_s24_r;
    reg serializer_active_r;
    reg [ROW_W-1:0] serializer_row_r;
    reg group_active_r;
    reg active_bank_r;
    reg [6:0] active_group_r;
    reg [ROW_W-1:0] had_output_row_r;
    reg [ROWS-1:0] row_done_r;
    reg bundle_valid_r;
    reg bundle_bank_r;
    reg [6:0] bundle_group_r;
    reg [ROWS*GROUP_SIZE*8-1:0] bundle_u8_r;
    reg [META_W-1:0] bundle_meta_r;
    reg control_error_r;

    wire had_in_ready;
    wire had_out_valid;
    wire had_out_ready;
    wire [GROUP_SIZE*27-1:0] had_out_s27;
    wire [31:0] had_input_count_unused;
    wire [31:0] had_output_count_unused;
    wire had_error;
    wire [ROWS-1:0] quant_in_ready;
    wire [ROWS-1:0] quant_in_valid;
    wire [ROWS-1:0] quant_out_valid;
    wire [ROWS-1:0] quant_error;
    wire [ROWS*GROUP_SIZE*8-1:0] quant_out_u8;
    wire [META_W-1:0] quant_out_meta;
    wire [ROWS-1:0] quant_collect;
    wire [ROWS-1:0] row_done_next;
    wire cache_wr_ready;
    wire cache_error;
    wire input_fire = in_valid && in_ready;
    wire [23:0] input_fire_local;

    genvar input_capture_bank;
    generate
        for (input_capture_bank = 0; input_capture_bank < 24;
             input_capture_bank = input_capture_bank + 1) begin : g_input_capture_control
            (* DONT_TOUCH = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(input_fire), .O(input_fire_local[input_capture_bank])
            );
        end
    endgenerate

    wire serializer_start = !serializer_active_r && !group_active_r &&
        !bundle_valid_r && input_buffer_valid_r && (&quant_in_ready);
    wire had_in_fire = serializer_active_r && had_in_ready;
    wire had_out_fire = had_out_valid && had_out_ready;
    wire cache_wr_fire = bundle_valid_r && cache_wr_ready;

    assign in_ready = rst_n && !clear && !control_error_r &&
        !input_buffer_valid_r;
    assign had_out_ready = group_active_r && quant_in_ready[had_output_row_r];
    assign quant_collect = quant_out_valid & {ROWS{group_active_r}} & ~row_done_r;
    assign row_done_next = row_done_r | quant_collect;
    assign error = control_error_r | had_error | (|quant_error) | cache_error;

    hap_hadamard32_norm_stream u_hadamard (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(serializer_active_r), .in_ready(had_in_ready),
        .in_s24(input_buffer_s24_r[
            serializer_row_r*GROUP_SIZE*24 +: GROUP_SIZE*24]),
        .out_valid(had_out_valid), .out_ready(had_out_ready),
        .out_s27(had_out_s27), .input_group_count(had_input_count_unused),
        .output_group_count(had_output_count_unused),
        .saturation_count(hadamard_saturation_count), .error(had_error)
    );

    genvar row;
    generate
        for (row = 0; row < ROWS; row = row + 1) begin : g_quantizer
            wire [31:0] unused_quant_input_count;
            wire [31:0] unused_quant_output_count;
            wire [31:0] unused_quant_cycle_count;
            assign quant_in_valid[row] = had_out_valid &&
                (had_output_row_r == row[ROW_W-1:0]);
            m1_native_fp_a8_quantizer #(.FP_W(FP_W)) u_quantizer (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(quant_in_valid[row]), .in_ready(quant_in_ready[row]),
                .in_s27(had_out_s27), .out_valid(quant_out_valid[row]),
                .out_ready(group_active_r && !row_done_r[row]),
                .out_u8(quant_out_u8[row*GROUP_SIZE*8 +: GROUP_SIZE*8]),
                .out_meta(quant_out_meta[row*(FP_W+8) +: FP_W+8]),
                .input_group_count(unused_quant_input_count),
                .output_group_count(unused_quant_output_count),
                .cycle_count(unused_quant_cycle_count), .error(quant_error[row])
            );
        end
    endgenerate

    m1_fp_activation_cache_8row #(.FP_W(FP_W)) u_cache (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(bundle_valid_r), .wr_ready(cache_wr_ready),
        .wr_bank(bundle_bank_r), .wr_group(bundle_group_r),
        .wr_u8(bundle_u8_r), .wr_meta(bundle_meta_r),
        .rd_req_valid(rd_req_valid), .rd_req_ready(rd_req_ready),
        .rd_req_bank(rd_req_bank), .rd_req_group(rd_req_group),
        .rd_rsp_valid(rd_rsp_valid), .rd_rsp_ready(rd_rsp_ready),
        .rd_rsp_bank(rd_rsp_bank), .rd_rsp_group(rd_rsp_group),
        .rd_rsp_u8(rd_rsp_u8), .rd_rsp_meta(rd_rsp_meta),
        .release_valid(release_valid), .release_ready(release_ready),
        .release_bank(release_bank), .bank_ready(bank_ready),
        .write_count(cache_write_count), .read_count(cache_read_count),
        .release_count(cache_release_count),
        .format_error_count(format_error_count), .error(cache_error)
    );

    integer capture_row;
    integer input_capture_index;
    always @(posedge clk) begin
        for (input_capture_index = 0; input_capture_index < 24;
             input_capture_index = input_capture_index + 1)
            if (input_fire_local[input_capture_index])
                input_buffer_s24_r[input_capture_index*256 +: 256] <=
                    in_s24[input_capture_index*256 +: 256];
        if (group_active_r)
            for (capture_row = 0; capture_row < ROWS;
                 capture_row = capture_row + 1)
                if (quant_collect[capture_row]) begin
                    bundle_u8_r[capture_row*GROUP_SIZE*8 +: GROUP_SIZE*8] <=
                        quant_out_u8[capture_row*GROUP_SIZE*8 +: GROUP_SIZE*8];
                    bundle_meta_r[capture_row*(FP_W+8) +: FP_W+8] <=
                        quant_out_meta[capture_row*(FP_W+8) +: FP_W+8];
                end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            input_buffer_valid_r <= 1'b0;
            input_buffer_bank_r <= 1'b0;
            input_buffer_group_r <= 7'd0;
            serializer_active_r <= 1'b0;
            serializer_row_r <= '0;
            group_active_r <= 1'b0;
            active_bank_r <= 1'b0;
            active_group_r <= 7'd0;
            had_output_row_r <= '0;
            row_done_r <= '0;
            bundle_valid_r <= 1'b0;
            bundle_bank_r <= 1'b0;
            bundle_group_r <= 7'd0;
            input_group_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            input_buffer_valid_r <= 1'b0;
            serializer_active_r <= 1'b0;
            serializer_row_r <= '0;
            group_active_r <= 1'b0;
            had_output_row_r <= '0;
            row_done_r <= '0;
            bundle_valid_r <= 1'b0;
            input_group_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (input_fire) begin
                input_buffer_valid_r <= 1'b1;
                input_buffer_bank_r <= in_bank;
                input_buffer_group_r <= in_group;
                input_group_count <= input_group_count + 32'd1;
            end
            if (serializer_start) begin
                serializer_active_r <= 1'b1;
                serializer_row_r <= '0;
                group_active_r <= 1'b1;
                active_bank_r <= input_buffer_bank_r;
                active_group_r <= input_buffer_group_r;
                had_output_row_r <= '0;
                row_done_r <= '0;
            end
            if (had_in_fire) begin
                if (serializer_row_r == ROWS-1) begin
                    serializer_active_r <= 1'b0;
                    serializer_row_r <= '0;
                    input_buffer_valid_r <= 1'b0;
                end else
                    serializer_row_r <= serializer_row_r + 1'b1;
            end
            if (had_out_fire) begin
                if (had_output_row_r == ROWS-1)
                    had_output_row_r <= '0;
                else
                    had_output_row_r <= had_output_row_r + 1'b1;
            end
            if (group_active_r) begin
                row_done_r <= row_done_next;
                if (&row_done_next) begin
                    group_active_r <= 1'b0;
                    row_done_r <= '0;
                    bundle_valid_r <= 1'b1;
                    bundle_bank_r <= active_bank_r;
                    bundle_group_r <= active_group_r;
                end
            end
            if (cache_wr_fire)
                bundle_valid_r <= 1'b0;
            if ((had_out_valid && !group_active_r) ||
                    ((|quant_out_valid) && !group_active_r))
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if ((FP_W != 16) && (FP_W != 32))
            $error("m1_fp_attention_frontend_8row FP_W must be 16 or 32");
    end
endmodule

module m1_fp16_attention_frontend_8row (
    input wire clk, rst_n, clear, in_valid, input wire in_bank,
    input wire [6:0] in_group, input wire [6143:0] in_s24,
    output wire in_ready, input wire rd_req_valid, input wire rd_req_bank,
    input wire [6:0] rd_req_group, output wire rd_req_ready,
    output wire rd_rsp_valid, input wire rd_rsp_ready,
    output wire rd_rsp_bank, output wire [6:0] rd_rsp_group,
    output wire [2047:0] rd_rsp_u8, output wire [191:0] rd_rsp_meta,
    input wire release_valid, input wire release_bank,
    output wire release_ready, output wire [1:0] bank_ready,
    output wire [31:0] input_group_count, cache_write_count,
    output wire [31:0] cache_read_count, cache_release_count,
    output wire [31:0] hadamard_saturation_count, format_error_count,
    output wire error
);
    m1_fp_attention_frontend_8row #(.FP_W(16)) u_frontend (.*);
endmodule

module m1_fp32_attention_frontend_8row (
    input wire clk, rst_n, clear, in_valid, input wire in_bank,
    input wire [6:0] in_group, input wire [6143:0] in_s24,
    output wire in_ready, input wire rd_req_valid, input wire rd_req_bank,
    input wire [6:0] rd_req_group, output wire rd_req_ready,
    output wire rd_rsp_valid, input wire rd_rsp_ready,
    output wire rd_rsp_bank, output wire [6:0] rd_rsp_group,
    output wire [2047:0] rd_rsp_u8, output wire [319:0] rd_rsp_meta,
    input wire release_valid, input wire release_bank,
    output wire release_ready, output wire [1:0] bank_ready,
    output wire [31:0] input_group_count, cache_write_count,
    output wire [31:0] cache_read_count, cache_release_count,
    output wire [31:0] hadamard_saturation_count, format_error_count,
    output wire error
);
    m1_fp_attention_frontend_8row #(.FP_W(32)) u_frontend (.*);
endmodule
