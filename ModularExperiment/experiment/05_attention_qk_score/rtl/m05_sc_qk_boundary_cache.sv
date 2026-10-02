`timescale 1ns / 1ps

// Isolated boundary-inclusive SC QK slot.  A complete row is loaded through a
// common II=2 interface, retained as four Q S24 groups plus 512 compact
// K S12+ScaleCode group records, then replayed into the unmodified production
// QK implementation.  Cache storage and replay control are inside this top.
module m05_sc_qk_boundary_cache (
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
    input  wire [15:0]           key_load_meta16,
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
    output reg                   error
);
    localparam [1:0] ST_LOAD = 2'd0;
    localparam [1:0] ST_QUERY_REPLAY = 2'd1;
    localparam [1:0] ST_KEY_REPLAY = 2'd2;

    reg [1:0] state_r;
    reg load_cooldown_r;
    reg [2:0] query_load_count_r;
    reg [9:0] expected_key_address_r;
    reg key_load_complete_r;
    reg [8:0] last_key_address_r;
    reg current_key_mask_r;

    reg [32*24-1:0] query_group0_r;
    reg [32*24-1:0] query_group1_r;
    reg [32*24-1:0] query_group2_r;
    reg [32*24-1:0] query_group3_r;
    reg [1:0] query_replay_group_r;
    reg [32*24-1:0] selected_query_s24;

    (* ram_style = "block" *) reg [399:0] key_cache_mem [0:511];
    reg key_mask_mem [0:127];
    reg [9:0] cache_read_index_r;
    reg cache_buffer_valid_r;
    reg [8:0] cache_buffer_address_r;
    reg [399:0] cache_buffer_data_r;
    reg cache_buffer_mask_r;

    wire query_load_fire = query_load_valid && query_load_ready;
    wire key_load_fire = key_load_valid && key_load_ready;
    wire start_fire = start_valid && start_ready;
    wire [8:0] key_load_address = {key_load_index,key_load_group};
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

    assign query_load_ready = rst_n && !clear && state_r == ST_LOAD &&
        query_load_count_r < 4 && !load_cooldown_r;
    assign key_load_ready = rst_n && !clear && state_r == ST_LOAD &&
        query_load_count_r == 4 && !key_load_complete_r &&
        !load_cooldown_r;
    assign start_ready = rst_n && !clear && state_r == ST_LOAD &&
        query_load_count_r == 4 && key_load_complete_r &&
        !load_cooldown_r;

    always @* begin
        case (query_replay_group_r)
            2'd0: selected_query_s24 = query_group0_r;
            2'd1: selected_query_s24 = query_group1_r;
            2'd2: selected_query_s24 = query_group2_r;
            default: selected_query_s24 = query_group3_r;
        endcase
    end

    hap_qk_score_row_128 u_qk (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .query_load_valid(state_r == ST_QUERY_REPLAY),
        .query_load_ready(core_query_load_ready),
        .query_load_group(query_replay_group_r),
        .query_load_s24(selected_query_s24), .query_ready(core_query_ready),
        .in_valid(cache_buffer_valid_r), .in_ready(core_in_ready),
        .in_first_key(cache_buffer_address_r == 0),
        .in_last_key(cache_buffer_address_r == last_key_address_r),
        .in_group(cache_buffer_address_r[1:0]),
        .in_mask(cache_buffer_mask_r),
        .in_key_s12(cache_buffer_data_r[0 +: 384]),
        .in_key_meta16(cache_buffer_data_r[384 +: 16]),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_score_q14_s20(out_score_q14_s20), .out_mask(out_mask),
        .out_key_index(out_key_index), .out_last_key(out_last_key),
        .input_group_count(input_group_count),
        .output_score_count(output_score_count), .clip_count(clip_count),
        .error(core_error));

    always @(posedge clk) begin
        if (query_load_fire) begin
            case (query_load_group)
                2'd0: query_group0_r <= query_load_s24;
                2'd1: query_group1_r <= query_load_s24;
                2'd2: query_group2_r <= query_load_s24;
                default: query_group3_r <= query_load_s24;
            endcase
        end
        if (key_load_fire) begin
            key_cache_mem[key_load_address] <= {key_load_meta16,key_load_s12};
            if (key_load_group == 3)
                key_mask_mem[key_load_index] <= key_load_mask;
        end
        if (cache_read_enable) begin
            cache_buffer_data_r <= key_cache_mem[cache_read_index_r[8:0]];
            cache_buffer_mask_r <= key_mask_mem[cache_read_index_r[8:2]];
            cache_buffer_address_r <= cache_read_index_r[8:0];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_LOAD;
            load_cooldown_r <= 1'b0;
            query_load_count_r <= 3'd0;
            expected_key_address_r <= 10'd0;
            key_load_complete_r <= 1'b0;
            last_key_address_r <= 9'd0;
            current_key_mask_r <= 1'b0;
            query_replay_group_r <= 2'd0;
            cache_read_index_r <= 10'd0;
            cache_buffer_valid_r <= 1'b0;
            query_cache_write_count <= 32'd0;
            key_cache_write_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            state_r <= ST_LOAD;
            load_cooldown_r <= 1'b0;
            query_load_count_r <= 3'd0;
            expected_key_address_r <= 10'd0;
            key_load_complete_r <= 1'b0;
            last_key_address_r <= 9'd0;
            current_key_mask_r <= 1'b0;
            query_replay_group_r <= 2'd0;
            cache_read_index_r <= 10'd0;
            cache_buffer_valid_r <= 1'b0;
            query_cache_write_count <= 32'd0;
            key_cache_write_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (load_cooldown_r)
                load_cooldown_r <= 1'b0;
            if (query_load_fire || key_load_fire)
                load_cooldown_r <= 1'b1;

            if (query_load_fire) begin
                if (query_load_group != query_load_count_r[1:0])
                    error <= 1'b1;
                query_load_count_r <= query_load_count_r + 1'b1;
                query_cache_write_count <= query_cache_write_count + 1'b1;
            end

            if (key_load_fire) begin
                if ({1'b0,key_load_address} != expected_key_address_r ||
                    key_load_meta16[15:14] != 0 ||
                    ((key_load_meta16[7:0] == 0) &&
                     (key_load_meta16[13:8] != 0)) ||
                    ((key_load_meta16[7:0] != 0) &&
                     ((key_load_meta16[13:8] < 8) ||
                      (key_load_meta16[13:8] > 32))))
                    error <= 1'b1;
                if (key_load_group == 0)
                    current_key_mask_r <= key_load_mask;
                else if (key_load_mask != current_key_mask_r)
                    error <= 1'b1;
                if (key_load_last && key_load_group != 3)
                    error <= 1'b1;
                if (key_load_last) begin
                    key_load_complete_r <= 1'b1;
                    last_key_address_r <= key_load_address;
                end
                expected_key_address_r <= expected_key_address_r + 1'b1;
                key_cache_write_count <= key_cache_write_count + 1'b1;
            end

            if (start_fire) begin
                if (last_key_address_r[1:0] != 3 ||
                    expected_key_address_r !=
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
                end else if (core_input_fire) begin
                    cache_buffer_valid_r <= 1'b0;
                end
                if (out_valid && out_ready && out_last_key) begin
                    state_r <= ST_LOAD;
                    load_cooldown_r <= 1'b0;
                    query_load_count_r <= 3'd0;
                    expected_key_address_r <= 10'd0;
                    key_load_complete_r <= 1'b0;
                    last_key_address_r <= 9'd0;
                    cache_buffer_valid_r <= 1'b0;
                end
            end else if (state_r != ST_QUERY_REPLAY) begin
                cache_buffer_valid_r <= 1'b0;
            end

            if (core_error ||
                (query_load_valid && key_load_valid) ||
                (start_valid && (query_load_valid || key_load_valid)) ||
                (state_r == ST_KEY_REPLAY && !core_query_ready) ||
                (cache_buffer_valid_r &&
                 cache_buffer_address_r > last_key_address_r))
                error <= 1'b1;
        end
    end
endmodule
