`timescale 1ns / 1ps

// Common 256-bit physical harness.  Every input command occupies four words:
//   [767:0]   Q S24x32 (query) or [383:0] K S12x32 (key)
//   [799:768] SC meta / FP native scale
//   [806:800] key index
//   [808:807] group index
//   [809]     mask
//   [810]     last key-group record
//   [812:811] 0=query, 1=key, 2=start
// The full cache, boundary conversion and QK arithmetic remain inside the top.
module m05_qk_boundary_serial_ooc_wrapper #(
    parameter integer VARIANT = 0
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  load_valid,
    output wire                  load_ready,
    input  wire [255:0]          load_data,
    output wire                  result_valid,
    input  wire                  result_ready,
    output wire [255:0]          result_data,
    output wire                  result_last,
    output wire [31:0]           input_group_count,
    output wire [31:0]           output_score_count,
    output wire [31:0]           clip_count,
    output wire [31:0]           query_cache_write_count,
    output wire [31:0]           key_cache_write_count,
    output wire                  error
);
    localparam ST_LOAD = 1'b0;
    localparam ST_DISPATCH = 1'b1;
    reg state_r;
    reg [1:0] load_word_r;
    reg [1023:0] load_payload_r;
    reg command_error_r;
    wire load_fire = load_valid && load_ready;
    wire [1:0] command_type = load_payload_r[812:811];
    wire query_command = command_type == 0;
    wire key_command = command_type == 1;
    wire start_command = command_type == 2;
    wire query_load_valid = state_r == ST_DISPATCH && query_command;
    wire key_load_valid = state_r == ST_DISPATCH && key_command;
    wire start_valid = state_r == ST_DISPATCH && start_command;
    wire query_load_ready;
    wire key_load_ready;
    wire start_ready;
    wire command_fire = (query_load_valid && query_load_ready) ||
        (key_load_valid && key_load_ready) ||
        (start_valid && start_ready);
    wire core_out_valid;
    wire signed [19:0] core_score;
    wire core_mask;
    wire [6:0] core_key_index;
    wire core_last_key;
    wire core_error;

    assign load_ready = rst_n && !clear && state_r == ST_LOAD;
    assign result_valid = core_out_valid;
    assign result_data = {227'd0,core_last_key,core_key_index,
        core_mask,core_score};
    assign result_last = 1'b1;
    assign error = command_error_r || core_error;

    generate
        if (VARIANT == 0) begin : g_sc
            m05_sc_qk_boundary_cache u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(load_payload_r[808:807]),
                .query_load_s24(load_payload_r[0 +: 768]),
                .key_load_valid(key_load_valid),
                .key_load_ready(key_load_ready),
                .key_load_index(load_payload_r[806:800]),
                .key_load_group(load_payload_r[808:807]),
                .key_load_s12(load_payload_r[0 +: 384]),
                .key_load_meta16(load_payload_r[768 +: 16]),
                .key_load_mask(load_payload_r[809]),
                .key_load_last(load_payload_r[810]),
                .start_valid(start_valid), .start_ready(start_ready),
                .out_valid(core_out_valid), .out_ready(result_ready),
                .out_score_q14_s20(core_score), .out_mask(core_mask),
                .out_key_index(core_key_index), .out_last_key(core_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count),
                .query_cache_write_count(query_cache_write_count),
                .key_cache_write_count(key_cache_write_count),
                .error(core_error));
        end else if (VARIANT == 1) begin : g_fp16
            wire frontend_idle_unused;
            m05_fp16_qk_boundary_cache u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(load_payload_r[808:807]),
                .query_load_s24(load_payload_r[0 +: 768]),
                .key_load_valid(key_load_valid),
                .key_load_ready(key_load_ready),
                .key_load_index(load_payload_r[806:800]),
                .key_load_group(load_payload_r[808:807]),
                .key_load_s12(load_payload_r[0 +: 384]),
                .key_load_scale_fp(load_payload_r[768 +: 16]),
                .key_load_mask(load_payload_r[809]),
                .key_load_last(load_payload_r[810]),
                .start_valid(start_valid), .start_ready(start_ready),
                .out_valid(core_out_valid), .out_ready(result_ready),
                .out_score_q14_s20(core_score), .out_mask(core_mask),
                .out_key_index(core_key_index), .out_last_key(core_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count),
                .query_cache_write_count(query_cache_write_count),
                .key_cache_write_count(key_cache_write_count),
                .frontend_idle(frontend_idle_unused), .error(core_error));
        end else begin : g_fp32
            wire frontend_idle_unused;
            m05_fp32_qk_boundary_cache u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid),
                .query_load_ready(query_load_ready),
                .query_load_group(load_payload_r[808:807]),
                .query_load_s24(load_payload_r[0 +: 768]),
                .key_load_valid(key_load_valid),
                .key_load_ready(key_load_ready),
                .key_load_index(load_payload_r[806:800]),
                .key_load_group(load_payload_r[808:807]),
                .key_load_s12(load_payload_r[0 +: 384]),
                .key_load_scale_fp(load_payload_r[768 +: 32]),
                .key_load_mask(load_payload_r[809]),
                .key_load_last(load_payload_r[810]),
                .start_valid(start_valid), .start_ready(start_ready),
                .out_valid(core_out_valid), .out_ready(result_ready),
                .out_score_q14_s20(core_score), .out_mask(core_mask),
                .out_key_index(core_key_index), .out_last_key(core_last_key),
                .input_group_count(input_group_count),
                .output_score_count(output_score_count),
                .clip_count(clip_count),
                .query_cache_write_count(query_cache_write_count),
                .key_cache_write_count(key_cache_write_count),
                .frontend_idle(frontend_idle_unused), .error(core_error));
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_LOAD;
            load_word_r <= 2'd0;
            command_error_r <= 1'b0;
        end else if (clear) begin
            state_r <= ST_LOAD;
            load_word_r <= 2'd0;
            command_error_r <= 1'b0;
        end else begin
            if (state_r == ST_LOAD && load_fire) begin
                load_payload_r[load_word_r*256 +: 256] <= load_data;
                if (load_word_r == 3) begin
                    load_word_r <= 2'd0;
                    state_r <= ST_DISPATCH;
                end else
                    load_word_r <= load_word_r + 1'b1;
            end
            if (state_r == ST_DISPATCH) begin
                if (command_type == 3)
                    command_error_r <= 1'b1;
                if (command_fire)
                    state_r <= ST_LOAD;
            end
        end
    end

    initial begin
        if (VARIANT < 0 || VARIANT > 2)
            $error("M05 serial boundary VARIANT must be 0, 1, or 2");
    end
endmodule


module m05_sc_qk_boundary_serial_ooc_wrapper (
    input wire clk, rst_n, clear, load_valid,
    output wire load_ready,
    input wire [255:0] load_data,
    output wire result_valid,
    input wire result_ready,
    output wire [255:0] result_data,
    output wire result_last,
    output wire [31:0] input_group_count, output_score_count, clip_count,
    query_cache_write_count, key_cache_write_count,
    output wire error
);
    m05_qk_boundary_serial_ooc_wrapper #(.VARIANT(0)) u_wrapper (.*);
endmodule


module m05_fp16_qk_boundary_serial_ooc_wrapper (
    input wire clk, rst_n, clear, load_valid,
    output wire load_ready,
    input wire [255:0] load_data,
    output wire result_valid,
    input wire result_ready,
    output wire [255:0] result_data,
    output wire result_last,
    output wire [31:0] input_group_count, output_score_count, clip_count,
    query_cache_write_count, key_cache_write_count,
    output wire error
);
    m05_qk_boundary_serial_ooc_wrapper #(.VARIANT(1)) u_wrapper (.*);
endmodule


module m05_fp32_qk_boundary_serial_ooc_wrapper (
    input wire clk, rst_n, clear, load_valid,
    output wire load_ready,
    input wire [255:0] load_data,
    output wire result_valid,
    input wire result_ready,
    output wire [255:0] result_data,
    output wire result_last,
    output wire [31:0] input_group_count, output_score_count, clip_count,
    query_cache_write_count, key_cache_write_count,
    output wire error
);
    m05_qk_boundary_serial_ooc_wrapper #(.VARIANT(2)) u_wrapper (.*);
endmodule
