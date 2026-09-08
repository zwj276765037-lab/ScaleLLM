`timescale 1ns / 1ps

// Cohort16 MLP input frontend/cache.  Dell supplies RMSNorm output as S24
// Q8.16 group32 records.  Two physically independent eight-row frontends
// perform normalized Hadamard + robust A8 and retain all 128 hidden groups in
// matching ping-pong cache banks.  Read/release operations are forked and
// joined atomically so the gate/up scheduler always receives one coherent
// 16-request activation group.
module hap_mlp_input_frontend16_cache (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_bank,
    input  wire [6:0]                    in_group,
    input  wire [16*32*24-1:0]           in_s24x16x32,

    input  wire                          rd_req_valid,
    output wire                          rd_req_ready,
    input  wire                          rd_req_bank,
    input  wire [6:0]                    rd_req_group,
    output wire                          rd_rsp_valid,
    input  wire                          rd_rsp_ready,
    output wire                          rd_rsp_bank,
    output wire [6:0]                    rd_rsp_group,
    output wire [16*32*8-1:0]            rd_rsp_u8x16x32,
    output wire [16*24-1:0]              rd_rsp_meta_u24x16,

    input  wire                          release_valid,
    output wire                          release_ready,
    input  wire                          release_bank,
    output wire [1:0]                    bank_ready,
    output reg  [31:0]                   input_group_count,
    output reg  [31:0]                   read_group_count,
    output reg  [31:0]                   release_count,
    output wire [31:0]                   hadamard_saturation_count,
    output reg                           error
);

    reg input_stage_valid_r;
    reg input_pending0_r;
    reg input_pending1_r;
    reg input_bank_r;
    reg [6:0] input_group_r;
    reg [16*32*24-1:0] input_s24_r;

    reg release_stage_valid_r;
    reg release_pending0_r;
    reg release_pending1_r;
    reg release_bank_r;

    wire half0_in_ready, half1_in_ready;
    wire half0_rd_req_ready, half1_rd_req_ready;
    wire half0_rsp_valid, half1_rsp_valid;
    wire half0_rsp_ready, half1_rsp_ready;
    wire half0_rsp_bank, half1_rsp_bank;
    wire [6:0] half0_rsp_group, half1_rsp_group;
    wire [8*32*8-1:0] half0_rsp_u8, half1_rsp_u8;
    wire [8*24-1:0] half0_rsp_meta, half1_rsp_meta;
    wire half0_release_ready, half1_release_ready;
    wire [1:0] half0_bank_ready, half1_bank_ready;
    wire [31:0] half0_saturation, half1_saturation;
    wire half0_error, half1_error;

    wire input_accept0 = input_stage_valid_r && input_pending0_r &&
        half0_in_ready;
    wire input_accept1 = input_stage_valid_r && input_pending1_r &&
        half1_in_ready;
    wire input_stage_done = input_stage_valid_r &&
        (!input_pending0_r || half0_in_ready) &&
        (!input_pending1_r || half1_in_ready);
    wire input_fire = in_valid && in_ready;

    wire read_fire = rd_req_valid && rd_req_ready;
    wire response_fire = rd_rsp_valid && rd_rsp_ready;

    wire release_accept0 = release_stage_valid_r && release_pending0_r &&
        half0_release_ready;
    wire release_accept1 = release_stage_valid_r && release_pending1_r &&
        half1_release_ready;
    wire release_stage_done = release_stage_valid_r &&
        (!release_pending0_r || half0_release_ready) &&
        (!release_pending1_r || half1_release_ready);
    wire release_fire = release_valid && release_ready;

    assign in_ready = rst_n && !clear &&
        (!input_stage_valid_r || input_stage_done);
    // Reads have a returned transaction and each half owns only a one-entry
    // response register.  Unlike input writes, a read request must enter both
    // halves on the same edge; split delivery could pair one half's next
    // response with the other half's previous response under backpressure.
    assign rd_req_ready = rst_n && !clear &&
        half0_rd_req_ready && half1_rd_req_ready;
    assign release_ready = rst_n && !clear &&
        (!release_stage_valid_r || release_stage_done);

    assign rd_rsp_valid = rst_n && !clear &&
        half0_rsp_valid && half1_rsp_valid;
    assign half0_rsp_ready = rd_rsp_ready && half1_rsp_valid;
    assign half1_rsp_ready = rd_rsp_ready && half0_rsp_valid;
    assign rd_rsp_bank = half0_rsp_bank;
    assign rd_rsp_group = half0_rsp_group;
    assign rd_rsp_u8x16x32[0 +: 8*32*8] = half0_rsp_u8;
    assign rd_rsp_u8x16x32[8*32*8 +: 8*32*8] = half1_rsp_u8;
    assign rd_rsp_meta_u24x16[0 +: 8*24] = half0_rsp_meta;
    assign rd_rsp_meta_u24x16[8*24 +: 8*24] = half1_rsp_meta;
    assign bank_ready = half0_bank_ready & half1_bank_ready;
    assign hadamard_saturation_count = half0_saturation + half1_saturation;

    hap_attention_frontend_8row u_half0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(input_stage_valid_r && input_pending0_r),
        .in_ready(half0_in_ready), .in_bank(input_bank_r),
        .in_group(input_group_r),
        .in_s24(input_s24_r[0 +: 8*32*24]),
        .rd_req_valid(rd_req_valid && half1_rd_req_ready),
        .rd_req_ready(half0_rd_req_ready), .rd_req_bank(rd_req_bank),
        .rd_req_group(rd_req_group), .rd_rsp_valid(half0_rsp_valid),
        .rd_rsp_ready(half0_rsp_ready), .rd_rsp_bank(half0_rsp_bank),
        .rd_rsp_group(half0_rsp_group), .rd_rsp_u8(half0_rsp_u8),
        .rd_rsp_meta(half0_rsp_meta),
        .release_valid(release_stage_valid_r && release_pending0_r),
        .release_ready(half0_release_ready),
        .release_bank(release_bank_r), .bank_ready(half0_bank_ready),
        .input_group_count(), .cache_write_count(), .cache_read_count(),
        .cache_release_count(),
        .hadamard_saturation_count(half0_saturation), .error(half0_error)
    );

    hap_attention_frontend_8row u_half1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(input_stage_valid_r && input_pending1_r),
        .in_ready(half1_in_ready), .in_bank(input_bank_r),
        .in_group(input_group_r),
        .in_s24(input_s24_r[8*32*24 +: 8*32*24]),
        .rd_req_valid(rd_req_valid && half0_rd_req_ready),
        .rd_req_ready(half1_rd_req_ready), .rd_req_bank(rd_req_bank),
        .rd_req_group(rd_req_group), .rd_rsp_valid(half1_rsp_valid),
        .rd_rsp_ready(half1_rsp_ready), .rd_rsp_bank(half1_rsp_bank),
        .rd_rsp_group(half1_rsp_group), .rd_rsp_u8(half1_rsp_u8),
        .rd_rsp_meta(half1_rsp_meta),
        .release_valid(release_stage_valid_r && release_pending1_r),
        .release_ready(half1_release_ready),
        .release_bank(release_bank_r), .bank_ready(half1_bank_ready),
        .input_group_count(), .cache_write_count(), .cache_read_count(),
        .cache_release_count(),
        .hadamard_saturation_count(half1_saturation), .error(half1_error)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            input_stage_valid_r <= 1'b0;
            input_pending0_r <= 1'b0;
            input_pending1_r <= 1'b0;
            release_stage_valid_r <= 1'b0;
            release_pending0_r <= 1'b0;
            release_pending1_r <= 1'b0;
            input_group_count <= 32'd0;
            read_group_count <= 32'd0;
            release_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (input_accept0) input_pending0_r <= 1'b0;
            if (input_accept1) input_pending1_r <= 1'b0;
            if (input_stage_done && !input_fire) begin
                input_stage_valid_r <= 1'b0;
                input_pending0_r <= 1'b0;
                input_pending1_r <= 1'b0;
            end
            if (input_fire) begin
                input_stage_valid_r <= 1'b1;
                input_pending0_r <= 1'b1;
                input_pending1_r <= 1'b1;
                input_bank_r <= in_bank;
                input_group_r <= in_group;
                input_s24_r <= in_s24x16x32;
                input_group_count <= input_group_count + 32'd1;
            end

            if (response_fire)
                read_group_count <= read_group_count + 32'd1;

            if (release_accept0) release_pending0_r <= 1'b0;
            if (release_accept1) release_pending1_r <= 1'b0;
            if (release_stage_done && !release_fire) begin
                release_stage_valid_r <= 1'b0;
                release_pending0_r <= 1'b0;
                release_pending1_r <= 1'b0;
                release_count <= release_count + 32'd1;
            end
            if (release_fire) begin
                release_stage_valid_r <= 1'b1;
                release_pending0_r <= 1'b1;
                release_pending1_r <= 1'b1;
                release_bank_r <= release_bank;
            end

            if (half0_error || half1_error ||
                (half0_rsp_valid && half1_rsp_valid &&
                 (half0_rsp_bank != half1_rsp_bank ||
                  half0_rsp_group != half1_rsp_group)))
                error <= 1'b1;
        end
    end

endmodule
