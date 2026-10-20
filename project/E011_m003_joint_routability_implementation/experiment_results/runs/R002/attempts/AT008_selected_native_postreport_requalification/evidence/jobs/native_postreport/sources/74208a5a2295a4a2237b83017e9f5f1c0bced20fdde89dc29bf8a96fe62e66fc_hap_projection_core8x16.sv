`timescale 1ns / 1ps

module hap_projection_core8x16 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  activation_valid,
    output wire                  activation_ready,
    input  wire [8*32*24-1:0]    activation_s24,
    input  wire [6:0]            activation_group,
    output wire                  activation_cached,
    input  wire                  activation_release,
    input  wire                  project_start,
    output wire                  weight_ready,
    input  wire                  weight_valid,
    input  wire [6:0]            weight_group,
    input  wire [16*32*8-1:0]    weight_s8,
    input  wire [16*16-1:0]      weight_meta16,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [8*16*24-1:0]    out_s24,
    output wire [31:0]           accepted_group_count,
    output wire [31:0]           output_tile_count,
    output wire [31:0]           saturation_count,
    output wire                  error
);

    localparam [1:0] ST_FILL = 2'd0;
    localparam [1:0] ST_READY = 2'd1;
    localparam [1:0] ST_PROJECT = 2'd2;
    localparam [1:0] ST_ERROR = 2'd3;
    reg [1:0] state_r;
    reg [6:0] next_weight_group_r;
    reg control_error_r;
    reg tile_input_complete_r;

    wire frontend_rd_req_ready;
    wire frontend_in_ready;
    wire frontend_rd_rsp_valid;
    wire frontend_rd_rsp_bank;
    wire [6:0] frontend_rd_rsp_group;
    wire [8*32*8-1:0] frontend_rd_rsp_u8;
    wire [8*24-1:0] frontend_rd_rsp_meta;
    wire [1:0] frontend_bank_ready;
    wire [31:0] frontend_input_count_unused;
    wire [31:0] frontend_write_count_unused;
    wire [31:0] frontend_read_count_unused;
    wire [31:0] frontend_release_count_unused;
    wire [31:0] frontend_hadamard_sat_unused;
    wire frontend_error;
    reg weight_buffer_valid_r;
    reg [6:0] weight_buffer_group_r;
    reg [16*32*8-1:0] weight_buffer_s8_r;
    reg [16*16-1:0] weight_buffer_meta16_r;
    reg group_stage_valid_r;
    // This is a real timing boundary, not just a behavioral convenience.
    // Without DONT_TOUCH Vivado can merge/rewire these payload registers back
    // into the activation BRAM outputs.  On the full VCU118 design that forms
    // BRAM(SLR2)->lane(SLR1) paths containing the ScaleCode multiplier or DSP
    // pre-adder.  Keep the complete payload together so the first path ends at
    // an FF and the second starts at an FF.  The valid/ready protocol and II=2
    // are unchanged because this stage already existed architecturally.
    (* DONT_TOUCH = "yes" *) reg [6:0] group_stage_group_r;
    (* DONT_TOUCH = "yes" *) reg [8*24-1:0] group_stage_act_meta_r;
    // Balance both sides of this physical boundary.  One row copy drives 16
    // distant lanes; one copy per lane makes each BRAM bit drive 16 protected
    // capture FFs and congests the SLL columns.  Four regional copies per row
    // give fanout four on both BRAM->capture and capture->lane paths.  All
    // copies are sampled on the existing capture edge, so protocol, latency,
    // arithmetic and II=2 remain unchanged.
    (* DONT_TOUCH = "yes" *) reg [8*4*32*8-1:0]
        group_stage_act_u8_region_r;
    // The activation zero point is consumed by every multiplier in a row.
    // Per-lane capture made each cache BRAM output bit drive sixteen protected
    // FFs across an SLR boundary; that BRAM-to-FF route became the full
    // Attention critical path.  Capture four regional copies per row instead,
    // then let each copy feed four adjacent physical lanes.  Both sides now
    // have fanout four, while all copies still sample the same metadata on the
    // existing edge, so arithmetic, latency and array II=2 are unchanged.
    (* DONT_TOUCH = "yes" *) reg [8*4*8-1:0]
        group_stage_act_zero_point_region_r;
    wire [8*16*8-1:0] group_stage_act_zero_point_lane;
    (* DONT_TOUCH = "yes" *) reg [16*32*8-1:0] group_stage_weight_s8_r;
    (* DONT_TOUCH = "yes" *) reg [16*16-1:0] group_stage_weight_meta16_r;
    wire array_in_ready;
    wire array_out_valid;
    wire [16*16*24-1:0] array_out_s24;
    wire [31:0] array_accum_count_unused;
    wire array_error;
    // Decouple the BRAM-backed activation cache from the 128 lane DSP
    // inputs.  The array accepts one group every two cycles, so this single
    // elastic stage preserves II=2 while removing BRAM-to-DSP SLR paths.
    wire capture_group = frontend_rd_rsp_valid && weight_buffer_valid_r &&
        !group_stage_valid_r;
    // Run 0138 showed that capture_group was promoted to a data BUFG after
    // driving exactly 12,999 payload FFs (8192 regional activation, 4096
    // weight, 192 activation metadata, 256 zero point, 256 weight metadata
    // and 7 group-tag bits).  Preserve the protocol event itself for cache
    // response retirement and state updates, but fan it through protected
    // identity LUTs before it reaches payload CEs.  The LUTs are combinational
    // boundaries, so every bank still samples on the original capture edge:
    // no latency, tag ordering or array II is changed.
    localparam integer CAPTURE_ACT_BASE = 0;
    localparam integer CAPTURE_WEIGHT_BASE = 32;
    localparam integer CAPTURE_ACT_META = 48;
    localparam integer CAPTURE_ACT_ZERO = 49;
    localparam integer CAPTURE_WEIGHT_META = 50;
    localparam integer CAPTURE_GROUP_TAG = 51;
    wire [51:0] capture_group_local;
    genvar capture_control;
    generate
        for (capture_control = 0; capture_control < 52;
             capture_control = capture_control + 1) begin : g_capture_control
            (* DONT_TOUCH = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(capture_group),
                .O(capture_group_local[capture_control])
            );
        end
    endgenerate
    wire issue_group = group_stage_valid_r && array_in_ready;
    wire request_group = weight_valid && weight_ready;
    // While the one-entry buffer is architecturally empty its payload is
    // don't-care, so it may track the input even before valid is asserted.
    // AXI-style valid semantics guarantee that the payload is stable on the
    // request_group edge; once committed, weight_buffer_valid_r freezes it.
    // request_group remains the sole acceptance event.  This local enable
    // removes both group-equality and top-level weight_valid routing from all
    // 4352 payload-register CEs without changing state, latency or counters.
    wire preload_weight_payload = !weight_buffer_valid_r;
    wire output_fire = out_valid && out_ready;
    wire frontend_release_ready;

    assign activation_ready = (state_r == ST_FILL) && frontend_in_ready;
    assign activation_cached = (state_r == ST_READY) ||
        (state_r == ST_PROJECT);
    assign weight_ready = (state_r == ST_PROJECT) &&
        !tile_input_complete_r && !weight_buffer_valid_r &&
        frontend_rd_req_ready &&
        (weight_group == next_weight_group_r);
    assign out_valid = array_out_valid;
    assign out_s24 = array_out_s24[8*16*24-1:0];
    assign error = control_error_r | frontend_error | array_error;

    hap_attention_frontend_8row u_frontend (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(activation_valid && (state_r == ST_FILL)),
        .in_ready(frontend_in_ready), .in_bank(1'b0), .in_group(activation_group),
        .in_s24(activation_s24),
        .rd_req_valid(request_group), .rd_req_ready(frontend_rd_req_ready),
        .rd_req_bank(1'b0), .rd_req_group(next_weight_group_r),
        .rd_rsp_valid(frontend_rd_rsp_valid),
        .rd_rsp_ready(capture_group), .rd_rsp_bank(frontend_rd_rsp_bank),
        .rd_rsp_group(frontend_rd_rsp_group),
        .rd_rsp_u8(frontend_rd_rsp_u8), .rd_rsp_meta(frontend_rd_rsp_meta),
        .release_valid(activation_release && (state_r == ST_READY)),
        .release_ready(frontend_release_ready), .release_bank(1'b0),
        .bank_ready(frontend_bank_ready),
        .input_group_count(frontend_input_count_unused),
        .cache_write_count(frontend_write_count_unused),
        .cache_read_count(frontend_read_count_unused),
        .cache_release_count(frontend_release_count_unused),
        .hadamard_saturation_count(frontend_hadamard_sat_unused),
        .error(frontend_error)
    );

    wire [16*8-1:0] row_scale_code;
    wire [16*6-1:0] row_scale_shift;
    wire [16*8-1:0] col_scale_code;
    wire [16*6-1:0] col_scale_shift;
    genvar row;
    genvar zero_row;
    genvar zero_col;
    generate
        for (row = 0; row < 16; row = row + 1) begin : g_row_meta
            if (row < 8) begin
                assign row_scale_code[row*8 +: 8] =
                    group_stage_act_meta_r[row*24+8 +: 8];
                assign row_scale_shift[row*6 +: 6] =
                    group_stage_act_meta_r[row*24+16 +: 6];
            end else begin
                assign row_scale_code[row*8 +: 8] = 8'd0;
                assign row_scale_shift[row*6 +: 6] = 6'd0;
            end
        end
        genvar col;
        for (col = 0; col < 16; col = col + 1) begin : g_col_meta
            assign col_scale_code[col*8 +: 8] =
                group_stage_weight_meta16_r[col*16 +: 8];
            assign col_scale_shift[col*6 +: 6] =
                group_stage_weight_meta16_r[col*16+8 +: 6];
        end
        for (zero_row = 0; zero_row < 8;
             zero_row = zero_row + 1) begin : g_zero_point_row
            for (zero_col = 0; zero_col < 16;
                 zero_col = zero_col + 1) begin : g_zero_point_col
                assign group_stage_act_zero_point_lane[
                    (zero_row*16+zero_col)*8 +: 8] =
                    group_stage_act_zero_point_region_r[
                    (zero_row*4+(zero_col/4))*8 +: 8];
            end
        end
    endgenerate

    // Three complete column shards keep lane DSPs, lane FIFOs and their
    // accumulator lanes together on the target SLR.  The wrapper retains the
    // fixed external shape and one lockstep tag/ready contract.
    hap_a8w8_array_16x16_s42_col3 u_array (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(issue_group), .in_ready(array_in_ready),
        .in_first_group(group_stage_group_r == 0),
        .in_last_group(group_stage_group_r == 7'd127),
        .in_wave(1'b0),
        .region_act_u8(group_stage_act_u8_region_r),
        .lane_act_zero_point(group_stage_act_zero_point_lane),
        .row_act_scale_code(row_scale_code),
        .row_act_scale_shift(row_scale_shift),
        .col_wgt_s8(group_stage_weight_s8_r),
        .col_wgt_scale_code(col_scale_code),
        .col_wgt_scale_shift(col_scale_shift),
        .out_valid(array_out_valid), .out_ready(out_ready), .out_wave(),
        .out_s24(array_out_s24),
        .accepted_group_count(accepted_group_count),
        .accumulated_group_count(array_accum_count_unused),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(array_error)
    );

    integer activation_copy_row;
    integer activation_copy_region;
    always @(posedge clk) begin
        if (preload_weight_payload) begin
            weight_buffer_s8_r <= weight_s8;
            weight_buffer_meta16_r <= weight_meta16;
            weight_buffer_group_r <= weight_group;
        end
        if (capture_group_local[CAPTURE_GROUP_TAG])
            group_stage_group_r <= weight_buffer_group_r;
        if (capture_group_local[CAPTURE_ACT_META])
            group_stage_act_meta_r <= frontend_rd_rsp_meta;
        for (activation_copy_row = 0; activation_copy_row < 8;
             activation_copy_row = activation_copy_row + 1)
            for (activation_copy_region = 0; activation_copy_region < 4;
                 activation_copy_region = activation_copy_region + 1)
                if (capture_group_local[CAPTURE_ACT_BASE +
                    activation_copy_row*4 + activation_copy_region])
                    group_stage_act_u8_region_r[
                        (activation_copy_row*4+activation_copy_region)*32*8
                        +: 32*8] <= frontend_rd_rsp_u8[
                        activation_copy_row*32*8 +: 32*8];
        if (capture_group_local[CAPTURE_ACT_ZERO]) begin
            for (activation_copy_row = 0; activation_copy_row < 8;
                 activation_copy_row = activation_copy_row + 1)
                for (activation_copy_region = 0; activation_copy_region < 4;
                     activation_copy_region = activation_copy_region + 1)
                    group_stage_act_zero_point_region_r[
                        (activation_copy_row*4+activation_copy_region)*8
                        +: 8] <= frontend_rd_rsp_meta[
                        activation_copy_row*24 +: 8];
        end
        for (activation_copy_region = 0; activation_copy_region < 16;
             activation_copy_region = activation_copy_region + 1)
            if (capture_group_local[CAPTURE_WEIGHT_BASE +
                activation_copy_region])
                group_stage_weight_s8_r[
                    activation_copy_region*32*8 +: 32*8] <=
                    weight_buffer_s8_r[
                        activation_copy_region*32*8 +: 32*8];
        if (capture_group_local[CAPTURE_WEIGHT_META])
            group_stage_weight_meta16_r <= weight_buffer_meta16_r;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_FILL;
            next_weight_group_r <= 7'd0;
            weight_buffer_valid_r <= 1'b0;
            group_stage_valid_r <= 1'b0;
            tile_input_complete_r <= 1'b0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            state_r <= ST_FILL;
            next_weight_group_r <= 7'd0;
            weight_buffer_valid_r <= 1'b0;
            group_stage_valid_r <= 1'b0;
            tile_input_complete_r <= 1'b0;
            control_error_r <= 1'b0;
        end else begin
            if ((state_r == ST_FILL) && frontend_bank_ready[0])
                state_r <= ST_READY;
            if ((state_r == ST_READY) && project_start)
                state_r <= ST_PROJECT;
            if (request_group)
                weight_buffer_valid_r <= 1'b1;
            if (capture_group) begin
                weight_buffer_valid_r <= 1'b0;
                group_stage_valid_r <= 1'b1;
                if (weight_buffer_group_r == 7'd127)
                    next_weight_group_r <= 7'd0;
                else
                    next_weight_group_r <= weight_buffer_group_r + 1'b1;
                if (frontend_rd_rsp_group != weight_buffer_group_r ||
                    frontend_rd_rsp_bank != 0)
                    control_error_r <= 1'b1;
                if (weight_buffer_group_r == 7'd127)
                    tile_input_complete_r <= 1'b1;
            end
            if (issue_group)
                group_stage_valid_r <= 1'b0;
            if (output_fire) begin
                tile_input_complete_r <= 1'b0;
                state_r <= ST_READY;
            end
            if ((state_r == ST_READY) && activation_release) begin
                if (frontend_release_ready)
                    state_r <= ST_FILL;
                else
                    control_error_r <= 1'b1;
            end
            if (frontend_error || array_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

endmodule
