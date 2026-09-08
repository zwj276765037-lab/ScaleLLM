`timescale 1ns / 1ps

module hap_activation_cache_8row #(
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
    input  wire [$clog2(BANK_COUNT)-1:0]     wr_bank,
    input  wire [$clog2(GROUP_COUNT)-1:0]    wr_group,
    input  wire [ROWS*GROUP_SIZE*8-1:0]      wr_u8,
    input  wire [ROWS*24-1:0]                wr_meta,

    input  wire                              rd_req_valid,
    output wire                              rd_req_ready,
    input  wire [$clog2(BANK_COUNT)-1:0]     rd_req_bank,
    input  wire [$clog2(GROUP_COUNT)-1:0]    rd_req_group,
    output wire                              rd_rsp_valid,
    input  wire                              rd_rsp_ready,
    output wire [$clog2(BANK_COUNT)-1:0]     rd_rsp_bank,
    output wire [$clog2(GROUP_COUNT)-1:0]    rd_rsp_group,
    output wire [ROWS*GROUP_SIZE*8-1:0]      rd_rsp_u8,
    output wire [ROWS*24-1:0]                rd_rsp_meta,

    input  wire                              release_valid,
    output wire                              release_ready,
    input  wire [$clog2(BANK_COUNT)-1:0]     release_bank,
    output wire [BANK_COUNT-1:0]             bank_ready,

    output reg  [31:0]                       write_count,
    output reg  [31:0]                       read_count,
    output reg  [31:0]                       release_count,
    output reg                               error
);

    localparam integer BANK_W = $clog2(BANK_COUNT);
    localparam integer GROUP_W = $clog2(GROUP_COUNT);
    localparam integer ADDR_W = $clog2(BANK_COUNT * GROUP_COUNT);
    localparam integer DATA_W = ROWS * GROUP_SIZE * 8;
    localparam integer META_W = ROWS * 24;
    localparam integer DATA_SLICE_W = 512;
    localparam integer DATA_SLICE_COUNT = DATA_W / DATA_SLICE_W;

    reg [GROUP_COUNT-1:0] valid_map_r [0:BANK_COUNT-1];
    reg [BANK_COUNT-1:0] bank_ready_r;
    reg rd_rsp_valid_r;
    reg [BANK_W-1:0] rd_rsp_bank_r;
    reg [GROUP_W-1:0] rd_rsp_group_r;
    reg [DATA_W-1:0] rd_rsp_u8_r;
    reg [META_W-1:0] rd_rsp_meta_r;

    wire [ADDR_W-1:0] wr_addr = {wr_bank, wr_group};
    wire [ADDR_W-1:0] rd_addr = {rd_req_bank, rd_req_group};
    wire wr_fire = wr_valid && wr_ready;
    wire rd_req_fire = rd_req_valid && rd_req_ready;
    wire rd_rsp_fire = rd_rsp_valid && rd_rsp_ready;
    wire release_fire = release_valid && release_ready;
    wire [GROUP_COUNT-1:0] wr_valid_map_next =
        valid_map_r[wr_bank] |
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

    integer bank_idx;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (bank_idx = 0; bank_idx < BANK_COUNT;
                 bank_idx = bank_idx + 1)
                valid_map_r[bank_idx] <= '0;
            bank_ready_r <= '0;
            rd_rsp_valid_r <= 1'b0;
            rd_rsp_bank_r <= '0;
            rd_rsp_group_r <= '0;
            write_count <= 32'd0;
            read_count <= 32'd0;
            release_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            for (bank_idx = 0; bank_idx < BANK_COUNT;
                 bank_idx = bank_idx + 1)
                valid_map_r[bank_idx] <= '0;
            bank_ready_r <= '0;
            rd_rsp_valid_r <= 1'b0;
            write_count <= 32'd0;
            read_count <= 32'd0;
            release_count <= 32'd0;
            error <= 1'b0;
        end else begin
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
            end else if (wr_valid && !wr_ready) begin
                error <= 1'b1;
            end

            if (release_fire) begin
                valid_map_r[release_bank] <= '0;
                bank_ready_r[release_bank] <= 1'b0;
                release_count <= release_count + 32'd1;
            end else if (release_valid && !release_ready) begin
                error <= 1'b1;
            end
        end
    end

    initial begin
        if (GROUP_COUNT != 128 || BANK_COUNT != 2 || ROWS != 8 ||
            GROUP_SIZE != 32 || (DATA_W % DATA_SLICE_W) != 0)
            $error("hap_activation_cache_8row production shape is 2x128x8xgroup32");
    end

endmodule
