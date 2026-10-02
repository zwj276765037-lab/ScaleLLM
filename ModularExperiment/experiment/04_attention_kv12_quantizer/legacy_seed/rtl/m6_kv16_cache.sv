`timescale 1ns/1ps

// Matched KV16 cache baselines.  Both variants preserve the production
// cache's independent K/V read ports, one-record response buffers, counters,
// format validation, depth, and ready/valid boundary.  Only record format
// changes: 32 x S16 plus an IEEE FP16 or FP32 scale.
module m6_kv16_cache #(
    parameter integer META_W = 16,
    parameter integer ADDR_W = 12,
    parameter integer DEPTH = 4096
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 wr_valid,
    output wire                 wr_ready,
    input  wire                 wr_is_v,
    input  wire [ADDR_W-1:0]    wr_addr,
    input  wire [511:0]         wr_s16,
    input  wire [META_W-1:0]    wr_scale,
    input  wire                 k_rd_valid,
    output wire                 k_rd_ready,
    input  wire [ADDR_W-1:0]    k_rd_addr,
    output wire                 k_rsp_valid,
    input  wire                 k_rsp_ready,
    output wire [511:0]         k_rsp_s16,
    output wire [META_W-1:0]    k_rsp_scale,
    input  wire                 v_rd_valid,
    output wire                 v_rd_ready,
    input  wire [ADDR_W-1:0]    v_rd_addr,
    output wire                 v_rsp_valid,
    input  wire                 v_rsp_ready,
    output wire [511:0]         v_rsp_s16,
    output wire [META_W-1:0]    v_rsp_scale,
    output reg [31:0]           k_write_count,
    output reg [31:0]           v_write_count,
    output reg [31:0]           k_read_count,
    output reg [31:0]           v_read_count,
    output reg [31:0]           format_error_count,
    output reg                  error
);
    localparam integer RECORD_W = 512 + META_W;
    (* ram_style = "block" *) reg [RECORD_W-1:0] k_record_mem [0:DEPTH-1];
    (* ram_style = "block" *) reg [RECORD_W-1:0] v_record_mem [0:DEPTH-1];
    reg [RECORD_W-1:0] k_rsp_record_r, v_rsp_record_r;
    reg k_rsp_valid_r, v_rsp_valid_r;

    wire wr_fire = wr_valid && wr_ready;
    wire k_rd_fire = k_rd_valid && k_rd_ready;
    wire v_rd_fire = v_rd_valid && v_rd_ready;
    wire k_rsp_fire = k_rsp_valid && k_rsp_ready;
    wire v_rsp_fire = v_rsp_valid && v_rsp_ready;
    assign wr_ready = rst_n && !clear;
    assign k_rd_ready = rst_n && !clear && (!k_rsp_valid_r || k_rsp_ready);
    assign v_rd_ready = rst_n && !clear && (!v_rsp_valid_r || v_rsp_ready);
    assign k_rsp_valid = rst_n && !clear && k_rsp_valid_r;
    assign v_rsp_valid = rst_n && !clear && v_rsp_valid_r;
    assign k_rsp_s16 = k_rsp_record_r[511:0];
    assign v_rsp_s16 = v_rsp_record_r[511:0];
    assign k_rsp_scale = k_rsp_record_r[RECORD_W-1:512];
    assign v_rsp_scale = v_rsp_record_r[RECORD_W-1:512];

    always @(posedge clk) begin
        if (wr_fire && !wr_is_v)
            k_record_mem[wr_addr] <= {wr_scale, wr_s16};
        if (wr_fire && wr_is_v)
            v_record_mem[wr_addr] <= {wr_scale, wr_s16};
        if (k_rd_fire)
            k_rsp_record_r <= k_record_mem[k_rd_addr];
        if (v_rd_fire)
            v_rsp_record_r <= v_record_mem[v_rd_addr];
    end

    function automatic record_has_format_error;
        input [511:0] values;
        input [META_W-1:0] scale;
        integer lane;
        reg invalid;
        begin
            // Infinity/NaN are illegal. Zero scale is legal only for an
            // all-zero group, checked by the lane loop below.
            if (META_W == 16)
                invalid = (&scale[14:10]);
            else
                invalid = (&scale[30:23]);
            for (lane = 0; lane < 32; lane = lane + 1) begin
                if (values[lane*16 +: 16] == 16'h8000)
                    invalid = 1'b1;
                if ((scale == 0) && (values[lane*16 +: 16] != 0))
                    invalid = 1'b1;
            end
            record_has_format_error = invalid;
        end
    endfunction

    integer format_increment;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            k_rsp_valid_r <= 0; v_rsp_valid_r <= 0;
            k_write_count <= 0; v_write_count <= 0;
            k_read_count <= 0; v_read_count <= 0;
            format_error_count <= 0; error <= 0;
        end else if (clear) begin
            k_rsp_valid_r <= 0; v_rsp_valid_r <= 0;
            k_write_count <= 0; v_write_count <= 0;
            k_read_count <= 0; v_read_count <= 0;
            format_error_count <= 0; error <= 0;
        end else begin
            if (k_rsp_fire) k_rsp_valid_r <= 0;
            if (v_rsp_fire) v_rsp_valid_r <= 0;
            if (k_rd_fire) k_rsp_valid_r <= 1;
            if (v_rd_fire) v_rsp_valid_r <= 1;
            format_increment = 0;
            if (wr_fire) begin
                if (wr_is_v) v_write_count <= v_write_count + 1;
                else k_write_count <= k_write_count + 1;
                if (record_has_format_error(wr_s16, wr_scale))
                    format_increment = format_increment + 1;
            end
            if (k_rsp_fire) begin
                k_read_count <= k_read_count + 1;
                if (record_has_format_error(k_rsp_s16, k_rsp_scale))
                    format_increment = format_increment + 1;
            end
            if (v_rsp_fire) begin
                v_read_count <= v_read_count + 1;
                if (record_has_format_error(v_rsp_s16, v_rsp_scale))
                    format_increment = format_increment + 1;
            end
            if (format_increment != 0) begin
                format_error_count <= format_error_count + format_increment;
                error <= 1;
            end
        end
    end

    initial begin
        if ((META_W != 16 && META_W != 32) || ADDR_W != 12 || DEPTH != 4096)
            $error("M6 KV16 cache supports only matched production cases");
    end
endmodule

module m6_kv16_fp16_cache (
    input wire clk, rst_n, clear,
    input wire wr_valid, output wire wr_ready, input wire wr_is_v,
    input wire [11:0] wr_addr, input wire [511:0] wr_s16,
    input wire [15:0] wr_scale,
    input wire k_rd_valid, output wire k_rd_ready, input wire [11:0] k_rd_addr,
    output wire k_rsp_valid, input wire k_rsp_ready,
    output wire [511:0] k_rsp_s16, output wire [15:0] k_rsp_scale,
    input wire v_rd_valid, output wire v_rd_ready, input wire [11:0] v_rd_addr,
    output wire v_rsp_valid, input wire v_rsp_ready,
    output wire [511:0] v_rsp_s16, output wire [15:0] v_rsp_scale,
    output wire [31:0] k_write_count, v_write_count, k_read_count,
    output wire [31:0] v_read_count, format_error_count, output wire error
);
    m6_kv16_cache #(.META_W(16)) u_cache (.*);
endmodule

module m6_kv16_fp32_cache (
    input wire clk, rst_n, clear,
    input wire wr_valid, output wire wr_ready, input wire wr_is_v,
    input wire [11:0] wr_addr, input wire [511:0] wr_s16,
    input wire [31:0] wr_scale,
    input wire k_rd_valid, output wire k_rd_ready, input wire [11:0] k_rd_addr,
    output wire k_rsp_valid, input wire k_rsp_ready,
    output wire [511:0] k_rsp_s16, output wire [31:0] k_rsp_scale,
    input wire v_rd_valid, output wire v_rd_ready, input wire [11:0] v_rd_addr,
    output wire v_rsp_valid, input wire v_rsp_ready,
    output wire [511:0] v_rsp_s16, output wire [31:0] v_rsp_scale,
    output wire [31:0] k_write_count, v_write_count, k_read_count,
    output wire [31:0] v_read_count, format_error_count, output wire error
);
    m6_kv16_cache #(.META_W(32)) u_cache (.*);
endmodule
