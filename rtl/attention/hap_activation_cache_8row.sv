`timescale 1ns / 1ps

module hap_activation_cache_8row #(
    parameter integer GROUP_COUNT = 128,
    parameter integer BANK_COUNT = 2,
    parameter integer ROWS = 8,
    parameter integer GROUP_SIZE = 32,
    parameter integer RD_RESPONSE_DEPTH = 1
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
    localparam integer FIFO_DATA_CHUNK_W = 256;
    localparam integer FIFO_DATA_CHUNK_COUNT =
        DATA_W / FIFO_DATA_CHUNK_W;
    reg [GROUP_COUNT-1:0] valid_map_r [0:BANK_COUNT-1];
    reg [BANK_COUNT-1:0] bank_ready_r;
    // Keep the inferred BRAM read destination fixed.  A variable-indexed
    // destination makes Vivado implement the 256-deep cache itself in LUTRAM.
    reg rd_mem_valid_r;
    reg [BANK_W-1:0] rd_mem_bank_r;
    reg [GROUP_W-1:0] rd_mem_group_r;
    reg [DATA_W-1:0] rd_mem_u8_r;
    reg [META_W-1:0] rd_mem_meta_r;

    // Depth-two mode adds a local queue after the fixed BRAM output stage.
    // The extra in-flight stage is intentional: it permits II=1 without a
    // combinational rd_rsp_ready path back to rd_req_ready.
    reg rd_rsp_wr_ptr_r;
    reg rd_rsp_rd_ptr_r;
    reg [1:0] rd_rsp_count_r;
    // Explicit FF entries avoid the unfixable RAMD32-to-FF intra-site hold
    // path seen in the depth-two physical shell.  Segmenting each write CE
    // keeps the FF implementation local without promoting a 2248-load data
    // predicate onto a BUFG.
    (* ram_style = "registers" *) reg [DATA_W-1:0] rd_rsp_u8_fifo0_r;
    (* ram_style = "registers" *) reg [DATA_W-1:0] rd_rsp_u8_fifo1_r;
    (* ram_style = "registers" *) reg [META_W-1:0] rd_rsp_meta_fifo0_r;
    (* ram_style = "registers" *) reg [META_W-1:0] rd_rsp_meta_fifo1_r;
    reg [BANK_W-1:0] rd_rsp_bank_fifo0_r;
    reg [BANK_W-1:0] rd_rsp_bank_fifo1_r;
    reg [GROUP_W-1:0] rd_rsp_group_fifo0_r;
    reg [GROUP_W-1:0] rd_rsp_group_fifo1_r;
    wire [1:0] rd_rsp_entry_write_fire;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [2*FIFO_DATA_CHUNK_COUNT-1:0]
        rd_rsp_u8_fifo_write_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [1:0] rd_rsp_meta_tag_fifo_write_enable;

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
    // Depth two is a no-bypass elastic boundary.  The fixed BRAM output stage
    // plus two local queue entries absorb an unexpected downstream stall;
    // only registered occupancy controls the request path.
    wire rd_rsp_capacity = RD_RESPONSE_DEPTH == 1 ?
        (!rd_mem_valid_r || rd_rsp_ready) :
        (!rd_mem_valid_r || rd_rsp_count_r < 2);
    wire rd_mem_advance = RD_RESPONSE_DEPTH == 2 && rd_mem_valid_r &&
        rd_rsp_count_r < 2;
    assign rd_rsp_entry_write_fire[0] =
        rd_mem_advance && !rd_rsp_wr_ptr_r;
    assign rd_rsp_entry_write_fire[1] =
        rd_mem_advance && rd_rsp_wr_ptr_r;
    assign rd_req_ready = rst_n && !clear && !error && rd_rsp_capacity &&
        valid_map_r[rd_req_bank][rd_req_group];
    assign rd_rsp_valid = RD_RESPONSE_DEPTH == 1 ? rd_mem_valid_r :
        rd_rsp_count_r != 0;
    assign rd_rsp_bank = RD_RESPONSE_DEPTH == 1 ? rd_mem_bank_r :
        (rd_rsp_rd_ptr_r ? rd_rsp_bank_fifo1_r : rd_rsp_bank_fifo0_r);
    assign rd_rsp_group = RD_RESPONSE_DEPTH == 1 ? rd_mem_group_r :
        (rd_rsp_rd_ptr_r ? rd_rsp_group_fifo1_r :
            rd_rsp_group_fifo0_r);
    assign rd_rsp_u8 = RD_RESPONSE_DEPTH == 1 ? rd_mem_u8_r :
        (rd_rsp_rd_ptr_r ? rd_rsp_u8_fifo1_r : rd_rsp_u8_fifo0_r);
    assign rd_rsp_meta = RD_RESPONSE_DEPTH == 1 ? rd_mem_meta_r :
        (rd_rsp_rd_ptr_r ? rd_rsp_meta_fifo1_r :
            rd_rsp_meta_fifo0_r);
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
                    rd_mem_u8_r[data_slice*DATA_SLICE_W +:
                        DATA_SLICE_W] <= mem[rd_addr];
            end
        end
    endgenerate

    (* ram_style = "block" *) reg [META_W-1:0]
        meta_mem [0:BANK_COUNT*GROUP_COUNT-1];

    always @(posedge clk) begin
        if (wr_fire)
            meta_mem[wr_addr] <= wr_meta;
        if (rd_req_fire)
            rd_mem_meta_r <= meta_mem[rd_addr];
    end

    genvar fifo_entry;
    genvar fifo_chunk;
    generate
        for (fifo_entry = 0; fifo_entry < 2;
             fifo_entry = fifo_entry + 1) begin : g_rsp_fifo_entry
            for (fifo_chunk = 0; fifo_chunk < FIFO_DATA_CHUNK_COUNT;
                 fifo_chunk = fifo_chunk + 1) begin : g_data_chunk
                localparam integer ENABLE_INDEX =
                    fifo_entry * FIFO_DATA_CHUNK_COUNT + fifo_chunk;
                (* DONT_TOUCH = "yes", KEEP = "yes" *)
                LUT1 #(.INIT(2'h2)) u_write_enable (
                    .I0(rd_rsp_entry_write_fire[fifo_entry]),
                    .O(rd_rsp_u8_fifo_write_enable[ENABLE_INDEX])
                );
                if (fifo_entry == 0) begin : g_entry0
                    always @(posedge clk)
                        if (rd_rsp_u8_fifo_write_enable[ENABLE_INDEX])
                            rd_rsp_u8_fifo0_r[
                                fifo_chunk*FIFO_DATA_CHUNK_W +:
                                FIFO_DATA_CHUNK_W] <=
                                rd_mem_u8_r[
                                    fifo_chunk*FIFO_DATA_CHUNK_W +:
                                    FIFO_DATA_CHUNK_W];
                end else begin : g_entry1
                    always @(posedge clk)
                        if (rd_rsp_u8_fifo_write_enable[ENABLE_INDEX])
                            rd_rsp_u8_fifo1_r[
                                fifo_chunk*FIFO_DATA_CHUNK_W +:
                                FIFO_DATA_CHUNK_W] <=
                                rd_mem_u8_r[
                                    fifo_chunk*FIFO_DATA_CHUNK_W +:
                                    FIFO_DATA_CHUNK_W];
                end
            end

            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT1 #(.INIT(2'h2)) u_meta_tag_write_enable (
                .I0(rd_rsp_entry_write_fire[fifo_entry]),
                .O(rd_rsp_meta_tag_fifo_write_enable[fifo_entry])
            );
            if (fifo_entry == 0) begin : g_meta_tag_entry0
                always @(posedge clk)
                    if (rd_rsp_meta_tag_fifo_write_enable[fifo_entry]) begin
                        rd_rsp_bank_fifo0_r <= rd_mem_bank_r;
                        rd_rsp_group_fifo0_r <= rd_mem_group_r;
                        rd_rsp_meta_fifo0_r <= rd_mem_meta_r;
                    end
            end else begin : g_meta_tag_entry1
                always @(posedge clk)
                    if (rd_rsp_meta_tag_fifo_write_enable[fifo_entry]) begin
                        rd_rsp_bank_fifo1_r <= rd_mem_bank_r;
                        rd_rsp_group_fifo1_r <= rd_mem_group_r;
                        rd_rsp_meta_fifo1_r <= rd_mem_meta_r;
                    end
            end
        end
    endgenerate

    integer bank_idx;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (bank_idx = 0; bank_idx < BANK_COUNT;
                 bank_idx = bank_idx + 1)
                valid_map_r[bank_idx] <= '0;
            bank_ready_r <= '0;
            rd_mem_valid_r <= 1'b0;
            rd_rsp_wr_ptr_r <= 1'b0;
            rd_rsp_rd_ptr_r <= 1'b0;
            rd_rsp_count_r <= 2'd0;
            write_count <= 32'd0;
            read_count <= 32'd0;
            release_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            for (bank_idx = 0; bank_idx < BANK_COUNT;
                 bank_idx = bank_idx + 1)
                valid_map_r[bank_idx] <= '0;
            bank_ready_r <= '0;
            rd_mem_valid_r <= 1'b0;
            rd_rsp_wr_ptr_r <= 1'b0;
            rd_rsp_rd_ptr_r <= 1'b0;
            rd_rsp_count_r <= 2'd0;
            write_count <= 32'd0;
            read_count <= 32'd0;
            release_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (rd_req_fire) begin
                rd_mem_bank_r <= rd_req_bank;
                rd_mem_group_r <= rd_req_group;
                read_count <= read_count + 32'd1;
            end
            if (RD_RESPONSE_DEPTH == 1) begin
                case ({rd_req_fire, rd_rsp_fire})
                    2'b10: rd_mem_valid_r <= 1'b1;
                    2'b01: rd_mem_valid_r <= 1'b0;
                    2'b11: rd_mem_valid_r <= 1'b1;
                    default: rd_mem_valid_r <= rd_mem_valid_r;
                endcase
            end else begin
                if (rd_mem_advance) begin
                    rd_rsp_wr_ptr_r <= ~rd_rsp_wr_ptr_r;
                end
                if (rd_rsp_fire)
                    rd_rsp_rd_ptr_r <= ~rd_rsp_rd_ptr_r;
                case ({rd_mem_advance, rd_rsp_fire})
                    2'b10: rd_rsp_count_r <= rd_rsp_count_r + 1'b1;
                    2'b01: rd_rsp_count_r <= rd_rsp_count_r - 1'b1;
                    default: rd_rsp_count_r <= rd_rsp_count_r;
                endcase
                case ({rd_req_fire, rd_mem_advance})
                    2'b10: rd_mem_valid_r <= 1'b1;
                    2'b01: rd_mem_valid_r <= 1'b0;
                    2'b11: rd_mem_valid_r <= 1'b1;
                    default: rd_mem_valid_r <= rd_mem_valid_r;
                endcase
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
            GROUP_SIZE != 32 || (DATA_W % DATA_SLICE_W) != 0 ||
            (DATA_W % FIFO_DATA_CHUNK_W) != 0 ||
            (RD_RESPONSE_DEPTH != 1 && RD_RESPONSE_DEPTH != 2))
            $error("hap_activation_cache_8row production shape is 2x128x8xgroup32");
    end

endmodule
