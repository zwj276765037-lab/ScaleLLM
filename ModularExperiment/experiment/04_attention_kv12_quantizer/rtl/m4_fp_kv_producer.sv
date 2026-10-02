`timescale 1ns/1ps

// Minimum-area direct-FP producer for the four-row KV boundary.  One physical
// fixed-to-float converter accepts one S24 Q8.16 lane per cycle.  Four complete
// group32 records are retained in a real FIFO, so arbitrary downstream stalls
// cannot overwrite data already produced by the non-stoppable IP pipeline.
module m4_fp_kv_producer #(
    parameter integer FP_W = 16
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     in_valid,
    output wire                     in_ready,
    input  wire [4*32*24-1:0]       in_s24,
    output wire                     out_valid,
    input  wire                     out_ready,
    output wire [1:0]               out_lane,
    output wire                     out_batch_last,
    output wire [32*FP_W-1:0]       out_fp,
    output reg  [31:0]              input_batch_count,
    output reg  [31:0]              output_group_count,
    output reg  [31:0]              converted_lane_count,
    output wire                     error
);
    localparam integer RECORD_W = 32*FP_W;

    reg signed [23:0] source_mem [0:127];
    reg batch_active_r;
    reg [7:0] issue_count_r;
    reg [7:0] result_count_r;
    reg control_error_r;

    reg [RECORD_W-1:0] record_build_r;
    reg [RECORD_W-1:0] fifo_mem [0:3];
    reg [1:0] fifo_lane_mem [0:3];
    reg [1:0] fifo_wr_ptr_r;
    reg [1:0] fifo_rd_ptr_r;
    reg [2:0] fifo_count_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire converter_issue = batch_active_r && (issue_count_r < 8'd128);
    wire signed [23:0] converter_input = source_mem[issue_count_r[6:0]];
    wire converter_valid;
    wire [FP_W-1:0] converter_result;
    wire [4:0] result_lane = result_count_r[4:0];
    wire [1:0] result_group = result_count_r[6:5];
    wire record_commit = converter_valid && (result_lane == 5'd31);
    wire [RECORD_W-1:0] completed_record =
        {converter_result, record_build_r[31*FP_W-1:0]};

    assign in_ready = rst_n && !clear && !batch_active_r &&
        (fifo_count_r == 0);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_lane = fifo_lane_mem[fifo_rd_ptr_r];
    assign out_batch_last = out_lane == 2'd3;
    assign out_fp = fifo_mem[fifo_rd_ptr_r];
    assign error = control_error_r;

    generate
        if (FP_W == 16) begin : g_fp16
            wire stage1_valid;
            wire [31:0] stage1_fp32;
            m4_s24_to_fp32_for_fp16 u_fixed_to_single (
                .aclk(clk),
                .s_axis_a_tvalid(converter_issue),
                .s_axis_a_tdata(converter_input),
                .m_axis_result_tvalid(stage1_valid),
                .m_axis_result_tdata(stage1_fp32)
            );
            m4_fp32_to_fp16 u_single_to_half (
                .aclk(clk),
                .s_axis_a_tvalid(stage1_valid),
                .s_axis_a_tdata(stage1_fp32),
                .m_axis_result_tvalid(converter_valid),
                .m_axis_result_tdata(converter_result)
            );
        end else begin : g_fp32
            m4_s24_to_fp32 u_convert (
                .aclk(clk),
                .s_axis_a_tvalid(converter_issue),
                .s_axis_a_tdata(converter_input),
                .m_axis_result_tvalid(converter_valid),
                .m_axis_result_tdata(converter_result)
            );
        end
    endgenerate

    integer lane;
    always @(posedge clk) begin
        if (in_fire)
            for (lane = 0; lane < 128; lane = lane + 1)
                source_mem[lane] <= in_s24[lane*24 +: 24];
        if (converter_valid && (result_lane != 5'd31))
            record_build_r[result_lane*FP_W +: FP_W] <= converter_result;
        if (record_commit) begin
            fifo_mem[fifo_wr_ptr_r] <= completed_record;
            fifo_lane_mem[fifo_wr_ptr_r] <= result_group;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            batch_active_r <= 1'b0;
            issue_count_r <= 8'd0;
            result_count_r <= 8'd0;
            fifo_wr_ptr_r <= 2'd0;
            fifo_rd_ptr_r <= 2'd0;
            fifo_count_r <= 3'd0;
            input_batch_count <= 32'd0;
            output_group_count <= 32'd0;
            converted_lane_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            batch_active_r <= 1'b0;
            issue_count_r <= 8'd0;
            result_count_r <= 8'd0;
            fifo_wr_ptr_r <= 2'd0;
            fifo_rd_ptr_r <= 2'd0;
            fifo_count_r <= 3'd0;
            input_batch_count <= 32'd0;
            output_group_count <= 32'd0;
            converted_lane_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (in_fire) begin
                batch_active_r <= 1'b1;
                issue_count_r <= 8'd0;
                result_count_r <= 8'd0;
                input_batch_count <= input_batch_count + 32'd1;
            end
            if (converter_issue)
                issue_count_r <= issue_count_r + 1'b1;
            if (converter_valid) begin
                result_count_r <= result_count_r + 1'b1;
                converted_lane_count <= converted_lane_count + 32'd1;
                if ((fifo_count_r == 4) && !out_fire)
                    control_error_r <= 1'b1;
            end
            if (record_commit && ((fifo_count_r != 4) || out_fire))
                fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                output_group_count <= output_group_count + 32'd1;
                if (out_batch_last)
                    batch_active_r <= 1'b0;
            end
            case ({record_commit && ((fifo_count_r != 4) || out_fire),
                    out_fire})
                2'b10: fifo_count_r <= fifo_count_r + 1'b1;
                2'b01: fifo_count_r <= fifo_count_r - 1'b1;
                default: fifo_count_r <= fifo_count_r;
            endcase
            if ((result_count_r > 128) || (issue_count_r > 128) ||
                    (fifo_count_r > 4) ||
                    (out_fire && out_batch_last &&
                     (converted_lane_count + 32'd1 <
                      (input_batch_count * 32'd128))))
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if ((FP_W != 16) && (FP_W != 32))
            $error("m4_fp_kv_producer FP_W must be 16 or 32");
    end
endmodule
