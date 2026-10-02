`timescale 1ns/1ps

// Direct-FP cache with the same depth, independent K/V read ports, elastic
// one-record response buffers, counters and ready/valid behavior as the
// production KV12 cache.  No per-group scale metadata is needed because each
// lane is stored as a fully dequantized IEEE value.
module m4_fp_kv_cache #(
    parameter integer FP_W = 16,
    parameter integer ADDR_W = 12,
    parameter integer DEPTH = 4096
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     wr_valid,
    output wire                     wr_ready,
    input  wire                     wr_is_v,
    input  wire [ADDR_W-1:0]        wr_addr,
    input  wire [32*FP_W-1:0]       wr_fp,
    input  wire                     k_rd_valid,
    output wire                     k_rd_ready,
    input  wire [ADDR_W-1:0]        k_rd_addr,
    output wire                     k_rsp_valid,
    input  wire                     k_rsp_ready,
    output wire [32*FP_W-1:0]       k_rsp_fp,
    input  wire                     v_rd_valid,
    output wire                     v_rd_ready,
    input  wire [ADDR_W-1:0]        v_rd_addr,
    output wire                     v_rsp_valid,
    input  wire                     v_rsp_ready,
    output wire [32*FP_W-1:0]       v_rsp_fp,
    output reg  [31:0]              k_write_count,
    output reg  [31:0]              v_write_count,
    output reg  [31:0]              k_read_count,
    output reg  [31:0]              v_read_count,
    output reg  [31:0]              format_error_count,
    output reg                      error
);
    localparam integer RECORD_W = 32*FP_W;
    (* ram_style = "block" *) reg [RECORD_W-1:0] k_record_mem [0:DEPTH-1];
    (* ram_style = "block" *) reg [RECORD_W-1:0] v_record_mem [0:DEPTH-1];
    reg [RECORD_W-1:0] k_rsp_record_r;
    reg [RECORD_W-1:0] v_rsp_record_r;
    reg k_rsp_valid_r;
    reg v_rsp_valid_r;

    wire wr_fire = wr_valid && wr_ready;
    wire k_rd_fire = k_rd_valid && k_rd_ready;
    wire v_rd_fire = v_rd_valid && v_rd_ready;
    wire k_rsp_fire = k_rsp_valid && k_rsp_ready;
    wire v_rsp_fire = v_rsp_valid && v_rsp_ready;

    assign wr_ready = rst_n && !clear;
    assign k_rd_ready = rst_n && !clear &&
        (!k_rsp_valid_r || k_rsp_ready);
    assign v_rd_ready = rst_n && !clear &&
        (!v_rsp_valid_r || v_rsp_ready);
    assign k_rsp_valid = rst_n && !clear && k_rsp_valid_r;
    assign v_rsp_valid = rst_n && !clear && v_rsp_valid_r;
    assign k_rsp_fp = k_rsp_record_r;
    assign v_rsp_fp = v_rsp_record_r;

    always @(posedge clk) begin
        if (wr_fire && !wr_is_v)
            k_record_mem[wr_addr] <= wr_fp;
        if (wr_fire && wr_is_v)
            v_record_mem[wr_addr] <= wr_fp;
        if (k_rd_fire)
            k_rsp_record_r <= k_record_mem[k_rd_addr];
        if (v_rd_fire)
            v_rsp_record_r <= v_record_mem[v_rd_addr];
    end

    function automatic record_has_format_error;
        input [RECORD_W-1:0] values;
        integer lane;
        reg invalid;
        reg [FP_W-1:0] value;
        reg [31:0] extended;
        begin
            invalid = 1'b0;
            for (lane = 0; lane < 32; lane = lane + 1) begin
                value = values[lane*FP_W +: FP_W];
                extended = 32'd0;
                extended[FP_W-1:0] = value;
                if ((FP_W == 16 && (&extended[14:10])) ||
                        (FP_W == 32 && (&extended[30:23])))
                    invalid = 1'b1;
            end
            record_has_format_error = invalid;
        end
    endfunction

    integer format_increment;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            k_rsp_valid_r <= 1'b0;
            v_rsp_valid_r <= 1'b0;
            k_write_count <= 32'd0;
            v_write_count <= 32'd0;
            k_read_count <= 32'd0;
            v_read_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            k_rsp_valid_r <= 1'b0;
            v_rsp_valid_r <= 1'b0;
            k_write_count <= 32'd0;
            v_write_count <= 32'd0;
            k_read_count <= 32'd0;
            v_read_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (k_rsp_fire)
                k_rsp_valid_r <= 1'b0;
            if (v_rsp_fire)
                v_rsp_valid_r <= 1'b0;
            if (k_rd_fire)
                k_rsp_valid_r <= 1'b1;
            if (v_rd_fire)
                v_rsp_valid_r <= 1'b1;
            format_increment = 0;
            if (wr_fire) begin
                if (wr_is_v)
                    v_write_count <= v_write_count + 32'd1;
                else
                    k_write_count <= k_write_count + 32'd1;
                if (record_has_format_error(wr_fp))
                    format_increment = format_increment + 1;
            end
            if (k_rsp_fire) begin
                k_read_count <= k_read_count + 32'd1;
                if (record_has_format_error(k_rsp_fp))
                    format_increment = format_increment + 1;
            end
            if (v_rsp_fire) begin
                v_read_count <= v_read_count + 32'd1;
                if (record_has_format_error(v_rsp_fp))
                    format_increment = format_increment + 1;
            end
            if (format_increment != 0) begin
                format_error_count <= format_error_count + format_increment;
                error <= 1'b1;
            end
        end
    end

    initial begin
        if (((FP_W != 16) && (FP_W != 32)) ||
                (ADDR_W != 12) || (DEPTH != 4096))
            $error("m4_fp_kv_cache parameters do not match production");
    end
endmodule
