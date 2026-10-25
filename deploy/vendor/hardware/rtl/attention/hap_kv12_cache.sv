`timescale 1ns / 1ps

module hap_kv12_cache #(
    parameter integer ADDR_W = 12,
    parameter integer DEPTH = 4096
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,

    input  wire                  wr_valid,
    output wire                  wr_ready,
    input  wire                  wr_is_v,
    input  wire [ADDR_W-1:0]     wr_addr,
    input  wire [383:0]          wr_s12,
    input  wire [15:0]           wr_meta,

    input  wire                  k_rd_valid,
    output wire                  k_rd_ready,
    input  wire [ADDR_W-1:0]     k_rd_addr,
    output wire                  k_rsp_valid,
    input  wire                  k_rsp_ready,
    output wire [383:0]          k_rsp_s12,
    output wire [15:0]           k_rsp_meta,

    input  wire                  v_rd_valid,
    output wire                  v_rd_ready,
    input  wire [ADDR_W-1:0]     v_rd_addr,
    output wire                  v_rsp_valid,
    input  wire                  v_rsp_ready,
    output wire [383:0]          v_rsp_s12,
    output wire [15:0]           v_rsp_meta,

    output reg  [31:0]           k_write_count,
    output reg  [31:0]           v_write_count,
    output reg  [31:0]           k_read_count,
    output reg  [31:0]           v_read_count,
    output reg  [31:0]           format_error_count,
    output reg                   error
);

    (* ram_style = "block" *) reg [399:0] k_record_mem [0:DEPTH-1];
    (* ram_style = "block" *) reg [399:0] v_record_mem [0:DEPTH-1];
    reg [399:0] k_rsp_record_r;
    reg [399:0] v_rsp_record_r;
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
    assign k_rsp_s12 = k_rsp_record_r[383:0];
    assign k_rsp_meta = k_rsp_record_r[399:384];
    assign v_rsp_s12 = v_rsp_record_r[383:0];
    assign v_rsp_meta = v_rsp_record_r[399:384];

    // Memory contents intentionally have no reset.  Valid bits prevent stale
    // data from becoming observable, preserving block-RAM inference.
    always @(posedge clk) begin
        if (wr_fire && !wr_is_v)
            k_record_mem[wr_addr] <= {wr_meta, wr_s12};
        if (wr_fire && wr_is_v)
            v_record_mem[wr_addr] <= {wr_meta, wr_s12};
        if (k_rd_fire)
            k_rsp_record_r <= k_record_mem[k_rd_addr];
        if (v_rd_fire)
            v_rsp_record_r <= v_record_mem[v_rd_addr];
    end

    function automatic record_has_format_error;
        input [383:0] values;
        input [15:0] meta;
        integer lane;
        reg invalid;
        begin
            invalid = (meta[15:14] != 0) ||
                ((meta[7:0] == 0) && (meta[13:8] != 0)) ||
                ((meta[7:0] != 0) &&
                 ((meta[13:8] < 8) || (meta[13:8] > 32)));
            for (lane = 0; lane < 32; lane = lane + 1)
                if (values[lane*12 +: 12] == 12'h800)
                    invalid = 1'b1;
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
                if (record_has_format_error(wr_s12, wr_meta))
                    format_increment = format_increment + 1;
            end
            if (k_rsp_fire) begin
                k_read_count <= k_read_count + 32'd1;
                if (record_has_format_error(k_rsp_s12, k_rsp_meta))
                    format_increment = format_increment + 1;
            end
            if (v_rsp_fire) begin
                v_read_count <= v_read_count + 32'd1;
                if (record_has_format_error(v_rsp_s12, v_rsp_meta))
                    format_increment = format_increment + 1;
            end
            if (format_increment != 0) begin
                format_error_count <= format_error_count + format_increment;
                error <= 1'b1;
            end
        end
    end

    initial begin
        if (ADDR_W != 12 || DEPTH != 4096)
            $error("hap_kv12_cache production parameters are fixed");
    end

endmodule
