`timescale 1ns / 1ps

// Fixed-shape Attention-only compute top:
// post-RMSNorm S24 -> H+A8 -> Q/K/V -> RoPE/KV12 -> Attention ->
// context H+A8 -> Wo S24.  One projection array owns all Q/K/V/Wo work.
module hap_attention_compute_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  start,
    input  wire [31:0]           format_id,
    input  wire [6:0]            query_start,
    input  wire [7:0]            valid_key_count,
    output wire                  busy,
    output reg                   done,
    output wire                  error,

    input  wire                  rope_wr_valid,
    output wire                  rope_wr_ready,
    input  wire [8:0]            rope_wr_addr,
    input  wire signed [17:0]    rope_wr_cos_s18,
    input  wire signed [17:0]    rope_wr_sin_s18,

    input  wire                  kv_preload_valid,
    output wire                  kv_preload_ready,
    input  wire                  kv_preload_is_v,
    input  wire [11:0]           kv_preload_addr,
    input  wire [32*12-1:0]      kv_preload_s12,
    input  wire [15:0]           kv_preload_meta16,

    input  wire                  activation_valid,
    output wire                  activation_ready,
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
    output wire [7:0]            out_tile,
    output wire [8*16*24-1:0]    out_s24,

    output reg  [31:0]           cycle_count,
    output reg  [31:0]           accepted_weight_group_count,
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
    localparam [4:0] ST_ERROR = 5'd31;

    reg [4:0] state_r;
    reg control_error_r;
    reg [6:0] query_start_r;
    reg [7:0] valid_key_count_r;
    reg [6:0] expected_activation_group_r;
    reg [9:0] projection_tile_r;

    // RoPE coefficients are shared by all heads at the same query token and
    // pair-within-head: 8 tokens x 64 pairs.
    (* ram_style = "block" *) reg [35:0] rope_mem [0:511];

    // Current query Q and complete context are each exactly 96 KiB.  Split
    // the 768-bit query word into four physical 192-bit regions.  Each region
    // has its own local read-address capture, so head/row/group control drives
    // only four register copies instead of every synthesis-created replica
    // beside the wide BRAM columns.
    (* ram_style = "block" *) reg [191:0] query_mem_region0 [0:1023];
    (* ram_style = "block" *) reg [191:0] query_mem_region1 [0:1023];
    (* ram_style = "block" *) reg [191:0] query_mem_region2 [0:1023];
    (* ram_style = "block" *) reg [191:0] query_mem_region3 [0:1023];
    (* ram_style = "block" *) reg [383:0] context_mem [0:2047];
    (* keep = "true", dont_touch = "yes" *)
    reg [9:0] query_read_addr_region_r [0:3];
    reg [767:0] query_read_data_r;
    // RoPE produces one 48-bit pair per cycle in row-major order.  Assemble
    // all 16 pairs of one query group and then issue one full-width BRAM write.
    // This preserves the one-pair-per-cycle producer rate while allowing each
    // 192-bit region to infer a compact full-write block RAM instead of 192
    // independent bit-write RAMB18 primitives.
    reg [767:0] query_write_word_buffer_r;
    reg [767:0] query_write_word_r;
    (* keep = "true", dont_touch = "yes" *)
    reg [9:0] query_write_addr_region_r [0:3];
    reg query_write_valid_r;
    // Register the completed context write before the wide memory.  The old
    // direct expression let attention_head_r drive more than one thousand
    // distributed-RAM address pins over a 98.7%-routing path.  This one-entry
    // write pipeline accepts consecutive output tiles every cycle; max_fanout
    // allows implementation to replicate the local address copy beside the
    // RAM banks.  It changes neither memory contents nor Attention scheduling.
    (* max_fanout = 64 *) reg [10:0] context_write_addr_r;
    reg [383:0] context_write_data_r;
    reg context_write_valid_r;
    reg [6143:0] context_activation_buffer_r;

    // One completed 8x32 projection pair, organized as eight independent
    // 16-value rows.  During RoPE each row is consumed as a 48-bit shift
    // stream.  This keeps the storage cost equal to the former lower/upper
    // tile registers while replacing a 64:1 dynamic part-select (including
    // an inferred lane-base multiplier) with an 8:1 row select.
    reg [767:0] projection_pair_row_r [0:7];
    reg [767:0] post_group_s24_r [0:7];
    reg [7:0] rope_input_index_r;
    reg [7:0] rope_output_index_r;
    reg [3:0] quant_row_r;

    reg [2:0] attention_row_r;
    reg [5:0] attention_head_r;
    reg [2:0] attention_query_group_r;
    reg [6:0] attention_key_r;
    reg [2:0] attention_key_group_r;
    reg [6:0] attention_value_key_r;
    reg [6:0] context_group_r;
    reg [3:0] context_read_slot_r;

    wire projection_activation_ready;
    wire projection_activation_cached;
    wire projection_weight_ready;
    wire projection_out_valid;
    wire [8*16*24-1:0] projection_out_s24;
    wire projection_error;
    wire projection_activation_release =
        (state_r == ST_RELEASE_INPUT) ||
        (state_r == ST_RELEASE_CONTEXT);
    wire projection_start = (state_r == ST_PROJECT_START) &&
        projection_activation_cached;
    wire projection_out_ready = (state_r == ST_PROJECT_WAIT) &&
        ((projection_tile_r < 10'd384) || out_ready);
    wire projection_out_fire = projection_out_valid &&
        projection_out_ready;

    wire context_activation_valid = state_r == ST_CONTEXT_SEND;
    wire projection_activation_valid =
        ((state_r == ST_INPUT_FILL) && activation_valid &&
            (activation_group == expected_activation_group_r)) ||
        context_activation_valid;
    wire [6:0] projection_activation_group =
        context_activation_valid ? context_group_r : activation_group;
    wire [8*32*24-1:0] projection_activation_s24 =
        context_activation_valid ? context_activation_buffer_r : activation_s24;
    wire projection_activation_fire = projection_activation_valid &&
        projection_activation_ready;

    assign activation_ready = (state_r == ST_INPUT_FILL) &&
        projection_activation_ready &&
        (activation_group == expected_activation_group_r);
    assign weight_ready = (state_r == ST_WEIGHT) &&
        (weight_tile == projection_tile_r) && projection_weight_ready;
    wire weight_fire = weight_valid && weight_ready;

    assign out_valid = (state_r == ST_PROJECT_WAIT) &&
        (projection_tile_r >= 10'd384) && projection_out_valid;
    assign out_tile = projection_tile_r - 10'd384;
    assign out_s24 = projection_out_s24;

    hap_projection_core8x16 u_projection (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(projection_activation_valid),
        .activation_ready(projection_activation_ready),
        .activation_s24(projection_activation_s24),
        .activation_group(projection_activation_group),
        .activation_cached(projection_activation_cached),
        .activation_release(projection_activation_release),
        .project_start(projection_start),
        .weight_ready(projection_weight_ready),
        .weight_valid(weight_valid && (state_r == ST_WEIGHT) &&
            (weight_tile == projection_tile_r)),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16),
        .out_valid(projection_out_valid),
        .out_ready(projection_out_ready), .out_s24(projection_out_s24),
        .accepted_group_count(), .output_tile_count(),
        .saturation_count(), .error(projection_error)
    );

    wire rope_in_ready;
    wire rope_out_valid;
    wire signed [23:0] rope_out_y0_s24;
    wire signed [23:0] rope_out_y1_s24;
    wire rope_error;
    wire rope_feed_active = (state_r == ST_POST_ROPE) &&
        (rope_input_index_r < 8'd128);
    wire [2:0] rope_input_row = rope_input_index_r[6:4];
    wire [3:0] rope_input_pair = rope_input_index_r[3:0];
    wire [5:0] projection_group32 = projection_tile_r < 10'd256 ?
        projection_tile_r[7:1] % 4 :
        ((projection_tile_r < 10'd320 ? projection_tile_r - 10'd256 :
          projection_tile_r - 10'd320) >> 1) % 4;
    wire [8:0] rope_read_addr = {rope_input_row, projection_group32[1:0],
        rope_input_pair};
    wire [35:0] rope_coeff = rope_mem[rope_read_addr];
    wire [47:0] rope_input_pair_s24 =
        projection_pair_row_r[rope_input_row][47:0];
    wire rope_in_fire = rope_feed_active && rope_in_ready;
    wire rope_out_fire = rope_out_valid;

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

    wire kv_quant4_in_ready;
    wire kv_quant4_out_valid;
    wire [1:0] kv_quant4_out_lane;
    wire kv_quant4_out_batch_last;
    wire [383:0] kv_quant4_out_s12;
    wire [15:0] kv_quant4_out_meta;
    wire kv_quant_error;
    wire cache_wr_ready;
    wire kv_quant4_in_valid = state_r == ST_POST_QUANT;
    wire [4*768-1:0] kv_quant4_in_s24 = {
        post_group_s24_r[quant_row_r[2:0] + 3],
        post_group_s24_r[quant_row_r[2:0] + 2],
        post_group_s24_r[quant_row_r[2:0] + 1],
        post_group_s24_r[quant_row_r[2:0] + 0]
    };
    wire kv_quant4_out_ready = (state_r == ST_POST_QUANT) && cache_wr_ready;
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
    wire [2:0] quant_selected_row =
        quant_row_r[2:0] + kv_quant4_out_lane;
    wire [6:0] quant_token = query_start_r + quant_selected_row;
    wire [2:0] quant_head = quant_is_v ?
        (projection_tile_r - 10'd320) >> 3 :
        (projection_tile_r - 10'd256) >> 3;
    wire [1:0] quant_group = quant_is_v ?
        ((projection_tile_r - 10'd320) >> 1) & 2'b11 :
        ((projection_tile_r - 10'd256) >> 1) & 2'b11;
    wire cache_wr_from_quant = (state_r == ST_POST_QUANT) &&
        kv_quant4_out_valid;
    wire cache_wr_from_preload = (state_r == ST_IDLE) &&
        kv_preload_valid && !start;
    wire cache_wr_valid = cache_wr_from_quant || cache_wr_from_preload;
    wire cache_wr_is_v = cache_wr_from_quant ? quant_is_v :
        kv_preload_is_v;
    wire [11:0] cache_wr_addr = cache_wr_from_quant ?
        kv_addr(quant_head, quant_token, quant_group) : kv_preload_addr;
    wire [383:0] cache_wr_s12 = cache_wr_from_quant ?
        kv_quant4_out_s12 : kv_preload_s12;
    wire [15:0] cache_wr_meta = cache_wr_from_quant ?
        kv_quant4_out_meta : kv_preload_meta16;
    assign kv_preload_ready = (state_r == ST_IDLE) && !start &&
        cache_wr_ready;

    wire [7:0] attention_causal_key_count =
        {1'b0, query_start_r} + {5'd0, attention_row_r} + 8'd1;
    wire [7:0] attention_row_key_count =
        attention_causal_key_count < valid_key_count_r ?
        attention_causal_key_count : valid_key_count_r;
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

    hap_kv12_cache u_kv_cache (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(cache_wr_valid), .wr_ready(cache_wr_ready),
        .wr_is_v(cache_wr_is_v), .wr_addr(cache_wr_addr),
        .wr_s12(cache_wr_s12), .wr_meta(cache_wr_meta),
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
        .k_write_count(), .v_write_count(), .k_read_count(), .v_read_count(),
        .format_error_count(), .error(cache_error)
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
    assign cache_k_rsp_ready = (state_r == ST_ATT_K_SEND) && row_key_ready;
    assign cache_v_rsp_ready = (state_r == ST_ATT_V_SEND) && row_value_ready;

    hap_attention_row_head128 u_attention_row (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .row_key_count(attention_row_key_count),
        .query_load_valid(row_query_valid),
        .query_load_ready(row_query_load_ready),
        .query_load_group(attention_query_group_r[1:0]),
        .query_load_s24(query_read_data_r), .query_ready(row_query_ready),
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

    assign rope_wr_ready = state_r == ST_IDLE;
    assign busy = state_r != ST_IDLE;
    assign error = control_error_r | projection_error | rope_error |
        kv_quant_error | cache_error | row_error;

    integer row_index;
    always @(posedge clk) begin
        if (rope_wr_valid && rope_wr_ready)
            rope_mem[rope_wr_addr] <= {rope_wr_sin_s18, rope_wr_cos_s18};

        if (projection_out_fire && (projection_tile_r < 10'd384)) begin
            for (row_index = 0; row_index < 8; row_index = row_index + 1) begin
                if (!projection_tile_r[0])
                    projection_pair_row_r[row_index][0 +: 384] <=
                        projection_out_s24[row_index*384 +: 384];
                else
                    projection_pair_row_r[row_index][384 +: 384] <=
                        projection_out_s24[row_index*384 +: 384];
            end
        end

        if (projection_out_fire && projection_tile_r[0] &&
                (projection_tile_r >= 10'd320) &&
                (projection_tile_r < 10'd384)) begin
            for (row_index = 0; row_index < 8; row_index = row_index + 1)
                post_group_s24_r[row_index] <= {
                    projection_out_s24[row_index*384 +: 384],
                    projection_pair_row_r[row_index][0 +: 384]};
        end

        if (rope_in_fire)
            projection_pair_row_r[rope_input_row] <=
                {48'd0, projection_pair_row_r[rope_input_row][767:48]};

        if (query_write_valid_r && rst_n && !clear) begin
            query_mem_region0[query_write_addr_region_r[0]] <=
                query_write_word_r[191:0];
            query_mem_region1[query_write_addr_region_r[1]] <=
                query_write_word_r[383:192];
            query_mem_region2[query_write_addr_region_r[2]] <=
                query_write_word_r[575:384];
            query_mem_region3[query_write_addr_region_r[3]] <=
                query_write_word_r[767:576];
        end

        if (rope_out_fire && (projection_tile_r < 10'd256)) begin
            query_write_word_buffer_r[
                rope_output_index_r[3:0]*48 +: 48] <=
                {rope_out_y1_s24, rope_out_y0_s24};
            if (rope_output_index_r[3:0] == 4'd15) begin
                query_write_word_r <= {
                    rope_out_y1_s24, rope_out_y0_s24,
                    query_write_word_buffer_r[719:0]};
                query_write_addr_region_r[0] <=
                    rope_output_index_r[6:4]*128 +
                    (projection_tile_r >> 3)*4 +
                    ((projection_tile_r & 10'd7) >> 1);
                query_write_addr_region_r[1] <=
                    rope_output_index_r[6:4]*128 +
                    (projection_tile_r >> 3)*4 +
                    ((projection_tile_r & 10'd7) >> 1);
                query_write_addr_region_r[2] <=
                    rope_output_index_r[6:4]*128 +
                    (projection_tile_r >> 3)*4 +
                    ((projection_tile_r & 10'd7) >> 1);
                query_write_addr_region_r[3] <=
                    rope_output_index_r[6:4]*128 +
                    (projection_tile_r >> 3)*4 +
                    ((projection_tile_r & 10'd7) >> 1);
            end
        end

        if (rope_out_fire) begin
            if (projection_tile_r >= 10'd256) begin
                post_group_s24_r[rope_output_index_r[6:4]][
                    rope_output_index_r[3:0]*48 +: 48] <=
                    {rope_out_y1_s24, rope_out_y0_s24};
            end
        end

        if (state_r == ST_ATT_Q_READ) begin
            query_read_addr_region_r[0] <= {attention_row_r,
                attention_head_r[4:0], attention_query_group_r[1:0]};
            query_read_addr_region_r[1] <= {attention_row_r,
                attention_head_r[4:0], attention_query_group_r[1:0]};
            query_read_addr_region_r[2] <= {attention_row_r,
                attention_head_r[4:0], attention_query_group_r[1:0]};
            query_read_addr_region_r[3] <= {attention_row_r,
                attention_head_r[4:0], attention_query_group_r[1:0]};
        end

        if (state_r == ST_ATT_Q_DATA) begin
            query_read_data_r[191:0] <=
                query_mem_region0[query_read_addr_region_r[0]];
            query_read_data_r[383:192] <=
                query_mem_region1[query_read_addr_region_r[1]];
            query_read_data_r[575:384] <=
                query_mem_region2[query_read_addr_region_r[2]];
            query_read_data_r[767:576] <=
                query_mem_region3[query_read_addr_region_r[3]];
        end

        if (context_write_valid_r && rst_n && !clear)
            context_mem[context_write_addr_r] <= context_write_data_r;

        if (row_out_fire) begin
            context_write_addr_r <= attention_row_r*256 +
                attention_head_r*8 + row_out_tile_index;
            context_write_data_r <= row_out_context_s24;
        end

        if (state_r == ST_CONTEXT_READ)
            context_activation_buffer_r[
                context_read_slot_r[3:1]*768 +
                context_read_slot_r[0]*384 +: 384] <=
                context_mem[context_read_slot_r[3:1]*256 +
                    context_group_r*2 + context_read_slot_r[0]];
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_IDLE;
            control_error_r <= 1'b0;
            done <= 1'b0;
            query_start_r <= 7'd0;
            valid_key_count_r <= 8'd0;
            expected_activation_group_r <= 7'd0;
            projection_tile_r <= 10'd0;
            rope_input_index_r <= 8'd0;
            rope_output_index_r <= 8'd0;
            quant_row_r <= 4'd0;
            attention_row_r <= 3'd0;
            attention_head_r <= 6'd0;
            attention_query_group_r <= 3'd0;
            attention_key_r <= 7'd0;
            attention_key_group_r <= 3'd0;
            attention_value_key_r <= 7'd0;
            context_group_r <= 7'd0;
            context_read_slot_r <= 4'd0;
            context_write_valid_r <= 1'b0;
            query_write_valid_r <= 1'b0;
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
            state_r <= ST_IDLE;
            control_error_r <= 1'b0;
            done <= 1'b0;
            expected_activation_group_r <= 7'd0;
            projection_tile_r <= 10'd0;
            rope_input_index_r <= 8'd0;
            rope_output_index_r <= 8'd0;
            quant_row_r <= 4'd0;
            attention_row_r <= 3'd0;
            attention_head_r <= 6'd0;
            attention_query_group_r <= 3'd0;
            attention_key_r <= 7'd0;
            attention_key_group_r <= 3'd0;
            attention_value_key_r <= 7'd0;
            context_group_r <= 7'd0;
            context_read_slot_r <= 4'd0;
            context_write_valid_r <= 1'b0;
            query_write_valid_r <= 1'b0;
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
            // The memory always block consumes the previous cycle's valid,
            // while this assignment records the current output acceptance.
            context_write_valid_r <= row_out_fire;
            query_write_valid_r <= rope_out_fire &&
                (projection_tile_r < 10'd256) &&
                (rope_output_index_r[3:0] == 4'd15);
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
                ST_CONTEXT_READ, ST_CONTEXT_SEND, ST_CONTEXT_WAIT:
                    context_frontend_cycle_count <=
                        context_frontend_cycle_count + 32'd1;
                ST_IDLE: begin end
                default:
                    control_overhead_cycle_count <=
                        control_overhead_cycle_count + 32'd1;
            endcase

            if ((state_r == ST_IDLE) && start) begin
                if ((format_id != FORMAT_ID) ||
                    (query_start > 7'd120) ||
                    (valid_key_count == 0) ||
                    (valid_key_count > 8'd128) ||
                    ({1'b0, query_start} + 8'd8 > valid_key_count)) begin
                    control_error_r <= 1'b1;
                    state_r <= ST_ERROR;
                end else begin
                    query_start_r <= query_start;
                    valid_key_count_r <= valid_key_count;
                    expected_activation_group_r <= 7'd0;
                    projection_tile_r <= 10'd0;
                    attention_row_r <= 3'd0;
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
                    (activation_group != expected_activation_group_r))
                control_error_r <= 1'b1;
            if ((state_r == ST_INPUT_FILL) && projection_activation_fire) begin
                if (expected_activation_group_r == 7'd127)
                    state_r <= ST_INPUT_WAIT;
                else
                    expected_activation_group_r <=
                        expected_activation_group_r + 1'b1;
            end
            if ((state_r == ST_INPUT_WAIT) && projection_activation_cached)
                state_r <= ST_PROJECT_START;

            if (projection_start)
                state_r <= ST_WEIGHT;

            if (weight_fire) begin
                accepted_weight_group_count <=
                    accepted_weight_group_count + 32'd1;
                if (weight_group == 7'd127)
                    state_r <= ST_PROJECT_WAIT;
            end

            if (projection_out_fire) begin
                completed_projection_tile_count <=
                    completed_projection_tile_count + 32'd1;
                if (projection_tile_r >= 10'd384) begin
                    completed_wo_tile_count <= completed_wo_tile_count + 32'd1;
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
                    rope_input_index_r <= 8'd0;
                    rope_output_index_r <= 8'd0;
                    state_r <= ST_POST_ROPE;
                end else begin
                    quant_row_r <= 4'd0;
                    state_r <= ST_POST_QUANT;
                end
            end

            if (rope_in_fire)
                rope_input_index_r <= rope_input_index_r + 1'b1;
            if (rope_out_fire && (state_r == ST_POST_ROPE)) begin
                rope_output_index_r <= rope_output_index_r + 1'b1;
                if (rope_output_index_r == 8'd127) begin
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
                if (quant_row_r == 4'd4) begin
                    quant_row_r <= 4'd0;
                    if (projection_tile_r == 10'd383)
                        state_r <= ST_RELEASE_INPUT;
                    else begin
                        projection_tile_r <= projection_tile_r + 1'b1;
                        state_r <= ST_PROJECT_START;
                    end
                end else begin
                    quant_row_r <= 4'd4;
                end
            end

            if (state_r == ST_RELEASE_INPUT) begin
                attention_row_r <= 3'd0;
                attention_head_r <= 6'd0;
                attention_query_group_r <= 3'd0;
                state_r <= ST_ATT_Q_READ;
            end

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
                    if ((attention_row_r == 3'd7) &&
                            (attention_head_r == 6'd31)) begin
                        context_group_r <= 7'd0;
                        context_read_slot_r <= 4'd0;
                        state_r <= ST_CONTEXT_READ;
                    end else begin
                        if (attention_head_r == 6'd31) begin
                            attention_head_r <= 6'd0;
                            attention_row_r <= attention_row_r + 1'b1;
                        end else begin
                            attention_head_r <= attention_head_r + 1'b1;
                        end
                        attention_query_group_r <= 3'd0;
                        state_r <= ST_ATT_Q_READ;
                    end
                end else begin
                    attention_value_key_r <= 7'd0;
                    state_r <= ST_ATT_VALUE_WAIT;
                end
            end

            if (state_r == ST_CONTEXT_READ) begin
                if (context_read_slot_r == 4'd15)
                    state_r <= ST_CONTEXT_SEND;
                else
                    context_read_slot_r <= context_read_slot_r + 1'b1;
            end
            if ((state_r == ST_CONTEXT_SEND) &&
                    projection_activation_ready) begin
                if (context_group_r == 7'd127)
                    state_r <= ST_CONTEXT_WAIT;
                else begin
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

            if (state_r == ST_RELEASE_CONTEXT) begin
                done <= 1'b1;
                state_r <= ST_IDLE;
            end

            if (projection_error || rope_error || kv_quant_error ||
                    cache_error || row_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

endmodule
