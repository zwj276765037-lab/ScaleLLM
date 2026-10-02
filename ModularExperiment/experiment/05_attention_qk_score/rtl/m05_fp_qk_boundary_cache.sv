`timescale 1ns / 1ps

// Boundary-inclusive FP QK slot.  The shared 16-lane conversion frontend
// materializes Q and K from the common integer boundary, K is retained in a
// complete 128-key FP cache, and the cached row is replayed into the existing
// matched-throughput 16-lane QK implementation.
module m05_fp_qk_boundary_cache #(
    parameter integer FP_W = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  query_load_valid,
    output wire                  query_load_ready,
    input  wire [1:0]            query_load_group,
    input  wire [32*24-1:0]      query_load_s24,
    input  wire                  key_load_valid,
    output wire                  key_load_ready,
    input  wire [6:0]            key_load_index,
    input  wire [1:0]            key_load_group,
    input  wire [32*12-1:0]      key_load_s12,
    input  wire [FP_W-1:0]       key_load_scale_fp,
    input  wire                  key_load_mask,
    input  wire                  key_load_last,
    input  wire                  start_valid,
    output wire                  start_ready,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [19:0]    out_score_q14_s20,
    output wire                  out_mask,
    output wire [6:0]            out_key_index,
    output wire                  out_last_key,
    output wire [31:0]           input_group_count,
    output wire [31:0]           output_score_count,
    output wire [31:0]           clip_count,
    output reg  [31:0]           query_cache_write_count,
    output reg  [31:0]           key_cache_write_count,
    output wire                  frontend_idle,
    output reg                   error
);
    localparam [2:0] ST_QUERY_LOAD = 3'd0;
    localparam [2:0] ST_QUERY_DRAIN = 3'd1;
    localparam [2:0] ST_KEY_LOAD = 3'd2;
    localparam [2:0] ST_KEY_DRAIN = 3'd3;
    localparam [2:0] ST_QUERY_REPLAY = 3'd4;
    localparam [2:0] ST_KEY_REPLAY = 3'd5;

    reg [2:0] state_r;
    reg [2:0] query_accept_count_r;
    reg [2:0] query_row_write_count_r;
    reg [9:0] expected_key_address_r;
    reg [9:0] expected_key_output_address_r;
    reg key_output_complete_r;
    reg [8:0] last_key_address_r;
    reg current_key_mask_r;
    reg [1:0] query_replay_group_r;

    reg [32*FP_W-1:0] query_group0_r;
    reg [32*FP_W-1:0] query_group1_r;
    reg [32*FP_W-1:0] query_group2_r;
    reg [32*FP_W-1:0] query_group3_r;
    reg [32*FP_W-1:0] selected_query_fp;
    (* ram_style = "block" *) reg [32*FP_W-1:0] key_cache_mem [0:511];
    reg key_mask_mem [0:127];

    reg [9:0] cache_read_index_r;
    reg cache_buffer_valid_r;
    reg [8:0] cache_buffer_address_r;
    reg [32*FP_W-1:0] cache_buffer_data_r;
    reg cache_buffer_mask_r;

    wire frontend_in_ready;
    wire frontend_in_valid =
        (state_r == ST_QUERY_LOAD && query_load_valid) ||
        (state_r == ST_KEY_LOAD && key_load_valid);
    wire frontend_in_is_key = state_r == ST_KEY_LOAD;
    wire [8:0] key_load_address = {key_load_index,key_load_group};
    wire [8:0] frontend_in_address = frontend_in_is_key ?
        key_load_address : {{7{1'b0}},query_load_group};
    wire frontend_out_valid;
    wire frontend_out_is_key;
    wire [8:0] frontend_out_address;
    wire [32*FP_W-1:0] frontend_out_group;
    wire [31:0] frontend_input_count;
    wire [31:0] frontend_output_count;
    wire frontend_error;

    assign query_load_ready = rst_n && !clear &&
        state_r == ST_QUERY_LOAD && frontend_in_ready;
    assign key_load_ready = rst_n && !clear &&
        state_r == ST_KEY_LOAD && frontend_in_ready;
    wire query_load_fire = query_load_valid && query_load_ready;
    wire key_load_fire = key_load_valid && key_load_ready;
    assign start_ready = rst_n && !clear && state_r == ST_KEY_DRAIN &&
        key_output_complete_r && frontend_idle;
    wire start_fire = start_valid && start_ready;

    m05_fp_group32_dequant16 #(.FP_W(FP_W)) u_frontend (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(frontend_in_valid), .in_ready(frontend_in_ready),
        .in_is_key(frontend_in_is_key),
        .in_address(frontend_in_address),
        .in_query_s24x32(query_load_s24),
        .in_key_s12x32(key_load_s12),
        .in_key_scale_fp(key_load_scale_fp),
        .out_valid(frontend_out_valid),
        .out_is_key(frontend_out_is_key),
        .out_address(frontend_out_address),
        .out_group_fp(frontend_out_group),
        .input_group_count(frontend_input_count),
        .output_group_count(frontend_output_count),
        .idle(frontend_idle), .error(frontend_error));

    always @* begin
        case (query_replay_group_r)
            2'd0: selected_query_fp = query_group0_r;
            2'd1: selected_query_fp = query_group1_r;
            2'd2: selected_query_fp = query_group2_r;
            default: selected_query_fp = query_group3_r;
        endcase
    end

    wire core_query_load_ready;
    wire core_query_ready;
    wire core_in_ready;
    wire core_error;
    wire core_query_fire = state_r == ST_QUERY_REPLAY &&
        core_query_load_ready;
    wire core_input_fire = cache_buffer_valid_r && core_in_ready;
    wire cache_read_enable = state_r == ST_KEY_REPLAY &&
        (!cache_buffer_valid_r || core_input_fire) &&
        cache_read_index_r <= {1'b0,last_key_address_r};

    m7_fp_qk_slot_arch #(.FP_W(FP_W)) u_qk (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .query_load_valid(state_r == ST_QUERY_REPLAY),
        .query_load_ready(core_query_load_ready),
        .query_load_group(query_replay_group_r),
        .query_group_fp(selected_query_fp), .query_ready(core_query_ready),
        .in_valid(cache_buffer_valid_r), .in_ready(core_in_ready),
        .in_first_key(cache_buffer_address_r == 0),
        .in_last_key(cache_buffer_address_r == last_key_address_r),
        .in_group(cache_buffer_address_r[1:0]),
        .in_mask(cache_buffer_mask_r),
        .key_group_fp(cache_buffer_data_r),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_score_q14_s20(out_score_q14_s20), .out_mask(out_mask),
        .out_key_index(out_key_index), .out_last_key(out_last_key),
        .input_group_count(input_group_count),
        .output_score_count(output_score_count), .clip_count(clip_count),
        .error(core_error));

    always @(posedge clk) begin
        if (frontend_out_valid && !frontend_out_is_key) begin
            case (frontend_out_address[1:0])
                2'd0: query_group0_r <= frontend_out_group;
                2'd1: query_group1_r <= frontend_out_group;
                2'd2: query_group2_r <= frontend_out_group;
                default: query_group3_r <= frontend_out_group;
            endcase
        end
        if (frontend_out_valid && frontend_out_is_key)
            key_cache_mem[frontend_out_address] <= frontend_out_group;
        if (key_load_fire && key_load_group == 3)
            key_mask_mem[key_load_index] <= key_load_mask;
        if (cache_read_enable) begin
            cache_buffer_data_r <= key_cache_mem[cache_read_index_r[8:0]];
            cache_buffer_mask_r <= key_mask_mem[cache_read_index_r[8:2]];
            cache_buffer_address_r <= cache_read_index_r[8:0];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_QUERY_LOAD;
            query_accept_count_r <= 3'd0;
            query_row_write_count_r <= 3'd0;
            expected_key_address_r <= 10'd0;
            expected_key_output_address_r <= 10'd0;
            key_output_complete_r <= 1'b0;
            last_key_address_r <= 9'd0;
            current_key_mask_r <= 1'b0;
            query_replay_group_r <= 2'd0;
            cache_read_index_r <= 10'd0;
            cache_buffer_valid_r <= 1'b0;
            query_cache_write_count <= 32'd0;
            key_cache_write_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_QUERY_LOAD;
            query_accept_count_r <= 3'd0;
            query_row_write_count_r <= 3'd0;
            expected_key_address_r <= 10'd0;
            expected_key_output_address_r <= 10'd0;
            key_output_complete_r <= 1'b0;
            last_key_address_r <= 9'd0;
            current_key_mask_r <= 1'b0;
            query_replay_group_r <= 2'd0;
            cache_read_index_r <= 10'd0;
            cache_buffer_valid_r <= 1'b0;
            query_cache_write_count <= 32'd0;
            key_cache_write_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (query_load_fire) begin
                if (query_load_group != query_accept_count_r[1:0])
                    error <= 1'b1;
                query_accept_count_r <= query_accept_count_r + 1'b1;
                if (query_accept_count_r == 3)
                    state_r <= ST_QUERY_DRAIN;
            end

            if (frontend_out_valid && !frontend_out_is_key) begin
                if (frontend_out_address != query_row_write_count_r ||
                    (state_r != ST_QUERY_LOAD &&
                     state_r != ST_QUERY_DRAIN))
                    error <= 1'b1;
                query_row_write_count_r <= query_row_write_count_r + 1'b1;
                query_cache_write_count <= query_cache_write_count + 1'b1;
            end
            if (state_r == ST_QUERY_DRAIN && frontend_idle &&
                query_row_write_count_r == 4)
                state_r <= ST_KEY_LOAD;

            if (key_load_fire) begin
                if ({1'b0,key_load_address} != expected_key_address_r)
                    error <= 1'b1;
                if (key_load_group == 0)
                    current_key_mask_r <= key_load_mask;
                else if (key_load_mask != current_key_mask_r)
                    error <= 1'b1;
                if (key_load_last && key_load_group != 3)
                    error <= 1'b1;
                if (key_load_last) begin
                    last_key_address_r <= key_load_address;
                    state_r <= ST_KEY_DRAIN;
                end
                expected_key_address_r <= expected_key_address_r + 1'b1;
            end

            if (frontend_out_valid && frontend_out_is_key) begin
                if ({1'b0,frontend_out_address} !=
                        expected_key_output_address_r ||
                    (state_r != ST_KEY_LOAD && state_r != ST_KEY_DRAIN))
                    error <= 1'b1;
                expected_key_output_address_r <=
                    expected_key_output_address_r + 1'b1;
                key_cache_write_count <= key_cache_write_count + 1'b1;
                if (frontend_out_address == last_key_address_r)
                    key_output_complete_r <= 1'b1;
            end

            if (start_fire) begin
                if (last_key_address_r[1:0] != 3 ||
                    expected_key_address_r !=
                        {1'b0,last_key_address_r} + 10'd1 ||
                    expected_key_output_address_r !=
                        {1'b0,last_key_address_r} + 10'd1)
                    error <= 1'b1;
                state_r <= ST_QUERY_REPLAY;
                query_replay_group_r <= 2'd0;
                cache_read_index_r <= 10'd0;
                cache_buffer_valid_r <= 1'b0;
            end

            if (state_r == ST_QUERY_REPLAY && core_query_fire) begin
                if (query_replay_group_r == 3) begin
                    state_r <= ST_KEY_REPLAY;
                    query_replay_group_r <= 2'd0;
                end else
                    query_replay_group_r <= query_replay_group_r + 1'b1;
            end

            if (state_r == ST_KEY_REPLAY) begin
                if (cache_read_enable) begin
                    cache_buffer_valid_r <= 1'b1;
                    cache_read_index_r <= cache_read_index_r + 1'b1;
                end else if (core_input_fire)
                    cache_buffer_valid_r <= 1'b0;
                if (out_valid && out_ready && out_last_key) begin
                    state_r <= ST_QUERY_LOAD;
                    query_accept_count_r <= 3'd0;
                    query_row_write_count_r <= 3'd0;
                    expected_key_address_r <= 10'd0;
                    expected_key_output_address_r <= 10'd0;
                    key_output_complete_r <= 1'b0;
                    last_key_address_r <= 9'd0;
                    cache_buffer_valid_r <= 1'b0;
                end
            end else if (state_r != ST_QUERY_REPLAY)
                cache_buffer_valid_r <= 1'b0;

            if (frontend_error || core_error ||
                (query_load_valid && key_load_valid) ||
                (start_valid && (query_load_valid || key_load_valid)) ||
                (state_r == ST_KEY_REPLAY && !core_query_ready) ||
                (cache_buffer_valid_r &&
                 cache_buffer_address_r > last_key_address_r) ||
                (frontend_input_count < frontend_output_count))
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m05_fp_qk_boundary_cache FP_W must be 16 or 32");
    end
endmodule


module m05_fp16_qk_boundary_cache (
    input wire clk, rst_n, clear,
    input wire query_load_valid,
    output wire query_load_ready,
    input wire [1:0] query_load_group,
    input wire [32*24-1:0] query_load_s24,
    input wire key_load_valid,
    output wire key_load_ready,
    input wire [6:0] key_load_index,
    input wire [1:0] key_load_group,
    input wire [32*12-1:0] key_load_s12,
    input wire [15:0] key_load_scale_fp,
    input wire key_load_mask, key_load_last, start_valid,
    output wire start_ready, out_valid,
    input wire out_ready,
    output wire signed [19:0] out_score_q14_s20,
    output wire out_mask,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output wire [31:0] input_group_count, output_score_count, clip_count,
    query_cache_write_count, key_cache_write_count,
    output wire frontend_idle, error
);
    m05_fp_qk_boundary_cache #(.FP_W(16)) u_core (.*);
endmodule


module m05_fp32_qk_boundary_cache (
    input wire clk, rst_n, clear,
    input wire query_load_valid,
    output wire query_load_ready,
    input wire [1:0] query_load_group,
    input wire [32*24-1:0] query_load_s24,
    input wire key_load_valid,
    output wire key_load_ready,
    input wire [6:0] key_load_index,
    input wire [1:0] key_load_group,
    input wire [32*12-1:0] key_load_s12,
    input wire [31:0] key_load_scale_fp,
    input wire key_load_mask, key_load_last, start_valid,
    output wire start_ready, out_valid,
    input wire out_ready,
    output wire signed [19:0] out_score_q14_s20,
    output wire out_mask,
    output wire [6:0] out_key_index,
    output wire out_last_key,
    output wire [31:0] input_group_count, output_score_count, clip_count,
    query_cache_write_count, key_cache_write_count,
    output wire frontend_idle, error
);
    m05_fp_qk_boundary_cache #(.FP_W(32)) u_core (.*);
endmodule
