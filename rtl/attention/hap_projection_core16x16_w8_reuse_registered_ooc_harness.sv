`timescale 1ns / 1ps

// Exception-free registered shell for 150 MHz out-of-context timing.  Only
// clk is a top-level port; every functional input and output crosses a real
// proxy FF so OOC timing does not depend on abstract input/output delays.
module hap_projection_core16x16_w8_reuse_registered_ooc_harness (
    input wire clk
);
    localparam integer SRC_W = 10600;
    localparam integer SINK_W = 3327;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_ACT_VALID = 2;
    localparam integer S_ACT_WAVE = 3;
    localparam integer S_ACT = 4;
    localparam integer S_ACT_GROUP = S_ACT + 6144;
    localparam integer S_ACT_RELEASE = S_ACT_GROUP + 7;
    localparam integer S_PROJECT_START = S_ACT_RELEASE + 1;
    localparam integer S_REQUEST = S_PROJECT_START + 1;
    localparam integer S_COHORT = S_REQUEST + 32;
    localparam integer S_LAYER = S_COHORT + 16;
    localparam integer S_OP = S_LAYER + 6;
    localparam integer S_TILE = S_OP + 3;
    localparam integer S_QUERY_START = S_TILE + 10;
    localparam integer S_VALID_KEYS = S_QUERY_START + 7;
    localparam integer S_WEIGHT_VALID = S_VALID_KEYS + 8;
    localparam integer S_WEIGHT_GROUP = S_WEIGHT_VALID + 1;
    localparam integer S_WEIGHT = S_WEIGHT_GROUP + 7;
    localparam integer S_WEIGHT_META = S_WEIGHT + 4096;
    localparam integer S_OUT_READY = S_WEIGHT_META + 256;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire activation_ready;
    wire activation_cached;
    wire activation_release_ready;
    wire activation_released;
    wire project_ready;
    wire project_done;
    wire weight_ready;
    wire out_valid;
    wire out_wave;
    wire [3071:0] out_s24;
    wire [31:0] out_request_id;
    wire [15:0] out_cohort_id;
    wire [5:0] out_layer_id;
    wire [2:0] out_op_id;
    wire [9:0] out_tile_id;
    wire [6:0] out_query_start;
    wire [7:0] out_valid_key_count;
    wire [31:0] accepted_weight_group_count;
    wire [31:0] consumed_wave_group_count;
    wire [31:0] released_weight_group_count;
    wire [31:0] output_wave_tile_count;
    wire [31:0] saturation_count;
    wire [1:0] weight_fifo_high_watermark;
    wire busy;
    wire error;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_projection_core16x16_w8_reuse u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .activation_valid(src_r[S_ACT_VALID]),
        .activation_ready(activation_ready),
        .activation_wave(src_r[S_ACT_WAVE]),
        .activation_s24(src_r[S_ACT +: 6144]),
        .activation_group(src_r[S_ACT_GROUP +: 7]),
        .activation_cached(activation_cached),
        .activation_release(src_r[S_ACT_RELEASE]),
        .activation_release_ready(activation_release_ready),
        .activation_released(activation_released),
        .project_start(src_r[S_PROJECT_START]),
        .project_ready(project_ready), .project_done(project_done),
        .project_request_id(src_r[S_REQUEST +: 32]),
        .project_cohort_id(src_r[S_COHORT +: 16]),
        .project_layer_id(src_r[S_LAYER +: 6]),
        .project_op_id(src_r[S_OP +: 3]),
        .project_tile_id(src_r[S_TILE +: 10]),
        .project_query_start(src_r[S_QUERY_START +: 7]),
        .project_valid_key_count(src_r[S_VALID_KEYS +: 8]),
        .weight_ready(weight_ready),
        .weight_valid(src_r[S_WEIGHT_VALID]),
        .weight_group(src_r[S_WEIGHT_GROUP +: 7]),
        .weight_s8(src_r[S_WEIGHT +: 4096]),
        .weight_meta16(src_r[S_WEIGHT_META +: 256]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .out_wave(out_wave), .out_s24(out_s24),
        .out_request_id(out_request_id), .out_cohort_id(out_cohort_id),
        .out_layer_id(out_layer_id), .out_op_id(out_op_id),
        .out_tile_id(out_tile_id), .out_query_start(out_query_start),
        .out_valid_key_count(out_valid_key_count),
        .accepted_weight_group_count(accepted_weight_group_count),
        .consumed_wave_group_count(consumed_wave_group_count),
        .released_weight_group_count(released_weight_group_count),
        .output_wave_tile_count(output_wave_tile_count),
        .saturation_count(saturation_count),
        .weight_fifo_high_watermark(weight_fifo_high_watermark),
        .busy(busy), .error(error)
    );

    wire [SINK_W-1:0] dut_outputs = {
        error, busy, weight_fifo_high_watermark, saturation_count,
        output_wave_tile_count, released_weight_group_count,
        consumed_wave_group_count, accepted_weight_group_count,
        out_valid_key_count, out_query_start, out_tile_id, out_op_id,
        out_layer_id, out_cohort_id, out_request_id, out_s24, out_wave,
        out_valid, weight_ready, project_done, project_ready,
        activation_released, activation_release_ready, activation_cached,
        activation_ready
    };

    always @(posedge clk)
        sink_r <= dut_outputs;

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("projection reuse registered OOC vector layout mismatch");
    end

endmodule

