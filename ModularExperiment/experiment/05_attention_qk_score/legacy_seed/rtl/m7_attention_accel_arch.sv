`timescale 1ns/1ps

// Attention-stage scheduler extracted from hap_attention_compute_top.  One
// physical row/QK slot is reused in row-major/head-major order.  Query and
// key memory data are external so the same synthesizable scheduler can be
// driven by the architecture vector memories in the TB.
module m7_attention_accel_arch #(
    parameter integer CASE_ID = 0,
    parameter integer QUERY_START = 0,
    parameter integer VALID_KEYS = 8
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  start,

    output wire [9:0]            query_record_addr,
    input  wire [767:0]          query_record_fixed,
    input  wire [511:0]          query_record_fp16,
    input  wire [1023:0]         query_record_fp32,
    // The low 12 bits are the production KV-cache address
    // {kv_head[2:0], token[6:0], group[1:0]}; the upper bits are zero.
    output wire [16:0]           key_record_addr,
    input  wire [383:0]          key_record_fixed,
    input  wire [15:0]           key_meta_fixed,
    input  wire [511:0]          key_record_fp16,
    input  wire [1023:0]         key_record_fp32,

    // Explicit one-cycle cache-request observation points for the TB.  Data
    // is captured in the following DATA/SEND state by the zero-contention
    // cache model.
    output wire                  query_record_req,
    output wire                  key_record_req,

    output wire                  busy,
    output reg                   done,
    output wire [2:0]            attention_row,
    output wire [5:0]            attention_head,
    output wire [2:0]            attention_kv_head,
    output reg  [31:0]           launch_cycle_count,
    output reg  [31:0]           pre_pv_frontend_cycle_count,
    output reg  [31:0]           scheduler_wait_cycle_count,
    output reg  [31:0]           query_group_count,
    output reg  [31:0]           key_group_count,
    output reg  [31:0]           value_record_count,
    output wire [31:0]           completed_row_count,
    output wire [31:0]           completed_context_tile_count,
    output wire                  score_fire,
    output wire signed [19:0]    score_q14_s20,
    output wire                  score_mask,
    output wire [6:0]            score_key_index,
    output wire                  score_last_key,
    output wire [31:0]           score_clip_count,
    output wire [31:0]           context_saturation_count,
    output wire                  error
);
    localparam [4:0] ST_IDLE = 5'd0;
    localparam [4:0] ST_ATT_Q_READ = 5'd1;
    localparam [4:0] ST_ATT_Q_DATA = 5'd2;
    localparam [4:0] ST_ATT_Q_SEND = 5'd3;
    localparam [4:0] ST_ATT_K_REQ = 5'd4;
    localparam [4:0] ST_ATT_K_SEND = 5'd5;
    localparam [4:0] ST_ATT_VALUE_WAIT = 5'd6;
    localparam [4:0] ST_ATT_V_REQ = 5'd7;
    localparam [4:0] ST_ATT_V_SEND = 5'd8;
    localparam [4:0] ST_ATT_CONTEXT_WAIT = 5'd9;
    localparam [4:0] ST_ERROR = 5'd10;

    reg [4:0] state_r;
    reg [2:0] attention_row_r;
    reg [5:0] attention_head_r;
    reg [2:0] attention_query_group_r;
    reg [6:0] attention_key_r;
    reg [2:0] attention_key_group_r;
    reg [6:0] attention_value_key_r;
    reg [767:0] query_read_fixed_r;
    reg [511:0] query_read_fp16_r;
    reg [1023:0] query_read_fp32_r;
    reg control_error_r;

    wire [7:0] causal_key_count = QUERY_START + attention_row_r + 1;
    wire [7:0] row_key_count = (causal_key_count < VALID_KEYS) ?
        causal_key_count : VALID_KEYS;
    wire [6:0] row_last_key = row_key_count - 1'b1;
    wire row_query_load_ready, row_query_ready, row_key_ready;
    wire row_value_phase, row_value_ready, row_out_valid;
    wire [2:0] row_value_tile_index, row_out_tile_index;
    wire [383:0] row_out_context;
    wire row_error;
    wire row_query_valid = state_r == ST_ATT_Q_SEND;
    wire row_key_valid = state_r == ST_ATT_K_SEND;
    wire row_value_valid = state_r == ST_ATT_V_SEND;
    wire row_query_fire = row_query_valid && row_query_load_ready;
    wire row_key_fire = row_key_valid && row_key_ready;
    wire row_value_fire = row_value_valid && row_value_ready;
    wire row_out_fire = row_out_valid;

    assign busy = state_r != ST_IDLE;
    assign attention_row = attention_row_r;
    assign attention_head = attention_head_r;
    assign attention_kv_head = attention_head_r[4:2];
    assign query_record_addr = ({7'd0, attention_row_r} * 10'd128) +
        ({4'd0, attention_head_r} * 10'd4) + attention_query_group_r[1:0];
    assign key_record_addr = {5'd0, attention_head_r[4:2],
        attention_key_r, attention_key_group_r[1:0]};
    assign query_record_req = state_r == ST_ATT_Q_READ;
    assign key_record_req = state_r == ST_ATT_K_REQ;
    assign error = control_error_r | row_error;

    m7_attention_row_arch #(.CASE_ID(CASE_ID)) u_attention_row (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .row_key_count(row_key_count), .query_load_valid(row_query_valid),
        .query_load_ready(row_query_load_ready),
        .query_load_group(attention_query_group_r[1:0]),
        .query_group_fixed(query_read_fixed_r),
        .query_group_fp16(query_read_fp16_r),
        .query_group_fp32(query_read_fp32_r), .query_ready(row_query_ready),
        .key_valid(row_key_valid), .key_ready(row_key_ready),
        .key_first((attention_key_r == 0) &&
                   (attention_key_group_r == 0)),
        .key_last((attention_key_r == row_last_key) &&
                  (attention_key_group_r == 3)),
        .key_group(attention_key_group_r[1:0]), .key_mask(1'b0),
        .key_group_fixed(key_record_fixed),
        .key_meta_fixed(key_meta_fixed),
        .key_group_fp16(key_record_fp16),
        .key_group_fp32(key_record_fp32),
        .value_phase(row_value_phase),
        .value_tile_index(row_value_tile_index),
        .value_valid(row_value_valid), .value_ready(row_value_ready),
        .value16_s12(192'd0), .value_meta16(16'd0),
        .out_valid(row_out_valid), .out_ready(1'b1),
        .out_tile_index(row_out_tile_index),
        .out_context16_s24(row_out_context), .score_fire(score_fire),
        .score_q14_s20(score_q14_s20), .score_mask(score_mask),
        .score_key_index(score_key_index), .score_last_key(score_last_key),
        .score_clip_count(score_clip_count),
        .context_saturation_count(context_saturation_count),
        .completed_row_count(completed_row_count),
        .completed_context_tile_count(completed_context_tile_count),
        .error(row_error));

    always @(posedge clk) begin
        if (state_r == ST_ATT_Q_DATA) begin
            query_read_fixed_r <= query_record_fixed;
            query_read_fp16_r <= query_record_fp16;
            query_read_fp32_r <= query_record_fp32;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_IDLE;
            attention_row_r <= 3'd0;
            attention_head_r <= 6'd0;
            attention_query_group_r <= 3'd0;
            attention_key_r <= 7'd0;
            attention_key_group_r <= 3'd0;
            attention_value_key_r <= 7'd0;
            done <= 1'b0;
            launch_cycle_count <= 32'd0;
            pre_pv_frontend_cycle_count <= 32'd0;
            scheduler_wait_cycle_count <= 32'd0;
            query_group_count <= 32'd0;
            key_group_count <= 32'd0;
            value_record_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            state_r <= ST_IDLE;
            attention_row_r <= 3'd0;
            attention_head_r <= 6'd0;
            attention_query_group_r <= 3'd0;
            attention_key_r <= 7'd0;
            attention_key_group_r <= 3'd0;
            attention_value_key_r <= 7'd0;
            done <= 1'b0;
            launch_cycle_count <= 32'd0;
            pre_pv_frontend_cycle_count <= 32'd0;
            scheduler_wait_cycle_count <= 32'd0;
            query_group_count <= 32'd0;
            key_group_count <= 32'd0;
            value_record_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            done <= 1'b0;
            if (busy)
                launch_cycle_count <= launch_cycle_count + 1'b1;
            if ((state_r >= ST_ATT_Q_READ) &&
                (state_r <= ST_ATT_VALUE_WAIT))
                pre_pv_frontend_cycle_count <=
                    pre_pv_frontend_cycle_count + 1'b1;
            if (((state_r == ST_ATT_Q_SEND) && !row_query_load_ready) ||
                ((state_r == ST_ATT_K_SEND) && !row_key_ready) ||
                ((state_r == ST_ATT_V_SEND) && !row_value_ready))
                scheduler_wait_cycle_count <= scheduler_wait_cycle_count + 1'b1;

            case (state_r)
                ST_IDLE: if (start) begin
                    attention_row_r <= 3'd0;
                    attention_head_r <= 6'd0;
                    attention_query_group_r <= 3'd0;
                    attention_key_r <= 7'd0;
                    attention_key_group_r <= 3'd0;
                    attention_value_key_r <= 7'd0;
                    launch_cycle_count <= 32'd0;
                    pre_pv_frontend_cycle_count <= 32'd0;
                    scheduler_wait_cycle_count <= 32'd0;
                    query_group_count <= 32'd0;
                    key_group_count <= 32'd0;
                    value_record_count <= 32'd0;
                    state_r <= ST_ATT_Q_READ;
                end
                ST_ATT_Q_READ: state_r <= ST_ATT_Q_DATA;
                ST_ATT_Q_DATA: state_r <= ST_ATT_Q_SEND;
                ST_ATT_Q_SEND: if (row_query_fire) begin
                    query_group_count <= query_group_count + 1'b1;
                    if (attention_query_group_r == 3) begin
                        attention_query_group_r <= 0;
                        attention_key_r <= 0;
                        attention_key_group_r <= 0;
                        state_r <= ST_ATT_K_REQ;
                    end else begin
                        attention_query_group_r <=
                            attention_query_group_r + 1'b1;
                        state_r <= ST_ATT_Q_READ;
                    end
                end
                ST_ATT_K_REQ: state_r <= ST_ATT_K_SEND;
                ST_ATT_K_SEND: if (row_key_fire) begin
                    key_group_count <= key_group_count + 1'b1;
                    if ((attention_key_r == row_last_key) &&
                        (attention_key_group_r == 3)) begin
                        state_r <= ST_ATT_VALUE_WAIT;
                    end else begin
                        if (attention_key_group_r == 3) begin
                            attention_key_group_r <= 0;
                            attention_key_r <= attention_key_r + 1'b1;
                        end else begin
                            attention_key_group_r <=
                                attention_key_group_r + 1'b1;
                        end
                        state_r <= ST_ATT_K_REQ;
                    end
                end
                ST_ATT_VALUE_WAIT: if (row_value_phase) begin
                    attention_value_key_r <= 0;
                    state_r <= ST_ATT_V_REQ;
                end
                ST_ATT_V_REQ: state_r <= ST_ATT_V_SEND;
                ST_ATT_V_SEND: if (row_value_fire) begin
                    value_record_count <= value_record_count + 1'b1;
                    if (attention_value_key_r == row_last_key)
                        state_r <= ST_ATT_CONTEXT_WAIT;
                    else begin
                        attention_value_key_r <= attention_value_key_r + 1'b1;
                        state_r <= ST_ATT_V_REQ;
                    end
                end
                ST_ATT_CONTEXT_WAIT: if (row_out_fire) begin
                    if (|row_out_context)
                        control_error_r <= 1'b1;
                    if (row_out_tile_index == 7) begin
                        if ((attention_row_r == 7) &&
                            (attention_head_r == 31)) begin
                            done <= 1'b1;
                            state_r <= ST_IDLE;
                        end else begin
                            if (attention_head_r == 31) begin
                                attention_head_r <= 0;
                                attention_row_r <= attention_row_r + 1'b1;
                            end else begin
                                attention_head_r <= attention_head_r + 1'b1;
                            end
                            attention_query_group_r <= 0;
                            state_r <= ST_ATT_Q_READ;
                        end
                    end else begin
                        attention_value_key_r <= 0;
                        state_r <= ST_ATT_VALUE_WAIT;
                    end
                end
                default: state_r <= ST_ERROR;
            endcase
            if (row_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

    initial begin
        if ((QUERY_START < 0) || (QUERY_START > 127) ||
            (VALID_KEYS < 1) || (VALID_KEYS > 128))
            $error("invalid M7 architecture workload");
    end
endmodule
