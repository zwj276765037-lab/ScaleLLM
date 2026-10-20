`timescale 1ns / 1ps

// Assemble four 512-bit DDR beats into one 2048-bit/8-column weight half
// and cross it into the 150-MHz compute clock domain.
module hap_ddr512_halfgroup_async #(
    parameter integer FIFO_DEPTH = 8
) (
    input  wire                  ddr_clk,
    input  wire                  ddr_rst_n,
    input  wire                  ddr_clear,
    input  wire                  beat_valid,
    output wire                  beat_ready,
    input  wire [511:0]          beat_data,
    input  wire                  beat_last,

    input  wire                  core_clk,
    input  wire                  core_rst_n,
    input  wire                  core_clear,
    output wire                  half_valid,
    input  wire                  half_ready,
    output wire [2047:0]         half_data,

    output reg  [31:0]           ddr_beat_count,
    output reg  [31:0]           ddr_half_count,
    output reg  [31:0]           core_half_count,
    output wire                  error
);

    localparam integer ADDR_W = $clog2(FIFO_DEPTH);
    localparam integer PTR_W = ADDR_W + 1;

    (* ram_style = "block" *) reg [2047:0] fifo_mem [0:FIFO_DEPTH-1];
    reg [1535:0] beat_staging_r;
    reg [1:0] beat_index_r;
    reg [PTR_W-1:0] wr_bin_r;
    wire [PTR_W-1:0] rd_bin_sync_wr;
    reg ddr_error_r;

    reg [PTR_W-1:0] rd_bin_r;
    wire [PTR_W-1:0] wr_bin_sync_rd;
    reg [2047:0] half_data_r;
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

    // Once beat0 reserves a free FIFO slot, later beats may complete the
    // same half-group even if the synchronized full flag changes.
    assign beat_ready = ddr_rst_n && !ddr_clear &&
        ((beat_index_r != 0) || !fifo_full) && !ddr_error_r;
    assign half_valid = core_rst_n && !core_clear && half_valid_r;
    assign half_data = half_data_r;
    // ddr_error_r is sticky in the independent MIG UI domain.  Never feed it
    // combinationally into core-domain status/control: synchronize it first.
    assign error = ddr_error_core | core_error_r;

    // ddr_error_r is already a registered, sticky source-domain level.  Use
    // the vendor CDC primitive so report_cdc can prove the structure instead
    // of classifying a hand-written ASYNC_REG chain as CDC-1 unknown logic.
    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(0)
    ) u_ddr_error_cdc (
        .src_clk(ddr_clk), .src_in(ddr_error_r),
        .dest_clk(core_clk), .dest_out(ddr_error_core)
    );

    // Use the vendor-recognized Gray CDC primitive.  Passing the binary
    // pointers is intentional: xpm_cdc_gray registers the Gray encoding in
    // the source domain, synchronizes it, and converts it back to binary in
    // the destination domain.  This prevents synthesis from folding away a
    // hand-written source Gray register and keeps report_cdc authoritative.
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
            if (beat_index_r != 2'd3)
                beat_staging_r[beat_index_r*512 +: 512] <= beat_data;
            else
                fifo_mem[wr_bin_r[ADDR_W-1:0]] <=
                    {beat_data, beat_staging_r};
        end
    end

    always @(posedge ddr_clk or negedge ddr_rst_n) begin
        if (!ddr_rst_n) begin
            beat_index_r <= 2'd0;
            wr_bin_r <= '0;
            ddr_beat_count <= 32'd0;
            ddr_half_count <= 32'd0;
            ddr_error_r <= 1'b0;
        end else if (ddr_clear) begin
            beat_index_r <= 2'd0;
            wr_bin_r <= '0;
            ddr_beat_count <= 32'd0;
            ddr_half_count <= 32'd0;
            ddr_error_r <= 1'b0;
        end else begin
            if (beat_fire) begin
                ddr_beat_count <= ddr_beat_count + 32'd1;
                if (beat_last != (beat_index_r == 2'd3))
                    ddr_error_r <= 1'b1;
                if (beat_index_r == 2'd3) begin
                    beat_index_r <= 2'd0;
                    wr_bin_r <= wr_bin_next;
                    ddr_half_count <= ddr_half_count + 32'd1;
                end else begin
                    beat_index_r <= beat_index_r + 1'b1;
                end
            end
            if (beat_fire && (beat_index_r == 2'd3) && fifo_full)
                ddr_error_r <= 1'b1;
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
            if (core_load) begin
                rd_bin_r <= rd_bin_r + 1'b1;
            end
            if (half_fire)
                core_half_count <= core_half_count + 32'd1;
            if (half_fire && !half_valid_r)
                core_error_r <= 1'b1;
        end
    end

    initial begin
        if (FIFO_DEPTH != 8)
            $error("hap_ddr512_halfgroup_async production FIFO_DEPTH must be 8");
    end

endmodule
