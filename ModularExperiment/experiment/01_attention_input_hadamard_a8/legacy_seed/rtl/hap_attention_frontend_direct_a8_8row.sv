`timescale 1ns / 1ps

// M1 ablation: preserve the production 8-row/cache boundary and remove only
// the shared normalized Hadamard transform. S24 values are exactly sign
// extended to the quantizer's S27 Q*.16 input; no rescaling is introduced.
module hap_attention_frontend_direct_a8_8row #(
    parameter integer ROWS = 8,
    parameter integer GROUP_SIZE = 32,
    parameter integer GROUP_COUNT = 128
) (
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              clear,
    input  wire                              in_valid,
    output wire                              in_ready,
    input  wire                              in_bank,
    input  wire [6:0]                        in_group,
    input  wire [ROWS*GROUP_SIZE*24-1:0]     in_s24,
    input  wire                              rd_req_valid,
    output wire                              rd_req_ready,
    input  wire                              rd_req_bank,
    input  wire [6:0]                        rd_req_group,
    output wire                              rd_rsp_valid,
    input  wire                              rd_rsp_ready,
    output wire                              rd_rsp_bank,
    output wire [6:0]                        rd_rsp_group,
    output wire [ROWS*GROUP_SIZE*8-1:0]      rd_rsp_u8,
    output wire [ROWS*24-1:0]                rd_rsp_meta,
    input  wire                              release_valid,
    output wire                              release_ready,
    input  wire                              release_bank,
    output wire [1:0]                        bank_ready,
    output reg  [31:0]                       input_group_count,
    output wire [31:0]                       cache_write_count,
    output wire [31:0]                       cache_read_count,
    output wire [31:0]                       cache_release_count,
    output wire [31:0]                       hadamard_saturation_count,
    output wire                              error
);

    reg input_buffer_valid_r;
    reg input_buffer_bank_r;
    reg [6:0] input_buffer_group_r;
    reg [ROWS*GROUP_SIZE*24-1:0] input_buffer_s24_r;
    reg group_active_r;
    reg active_bank_r;
    reg [6:0] active_group_r;
    reg [ROWS-1:0] row_done_r;
    reg bundle_valid_r;
    reg bundle_bank_r;
    reg [6:0] bundle_group_r;
    reg [ROWS*GROUP_SIZE*8-1:0] bundle_u8_r;
    reg [ROWS*24-1:0] bundle_meta_r;
    reg control_error_r;

    wire [ROWS-1:0] quant_in_ready;
    wire [ROWS-1:0] quant_out_valid;
    wire [ROWS-1:0] quant_error;
    wire [ROWS*GROUP_SIZE*8-1:0] quant_out_u8;
    wire [ROWS*24-1:0] quant_out_meta;
    wire [ROWS-1:0] quant_collect;
    wire [ROWS-1:0] row_done_next;
    wire cache_wr_ready;
    wire cache_error;

    wire input_fire = in_valid && in_ready;
    wire quant_launch = input_buffer_valid_r && !group_active_r &&
        !bundle_valid_r && (&quant_in_ready);
    wire cache_wr_fire = bundle_valid_r && cache_wr_ready;

    assign in_ready = rst_n && !clear && !control_error_r &&
        !input_buffer_valid_r;
    assign quant_collect = quant_out_valid & {ROWS{group_active_r}} &
        ~row_done_r;
    assign row_done_next = row_done_r | quant_collect;
    assign hadamard_saturation_count = 32'd0;
    assign error = control_error_r | (|quant_error) | cache_error;

    genvar row;
    genvar lane;
    generate
        for (row = 0; row < ROWS; row = row + 1) begin : g_quantizer
            wire [GROUP_SIZE*27-1:0] direct_s27;
            wire [31:0] unused_input_count;
            wire [31:0] unused_output_count;
            wire [31:0] unused_cycle_count;
            for (lane = 0; lane < GROUP_SIZE; lane = lane + 1) begin : g_extend
                wire [23:0] sample = input_buffer_s24_r[
                    (row*GROUP_SIZE+lane)*24 +: 24];
                assign direct_s27[lane*27 +: 27] = {{3{sample[23]}}, sample};
            end
            hap_robust_a8_quantizer u_quantizer (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(quant_launch), .in_ready(quant_in_ready[row]),
                .in_s27(direct_s27),
                .out_valid(quant_out_valid[row]),
                .out_ready(group_active_r && !row_done_r[row]),
                .out_u8(quant_out_u8[row*GROUP_SIZE*8 +: GROUP_SIZE*8]),
                .out_meta(quant_out_meta[row*24 +: 24]),
                .input_group_count(unused_input_count),
                .output_group_count(unused_output_count),
                .cycle_count(unused_cycle_count), .error(quant_error[row])
            );
        end
    endgenerate

    hap_activation_cache_8row u_cache (
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
        .release_count(cache_release_count), .error(cache_error)
    );

    integer capture_row;
    always @(posedge clk) begin
        if (input_fire)
            input_buffer_s24_r <= in_s24;
        if (group_active_r) begin
            for (capture_row = 0; capture_row < ROWS;
                 capture_row = capture_row + 1) begin
                if (quant_collect[capture_row]) begin
                    bundle_u8_r[capture_row*GROUP_SIZE*8 +: GROUP_SIZE*8]
                        <= quant_out_u8[capture_row*GROUP_SIZE*8 +: GROUP_SIZE*8];
                    bundle_meta_r[capture_row*24 +: 24]
                        <= quant_out_meta[capture_row*24 +: 24];
                end
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            input_buffer_valid_r <= 1'b0;
            input_buffer_bank_r <= 1'b0;
            input_buffer_group_r <= 7'd0;
            group_active_r <= 1'b0;
            active_bank_r <= 1'b0;
            active_group_r <= 7'd0;
            row_done_r <= '0;
            bundle_valid_r <= 1'b0;
            bundle_bank_r <= 1'b0;
            bundle_group_r <= 7'd0;
            input_group_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            input_buffer_valid_r <= 1'b0;
            group_active_r <= 1'b0;
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
            if (quant_launch) begin
                input_buffer_valid_r <= 1'b0;
                group_active_r <= 1'b1;
                active_bank_r <= input_buffer_bank_r;
                active_group_r <= input_buffer_group_r;
                row_done_r <= '0;
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
            if ((|quant_out_valid) && !group_active_r)
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if (ROWS != 8 || GROUP_SIZE != 32 || GROUP_COUNT != 128)
            $error("M1 direct frontend shape is fixed at 8x128xgroup32");
    end
endmodule

