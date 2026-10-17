`timescale 1ns / 1ps

// Assemble the two 512-bit beats belonging to one eight-column W4 group in
// its MIG UI domain, then cross the complete 1024-bit transaction into the
// 150-MHz core domain.  A slot is reserved on beat0 so a FIFO-full transition
// cannot split a two-beat group.
module hap_ddr512_w4_halfgroup_async #(
    parameter integer FIFO_DEPTH = 8
) (
    input  wire                  ddr_clk,
    input  wire                  ddr_rst_n,
    input  wire                  ddr_clear,
    input  wire                  beat_valid,
    output wire                  beat_ready,
    input  wire [511:0]          beat_data,
    input  wire                  beat_group_last,

    input  wire                  core_clk,
    input  wire                  core_rst_n,
    input  wire                  core_clear,
    output wire                  half_valid,
    input  wire                  half_ready,
    output wire [1023:0]         half_data,

    output reg  [31:0]           ddr_beat_count,
    output reg  [31:0]           ddr_half_count,
    output reg  [31:0]           core_half_count,
    output wire                  error
);

    localparam integer ADDR_W = $clog2(FIFO_DEPTH);
    localparam integer PTR_W = ADDR_W + 1;

    (* ram_style = "block" *) reg [1023:0] fifo_mem [0:FIFO_DEPTH-1];
    reg [511:0] first_beat_r;
    reg beat_index_r;
    reg [PTR_W-1:0] wr_bin_r;
    wire [PTR_W-1:0] rd_bin_sync_wr;
    reg ddr_error_r;

    reg [PTR_W-1:0] rd_bin_r;
    wire [PTR_W-1:0] wr_bin_sync_rd;
    reg [1023:0] half_data_r;
    reg half_valid_r;
    reg core_error_r;
    wire ddr_error_core;

    wire [PTR_W-1:0] wr_bin_next = wr_bin_r + 1'b1;
    wire fifo_full = wr_bin_next ==
        {~rd_bin_sync_wr[PTR_W-1], rd_bin_sync_wr[PTR_W-2:0]};
    wire fifo_empty = rd_bin_r == wr_bin_sync_rd;
    wire beat_fire = beat_valid && beat_ready;
    wire half_fire = half_valid && half_ready;
    wire core_load = (!half_valid_r || half_ready) && !fifo_empty;

    assign beat_ready = ddr_rst_n && !ddr_clear &&
        (beat_index_r || !fifo_full) && !ddr_error_r;
    assign half_valid = core_rst_n && !core_clear && half_valid_r;
    assign half_data = half_data_r;
    assign error = ddr_error_core || core_error_r;

    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(0)
    ) u_ddr_error_cdc (
        .src_clk(ddr_clk), .src_in(ddr_error_r),
        .dest_clk(core_clk), .dest_out(ddr_error_core)
    );

    xpm_cdc_gray #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .REG_OUTPUT(0),
        .SIM_ASSERT_CHK(0), .SIM_LOSSLESS_GRAY_CHK(0), .WIDTH(PTR_W)
    ) u_rd_pointer_cdc (
        .src_clk(core_clk), .src_in_bin(rd_bin_r),
        .dest_clk(ddr_clk), .dest_out_bin(rd_bin_sync_wr)
    );

    xpm_cdc_gray #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .REG_OUTPUT(0),
        .SIM_ASSERT_CHK(0), .SIM_LOSSLESS_GRAY_CHK(0), .WIDTH(PTR_W)
    ) u_wr_pointer_cdc (
        .src_clk(ddr_clk), .src_in_bin(wr_bin_r),
        .dest_clk(core_clk), .dest_out_bin(wr_bin_sync_rd)
    );

    always @(posedge ddr_clk) begin
        if (beat_fire) begin
            if (!beat_index_r)
                first_beat_r <= beat_data;
            else
                fifo_mem[wr_bin_r[ADDR_W-1:0]] <=
                    {beat_data, first_beat_r};
        end
    end

    always @(posedge ddr_clk or negedge ddr_rst_n) begin
        if (!ddr_rst_n) begin
            beat_index_r <= 1'b0;
            wr_bin_r <= '0;
            ddr_beat_count <= 32'd0;
            ddr_half_count <= 32'd0;
            ddr_error_r <= 1'b0;
        end else if (ddr_clear) begin
            beat_index_r <= 1'b0;
            wr_bin_r <= '0;
            ddr_beat_count <= 32'd0;
            ddr_half_count <= 32'd0;
            ddr_error_r <= 1'b0;
        end else if (beat_fire) begin
            ddr_beat_count <= ddr_beat_count + 32'd1;
            if (beat_group_last != beat_index_r)
                ddr_error_r <= 1'b1;
            if (beat_index_r) begin
                beat_index_r <= 1'b0;
                wr_bin_r <= wr_bin_next;
                ddr_half_count <= ddr_half_count + 32'd1;
                if (fifo_full)
                    ddr_error_r <= 1'b1;
            end else begin
                beat_index_r <= 1'b1;
            end
        end
    end

    always @(posedge core_clk) begin
        if (core_load)
            half_data_r <= fifo_mem[rd_bin_r[ADDR_W-1:0]];
    end

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            rd_bin_r <= '0;
            half_valid_r <= 1'b0;
            core_half_count <= 32'd0;
            core_error_r <= 1'b0;
        end else if (core_clear) begin
            rd_bin_r <= '0;
            half_valid_r <= 1'b0;
            core_half_count <= 32'd0;
            core_error_r <= 1'b0;
        end else begin
            if (!half_valid_r || half_ready)
                half_valid_r <= !fifo_empty;
            if (core_load)
                rd_bin_r <= rd_bin_r + 1'b1;
            if (half_fire)
                core_half_count <= core_half_count + 32'd1;
            if (half_fire && !half_valid_r)
                core_error_r <= 1'b1;
        end
    end

    initial begin
        if (FIFO_DEPTH != 8)
            $error("W4 production async FIFO_DEPTH must be 8");
    end

endmodule
