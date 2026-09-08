`timescale 1ns / 1ps

// Narrow physical wrapper for full-size RAM inference/timing probes.  The
// 128-lane datapath remains live through a pseudo-random guard generator and
// an output fold, while the package IO count stays legal for VCU118 OOC.
module hap_mlp_down_group_major_accum_s45_ooc_wrapper #(
    parameter integer LANES = 128,
    parameter integer TILES = 256,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire         start,
    output wire         busy,
    output wire [31:0]  result_fold,
    output wire [31:0]  input_tile_count,
    output wire [31:0]  output_tile_count,
    output wire         error
);

    reg active_r;
    reg [8:0] group_r;
    reg [TILE_W-1:0] tile_r;
    reg [31:0] lfsr_r;
    reg [31:0] fold_r;
    wire accum_in_ready;
    wire accum_out_valid;
    wire [TILE_W-1:0] accum_out_tile;
    wire signed [LANES*24-1:0] accum_out_projection;
    wire [31:0] accum_input_group_count;
    wire [31:0] accum_saturation_count;
    wire accum_error;
    wire accum_in_fire = active_r && accum_in_ready;
    wire accum_out_fire = accum_out_valid;

    wire signed [35:0] base_guard =
        $signed({lfsr_r[31:0], group_r[3:0]});
    wire signed [LANES*36-1:0] generated_guard;
    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin : gen_guard
            assign generated_guard[lane*36 +: 36] =
                base_guard ^ $signed(lane*36'h10001);
        end
    endgenerate

    assign busy = active_r;
    assign result_fold = fold_r;
    assign error = accum_error;

    hap_mlp_down_group_major_accum_s45 #(
        .LANES(LANES), .TILES(TILES), .GROUPS(448), .TILE_W(TILE_W)
    ) u_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(active_r), .in_ready(accum_in_ready),
        .in_first_group(group_r == 0),
        .in_last_group(group_r == 9'd447),
        .in_tile_index(tile_r), .in_guard_s36(generated_guard),
        .out_valid(accum_out_valid), .out_ready(1'b1),
        .out_tile_index(accum_out_tile),
        .out_projection_s24(accum_out_projection),
        .input_tile_count(input_tile_count),
        .input_group_count(accum_input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(accum_saturation_count),
        .error(accum_error)
    );

    function automatic [31:0] fold_projection;
        input [LANES*24-1:0] payload;
        integer word_index;
        reg [31:0] folded;
        begin
            folded = 32'd0;
            for (word_index = 0; word_index < (LANES*24)/32;
                 word_index = word_index + 1)
                folded = folded ^ payload[word_index*32 +: 32];
            fold_projection = folded;
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            active_r <= 1'b0;
            group_r <= '0;
            tile_r <= '0;
            lfsr_r <= 32'h1ace_b00c;
            fold_r <= '0;
        end else begin
            if (start && !active_r) begin
                active_r <= 1'b1;
                group_r <= '0;
                tile_r <= '0;
                lfsr_r <= 32'h1ace_b00c;
                fold_r <= '0;
            end
            if (accum_in_fire) begin
                lfsr_r <= {lfsr_r[30:0],
                    lfsr_r[31] ^ lfsr_r[21] ^ lfsr_r[1] ^ lfsr_r[0]};
                if (tile_r == TILES-1) begin
                    tile_r <= '0;
                    if (group_r == 9'd447)
                        active_r <= 1'b0;
                    else
                        group_r <= group_r + 1'b1;
                end else begin
                    tile_r <= tile_r + 1'b1;
                end
            end
            if (accum_out_fire) begin
                fold_r <= fold_r ^ {{(32-TILE_W){1'b0}}, accum_out_tile} ^
                    fold_projection(accum_out_projection);
            end
        end
    end

endmodule

// Exception-free timing harness for formal V5 OOC signoff.  All control and
// payload boundaries are same-clock resetless registers; the only top port is
// the real 150 MHz clock.  This avoids abstract reset/input part pins and does
// not require false paths, datapath-only constraints or relaxed I/O budgets.
module hap_mlp_down_group_major_accum_s45_registered_ooc_harness #(
    parameter integer LANES = 96,
    parameter integer TILES = 342,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
) (
    input wire clk
);
    localparam integer SRC_W = 6 + TILE_W + LANES*36;
    // in_ready/out_valid/error + tile + projection + exactly four counters.
    // The previous 5*32 bookkeeping typo made the registered OOC harness
    // expect 32 sink FFs that do not exist; the DUT port map was always four.
    localparam integer SINK_W = 3 + TILE_W + LANES*24 + 4*32;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_FIRST = 3;
    localparam integer S_LAST = 4;
    localparam integer S_OUT_READY = 5;
    localparam integer S_TILE = 6;
    localparam integer S_GUARD = S_TILE + TILE_W;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready, out_valid, error;
    wire [TILE_W-1:0] out_tile;
    wire signed [LANES*24-1:0] out_projection;
    wire [31:0] input_tiles, input_groups, output_tiles, saturation;
    wire [SINK_W-1:0] dut_outputs = {
        error, saturation, output_tiles, input_groups, input_tiles,
        out_projection, out_tile, out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_down_group_major_accum_s45 #(
        .LANES(LANES), .TILES(TILES), .GROUPS(448), .TILE_W(TILE_W)
    ) u_accum (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .in_first_group(src_r[S_FIRST]), .in_last_group(src_r[S_LAST]),
        .in_tile_index(src_r[S_TILE +: TILE_W]),
        .in_guard_s36(src_r[S_GUARD +: LANES*36]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .out_tile_index(out_tile), .out_projection_s24(out_projection),
        .input_tile_count(input_tiles), .input_group_count(input_groups),
        .output_tile_count(output_tiles), .saturation_count(saturation),
        .error(error)
    );

    initial begin
        if (S_GUARD + LANES*36 != SRC_W ||
            $bits(dut_outputs) != SINK_W)
            $error("down accumulator registered OOC vector layout mismatch");
    end
endmodule
