`timescale 1ns / 1ps

// 8x4096 S24 input buffer.  DMA writes row-major 256-bit beats; the loader
// transposes 24 beats/group into the compute top's 8-row x group32 record.
module hap_tensor24_input_buffer (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 wr_valid,
    output wire                 wr_ready,
    input  wire [11:0]          wr_addr,
    input  wire [255:0]         wr_data,
    input  wire                 load_start,
    output wire                 activation_valid,
    input  wire                 activation_ready,
    output wire [6:0]           activation_group,
    output wire [6143:0]        activation_s24,
    output wire                 busy,
    output reg                  error
);
    (* ram_style = "block" *) reg [255:0] input_mem [0:3071];
    reg active_r;
    reg output_valid_r;
    reg [6:0] group_r;
    reg [4:0] issue_index_r;
    reg [4:0] capture_index_r;
    reg read_pending_r;
    reg [255:0] read_data_r;
    // Keep a second explicit register after the inferred BRAM output.  The
    // full VCU118 design places the input BRAM bank in SLR1 and the 6144-bit
    // activation record in SLR2; without this stage Vivado routed a cascaded
    // BRAM output directly across the SLR boundary.  The loader is not the
    // II=2 projection datapath, so the one-cycle group-fill latency does not
    // reduce the array throughput.
    reg read_stage_valid_r;
    reg [255:0] read_stage_data_r;
    reg [6143:0] activation_r;
    wire output_fire = output_valid_r && activation_ready;
    // Same-edge capture qualification.  Each fixed 256-bit slot owns its
    // payload flops; only its scalar decode is protected from re-merging.
    wire capture_write_qual = !clear && active_r && !output_valid_r &&
        read_stage_valid_r;
    wire [23:0] capture_slot_ce;
    genvar capture_slot;
    generate
        for (capture_slot=0; capture_slot<24;
             capture_slot=capture_slot+1) begin : g_capture_slot
            // I5 is the qualification and I4:I0 are the slot index.  The
            // single set bit implements qual && (index == capture_slot).
            (* DONT_TOUCH = "yes" *)
            LUT6 #(.INIT(64'h0000000100000000 << capture_slot))
                u_capture_decode (
                    .I0(capture_index_r[0]), .I1(capture_index_r[1]),
                    .I2(capture_index_r[2]), .I3(capture_index_r[3]),
                    .I4(capture_index_r[4]), .I5(capture_write_qual),
                    .O(capture_slot_ce[capture_slot])
                );
            // Preserve the original asynchronous payload reset and clear
            // hold behavior; no new control or data pipeline stage.
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)
                    activation_r[capture_slot*256 +: 256] <= '0;
                else if (capture_slot_ce[capture_slot])
                    activation_r[capture_slot*256 +: 256] <= read_stage_data_r;
            end
        end
    endgenerate
    wire [2:0] issue_row = issue_index_r / 3;
    wire [1:0] issue_beat = issue_index_r % 3;
    wire [11:0] issue_addr = issue_row*12'd384 +
        group_r*12'd3 + issue_beat;

    assign wr_ready = rst_n && !clear && !active_r && (wr_addr < 3072);
    assign activation_valid = output_valid_r;
    assign activation_group = group_r;
    assign activation_s24 = activation_r;
    assign busy = active_r || output_valid_r;

    always @(posedge clk) begin
        if (wr_valid && wr_ready)
            input_mem[wr_addr] <= wr_data;
        if (active_r && !output_valid_r && (issue_index_r < 24))
            read_data_r <= input_mem[issue_addr];
        if (read_pending_r)
            read_stage_data_r <= read_data_r;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            output_valid_r <= 1'b0;
            group_r <= 7'd0;
            issue_index_r <= 5'd0;
            capture_index_r <= 5'd0;
            read_pending_r <= 1'b0;
            read_stage_valid_r <= 1'b0;
            error <= 1'b0;
        end else if (clear) begin
            active_r <= 1'b0;
            output_valid_r <= 1'b0;
            group_r <= 7'd0;
            issue_index_r <= 5'd0;
            capture_index_r <= 5'd0;
            read_pending_r <= 1'b0;
            read_stage_valid_r <= 1'b0;
            error <= 1'b0;
        end else begin
            if (load_start) begin
                if (busy) begin
                    error <= 1'b1;
                end else begin
                    active_r <= 1'b1;
                    group_r <= 7'd0;
                    issue_index_r <= 5'd0;
                    capture_index_r <= 5'd0;
                    read_pending_r <= 1'b0;
                    read_stage_valid_r <= 1'b0;
                end
            end
            if (active_r && !output_valid_r) begin
                read_stage_valid_r <= read_pending_r;
                if (read_stage_valid_r) begin
                    capture_index_r <= capture_index_r + 1'b1;
                    if (capture_index_r == 23) begin
                        // Drain the final BRAM response explicitly.  Leaving
                        // this set is harmless while output_valid_r stalls the
                        // loader, but it leaves a stale pending token across
                        // the group boundary and obscures the intended
                        // two-stage read-pipeline state.
                        read_pending_r <= 1'b0;
                        read_stage_valid_r <= 1'b0;
                        output_valid_r <= 1'b1;
                    end
                end
                if (issue_index_r < 24) begin
                    issue_index_r <= issue_index_r + 1'b1;
                    read_pending_r <= 1'b1;
                end
            end
            if (output_fire) begin
                output_valid_r <= 1'b0;
                if (group_r == 127) begin
                    active_r <= 1'b0;
                end else begin
                    group_r <= group_r + 1'b1;
                    issue_index_r <= 5'd0;
                    capture_index_r <= 5'd0;
                    read_pending_r <= 1'b0;
                    read_stage_valid_r <= 1'b0;
                end
            end
            if (wr_valid && (wr_addr >= 3072))
                error <= 1'b1;
        end
    end
endmodule

// Convert 256 compute tiles (8 rows x 16 S24) into the row-major packed S24
// image required by board_abi.md.  One memory write per cycle preserves BRAM
// inference; the compute output is backpressured for 24 cycles per tile pair.
module hap_tensor24_output_buffer (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire [7:0]           in_tile,
    input  wire [3071:0]        in_s24,
    output reg                  image_ready,
    input  wire                 image_release,
    input  wire                 rd_valid,
    output wire                 rd_ready,
    input  wire [11:0]          rd_addr,
    output wire                 rsp_valid,
    input  wire                 rsp_ready,
    output wire [255:0]         rsp_data,
    output reg                  error
);
    (* ram_style = "block" *) reg [255:0] output_mem [0:3071];
    reg have_even_r;
    reg [7:0] expected_tile_r;
    // Keep the two input tiles in beat-local banks instead of constructing a
    // 6144-bit pair register.  In the original implementation, the common
    // write enables for even_tile_r and pair_r drove 3042 and 5841 placed
    // loads, respectively, and Vivado promoted both data controls onto BUFGs.
    // Each local enable below drives at most 256 data FFs; the unbuffered
    // capture predicates drive only the 16 LUT1 replicas.  The storage is
    // also reduced from three tiles (9216 FFs) to two tiles (6144 FFs).
    reg [255:0] even_lo_r [0:7];
    reg [127:0] even_hi_r [0:7];
    reg [127:0] odd_lo_r  [0:7];
    reg [255:0] odd_hi_r  [0:7];
    reg write_active_r;
    reg [4:0] write_index_r;
    reg rsp_valid_r;
    reg [255:0] rsp_data_r;
    wire in_fire = in_valid && in_ready;
    wire [2:0] write_row = write_index_r / 3;
    wire [1:0] write_beat = write_index_r % 3;
    wire [6:0] write_group = (expected_tile_r - 1'b1) >> 1;
    wire [11:0] write_addr = write_row*12'd384 +
        write_group*12'd3 + write_beat;
    wire [255:0] write_data = (write_beat == 0) ?
        even_lo_r[write_row] :
        ((write_beat == 1) ?
            {odd_lo_r[write_row], even_hi_r[write_row]} :
            odd_hi_r[write_row]);
    wire rd_fire = rd_valid && rd_ready;

    wire capture_even = in_fire && (in_tile == expected_tile_r) &&
        !in_tile[0];
    wire capture_odd = in_fire && (in_tile == expected_tile_r) &&
        in_tile[0] && have_even_r;
    wire [15:0] capture_even_local;
    wire [15:0] capture_odd_local;

    // Explicit identity LUTs are intentional physical fanout boundaries.
    // DONT_TOUCH prevents synthesis/opt_design from merging the identical
    // replicas back into either original multi-thousand-load control net.
    genvar even_ctrl, odd_ctrl;
    generate
        for (even_ctrl=0; even_ctrl<16; even_ctrl=even_ctrl+1) begin : g_even_capture_buffer
            (* DONT_TOUCH = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(capture_even),
                .O(capture_even_local[even_ctrl])
            );
        end
        for (odd_ctrl=0; odd_ctrl<16; odd_ctrl=odd_ctrl+1) begin : g_odd_capture_buffer
            (* DONT_TOUCH = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(capture_odd),
                .O(capture_odd_local[odd_ctrl])
            );
        end
    endgenerate

    assign in_ready = rst_n && !clear && !image_ready && !write_active_r;
    // Single outstanding BRAM read.  A one-cycle bubble after response
    // retirement avoids accepting the same address twice when the requester
    // advances its address from the response handshake.
    assign rd_ready = rst_n && !clear && image_ready &&
        !rsp_valid_r && (rd_addr < 3072);
    assign rsp_valid = rsp_valid_r;
    assign rsp_data = rsp_data_r;

    always @(posedge clk) begin
        if (write_active_r)
            output_mem[write_addr] <= write_data;
        if (rd_fire)
            rsp_data_r <= output_mem[rd_addr];
    end

    integer row;
    // Wide tile data is banked solely to bound each local capture-enable
    // fanout.  No pipeline stage is added: both odd banks are visible to the
    // first BRAM write on the cycle immediately after the odd-tile handshake.
    always @(posedge clk) begin
        for (row=0; row<8; row=row+1) begin
            if (capture_even_local[2*row])
                even_lo_r[row] <= in_s24[row*384 +: 256];
            if (capture_even_local[2*row+1])
                even_hi_r[row] <= in_s24[row*384+256 +: 128];
            if (capture_odd_local[2*row])
                odd_lo_r[row] <= in_s24[row*384 +: 128];
            if (capture_odd_local[2*row+1])
                odd_hi_r[row] <= in_s24[row*384+128 +: 256];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            have_even_r <= 1'b0;
            expected_tile_r <= 8'd0;
            write_active_r <= 1'b0;
            write_index_r <= 5'd0;
            image_ready <= 1'b0;
            rsp_valid_r <= 1'b0;
            error <= 1'b0;
        end else if (clear) begin
            have_even_r <= 1'b0;
            expected_tile_r <= 8'd0;
            write_active_r <= 1'b0;
            write_index_r <= 5'd0;
            image_ready <= 1'b0;
            rsp_valid_r <= 1'b0;
            error <= 1'b0;
        end else begin
            if (image_release) begin
                image_ready <= 1'b0;
                expected_tile_r <= 8'd0;
                have_even_r <= 1'b0;
            end
            if (rsp_valid_r && rsp_ready)
                rsp_valid_r <= 1'b0;
            if (rd_fire)
                rsp_valid_r <= 1'b1;
            if (in_fire) begin
                if (in_tile != expected_tile_r) begin
                    error <= 1'b1;
                end else if (!in_tile[0]) begin
                    have_even_r <= 1'b1;
                    expected_tile_r <= expected_tile_r + 1'b1;
                end else if (!have_even_r) begin
                    error <= 1'b1;
                end else begin
                    have_even_r <= 1'b0;
                    write_active_r <= 1'b1;
                    write_index_r <= 5'd0;
                    expected_tile_r <= expected_tile_r + 1'b1;
                end
            end
            if (write_active_r) begin
                if (write_index_r == 23) begin
                    write_active_r <= 1'b0;
                    if (expected_tile_r == 0)
                        image_ready <= 1'b1;
                end else begin
                    write_index_r <= write_index_r + 1'b1;
                end
            end
            if (rd_valid && (rd_addr >= 3072))
                error <= 1'b1;
        end
    end
endmodule
