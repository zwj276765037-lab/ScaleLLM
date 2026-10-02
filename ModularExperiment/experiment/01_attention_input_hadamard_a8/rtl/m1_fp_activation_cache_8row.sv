`timescale 1ns/1ps

module m1_fp_activation_cache_8row #(
    parameter integer FP_W = 16,
    parameter integer GROUP_COUNT = 128,
    parameter integer BANK_COUNT = 2,
    parameter integer ROWS = 8,
    parameter integer GROUP_SIZE = 32
) (
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              clear,
    input  wire                              wr_valid,
    output wire                              wr_ready,
    input  wire                              wr_bank,
    input  wire [6:0]                        wr_group,
    input  wire [ROWS*GROUP_SIZE*8-1:0]      wr_u8,
    input  wire [ROWS*(FP_W+8)-1:0]          wr_meta,
    input  wire                              rd_req_valid,
    output wire                              rd_req_ready,
    input  wire                              rd_req_bank,
    input  wire [6:0]                        rd_req_group,
    output wire                              rd_rsp_valid,
    input  wire                              rd_rsp_ready,
    output wire                              rd_rsp_bank,
    output wire [6:0]                        rd_rsp_group,
    output wire [ROWS*GROUP_SIZE*8-1:0]      rd_rsp_u8,
    output wire [ROWS*(FP_W+8)-1:0]          rd_rsp_meta,
    input  wire                              release_valid,
    output wire                              release_ready,
    input  wire                              release_bank,
    output wire [1:0]                        bank_ready,
    output reg  [31:0]                       write_count,
    output reg  [31:0]                       read_count,
    output reg  [31:0]                       release_count,
    output reg  [31:0]                       format_error_count,
    output reg                               error
);
    localparam integer DATA_W = ROWS * GROUP_SIZE * 8;
    localparam integer META_W = ROWS * (FP_W + 8);
    localparam integer DATA_SLICE_W = 512;
    localparam integer DATA_SLICE_COUNT = DATA_W / DATA_SLICE_W;

    reg [GROUP_COUNT-1:0] valid_map_r [0:BANK_COUNT-1];
    reg [BANK_COUNT-1:0] bank_ready_r;
    reg rd_rsp_valid_r;
    reg rd_rsp_bank_r;
    reg [6:0] rd_rsp_group_r;
    reg [DATA_W-1:0] rd_rsp_u8_r;
    reg [META_W-1:0] rd_rsp_meta_r;

    wire [7:0] wr_addr = {wr_bank, wr_group};
    wire [7:0] rd_addr = {rd_req_bank, rd_req_group};
    wire wr_fire = wr_valid && wr_ready;
    wire rd_req_fire = rd_req_valid && rd_req_ready;
    wire rd_rsp_fire = rd_rsp_valid && rd_rsp_ready;
    wire release_fire = release_valid && release_ready;
    wire [GROUP_COUNT-1:0] wr_valid_map_next = valid_map_r[wr_bank] |
        ({{(GROUP_COUNT-1){1'b0}}, 1'b1} << wr_group);

    assign wr_ready = rst_n && !clear && !error &&
        !bank_ready_r[wr_bank] && !valid_map_r[wr_bank][wr_group] &&
        !(release_valid && (release_bank == wr_bank));
    assign rd_req_ready = rst_n && !clear && !error &&
        (!rd_rsp_valid_r || rd_rsp_ready) &&
        valid_map_r[rd_req_bank][rd_req_group];
    assign rd_rsp_valid = rd_rsp_valid_r;
    assign rd_rsp_bank = rd_rsp_bank_r;
    assign rd_rsp_group = rd_rsp_group_r;
    assign rd_rsp_u8 = rd_rsp_u8_r;
    assign rd_rsp_meta = rd_rsp_meta_r;
    assign release_ready = rst_n && !clear && !error &&
        bank_ready_r[release_bank];
    assign bank_ready = bank_ready_r;

    genvar data_slice;
    generate
        for (data_slice = 0; data_slice < DATA_SLICE_COUNT;
             data_slice = data_slice + 1) begin : g_data_mem
            (* ram_style = "block" *) reg [DATA_SLICE_W-1:0]
                mem [0:BANK_COUNT*GROUP_COUNT-1];
            always @(posedge clk) begin
                if (wr_fire)
                    mem[wr_addr] <= wr_u8[
                        data_slice*DATA_SLICE_W +: DATA_SLICE_W];
                if (rd_req_fire)
                    rd_rsp_u8_r[data_slice*DATA_SLICE_W +: DATA_SLICE_W]
                        <= mem[rd_addr];
            end
        end
    endgenerate

    (* ram_style = "block" *) reg [META_W-1:0]
        meta_mem [0:BANK_COUNT*GROUP_COUNT-1];
    always @(posedge clk) begin
        if (wr_fire)
            meta_mem[wr_addr] <= wr_meta;
        if (rd_req_fire)
            rd_rsp_meta_r <= meta_mem[rd_addr];
    end

    function automatic meta_has_format_error;
        input [META_W-1:0] metadata;
        integer row;
        reg invalid;
        reg [FP_W-1:0] scale_value;
        reg [31:0] extended;
        begin
            invalid = 1'b0;
            for (row = 0; row < ROWS; row = row + 1) begin
                scale_value = metadata[row*(FP_W+8)+8 +: FP_W];
                extended = 32'd0;
                extended[FP_W-1:0] = scale_value;
                if ((FP_W == 16 && (&extended[14:10])) ||
                        (FP_W == 32 && (&extended[30:23])))
                    invalid = 1'b1;
            end
            meta_has_format_error = invalid;
        end
    endfunction

    integer bank_idx;
    integer format_increment;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (bank_idx = 0; bank_idx < BANK_COUNT; bank_idx = bank_idx + 1)
                valid_map_r[bank_idx] <= '0;
            bank_ready_r <= '0;
            rd_rsp_valid_r <= 1'b0;
            rd_rsp_bank_r <= 1'b0;
            rd_rsp_group_r <= 7'd0;
            write_count <= 32'd0;
            read_count <= 32'd0;
            release_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            for (bank_idx = 0; bank_idx < BANK_COUNT; bank_idx = bank_idx + 1)
                valid_map_r[bank_idx] <= '0;
            bank_ready_r <= '0;
            rd_rsp_valid_r <= 1'b0;
            write_count <= 32'd0;
            read_count <= 32'd0;
            release_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else begin
            format_increment = 0;
            if (rd_rsp_fire)
                rd_rsp_valid_r <= 1'b0;
            if (rd_req_fire) begin
                rd_rsp_valid_r <= 1'b1;
                rd_rsp_bank_r <= rd_req_bank;
                rd_rsp_group_r <= rd_req_group;
                read_count <= read_count + 32'd1;
            end
            if (wr_fire) begin
                valid_map_r[wr_bank][wr_group] <= 1'b1;
                write_count <= write_count + 32'd1;
                if (&wr_valid_map_next)
                    bank_ready_r[wr_bank] <= 1'b1;
                if (meta_has_format_error(wr_meta))
                    format_increment = format_increment + 1;
            end else if (wr_valid && !wr_ready)
                error <= 1'b1;
            if (rd_rsp_fire && meta_has_format_error(rd_rsp_meta))
                format_increment = format_increment + 1;
            if (format_increment != 0) begin
                format_error_count <= format_error_count + format_increment;
                error <= 1'b1;
            end
            if (release_fire) begin
                valid_map_r[release_bank] <= '0;
                bank_ready_r[release_bank] <= 1'b0;
                release_count <= release_count + 32'd1;
            end else if (release_valid && !release_ready)
                error <= 1'b1;
        end
    end

    initial begin
        if (((FP_W != 16) && (FP_W != 32)) || GROUP_COUNT != 128 ||
                BANK_COUNT != 2 || ROWS != 8 || GROUP_SIZE != 32 ||
                (DATA_W % DATA_SLICE_W) != 0)
            $error("m1_fp_activation_cache_8row parameters do not match production");
    end
endmodule
