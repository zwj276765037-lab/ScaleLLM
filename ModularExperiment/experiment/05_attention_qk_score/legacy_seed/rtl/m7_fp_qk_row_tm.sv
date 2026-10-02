`timescale 1ns/1ps

// Throughput-matched QK baselines.  These modules deliberately reuse a
// 16-lane multiplier bank across eight contiguous chunks of each 128-wide
// key.  Unlike the original 128-lane diagnostic baseline, throughput is
// reduced by removing arithmetic hardware, not by injecting ready stalls.

module m7_tm_reduce16x8 (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire [15:0]  lane_valid,
    input  wire [511:0] lane_f32,
    output wire         out_valid,
    output wire [31:0]  out_sum_f32,
    output wire         error
);
    wire [7:0] s1v;
    wire [255:0] s1;
    wire [3:0] s2v;
    wire [127:0] s2;
    wire [1:0] s3v;
    wire [63:0] s3;
    wire local_valid;
    wire [31:0] local_sum;
    reg [2:0] chunk_index_r;
    reg [31:0] chunk_sum_r [0:6];
    wire key_fire = local_valid && (chunk_index_r == 3'd7);
    wire [3:0] k1v;
    wire [127:0] k1;
    wire [1:0] k2v;
    wire [63:0] k2;
    wire valid_mismatch = (lane_valid != {16{lane_valid[0]}}) ||
        (s1v != {8{s1v[0]}}) || (s2v != {4{s2v[0]}}) ||
        (s3v != {2{s3v[0]}}) || (k1v != {4{k1v[0]}}) ||
        (k2v != {2{k2v[0]}});

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : g_local_l1
            m7_f32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(lane_valid[2*i]),
                .s_axis_a_tdata(lane_f32[(2*i)*32 +: 32]),
                .s_axis_b_tvalid(lane_valid[2*i+1]),
                .s_axis_b_tdata(lane_f32[(2*i+1)*32 +: 32]),
                .m_axis_result_tvalid(s1v[i]),
                .m_axis_result_tdata(s1[i*32 +: 32])
            );
        end
        for (i = 0; i < 4; i = i + 1) begin : g_local_l2
            m7_f32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(s1v[2*i]),
                .s_axis_a_tdata(s1[(2*i)*32 +: 32]),
                .s_axis_b_tvalid(s1v[2*i+1]),
                .s_axis_b_tdata(s1[(2*i+1)*32 +: 32]),
                .m_axis_result_tvalid(s2v[i]),
                .m_axis_result_tdata(s2[i*32 +: 32])
            );
        end
        for (i = 0; i < 2; i = i + 1) begin : g_local_l3
            m7_f32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(s2v[2*i]),
                .s_axis_a_tdata(s2[(2*i)*32 +: 32]),
                .s_axis_b_tvalid(s2v[2*i+1]),
                .s_axis_b_tdata(s2[(2*i+1)*32 +: 32]),
                .m_axis_result_tvalid(s3v[i]),
                .m_axis_result_tdata(s3[i*32 +: 32])
            );
        end
    endgenerate

    m7_f32_add u_local_l4 (
        .aclk(clk),
        .s_axis_a_tvalid(s3v[0]), .s_axis_a_tdata(s3[31:0]),
        .s_axis_b_tvalid(s3v[1]), .s_axis_b_tdata(s3[63:32]),
        .m_axis_result_tvalid(local_valid),
        .m_axis_result_tdata(local_sum)
    );

    // The first seven chunk sums are retained.  On the eighth result the
    // complete 128-element tree continues with levels 5, 6, and 7.
    m7_f32_add u_key_l1_0 (
        .aclk(clk), .s_axis_a_tvalid(key_fire),
        .s_axis_a_tdata(chunk_sum_r[0]), .s_axis_b_tvalid(key_fire),
        .s_axis_b_tdata(chunk_sum_r[1]), .m_axis_result_tvalid(k1v[0]),
        .m_axis_result_tdata(k1[31:0]));
    m7_f32_add u_key_l1_1 (
        .aclk(clk), .s_axis_a_tvalid(key_fire),
        .s_axis_a_tdata(chunk_sum_r[2]), .s_axis_b_tvalid(key_fire),
        .s_axis_b_tdata(chunk_sum_r[3]), .m_axis_result_tvalid(k1v[1]),
        .m_axis_result_tdata(k1[63:32]));
    m7_f32_add u_key_l1_2 (
        .aclk(clk), .s_axis_a_tvalid(key_fire),
        .s_axis_a_tdata(chunk_sum_r[4]), .s_axis_b_tvalid(key_fire),
        .s_axis_b_tdata(chunk_sum_r[5]), .m_axis_result_tvalid(k1v[2]),
        .m_axis_result_tdata(k1[95:64]));
    m7_f32_add u_key_l1_3 (
        .aclk(clk), .s_axis_a_tvalid(key_fire),
        .s_axis_a_tdata(chunk_sum_r[6]), .s_axis_b_tvalid(key_fire),
        .s_axis_b_tdata(local_sum), .m_axis_result_tvalid(k1v[3]),
        .m_axis_result_tdata(k1[127:96]));
    m7_f32_add u_key_l2_0 (
        .aclk(clk), .s_axis_a_tvalid(k1v[0]), .s_axis_a_tdata(k1[31:0]),
        .s_axis_b_tvalid(k1v[1]), .s_axis_b_tdata(k1[63:32]),
        .m_axis_result_tvalid(k2v[0]), .m_axis_result_tdata(k2[31:0]));
    m7_f32_add u_key_l2_1 (
        .aclk(clk), .s_axis_a_tvalid(k1v[2]), .s_axis_a_tdata(k1[95:64]),
        .s_axis_b_tvalid(k1v[3]), .s_axis_b_tdata(k1[127:96]),
        .m_axis_result_tvalid(k2v[1]), .m_axis_result_tdata(k2[63:32]));
    m7_f32_add u_key_l3 (
        .aclk(clk), .s_axis_a_tvalid(k2v[0]), .s_axis_a_tdata(k2[31:0]),
        .s_axis_b_tvalid(k2v[1]), .s_axis_b_tdata(k2[63:32]),
        .m_axis_result_tvalid(out_valid), .m_axis_result_tdata(out_sum_f32));

    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            chunk_index_r <= 3'd0;
        else if (clear)
            chunk_index_r <= 3'd0;
        else if (local_valid) begin
            if (chunk_index_r != 3'd7)
                chunk_sum_r[chunk_index_r] <= local_sum;
            chunk_index_r <= chunk_index_r + 1'b1;
        end
    end
    assign error = valid_mismatch;
endmodule

module m7_fp32_qk_row_tm (
    input wire clk, rst_n, clear,
    input wire query_load_valid,
    output wire query_load_ready,
    input wire [4095:0] query_fp32,
    input wire in_valid,
    output wire in_ready,
    input wire in_last_key, in_mask,
    input wire [4095:0] key_fp32,
    output wire out_valid,
    input wire out_ready,
    output wire signed [19:0] out_score_q14_s20,
    output wire out_mask,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output reg [31:0] input_key_count,
    output reg [31:0] output_score_count,
    output reg [31:0] clip_count,
    output wire error
);
    reg [4095:0] query_r, key_r;
    reg query_ready_r, key_busy_r, key_last_r, key_mask_r;
    reg [2:0] chunk_r;
    reg control_error_r;
    wire chunk_issue = key_busy_r && query_ready_r;
    wire final_key_chunk = chunk_issue && (chunk_r == 3'd7);
    wire final_row_chunk = final_key_chunk && key_last_r;
    wire input_fire = in_valid && in_ready;
    wire query_fire = query_load_valid && query_load_ready;
    wire [15:0] product_valid;
    wire [511:0] product_f32;
    wire reduce_valid, reduce_error;
    wire [31:0] dot_f32;
    wire scale_valid, convert_valid;
    wire [31:0] scaled_f32;
    wire [23:0] converted_s24;

    reg tag_mask_mem [0:15];
    reg tag_last_mem [0:15];
    reg [3:0] tag_wr_r, tag_rd_r;
    reg [4:0] tag_count_r;
    reg [19:0] out_score_mem [0:15];
    reg out_mask_mem [0:15];
    reg out_last_mem [0:15];
    reg [3:0] out_wr_r, out_rd_r;
    reg [4:0] out_count_r;
    reg [6:0] out_index_r;
    wire output_fire = out_valid && out_ready;
    wire signed [19:0] converted_signed = $signed(converted_s24[19:0]);
    wire converted_clip = (converted_signed > 20'sd262144) ||
        (converted_signed < -20'sd262144);
    wire signed [19:0] clipped_score =
        (converted_signed > 20'sd262144) ? 20'sd262144 :
        (converted_signed < -20'sd262144) ? -20'sd262144 :
        converted_signed;

    assign query_load_ready = rst_n && !clear &&
        (!query_ready_r || final_row_chunk);
    assign in_ready = rst_n && !clear && query_ready_r &&
        (tag_count_r < 5'd15) &&
        (!key_busy_r || (final_key_chunk && !key_last_r));

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : g_mul
            m7_f32_mul u_mul (
                .aclk(clk),
                .s_axis_a_tvalid(chunk_issue),
                .s_axis_a_tdata(query_r[(chunk_r*512)+(i*32) +: 32]),
                .s_axis_b_tvalid(chunk_issue),
                .s_axis_b_tdata(key_r[(chunk_r*512)+(i*32) +: 32]),
                .m_axis_result_tvalid(product_valid[i]),
                .m_axis_result_tdata(product_f32[i*32 +: 32])
            );
        end
    endgenerate

    m7_tm_reduce16x8 u_reduce (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .lane_valid(product_valid), .lane_f32(product_f32),
        .out_valid(reduce_valid), .out_sum_f32(dot_f32),
        .error(reduce_error));
    m7_f32_mul u_head_scale (
        .aclk(clk), .s_axis_a_tvalid(reduce_valid),
        .s_axis_a_tdata(dot_f32), .s_axis_b_tvalid(reduce_valid),
        .s_axis_b_tdata(32'h3db50800),
        .m_axis_result_tvalid(scale_valid),
        .m_axis_result_tdata(scaled_f32));
    m7_f32_to_s20 u_convert (
        .aclk(clk), .s_axis_a_tvalid(scale_valid),
        .s_axis_a_tdata(scaled_f32),
        .m_axis_result_tvalid(convert_valid),
        .m_axis_result_tdata(converted_s24));

    assign out_valid = rst_n && !clear && (out_count_r != 0);
    assign out_score_q14_s20 = out_score_mem[out_rd_r];
    assign out_mask = out_mask_mem[out_rd_r];
    assign out_last_key = out_last_mem[out_rd_r];
    assign out_key_index = out_index_r;
    assign error = control_error_r || reduce_error ||
        (product_valid != {16{product_valid[0]}});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            query_ready_r <= 1'b0; key_busy_r <= 1'b0;
            key_last_r <= 1'b0; key_mask_r <= 1'b0; chunk_r <= 3'd0;
            tag_wr_r <= 4'd0; tag_rd_r <= 4'd0; tag_count_r <= 5'd0;
            out_wr_r <= 4'd0; out_rd_r <= 4'd0; out_count_r <= 5'd0;
            out_index_r <= 7'd0; input_key_count <= 32'd0;
            output_score_count <= 32'd0; clip_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            query_ready_r <= 1'b0; key_busy_r <= 1'b0;
            key_last_r <= 1'b0; key_mask_r <= 1'b0; chunk_r <= 3'd0;
            tag_wr_r <= 4'd0; tag_rd_r <= 4'd0; tag_count_r <= 5'd0;
            out_wr_r <= 4'd0; out_rd_r <= 4'd0; out_count_r <= 5'd0;
            out_index_r <= 7'd0; input_key_count <= 32'd0;
            output_score_count <= 32'd0; clip_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (query_fire) begin
                query_r <= query_fp32;
                query_ready_r <= 1'b1;
            end else if (final_row_chunk) begin
                query_ready_r <= 1'b0;
            end
            if (input_fire) begin
                key_r <= key_fp32;
                key_last_r <= in_last_key;
                key_mask_r <= in_mask;
                tag_mask_mem[tag_wr_r] <= in_mask;
                tag_last_mem[tag_wr_r] <= in_last_key;
                tag_wr_r <= tag_wr_r + 1'b1;
                input_key_count <= input_key_count + 1'b1;
            end
            if (chunk_issue) begin
                if (chunk_r == 3'd7) begin
                    chunk_r <= 3'd0;
                    if (input_fire && !key_last_r)
                        key_busy_r <= 1'b1;
                    else
                        key_busy_r <= 1'b0;
                end else begin
                    chunk_r <= chunk_r + 1'b1;
                end
            end else if (input_fire) begin
                key_busy_r <= 1'b1;
                chunk_r <= 3'd0;
            end
            if (convert_valid) begin
                if (tag_count_r == 0 || out_count_r == 5'd16)
                    control_error_r <= 1'b1;
                out_score_mem[out_wr_r] <= clipped_score;
                out_mask_mem[out_wr_r] <= tag_mask_mem[tag_rd_r];
                out_last_mem[out_wr_r] <= tag_last_mem[tag_rd_r];
                tag_rd_r <= tag_rd_r + 1'b1;
                out_wr_r <= out_wr_r + 1'b1;
                if (converted_clip)
                    clip_count <= clip_count + 1'b1;
            end
            if (output_fire) begin
                out_rd_r <= out_rd_r + 1'b1;
                output_score_count <= output_score_count + 1'b1;
                if (out_last_key)
                    out_index_r <= 7'd0;
                else
                    out_index_r <= out_index_r + 1'b1;
            end
            case ({input_fire, convert_valid})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
            case ({convert_valid, output_fire})
                2'b10: out_count_r <= out_count_r + 1'b1;
                2'b01: out_count_r <= out_count_r - 1'b1;
                default: out_count_r <= out_count_r;
            endcase
            if (tag_count_r > 5'd16 || out_count_r > 5'd16)
                control_error_r <= 1'b1;
        end
    end
endmodule

module m7_fp16_qk_row_tm (
    input wire clk, rst_n, clear,
    input wire query_load_valid,
    output wire query_load_ready,
    input wire [2047:0] query_fp16,
    input wire in_valid,
    output wire in_ready,
    input wire in_last_key, in_mask,
    input wire [2047:0] key_fp16,
    output wire out_valid,
    input wire out_ready,
    output wire signed [19:0] out_score_q14_s20,
    output wire out_mask,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output reg [31:0] input_key_count,
    output reg [31:0] output_score_count,
    output reg [31:0] clip_count,
    output wire error
);
    reg [2047:0] query_raw_r, query_scaled_r, key_r;
    reg query_ready_r, qscale_busy_r, qscale_issue_r;
    reg key_busy_r, key_last_r, key_mask_r;
    reg [2:0] qscale_issue_index_r, qscale_recv_index_r, chunk_r;
    reg control_error_r;
    wire chunk_issue = key_busy_r && query_ready_r;
    wire final_key_chunk = chunk_issue && (chunk_r == 3'd7);
    wire final_row_chunk = final_key_chunk && key_last_r;
    wire input_fire = in_valid && in_ready;
    wire query_fire = query_load_valid && query_load_ready;
    wire mul_input_valid = qscale_issue_r || chunk_issue;
    wire [15:0] mul_valid;
    wire [255:0] mul_f16;
    reg mode_mem [0:15];
    reg [3:0] mode_wr_r, mode_rd_r;
    reg [4:0] mode_count_r;
    wire mul_output_valid = mul_valid[0];
    wire mul_output_qscale = mode_mem[mode_rd_r];
    wire product16_valid = mul_output_valid && !mul_output_qscale;
    wire [15:0] convert32_valid;
    wire [511:0] product_f32;
    wire reduce_valid, reduce_error;
    wire [31:0] dot_f32;
    wire convert_valid;
    wire [23:0] converted_s24;

    reg tag_mask_mem [0:15];
    reg tag_last_mem [0:15];
    reg [3:0] tag_wr_r, tag_rd_r;
    reg [4:0] tag_count_r;
    reg [19:0] out_score_mem [0:15];
    reg out_mask_mem [0:15];
    reg out_last_mem [0:15];
    reg [3:0] out_wr_r, out_rd_r;
    reg [4:0] out_count_r;
    reg [6:0] out_index_r;
    wire output_fire = out_valid && out_ready;
    wire signed [19:0] converted_signed = $signed(converted_s24[19:0]);
    wire converted_clip = (converted_signed > 20'sd262144) ||
        (converted_signed < -20'sd262144);
    wire signed [19:0] clipped_score =
        (converted_signed > 20'sd262144) ? 20'sd262144 :
        (converted_signed < -20'sd262144) ? -20'sd262144 :
        converted_signed;

    assign query_load_ready = rst_n && !clear && !qscale_busy_r &&
        (!query_ready_r || final_row_chunk);
    assign in_ready = rst_n && !clear && query_ready_r &&
        (tag_count_r < 5'd15) &&
        (!key_busy_r || (final_key_chunk && !key_last_r));

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : g_mul_convert
            wire [15:0] mul_a = qscale_issue_r ?
                query_raw_r[(qscale_issue_index_r*256)+(i*16) +: 16] :
                query_scaled_r[(chunk_r*256)+(i*16) +: 16];
            wire [15:0] mul_b = qscale_issue_r ? 16'h2da8 :
                key_r[(chunk_r*256)+(i*16) +: 16];
            m7_f16_mul u_mul (
                .aclk(clk), .s_axis_a_tvalid(mul_input_valid),
                .s_axis_a_tdata(mul_a), .s_axis_b_tvalid(mul_input_valid),
                .s_axis_b_tdata(mul_b),
                .m_axis_result_tvalid(mul_valid[i]),
                .m_axis_result_tdata(mul_f16[i*16 +: 16]));
            m7_f16_to_f32 u_convert (
                .aclk(clk), .s_axis_a_tvalid(product16_valid),
                .s_axis_a_tdata(mul_f16[i*16 +: 16]),
                .m_axis_result_tvalid(convert32_valid[i]),
                .m_axis_result_tdata(product_f32[i*32 +: 32]));
        end
    endgenerate

    m7_tm_reduce16x8 u_reduce (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .lane_valid(convert32_valid), .lane_f32(product_f32),
        .out_valid(reduce_valid), .out_sum_f32(dot_f32),
        .error(reduce_error));
    m7_f32_to_s20 u_convert_score (
        .aclk(clk), .s_axis_a_tvalid(reduce_valid),
        .s_axis_a_tdata(dot_f32),
        .m_axis_result_tvalid(convert_valid),
        .m_axis_result_tdata(converted_s24));

    assign out_valid = rst_n && !clear && (out_count_r != 0);
    assign out_score_q14_s20 = out_score_mem[out_rd_r];
    assign out_mask = out_mask_mem[out_rd_r];
    assign out_last_key = out_last_mem[out_rd_r];
    assign out_key_index = out_index_r;
    assign error = control_error_r || reduce_error ||
        (mul_valid != {16{mul_valid[0]}}) ||
        (convert32_valid != {16{convert32_valid[0]}});

    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            query_ready_r <= 1'b0; qscale_busy_r <= 1'b0;
            qscale_issue_r <= 1'b0; qscale_issue_index_r <= 3'd0;
            qscale_recv_index_r <= 3'd0; key_busy_r <= 1'b0;
            key_last_r <= 1'b0; key_mask_r <= 1'b0; chunk_r <= 3'd0;
            mode_wr_r <= 4'd0; mode_rd_r <= 4'd0; mode_count_r <= 5'd0;
            tag_wr_r <= 4'd0; tag_rd_r <= 4'd0; tag_count_r <= 5'd0;
            out_wr_r <= 4'd0; out_rd_r <= 4'd0; out_count_r <= 5'd0;
            out_index_r <= 7'd0; input_key_count <= 32'd0;
            output_score_count <= 32'd0; clip_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            query_ready_r <= 1'b0; qscale_busy_r <= 1'b0;
            qscale_issue_r <= 1'b0; qscale_issue_index_r <= 3'd0;
            qscale_recv_index_r <= 3'd0; key_busy_r <= 1'b0;
            key_last_r <= 1'b0; key_mask_r <= 1'b0; chunk_r <= 3'd0;
            mode_wr_r <= 4'd0; mode_rd_r <= 4'd0; mode_count_r <= 5'd0;
            tag_wr_r <= 4'd0; tag_rd_r <= 4'd0; tag_count_r <= 5'd0;
            out_wr_r <= 4'd0; out_rd_r <= 4'd0; out_count_r <= 5'd0;
            out_index_r <= 7'd0; input_key_count <= 32'd0;
            output_score_count <= 32'd0; clip_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (query_fire) begin
                query_raw_r <= query_fp16;
                query_ready_r <= 1'b0;
                qscale_busy_r <= 1'b1;
                qscale_issue_r <= 1'b1;
                qscale_issue_index_r <= 3'd0;
                qscale_recv_index_r <= 3'd0;
            end else if (final_row_chunk) begin
                query_ready_r <= 1'b0;
            end
            if (qscale_issue_r) begin
                if (qscale_issue_index_r == 3'd7) begin
                    qscale_issue_r <= 1'b0;
                    qscale_issue_index_r <= 3'd0;
                end else begin
                    qscale_issue_index_r <= qscale_issue_index_r + 1'b1;
                end
            end
            if (mul_input_valid) begin
                mode_mem[mode_wr_r] <= qscale_issue_r;
                mode_wr_r <= mode_wr_r + 1'b1;
            end
            if (mul_output_valid) begin
                if (mode_count_r == 0)
                    control_error_r <= 1'b1;
                mode_rd_r <= mode_rd_r + 1'b1;
                if (mul_output_qscale) begin
                    for (j = 0; j < 16; j = j + 1)
                        query_scaled_r[(qscale_recv_index_r*256)+(j*16) +: 16]
                            <= mul_f16[j*16 +: 16];
                    if (qscale_recv_index_r == 3'd7) begin
                        qscale_recv_index_r <= 3'd0;
                        qscale_busy_r <= 1'b0;
                        query_ready_r <= 1'b1;
                    end else begin
                        qscale_recv_index_r <= qscale_recv_index_r + 1'b1;
                    end
                end
            end
            case ({mul_input_valid, mul_output_valid})
                2'b10: mode_count_r <= mode_count_r + 1'b1;
                2'b01: mode_count_r <= mode_count_r - 1'b1;
                default: mode_count_r <= mode_count_r;
            endcase
            if (input_fire) begin
                key_r <= key_fp16;
                key_last_r <= in_last_key;
                key_mask_r <= in_mask;
                tag_mask_mem[tag_wr_r] <= in_mask;
                tag_last_mem[tag_wr_r] <= in_last_key;
                tag_wr_r <= tag_wr_r + 1'b1;
                input_key_count <= input_key_count + 1'b1;
            end
            if (chunk_issue) begin
                if (chunk_r == 3'd7) begin
                    chunk_r <= 3'd0;
                    if (input_fire && !key_last_r)
                        key_busy_r <= 1'b1;
                    else
                        key_busy_r <= 1'b0;
                end else begin
                    chunk_r <= chunk_r + 1'b1;
                end
            end else if (input_fire) begin
                key_busy_r <= 1'b1;
                chunk_r <= 3'd0;
            end
            if (convert_valid) begin
                if (tag_count_r == 0 || out_count_r == 5'd16)
                    control_error_r <= 1'b1;
                out_score_mem[out_wr_r] <= clipped_score;
                out_mask_mem[out_wr_r] <= tag_mask_mem[tag_rd_r];
                out_last_mem[out_wr_r] <= tag_last_mem[tag_rd_r];
                tag_rd_r <= tag_rd_r + 1'b1;
                out_wr_r <= out_wr_r + 1'b1;
                if (converted_clip)
                    clip_count <= clip_count + 1'b1;
            end
            if (output_fire) begin
                out_rd_r <= out_rd_r + 1'b1;
                output_score_count <= output_score_count + 1'b1;
                if (out_last_key)
                    out_index_r <= 7'd0;
                else
                    out_index_r <= out_index_r + 1'b1;
            end
            case ({input_fire, convert_valid})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
            case ({convert_valid, output_fire})
                2'b10: out_count_r <= out_count_r + 1'b1;
                2'b01: out_count_r <= out_count_r - 1'b1;
                default: out_count_r <= out_count_r;
            endcase
            if (mode_count_r > 5'd16 || tag_count_r > 5'd16 ||
                out_count_r > 5'd16)
                control_error_r <= 1'b1;
        end
    end
endmodule
