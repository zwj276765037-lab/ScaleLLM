`timescale 1ns / 1ps

// Sixteen independent incremental request slots, with external persistent KV.
// Per-row RoPE entries must be loaded for that row's absolute position.
// One physical projection array remains shared across both eight-row waves.
// Decode16 Attention compute top:
// post-RMSNorm S24 -> H+A8 -> Q/K/V -> RoPE/KV12 -> Attention ->
// context H+A8 -> Wo S24. One projection array owns all Q/K/V/Wo work and
// each accepted W8 group serves wave0 and wave1 before release.
module hap_attention_decode16_top #(
    parameter integer USE_PROJECTION_STUB = 0
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  start,
    input  wire [31:0]           format_id,
    input  wire [31:0]           command_id,
    input  wire [15:0]           batch_id,
    input  wire [5:0]            layer_id,
    input  wire [15:0]           active_mask,
    input  wire [127:0]          row_positions,
    input  wire [511:0]          row_epochs,
    output wire [31:0]           done_command_id,
    output wire [5:0]            done_layer,
    output wire [15:0]           done_active_mask,
    output wire [511:0]          done_epochs,
    output wire                  busy,
    output reg                   done,
    output wire                  error,

    input  wire                  rope_wr_valid,
    output wire                  rope_wr_ready,
    input  wire [9:0]            rope_wr_addr,
    input  wire signed [17:0]    rope_wr_cos_s18,
    input  wire signed [17:0]    rope_wr_sin_s18,

    output wire                  kv_append_valid,
    input  wire                  kv_append_ready,
    output wire [31:0]           kv_append_command,
    output wire [5:0]            kv_append_layer,
    output wire [3:0]            kv_append_slot,
    output wire [31:0]           kv_append_epoch,
    output wire [6:0]            kv_append_position,
    output wire                  kv_append_is_v,
    output wire [2:0]            kv_append_head,
    output wire [1:0]            kv_append_group,
    output wire [383:0]          kv_append_s12,
    output wire [15:0]           kv_append_meta,
    output wire                  kv_append_last,

    input  wire                  write_commit_valid,
    output wire                  write_commit_ready,
    input  wire [31:0]           write_commit_command,
    input  wire [5:0]            write_commit_layer,
    input  wire [511:0]          write_commit_epochs,
    input  wire                  write_commit_success,

    output wire                  kv_load_request_valid,
    input  wire                  kv_load_request_ready,
    output wire [31:0]           kv_load_request_command,
    output wire [5:0]            kv_load_request_layer,
    output wire [3:0]            kv_load_request_slot,
    output wire [31:0]           kv_load_request_epoch,
    output wire [7:0]            kv_load_request_length,
    input  wire                  kv_load_valid,
    output wire                  kv_load_ready,
    input  wire [31:0]           kv_load_command,
    input  wire [4:0]            kv_load_layer,
    input  wire [3:0]            kv_load_slot,
    input  wire [31:0]           kv_load_epoch,
    input  wire [6:0]            kv_load_position,
    input  wire                  kv_load_is_v,
    input  wire [2:0]            kv_load_head,
    input  wire [1:0]            kv_load_group,
    input  wire [383:0]          kv_load_s12,
    input  wire [15:0]           kv_load_meta,
    input  wire                  kv_load_last,
    input  wire                  kv_load_error,

    input  wire                  activation_valid,
    output wire                  activation_ready,
    input  wire                  activation_wave,
    input  wire [6:0]            activation_group,
    input  wire [8*32*24-1:0]    activation_s24,

    input  wire                  weight_valid,
    output wire                  weight_ready,
    input  wire [9:0]            weight_tile,
    input  wire [6:0]            weight_group,
    input  wire [16*32*8-1:0]    weight_s8,
    input  wire [16*16-1:0]      weight_meta16,

    output wire                  out_valid,
    input  wire                  out_ready,
    output wire                  out_wave,
    output wire [7:0]            out_tile,
    output wire [8*16*24-1:0]    out_s24,

    output reg  [31:0]           cycle_count,
    output reg  [31:0]           accepted_weight_group_count,
    output wire [31:0]           consumed_wave_group_count,
    output wire [31:0]           released_weight_group_count,
    output wire [31:0]           completed_projection_wave_tile_count,
    output reg  [31:0]           completed_projection_tile_count,
    output reg  [31:0]           completed_attention_row_count,
    output reg  [31:0]           completed_wo_tile_count,
    output reg  [31:0]           input_frontend_cycle_count,
    output reg  [31:0]           qkv_projection_cycle_count,
    output reg  [31:0]           rope_cycle_count,
    output reg  [31:0]           kv12_cycle_count,
    output reg  [31:0]           attention_cycle_count,
    output reg  [31:0]           context_frontend_cycle_count,
    output reg  [31:0]           wo_projection_cycle_count,
    output reg  [31:0]           control_overhead_cycle_count
);

    localparam [31:0] FORMAT_ID = 32'h4838_4103;
    localparam [4:0] ST_IDLE = 5'd0;
    localparam [4:0] ST_INPUT_FILL = 5'd1;
    localparam [4:0] ST_INPUT_WAIT = 5'd2;
    localparam [4:0] ST_PROJECT_START = 5'd3;
    localparam [4:0] ST_WEIGHT = 5'd4;
    localparam [4:0] ST_PROJECT_WAIT = 5'd5;
    localparam [4:0] ST_POST_ROPE = 5'd6;
    localparam [4:0] ST_POST_QUANT = 5'd7;
    localparam [4:0] ST_RELEASE_INPUT = 5'd8;
    localparam [4:0] ST_ATT_Q_READ = 5'd9;
    localparam [4:0] ST_ATT_Q_SEND = 5'd10;
    localparam [4:0] ST_ATT_K_REQ = 5'd11;
    localparam [4:0] ST_ATT_K_SEND = 5'd12;
    localparam [4:0] ST_ATT_K_ZERO = 5'd13;
    localparam [4:0] ST_ATT_VALUE_WAIT = 5'd14;
    localparam [4:0] ST_ATT_V_REQ = 5'd15;
    localparam [4:0] ST_ATT_V_SEND = 5'd16;
    localparam [4:0] ST_ATT_V_ZERO = 5'd17;
    localparam [4:0] ST_ATT_CONTEXT_WAIT = 5'd18;
    localparam [4:0] ST_CONTEXT_READ = 5'd19;
    localparam [4:0] ST_CONTEXT_SEND = 5'd20;
    localparam [4:0] ST_CONTEXT_WAIT = 5'd21;
    localparam [4:0] ST_RELEASE_CONTEXT = 5'd22;
    localparam [4:0] ST_ATT_Q_DATA = 5'd23;
    localparam [4:0] ST_CONTEXT_DRAIN = 5'd24;
    localparam [4:0] ST_ATT_ROW_SELECT = 5'd25;
    localparam [4:0] ST_WAIT_COMMIT = 5'd26;
    localparam [4:0] ST_ATT_LOAD_REQUEST = 5'd27;
    localparam [4:0] ST_ATT_LOAD_WAIT = 5'd28;
    localparam [4:0] ST_ERROR = 5'd31;

    reg [4:0] state_r;
    reg control_error_r;
    reg [31:0] request_id_r;
    reg [15:0] cohort_id_r;
    reg [5:0] layer_id_r;
    reg [15:0] active_mask_r;
    reg [127:0] positions_r;
    reg [511:0] epochs_r;
    reg [10:0] appended_count_r;
    reg [10:0] expected_append_count_r;
    wire [31:0] projection_consumed_total;
    wire [31:0] projection_released_total;
    wire [31:0] projection_wave_tile_total;
    reg [31:0] consumed_base_r, released_base_r, wave_tile_base_r;
    assign consumed_wave_group_count = projection_consumed_total - consumed_base_r;
    assign released_weight_group_count = projection_released_total - released_base_r;
    assign completed_projection_wave_tile_count = projection_wave_tile_total - wave_tile_base_r;
    integer descriptor_row;
    reg descriptor_bad;
    integer descriptor_active_count;
    always @* begin
        descriptor_bad = (active_mask == 0);
        descriptor_active_count = 0;
        for (descriptor_row=0; descriptor_row<16; descriptor_row=descriptor_row+1)
            if (active_mask[descriptor_row]) begin
                descriptor_active_count = descriptor_active_count + 1;
                if (row_positions[descriptor_row*8 +: 8] > 127 ||
                    row_epochs[descriptor_row*32 +: 32] == 0)
                    descriptor_bad = 1;
            end
    end
    assign done_command_id = request_id_r;
    assign done_layer = layer_id_r;
    assign done_active_mask = active_mask_r;
    assign done_epochs = epochs_r;
    assign write_commit_ready = rst_n && !clear && state_r == ST_WAIT_COMMIT;

    reg expected_activation_wave_r;
    reg [6:0] expected_activation_group_r;
    reg [9:0] projection_tile_r;
    reg projection_expected_out_wave_r;

    // RoPE coefficients are shared by all heads at the same query token and
    // pair-within-head: 16 tokens x 64 pairs.
    (* ram_style = "block" *) reg [35:0] rope_mem [0:1023];

    wire [767:0] query_read_data;
    wire [6143:0] context_activation_buffer;
    wire [47:0] rope_input_pair_s24;
    wire [4*768-1:0] kv_quant4_in_s24;
    reg [8:0] rope_input_index_r;
    reg [8:0] rope_output_index_r;
    reg [3:0] quant_row_r;

    reg [3:0] attention_row_r;
    reg [5:0] attention_head_r;
    reg [2:0] attention_query_group_r;
    reg [6:0] attention_key_r;
    reg [2:0] attention_key_group_r;
    reg [6:0] attention_value_key_r;
    reg [6:0] context_group_r;
    reg [3:0] context_read_slot_r;
    reg context_wave_r;

    wire projection_activation_ready;
    wire projection_activation_cached;
    wire projection_activation_release_ready;
    wire projection_activation_released;
    wire projection_project_ready;
    wire projection_project_done;
    wire projection_weight_ready;
    wire projection_out_valid;
    wire projection_out_wave;
    wire [8*16*24-1:0] projection_out_s24;
    wire [31:0] projection_out_request_id;
    wire [15:0] projection_out_cohort_id;
    wire [5:0] projection_out_layer_id;
    wire [2:0] projection_out_op_id;
    wire [9:0] projection_out_tile_id;
    wire [6:0] projection_out_query_start;
    wire [7:0] projection_out_valid_key_count;
    wire projection_error;
    wire projection_activation_release =
        (state_r == ST_RELEASE_INPUT) ||
        (state_r == ST_RELEASE_CONTEXT);
    wire projection_start = (state_r == ST_PROJECT_START) &&
        projection_activation_cached;
    wire projection_start_fire = projection_start && projection_project_ready;
    wire projection_out_ready = (state_r == ST_PROJECT_WAIT) &&
        ((projection_tile_r < 10'd384) || out_ready);
    wire projection_out_fire = projection_out_valid &&
        projection_out_ready;
    wire [2:0] projection_op_id = projection_tile_r < 10'd256 ? 3'd0 :
        projection_tile_r < 10'd320 ? 3'd1 :
        projection_tile_r < 10'd384 ? 3'd2 : 3'd3;
    wire projection_descriptor_match =
        (projection_out_request_id == request_id_r) &&
        (projection_out_cohort_id == cohort_id_r) &&
        (projection_out_layer_id == layer_id_r) &&
        (projection_out_op_id == projection_op_id) &&
        (projection_out_tile_id == projection_tile_r) &&
        (projection_out_query_start == 7'd0) &&
        (projection_out_valid_key_count == 8'd128);

    wire context_activation_valid = state_r == ST_CONTEXT_SEND;
    wire projection_activation_wave = context_activation_valid ?
        context_wave_r : activation_wave;
    wire projection_activation_valid =
        ((state_r == ST_INPUT_FILL) && activation_valid &&
            (activation_wave == expected_activation_wave_r) &&
            (activation_group == expected_activation_group_r)) ||
        context_activation_valid;
    wire [6:0] projection_activation_group =
        context_activation_valid ? context_group_r : activation_group;
    wire [8*32*24-1:0] projection_activation_unmasked =
        context_activation_valid ? context_activation_buffer : activation_s24;
    wire [8*32*24-1:0] projection_activation_s24;
    genvar mask_row;
    generate for (mask_row=0; mask_row<8; mask_row=mask_row+1) begin : g_input_row_mask
        assign projection_activation_s24[mask_row*768 +: 768] =
            active_mask_r[(projection_activation_wave ? 8 : 0)+mask_row] ?
            projection_activation_unmasked[mask_row*768 +: 768] : 768'd0;
        assign out_s24[mask_row*384 +: 384] =
            active_mask_r[(projection_out_wave ? 8 : 0)+mask_row] ?
            projection_out_s24[mask_row*384 +: 384] : 384'd0;
    end endgenerate
    wire projection_activation_fire = projection_activation_valid &&
        projection_activation_ready;

    assign activation_ready = rst_n && !clear && (state_r == ST_INPUT_FILL) &&
        projection_activation_ready &&
        (activation_wave == expected_activation_wave_r) &&
        (activation_group == expected_activation_group_r);
    assign weight_ready = rst_n && !clear && (state_r == ST_WEIGHT) &&
        (weight_tile == projection_tile_r) && projection_weight_ready;
    wire weight_fire = weight_valid && weight_ready;

    assign out_valid = rst_n && !clear && (state_r == ST_PROJECT_WAIT) &&
        (projection_tile_r >= 10'd384) && projection_out_valid;
    assign out_wave = projection_out_wave;
    assign out_tile = projection_tile_r - 10'd384;

    generate if (USE_PROJECTION_STUB == 0) begin : g_projection_rtl
    hap_projection_core16x16_w8_reuse u_projection (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(projection_activation_valid),
        .activation_ready(projection_activation_ready),
        .activation_wave(projection_activation_wave),
        .activation_s24(projection_activation_s24),
        .activation_group(projection_activation_group),
        .activation_cached(projection_activation_cached),
        .activation_release(projection_activation_release),
        .activation_release_ready(projection_activation_release_ready),
        .activation_released(projection_activation_released),
        .project_start(projection_start), .project_ready(projection_project_ready),
        .project_done(projection_project_done),
        .project_request_id(request_id_r), .project_cohort_id(cohort_id_r),
        .project_layer_id(layer_id_r), .project_op_id(projection_op_id),
        .project_tile_id(projection_tile_r),
        .project_query_start(7'd0),
        .project_valid_key_count(8'd128),
        .weight_ready(projection_weight_ready),
        .weight_valid(weight_valid && (state_r == ST_WEIGHT) &&
            (weight_tile == projection_tile_r)),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16),
        .out_valid(projection_out_valid),
        .out_ready(projection_out_ready), .out_wave(projection_out_wave),
        .out_s24(projection_out_s24),
        .out_request_id(projection_out_request_id),
        .out_cohort_id(projection_out_cohort_id),
        .out_layer_id(projection_out_layer_id),
        .out_op_id(projection_out_op_id), .out_tile_id(projection_out_tile_id),
        .out_query_start(projection_out_query_start),
        .out_valid_key_count(projection_out_valid_key_count),
        .accepted_weight_group_count(),
        .consumed_wave_group_count(projection_consumed_total),
        .released_weight_group_count(projection_released_total),
        .output_wave_tile_count(projection_wave_tile_total),
        .saturation_count(), .weight_fifo_high_watermark(), .busy(),
        .error(projection_error)
    );
    end else begin : g_projection_stub
    hap_projection_core16x16_w8_reuse_stub u_projection (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(projection_activation_valid),
        .activation_ready(projection_activation_ready),
        .activation_wave(projection_activation_wave),
        .activation_s24(projection_activation_s24),
        .activation_group(projection_activation_group),
        .activation_cached(projection_activation_cached),
        .activation_release(projection_activation_release),
        .activation_release_ready(projection_activation_release_ready),
        .activation_released(projection_activation_released),
        .project_start(projection_start), .project_ready(projection_project_ready),
        .project_done(projection_project_done),
        .project_request_id(request_id_r), .project_cohort_id(cohort_id_r),
        .project_layer_id(layer_id_r), .project_op_id(projection_op_id),
        .project_tile_id(projection_tile_r),
        .project_query_start(7'd0),
        .project_valid_key_count(8'd128),
        .weight_ready(projection_weight_ready),
        .weight_valid(weight_valid && (state_r == ST_WEIGHT) &&
            (weight_tile == projection_tile_r)),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16),
        .out_valid(projection_out_valid), .out_ready(projection_out_ready),
        .out_wave(projection_out_wave), .out_s24(projection_out_s24),
        .out_request_id(projection_out_request_id),
        .out_cohort_id(projection_out_cohort_id),
        .out_layer_id(projection_out_layer_id),
        .out_op_id(projection_out_op_id), .out_tile_id(projection_out_tile_id),
        .out_query_start(projection_out_query_start),
        .out_valid_key_count(projection_out_valid_key_count),
        .accepted_weight_group_count(),
        .consumed_wave_group_count(projection_consumed_total),
        .released_weight_group_count(projection_released_total),
        .output_wave_tile_count(projection_wave_tile_total),
        .saturation_count(), .weight_fifo_high_watermark(), .busy(),
        .error(projection_error)
    );
    end endgenerate

    wire rope_in_ready;
    wire rope_out_valid;
    wire signed [23:0] rope_out_y0_s24;
    wire signed [23:0] rope_out_y1_s24;
    wire rope_error;
    wire rope_feed_active = (state_r == ST_POST_ROPE) &&
        (rope_input_index_r < 9'd256);
    wire [3:0] rope_input_row = rope_input_index_r[7:4];
    wire [3:0] rope_input_pair = rope_input_index_r[3:0];
    wire [5:0] projection_group32 = projection_tile_r < 10'd256 ?
        projection_tile_r[7:1] % 4 :
        ((projection_tile_r < 10'd320 ? projection_tile_r - 10'd256 :
          projection_tile_r - 10'd320) >> 1) % 4;
    wire [9:0] rope_read_addr = {rope_input_row, projection_group32[1:0],
        rope_input_pair};
    wire [35:0] rope_coeff = rope_mem[rope_read_addr];
    wire rope_in_fire = rope_feed_active && rope_in_ready;
    wire rope_out_fire = rope_out_valid;

    (* KEEP_HIERARCHY = "yes" *)
    hap_attention_cohort16_postprocess_store u_postprocess_store (
        .clk(clk),
        .projection_capture_valid(projection_out_fire &&
            projection_tile_r < 10'd384),
        .projection_tile(projection_tile_r),
        .projection_wave(projection_out_wave),
        .projection_s24(projection_out_s24),
        .rope_shift_valid(rope_in_fire),
        .rope_input_row(rope_input_row),
        .rope_store_valid(rope_out_fire && projection_tile_r >= 10'd256),
        .rope_output_index(rope_output_index_r),
        .rope_y0_s24(rope_out_y0_s24),
        .rope_y1_s24(rope_out_y1_s24),
        .quant_row(quant_row_r),
        .rope_input_pair_s24(rope_input_pair_s24),
        .quant_s24(kv_quant4_in_s24)
    );

    hap_rope_pair_s24 u_rope (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(rope_feed_active), .in_ready(rope_in_ready),
        .in_x0_s24(rope_input_pair_s24[23:0]),
        .in_x1_s24(rope_input_pair_s24[47:24]),
        .in_cos_s18(rope_coeff[17:0]), .in_sin_s18(rope_coeff[35:18]),
        .out_valid(rope_out_valid), .out_ready(1'b1),
        .out_y0_s24(rope_out_y0_s24), .out_y1_s24(rope_out_y1_s24),
        .input_pair_count(), .output_pair_count(), .saturation_count(),
        .error(rope_error)
    );

    (* KEEP_HIERARCHY = "yes" *)
    hap_attention_cohort16_query_store u_query_store (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .pair_valid(rope_out_fire && projection_tile_r < 10'd256),
        .pair_index(rope_output_index_r),
        .projection_tile(projection_tile_r),
        .pair_y0_s24(rope_out_y0_s24),
        .pair_y1_s24(rope_out_y1_s24),
        .read_addr_valid(state_r == ST_ATT_Q_READ),
        .read_data_valid(state_r == ST_ATT_Q_DATA),
        .read_row(attention_row_r),
        .read_head(attention_head_r[4:0]),
        .read_group(attention_query_group_r[1:0]),
        .read_data_s24(query_read_data)
    );

    wire kv_quant4_in_ready;
    wire kv_quant4_out_valid;
    wire [1:0] kv_quant4_out_lane;
    wire kv_quant4_out_batch_last;
    wire [383:0] kv_quant4_out_s12;
    wire [15:0] kv_quant4_out_meta;
    wire kv_quant_error;
    wire [3:0] quant_selected_row =
        quant_row_r + {2'd0, kv_quant4_out_lane};
    wire kv_quant4_in_valid = state_r == ST_POST_QUANT;
    wire kv_quant4_out_ready = rst_n && !clear && (state_r == ST_POST_QUANT) &&
        (!active_mask_r[quant_selected_row] || kv_append_ready);
    wire kv_quant4_out_fire = kv_quant4_out_valid && kv_quant4_out_ready;

    hap_kv12_quantizer4 u_kv_quantizer4 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(kv_quant4_in_valid), .in_ready(kv_quant4_in_ready),
        .in_s24(kv_quant4_in_s24), .out_valid(kv_quant4_out_valid),
        .out_ready(kv_quant4_out_ready), .out_lane(kv_quant4_out_lane),
        .out_batch_last(kv_quant4_out_batch_last),
        .out_s12(kv_quant4_out_s12), .out_meta(kv_quant4_out_meta),
        .input_batch_count(), .output_group_count(), .error(kv_quant_error)
    );

    function automatic [11:0] kv_addr;
        input [2:0] head;
        input [6:0] token;
        input [1:0] group_index;
        begin
            kv_addr = {head, token, group_index};
        end
    endfunction

    wire quant_is_v = projection_tile_r >= 10'd320;
    wire [7:0] quant_position = positions_r[quant_selected_row*8 +: 8];
    wire [2:0] quant_head = quant_is_v ?
        (projection_tile_r - 10'd320) >> 3 :
        (projection_tile_r - 10'd256) >> 3;
    wire [1:0] quant_group = quant_is_v ?
        ((projection_tile_r - 10'd320) >> 1) & 2'b11 :
        ((projection_tile_r - 10'd256) >> 1) & 2'b11;
    assign kv_append_valid = rst_n && !clear && (state_r == ST_POST_QUANT) &&
        kv_quant4_out_valid && active_mask_r[quant_selected_row];
    assign kv_append_command = request_id_r;
    assign kv_append_layer = layer_id_r;
    assign kv_append_slot = quant_selected_row;
    assign kv_append_epoch = epochs_r[quant_selected_row*32 +: 32];
    assign kv_append_position = quant_position[6:0];
    assign kv_append_is_v = quant_is_v;
    assign kv_append_head = quant_head;
    assign kv_append_group = quant_group;
    assign kv_append_s12 = kv_quant4_out_s12;
    assign kv_append_meta = kv_quant4_out_meta;
    assign kv_append_last = appended_count_r + 11'd1 == expected_append_count_r;
    wire [7:0] attention_row_key_count =
        positions_r[attention_row_r*8 +: 8] + 8'd1;
    wire [6:0] attention_row_last_key = attention_row_key_count - 8'd1;
    wire cache_k_rd_valid = state_r == ST_ATT_K_REQ;
    wire cache_k_rd_ready;
    wire cache_k_rsp_valid;
    wire cache_k_rsp_ready;
    wire [383:0] cache_k_rsp_s12;
    wire [15:0] cache_k_rsp_meta;
    wire cache_v_rd_valid = state_r == ST_ATT_V_REQ;
    wire cache_v_rd_ready;
    wire cache_v_rsp_valid;
    wire cache_v_rsp_ready;
    wire [383:0] cache_v_rsp_s12;
    wire [15:0] cache_v_rsp_meta;
    wire cache_error;
    wire [2:0] attention_kv_head = attention_head_r[4:2];
    wire [1:0] attention_value_group;

    wire scratch_begin_ready;
    wire scratch_sealed;
    assign kv_load_request_valid = rst_n && !clear &&
        (state_r == ST_ATT_LOAD_REQUEST) && scratch_begin_ready;
    wire load_request_fire = kv_load_request_valid && kv_load_request_ready;
    assign kv_load_request_command = request_id_r;
    assign kv_load_request_layer = layer_id_r;
    assign kv_load_request_slot = attention_row_r;
    assign kv_load_request_epoch = epochs_r[attention_row_r*32 +: 32];
    assign kv_load_request_length = attention_row_key_count;
    wire scratch_load_ready;
    assign kv_load_ready = (state_r == ST_ATT_LOAD_WAIT) && scratch_load_ready;
    hap_kv12_request_scratch u_kv_cache (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .begin_valid(load_request_fire), .begin_ready(scratch_begin_ready),
        .begin_command(request_id_r), .begin_layer(layer_id_r[4:0]),
        .begin_slot(attention_row_r),
        .begin_epoch(epochs_r[attention_row_r*32 +: 32]),
        .begin_length(attention_row_key_count),
        .load_valid(kv_load_valid && state_r == ST_ATT_LOAD_WAIT),
        .load_ready(scratch_load_ready), .load_command(kv_load_command),
        .load_layer(kv_load_layer), .load_slot(kv_load_slot),
        .load_epoch(kv_load_epoch), .load_position(kv_load_position),
        .load_is_v(kv_load_is_v), .load_head(kv_load_head), .load_group(kv_load_group),
        .load_s12(kv_load_s12), .load_meta(kv_load_meta),
        .load_last(kv_load_last), .load_error(kv_load_error), .sealed(scratch_sealed),
        .read_command(request_id_r), .read_layer(layer_id_r[4:0]),
        .read_slot(attention_row_r), .read_epoch(epochs_r[attention_row_r*32 +: 32]),
        .k_rd_valid(cache_k_rd_valid), .k_rd_ready(cache_k_rd_ready),
        .k_rd_addr(kv_addr(attention_kv_head, attention_key_r,
            attention_key_group_r[1:0])),
        .k_rsp_valid(cache_k_rsp_valid), .k_rsp_ready(cache_k_rsp_ready),
        .k_rsp_s12(cache_k_rsp_s12), .k_rsp_meta(cache_k_rsp_meta),
        .v_rd_valid(cache_v_rd_valid), .v_rd_ready(cache_v_rd_ready),
        .v_rd_addr(kv_addr(attention_kv_head, attention_value_key_r,
            attention_value_group)),
        .v_rsp_valid(cache_v_rsp_valid), .v_rsp_ready(cache_v_rsp_ready),
        .v_rsp_s12(cache_v_rsp_s12), .v_rsp_meta(cache_v_rsp_meta),
        .loaded_count(), .error(cache_error)
    );

    wire row_query_load_ready;
    wire row_query_ready;
    wire row_key_ready;
    wire row_value_phase;
    wire [2:0] row_value_tile_index;
    assign attention_value_group = row_value_tile_index[2:1];
    wire row_value_ready;
    wire row_out_valid;
    wire [2:0] row_out_tile_index;
    wire [383:0] row_out_context_s24;
    wire row_error;
    wire row_query_valid = state_r == ST_ATT_Q_SEND;
    wire row_key_valid = (state_r == ST_ATT_K_SEND) && cache_k_rsp_valid;
    wire row_key_fire = row_key_valid && row_key_ready;
    wire row_value_valid = (state_r == ST_ATT_V_SEND) && cache_v_rsp_valid;
    wire [191:0] row_value_s12 = row_value_tile_index[0] ?
        cache_v_rsp_s12[383:192] : cache_v_rsp_s12[191:0];
    wire [15:0] row_value_meta = cache_v_rsp_meta;
    wire row_value_fire = row_value_valid && row_value_ready;
    wire row_out_fire = row_out_valid;
    wire attention_mask = 1'b0;
    // The unchanged QK leaf retains its previous last-key index until the
    // current final key arrives. Reset only the finished head's arithmetic
    // state before group0 of the next query, so a longer request cannot expose
    // that stale index while earlier scores are already leaving the pipe.
    // Scratch/query/context storage and external KV are deliberately retained.
    wire attention_head_clear = clear ||
        ((state_r == ST_ATT_Q_READ) && (attention_query_group_r == 0));
    assign cache_k_rsp_ready = (state_r == ST_ATT_K_SEND) && row_key_ready;
    assign cache_v_rsp_ready = (state_r == ST_ATT_V_SEND) && row_value_ready;

    hap_attention_row_head128 u_attention_row (
        .clk(clk), .rst_n(rst_n), .clear(attention_head_clear),
        .row_key_count(attention_row_key_count),
        .query_load_valid(row_query_valid),
        .query_load_ready(row_query_load_ready),
        .query_load_group(attention_query_group_r[1:0]),
        .query_load_s24(query_read_data), .query_ready(row_query_ready),
        .key_valid(row_key_valid), .key_ready(row_key_ready),
        .key_first((attention_key_r == 0) &&
            (attention_key_group_r == 0)),
        .key_last((attention_key_r == attention_row_last_key) &&
            (attention_key_group_r == 3)),
        .key_group(attention_key_group_r[1:0]), .key_mask(attention_mask),
        .key_s12(cache_k_rsp_s12), .key_meta16(cache_k_rsp_meta),
        .value_phase(row_value_phase),
        .value_tile_index(row_value_tile_index),
        .value_valid(row_value_valid), .value_ready(row_value_ready),
        .value16_s12(row_value_s12), .value_meta16(row_value_meta),
        .out_valid(row_out_valid), .out_ready(1'b1),
        .out_tile_index(row_out_tile_index),
        .out_context16_s24(row_out_context_s24),
        .score_clip_count(), .context_saturation_count(),
        .completed_row_count(), .completed_context_tile_count(),
        .error(row_error)
    );

    (* KEEP_HIERARCHY = "yes" *)
    hap_attention_cohort16_context_store u_context_store (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .row_write_valid(row_out_fire),
        .row_write_row(attention_row_r),
        .row_write_head(attention_head_r[4:0]),
        .row_write_tile(row_out_tile_index),
        .row_write_s24(row_out_context_s24),
        .read_issue(state_r == ST_CONTEXT_READ),
        .read_wave(context_wave_r),
        .read_slot(context_read_slot_r),
        .read_group(context_group_r),
        .activation_s24(context_activation_buffer)
    );

    assign rope_wr_ready = rst_n && !clear && state_r == ST_IDLE;
    assign busy = state_r != ST_IDLE;
    assign error = control_error_r | projection_error | rope_error |
        kv_quant_error | cache_error | row_error;

    always @(posedge clk)
        if (rope_wr_valid && rope_wr_ready)
            rope_mem[rope_wr_addr] <= {rope_wr_sin_s18, rope_wr_cos_s18};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_IDLE;
            control_error_r <= 1'b0;
            done <= 1'b0;
            request_id_r <= 32'd0;
            cohort_id_r <= 16'd0;
            layer_id_r <= 6'd0;
            active_mask_r <= 0; positions_r <= 0; epochs_r <= 0;
            appended_count_r <= 0; expected_append_count_r <= 0;
            consumed_base_r <= 0; released_base_r <= 0; wave_tile_base_r <= 0;
            expected_activation_wave_r <= 1'b0;
            expected_activation_group_r <= 7'd0;
            projection_tile_r <= 10'd0;
            projection_expected_out_wave_r <= 1'b0;
            rope_input_index_r <= 9'd0;
            rope_output_index_r <= 9'd0;
            quant_row_r <= 4'd0;
            attention_row_r <= 4'd0;
            attention_head_r <= 6'd0;
            attention_query_group_r <= 3'd0;
            attention_key_r <= 7'd0;
            attention_key_group_r <= 3'd0;
            attention_value_key_r <= 7'd0;
            context_group_r <= 7'd0;
            context_read_slot_r <= 4'd0;
            context_wave_r <= 1'b0;
            cycle_count <= 32'd0;
            accepted_weight_group_count <= 32'd0;
            completed_projection_tile_count <= 32'd0;
            completed_attention_row_count <= 32'd0;
            completed_wo_tile_count <= 32'd0;
            input_frontend_cycle_count <= 32'd0;
            qkv_projection_cycle_count <= 32'd0;
            rope_cycle_count <= 32'd0;
            kv12_cycle_count <= 32'd0;
            attention_cycle_count <= 32'd0;
            context_frontend_cycle_count <= 32'd0;
            wo_projection_cycle_count <= 32'd0;
            control_overhead_cycle_count <= 32'd0;
        end else if (clear) begin
            active_mask_r <= 0; positions_r <= 0; epochs_r <= 0;
            appended_count_r <= 0; expected_append_count_r <= 0;
            consumed_base_r <= 0; released_base_r <= 0; wave_tile_base_r <= 0;
            state_r <= ST_IDLE;
            control_error_r <= 1'b0;
            done <= 1'b0;
            expected_activation_wave_r <= 1'b0;
            expected_activation_group_r <= 7'd0;
            projection_tile_r <= 10'd0;
            projection_expected_out_wave_r <= 1'b0;
            rope_input_index_r <= 9'd0;
            rope_output_index_r <= 9'd0;
            quant_row_r <= 4'd0;
            attention_row_r <= 4'd0;
            attention_head_r <= 6'd0;
            attention_query_group_r <= 3'd0;
            attention_key_r <= 7'd0;
            attention_key_group_r <= 3'd0;
            attention_value_key_r <= 7'd0;
            context_group_r <= 7'd0;
            context_read_slot_r <= 4'd0;
            context_wave_r <= 1'b0;
            cycle_count <= 32'd0;
            accepted_weight_group_count <= 32'd0;
            completed_projection_tile_count <= 32'd0;
            completed_attention_row_count <= 32'd0;
            completed_wo_tile_count <= 32'd0;
            input_frontend_cycle_count <= 32'd0;
            qkv_projection_cycle_count <= 32'd0;
            rope_cycle_count <= 32'd0;
            kv12_cycle_count <= 32'd0;
            attention_cycle_count <= 32'd0;
            context_frontend_cycle_count <= 32'd0;
            wo_projection_cycle_count <= 32'd0;
            control_overhead_cycle_count <= 32'd0;
        end else begin
            done <= 1'b0;
            if (state_r != ST_IDLE)
                cycle_count <= cycle_count + 32'd1;
            case (state_r)
                ST_INPUT_FILL, ST_INPUT_WAIT:
                    input_frontend_cycle_count <=
                        input_frontend_cycle_count + 32'd1;
                ST_PROJECT_START, ST_WEIGHT, ST_PROJECT_WAIT: begin
                    if (projection_tile_r < 10'd384)
                        qkv_projection_cycle_count <=
                            qkv_projection_cycle_count + 32'd1;
                    else
                        wo_projection_cycle_count <=
                            wo_projection_cycle_count + 32'd1;
                end
                ST_POST_ROPE:
                    rope_cycle_count <= rope_cycle_count + 32'd1;
                ST_POST_QUANT:
                    kv12_cycle_count <= kv12_cycle_count + 32'd1;
                ST_ATT_Q_READ, ST_ATT_Q_DATA, ST_ATT_Q_SEND, ST_ATT_K_REQ,
                ST_ATT_K_SEND, ST_ATT_K_ZERO, ST_ATT_VALUE_WAIT,
                ST_ATT_V_REQ, ST_ATT_V_SEND, ST_ATT_V_ZERO,
                ST_ATT_CONTEXT_WAIT:
                    attention_cycle_count <= attention_cycle_count + 32'd1;
                ST_CONTEXT_READ, ST_CONTEXT_DRAIN, ST_CONTEXT_SEND,
                ST_CONTEXT_WAIT:
                    context_frontend_cycle_count <=
                        context_frontend_cycle_count + 32'd1;
                ST_IDLE: begin end
                default:
                    control_overhead_cycle_count <=
                        control_overhead_cycle_count + 32'd1;
            endcase

            if ((state_r == ST_IDLE) && start) begin
                if ((format_id != FORMAT_ID) || (layer_id > 6'd31) || descriptor_bad) begin
                    control_error_r <= 1'b1;
                    state_r <= ST_ERROR;
                end else begin
                    request_id_r <= command_id;
                    cohort_id_r <= batch_id;
                    layer_id_r <= layer_id;
                    active_mask_r <= active_mask;
                    positions_r <= row_positions;
                    epochs_r <= row_epochs;
                    appended_count_r <= 0;
                    expected_append_count_r <= descriptor_active_count * 64;
                    consumed_base_r <= projection_consumed_total;
                    released_base_r <= projection_released_total;
                    wave_tile_base_r <= projection_wave_tile_total;
                    expected_activation_wave_r <= 1'b0;
                    expected_activation_group_r <= 7'd0;
                    projection_tile_r <= 10'd0;
                    projection_expected_out_wave_r <= 1'b0;
                    attention_row_r <= 4'd0;
                    attention_head_r <= 6'd0;
                    attention_query_group_r <= 3'd0;
                    cycle_count <= 32'd0;
                    accepted_weight_group_count <= 32'd0;
                    completed_projection_tile_count <= 32'd0;
                    completed_attention_row_count <= 32'd0;
                    completed_wo_tile_count <= 32'd0;
                    input_frontend_cycle_count <= 32'd0;
                    qkv_projection_cycle_count <= 32'd0;
                    rope_cycle_count <= 32'd0;
                    kv12_cycle_count <= 32'd0;
                    attention_cycle_count <= 32'd0;
                    context_frontend_cycle_count <= 32'd0;
                    wo_projection_cycle_count <= 32'd0;
                    control_overhead_cycle_count <= 32'd0;
                    state_r <= ST_INPUT_FILL;
                end
            end

            if ((state_r == ST_INPUT_FILL) && activation_valid &&
                    ((activation_wave != expected_activation_wave_r) ||
                     (activation_group != expected_activation_group_r)))
                control_error_r <= 1'b1;
            if ((state_r == ST_INPUT_FILL) && projection_activation_fire) begin
                if (expected_activation_group_r == 7'd127) begin
                    expected_activation_group_r <= 7'd0;
                    if (!expected_activation_wave_r)
                        expected_activation_wave_r <= 1'b1;
                    else
                        state_r <= ST_INPUT_WAIT;
                end else begin
                    expected_activation_group_r <=
                        expected_activation_group_r + 1'b1;
                end
            end
            if ((state_r == ST_INPUT_WAIT) && projection_activation_cached)
                state_r <= ST_PROJECT_START;

            if (projection_start_fire) begin
                projection_expected_out_wave_r <= 1'b0;
                state_r <= ST_WEIGHT;
            end

            if ((state_r == ST_WEIGHT) && weight_valid &&
                    (weight_tile != projection_tile_r))
                control_error_r <= 1'b1;

            if (weight_fire) begin
                accepted_weight_group_count <=
                    accepted_weight_group_count + 32'd1;
                if (weight_group == 7'd127)
                    state_r <= ST_PROJECT_WAIT;
            end

            if (projection_out_fire) begin
                if ((projection_out_wave != projection_expected_out_wave_r) ||
                        !projection_descriptor_match)
                    control_error_r <= 1'b1;
                projection_expected_out_wave_r <=
                    ~projection_expected_out_wave_r;
                if (projection_out_wave) begin
                    completed_projection_tile_count <=
                        completed_projection_tile_count + 32'd1;
                    if (projection_tile_r >= 10'd384) begin
                        completed_wo_tile_count <=
                            completed_wo_tile_count + 32'd1;
                        if (projection_tile_r == 10'd639)
                            state_r <= ST_RELEASE_CONTEXT;
                        else begin
                            projection_tile_r <= projection_tile_r + 1'b1;
                            state_r <= ST_PROJECT_START;
                        end
                    end else if (!projection_tile_r[0]) begin
                        projection_tile_r <= projection_tile_r + 1'b1;
                        state_r <= ST_PROJECT_START;
                    end else if (projection_tile_r < 10'd320) begin
                        rope_input_index_r <= 9'd0;
                        rope_output_index_r <= 9'd0;
                        state_r <= ST_POST_ROPE;
                    end else begin
                        quant_row_r <= 4'd0;
                        state_r <= ST_POST_QUANT;
                    end
                end
            end

            if (rope_in_fire)
                rope_input_index_r <= rope_input_index_r + 1'b1;
            if (rope_out_fire && (state_r == ST_POST_ROPE)) begin
                rope_output_index_r <= rope_output_index_r + 1'b1;
                if (rope_output_index_r == 9'd255) begin
                    if (projection_tile_r < 10'd256) begin
                        projection_tile_r <= projection_tile_r + 1'b1;
                        state_r <= ST_PROJECT_START;
                    end else begin
                        quant_row_r <= 4'd0;
                        state_r <= ST_POST_QUANT;
                    end
                end
            end

            if (kv_quant4_out_fire && (state_r == ST_POST_QUANT) &&
                    kv_quant4_out_batch_last) begin
                if (quant_row_r == 4'd12) begin
                    quant_row_r <= 4'd0;
                    if (projection_tile_r == 10'd383)
                        state_r <= ST_RELEASE_INPUT;
                    else begin
                        projection_tile_r <= projection_tile_r + 1'b1;
                        state_r <= ST_PROJECT_START;
                    end
                end else begin
                    quant_row_r <= quant_row_r + 4'd4;
                end
            end

            if (kv_append_valid && kv_append_ready)
                appended_count_r <= appended_count_r + 11'd1;
            if ((state_r == ST_RELEASE_INPUT) && projection_activation_released)
                state_r <= ST_WAIT_COMMIT;
            if (write_commit_valid && write_commit_ready) begin
                if (!write_commit_success || write_commit_command != request_id_r ||
                    write_commit_layer != layer_id_r || write_commit_epochs != epochs_r ||
                    appended_count_r != expected_append_count_r) begin
                    control_error_r <= 1;
                    state_r <= ST_ERROR;
                end else begin
                    attention_row_r <= 0; attention_head_r <= 0;
                    attention_query_group_r <= 0;
                    state_r <= ST_ATT_ROW_SELECT;
                end
            end
            if (state_r == ST_ATT_ROW_SELECT) begin
                if (active_mask_r[attention_row_r]) state_r <= ST_ATT_LOAD_REQUEST;
                else if (attention_row_r == 15) begin
                    context_group_r <= 0; context_read_slot_r <= 0; context_wave_r <= 0;
                    state_r <= ST_CONTEXT_READ;
                end else attention_row_r <= attention_row_r + 1'b1;
            end
            if (load_request_fire) state_r <= ST_ATT_LOAD_WAIT;
            if (state_r == ST_ATT_LOAD_WAIT && scratch_sealed)
                state_r <= ST_ATT_Q_READ;
            if (kv_load_valid && state_r != ST_ATT_LOAD_WAIT)
                control_error_r <= 1;

            if (state_r == ST_ATT_Q_READ)
                state_r <= ST_ATT_Q_DATA;
            if (state_r == ST_ATT_Q_DATA)
                state_r <= ST_ATT_Q_SEND;
            if ((state_r == ST_ATT_Q_SEND) && row_query_valid &&
                    row_query_load_ready) begin
                if (attention_query_group_r == 3'd3) begin
                    attention_query_group_r <= 3'd0;
                    attention_key_r <= 7'd0;
                    attention_key_group_r <= 3'd0;
                    state_r <= ST_ATT_K_REQ;
                end else begin
                    attention_query_group_r <=
                        attention_query_group_r + 1'b1;
                    state_r <= ST_ATT_Q_READ;
                end
            end

            if (state_r == ST_ATT_K_REQ) begin
                if (cache_k_rd_ready)
                    state_r <= ST_ATT_K_SEND;
            end
            if ((state_r == ST_ATT_K_SEND) && cache_k_rsp_valid &&
                    row_key_ready)
                state_r <= (attention_key_r == attention_row_last_key &&
                    attention_key_group_r == 3) ?
                    ST_ATT_VALUE_WAIT : ST_ATT_K_REQ;
            if (row_key_fire) begin
                if (attention_key_group_r == 3) begin
                    attention_key_group_r <= 3'd0;
                    attention_key_r <= attention_key_r + 1'b1;
                end else begin
                    attention_key_group_r <=
                        attention_key_group_r + 1'b1;
                end
            end

            if ((state_r == ST_ATT_VALUE_WAIT) && row_value_phase) begin
                attention_value_key_r <= 7'd0;
                state_r <= ST_ATT_V_REQ;
            end
            if (state_r == ST_ATT_V_REQ) begin
                if (cache_v_rd_ready)
                    state_r <= ST_ATT_V_SEND;
            end
            if ((state_r == ST_ATT_V_SEND) && cache_v_rsp_valid &&
                    row_value_ready)
                state_r <= (attention_value_key_r == attention_row_last_key) ?
                    ST_ATT_CONTEXT_WAIT : ST_ATT_V_REQ;
            if (row_value_fire)
                attention_value_key_r <= attention_value_key_r + 1'b1;

            if ((state_r == ST_ATT_CONTEXT_WAIT) && row_out_fire) begin
                if (row_out_tile_index == 3'd7) begin
                    completed_attention_row_count <=
                        completed_attention_row_count + 32'd1;
                    if ((attention_row_r == 4'd15) &&
                            (attention_head_r == 6'd31)) begin
                        context_group_r <= 7'd0;
                        context_read_slot_r <= 4'd0;
                        context_wave_r <= 1'b0;
                        state_r <= ST_CONTEXT_READ;
                    end else begin
                        if (attention_head_r == 6'd31) begin
                            attention_head_r <= 6'd0;
                            attention_row_r <= attention_row_r + 1'b1;
                            state_r <= ST_ATT_ROW_SELECT;
                        end else begin
                            attention_head_r <= attention_head_r + 1'b1;
                            state_r <= ST_ATT_Q_READ;
                        end
                        attention_query_group_r <= 3'd0;
                    end
                end else begin
                    attention_value_key_r <= 7'd0;
                    state_r <= ST_ATT_VALUE_WAIT;
                end
            end

            if (state_r == ST_CONTEXT_READ) begin
                if (context_read_slot_r == 4'd15)
                    state_r <= ST_CONTEXT_DRAIN;
                else
                    context_read_slot_r <= context_read_slot_r + 1'b1;
            end
            if (state_r == ST_CONTEXT_DRAIN)
                state_r <= ST_CONTEXT_SEND;
            if ((state_r == ST_CONTEXT_SEND) &&
                    projection_activation_ready) begin
                if (context_group_r == 7'd127) begin
                    if (!context_wave_r) begin
                        context_wave_r <= 1'b1;
                        context_group_r <= 7'd0;
                        context_read_slot_r <= 4'd0;
                        state_r <= ST_CONTEXT_READ;
                    end else begin
                        state_r <= ST_CONTEXT_WAIT;
                    end
                end else begin
                    context_group_r <= context_group_r + 1'b1;
                    context_read_slot_r <= 4'd0;
                    state_r <= ST_CONTEXT_READ;
                end
            end
            if ((state_r == ST_CONTEXT_WAIT) &&
                    projection_activation_cached) begin
                projection_tile_r <= 10'd384;
                state_r <= ST_PROJECT_START;
            end

            if ((state_r == ST_RELEASE_CONTEXT) &&
                    projection_activation_released) begin
                done <= 1'b1;
                state_r <= ST_IDLE;
            end

            if (projection_error || rope_error || kv_quant_error ||
                    cache_error || row_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

endmodule
