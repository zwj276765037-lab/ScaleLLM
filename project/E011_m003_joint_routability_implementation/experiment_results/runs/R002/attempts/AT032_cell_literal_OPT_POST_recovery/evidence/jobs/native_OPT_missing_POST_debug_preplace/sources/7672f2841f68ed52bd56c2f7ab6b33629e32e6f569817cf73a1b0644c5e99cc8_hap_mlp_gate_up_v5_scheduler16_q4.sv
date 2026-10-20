`timescale 1ns / 1ps

// Complete V5 gate/up command scheduler around the frozen 16-column DDR ABI.
//
// Source order remains the existing tile-major stream:
//   gate record0[g0..g127], up record0[g0..g127], ... record2 up.
// The ping-pong gather transposes one at-most-48-column block into:
//   pass0 gate[g0..g127], pass0 up[g0..g127], ... pass3 up.
// A small ordered request FIFO pairs every internal 12-column transaction
// with the corresponding activation-cache response.  The projection inverse
// gearbox restores the legacy 16-column gate/up stream before SwiGLU.  Thus
// metadata and DDR counts stay at the source-record count while the shared
// physical kernel sees the larger internal 12-column transaction count.
module hap_mlp_gate_up_v5_scheduler16_q4 #(
    parameter integer INTERMEDIATE_COLUMNS = 14336,
    parameter integer GROUPS = 128,
    parameter integer ENFORCE_PRODUCTION_SHAPE = 1,
    parameter integer REQUEST_FIFO_DEPTH = 4,
    parameter integer PROJECTION_TAG_DEPTH = 32,
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem",
    parameter integer BLOCKS = (INTERMEDIATE_COLUMNS+47)/48,
    parameter integer BLOCK_W = (BLOCKS <= 2) ? 1 : $clog2(BLOCKS),
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          command_valid,
    output wire                          command_ready,
    input  wire                          activation_bank,
    input  wire                          activation_bank_ready,

    output wire                          cache_rd_req_valid,
    input  wire                          cache_rd_req_ready,
    output wire                          cache_rd_req_bank,
    output wire [GROUP_W-1:0]            cache_rd_req_group,
    input  wire                          cache_rd_rsp_valid,
    output wire                          cache_rd_rsp_ready,
    input  wire                          cache_rd_rsp_bank,
    input  wire [GROUP_W-1:0]            cache_rd_rsp_group,
    input  wire [16*32*8-1:0]            cache_rd_rsp_u8x16x32,
    input  wire [16*24-1:0]              cache_rd_rsp_meta_u24x16,

    input  wire                          weight_valid,
    output wire                          weight_ready,
    input  wire signed [16*32*4-1:0]     weights_s4x16x32,
    input  wire [223:0]                  weight_meta_u224,

    output wire                          compute_valid,
    input  wire                          compute_ready,
    output wire                          compute_first,
    output wire                          compute_last,
    output wire signed [16*32*9-1:0]     compute_activation_s9x16x32,
    output wire signed [12*32*4-1:0]     compute_weights_s4x12x32,
    output wire [16*8-1:0]               compute_activation_code_u8x16,
    output wire [16*6-1:0]               compute_activation_shift_u6x16,
    output wire [12*8-1:0]               compute_weight_code_u8x12,
    output wire [12*6-1:0]               compute_weight_shift_u6x12,
    output wire [11:0]                    compute_column_valid_u12,

    input  wire                          projection_valid,
    output wire                          projection_ready,
    input  wire signed [16*12*24-1:0]    projection_s24x16x12,

    output wire                          activation_out_valid,
    input  wire                          activation_out_ready,
    output wire [16*32*8-1:0]            activation_out_u8x16x32,
    output wire [16*24-1:0]              activation_out_meta_u24x16,
    output wire                          busy,
    output reg                           done,
    output wire                          error,

    output reg  [31:0]                   source_transaction_count,
    output reg  [31:0]                   cache_request_count,
    output reg  [31:0]                   compute_transaction_count,
    output reg  [31:0]                   internal_projection_pass_count,
    output reg  [31:0]                   external_projection_record_count,
    output wire [31:0]                   product_group_count,
    output wire [31:0]                   activation_group_count,
    output wire [31:0]                   saturation_count,
    output wire                          format_error
);

    localparam integer TAIL_COLUMNS =
        INTERMEDIATE_COLUMNS - (BLOCKS-1)*48;
    localparam integer REQUEST_PTR_W = $clog2(REQUEST_FIFO_DEPTH);
    localparam integer REQUEST_COUNT_W = $clog2(REQUEST_FIFO_DEPTH+1);
    localparam integer TAG_PTR_W = $clog2(PROJECTION_TAG_DEPTH);
    localparam integer TAG_COUNT_W = $clog2(PROJECTION_TAG_DEPTH+1);
    localparam [1:0] S_IDLE = 2'd0;
    localparam [1:0] S_CLEAR = 2'd1;
    localparam [1:0] S_RUN = 2'd2;

    reg [1:0] state_r;
    // state_r[1] is the S_RUN protocol owner.  In the first V5 place it was
    // also allowed to spread through all scheduler endpoints (1,002 loads),
    // causing a data BUFG.  These endpoint-local replicas enter and leave RUN
    // on the same edges as state_r, preserving every ready/valid cycle.
    (* DONT_TOUCH = "yes" *) reg [7:0] run_endpoint_bank_r;
    reg active_bank_r;
    reg [BLOCK_W-1:0] source_block_r;
    reg [1:0] source_record_r;
    reg source_matrix_r;
    reg [GROUP_W-1:0] source_group_r;
    reg [10:0] projection_pair_r;
    reg sticky_error_r;
    reg metadata_format_error_r;
    integer metadata_row;

    wire local_clear = clear || state_r == S_CLEAR;
    wire command_fire = command_valid && command_ready;
    assign command_ready = rst_n && !clear && state_r == S_IDLE &&
        activation_bank_ready;
    assign busy = state_r != S_IDLE;

    function automatic [5:0] block_columns;
        input [BLOCK_W-1:0] block_index;
        begin
            block_columns = block_index == BLOCKS-1 ?
                TAIL_COLUMNS[5:0] : 6'd48;
        end
    endfunction

    function automatic [15:0] source_mask;
        input [5:0] columns;
        input [1:0] record_index;
        integer remaining;
        begin
            remaining = columns - record_index*16;
            if (remaining >= 16)
                source_mask = 16'hffff;
            else if (remaining > 0)
                source_mask = (16'h0001 << remaining) - 1'b1;
            else
                source_mask = 16'h0000;
        end
    endfunction

    wire [5:0] source_block_columns = block_columns(source_block_r);
    wire [15:0] source_column_mask = source_mask(
        source_block_columns, source_record_r);

    wire gather_in_ready;
    wire gather_out_valid;
    wire gather_out_ready;
    wire [BLOCK_W-1:0] gather_out_block;
    wire gather_out_matrix;
    wire [1:0] gather_out_pass;
    wire [GROUP_W-1:0] gather_out_group;
    wire gather_out_first;
    wire gather_out_last;
    wire gather_out_last_pass;
    wire gather_out_last_block_transaction;
    wire signed [12*32*4-1:0] gather_out_weights;
    wire [167:0] gather_out_meta;
    wire [11:0] gather_out_mask;
    wire [31:0] gather_input_count;
    wire [31:0] gather_input_blocks;
    wire [31:0] gather_output_count;
    wire [31:0] gather_output_blocks;
    wire gather_error;
    wire source_fire = weight_valid && weight_ready;

    assign weight_ready = run_endpoint_bank_r[0] && gather_in_ready;

    hap_mlp_gate_up_gather_pingpong12 #(
        .GROUPS(GROUPS), .BLOCK_W(BLOCK_W), .GROUP_W(GROUP_W)
    ) u_gather (
        .clk(clk), .rst_n(rst_n), .clear(local_clear),
        .in_valid(run_endpoint_bank_r[1] && weight_valid),
        .in_ready(gather_in_ready),
        .in_block_index(source_block_r),
        .in_block_valid_columns(source_block_columns),
        .in_matrix(source_matrix_r), .in_record_index(source_record_r),
        .in_k_group(source_group_r),
        .in_weights_s4x16x32(weights_s4x16x32),
        .in_weight_meta_u224(weight_meta_u224),
        .in_col_valid_u16(source_column_mask),
        .out_valid(gather_out_valid), .out_ready(gather_out_ready),
        .out_block_index(gather_out_block),
        .out_matrix(gather_out_matrix),
        .out_pass_index(gather_out_pass),
        .out_k_group(gather_out_group),
        .out_first_group(gather_out_first),
        .out_last_group(gather_out_last),
        .out_last_pass(gather_out_last_pass),
        .out_last_block_transaction(gather_out_last_block_transaction),
        .out_weights_s4x12x32(gather_out_weights),
        .out_weight_meta_u168(gather_out_meta),
        .out_col_valid_u12(gather_out_mask),
        .input_transaction_count(gather_input_count),
        .input_block_count(gather_input_blocks),
        .output_transaction_count(gather_output_count),
        .output_block_count(gather_output_blocks), .error(gather_error)
    );

    // Ordered cache-request payload FIFO.  A gather item and its activation
    // read request are accepted atomically; the response is paired with the
    // oldest stored weight item.  Four entries cover the one-cycle BRAM return
    // and elastic shared-kernel boundary while preserving steady II=1.
    reg signed [12*32*4-1:0] request_weights [0:REQUEST_FIFO_DEPTH-1];
    reg [167:0] request_meta [0:REQUEST_FIFO_DEPTH-1];
    reg [BLOCK_W-1:0] request_block [0:REQUEST_FIFO_DEPTH-1];
    reg request_matrix [0:REQUEST_FIFO_DEPTH-1];
    reg [1:0] request_pass [0:REQUEST_FIFO_DEPTH-1];
    reg [GROUP_W-1:0] request_group [0:REQUEST_FIFO_DEPTH-1];
    reg request_first [0:REQUEST_FIFO_DEPTH-1];
    reg request_last [0:REQUEST_FIFO_DEPTH-1];
    reg request_last_pass [0:REQUEST_FIFO_DEPTH-1];
    reg [11:0] request_mask [0:REQUEST_FIFO_DEPTH-1];
    reg [REQUEST_PTR_W-1:0] request_wr_ptr_r;
    reg [REQUEST_PTR_W-1:0] request_rd_ptr_r;
    reg [REQUEST_COUNT_W-1:0] request_count_r;
    wire request_full = request_count_r == REQUEST_FIFO_DEPTH;
    wire request_empty = request_count_r == 0;
    wire gather_fire = gather_out_valid && gather_out_ready;

    assign cache_rd_req_valid = run_endpoint_bank_r[2] &&
        gather_out_valid &&
        !request_full;
    assign cache_rd_req_bank = active_bank_r;
    assign cache_rd_req_group = gather_out_group;
    assign gather_out_ready = run_endpoint_bank_r[3] && !request_full &&
        cache_rd_req_ready;

    wire head_last = request_last[request_rd_ptr_r];

    // One tag is generated when the last K group of a pass enters the shared
    // kernel.  It is consumed only when the corresponding completed S24 pass
    // is accepted by the inverse projection gearbox.
    reg [BLOCK_W-1:0] projection_tag_block [0:PROJECTION_TAG_DEPTH-1];
    reg projection_tag_matrix [0:PROJECTION_TAG_DEPTH-1];
    reg [1:0] projection_tag_pass [0:PROJECTION_TAG_DEPTH-1];
    reg projection_tag_last_pass [0:PROJECTION_TAG_DEPTH-1];
    reg [11:0] projection_tag_mask [0:PROJECTION_TAG_DEPTH-1];
    reg [TAG_PTR_W-1:0] projection_tag_wr_ptr_r;
    reg [TAG_PTR_W-1:0] projection_tag_rd_ptr_r;
    reg [TAG_COUNT_W-1:0] projection_tag_count_r;
    wire projection_tag_full =
        projection_tag_count_r == PROJECTION_TAG_DEPTH;
    wire projection_tag_empty = projection_tag_count_r == 0;
    wire compute_admissible = !request_empty && cache_rd_rsp_valid &&
        (!head_last || !projection_tag_full);
    wire compute_fire = compute_valid && compute_ready;

    assign compute_valid = run_endpoint_bank_r[4] && compute_admissible;
    assign cache_rd_rsp_ready = run_endpoint_bank_r[5] && !request_empty &&
        (!head_last || !projection_tag_full) && compute_ready;
    assign compute_first = request_first[request_rd_ptr_r];
    assign compute_last = head_last;
    assign compute_weights_s4x12x32 = request_weights[request_rd_ptr_r];
    assign compute_weight_code_u8x12 =
        request_meta[request_rd_ptr_r][95:0];
    assign compute_weight_shift_u6x12 =
        request_meta[request_rd_ptr_r][167:96];
    assign compute_column_valid_u12 = request_mask[request_rd_ptr_r];

    genvar activation_row;
    genvar activation_lane;
    generate
        for (activation_row = 0; activation_row < 16;
             activation_row = activation_row + 1) begin : gen_activation_row
            wire [7:0] zero_point = cache_rd_rsp_meta_u24x16[
                activation_row*24 +: 8];
            assign compute_activation_code_u8x16[
                activation_row*8 +: 8] = cache_rd_rsp_meta_u24x16[
                activation_row*24+8 +: 8];
            assign compute_activation_shift_u6x16[
                activation_row*6 +: 6] = cache_rd_rsp_meta_u24x16[
                activation_row*24+16 +: 6];
            for (activation_lane = 0; activation_lane < 32;
                 activation_lane = activation_lane + 1) begin : gen_lane
                wire [7:0] value = cache_rd_rsp_u8x16x32[
                    (activation_row*32+activation_lane)*8 +: 8];
                assign compute_activation_s9x16x32[
                    (activation_row*32+activation_lane)*9 +: 9] =
                    $signed({1'b0, value}) -
                    $signed({1'b0, zero_point});
            end
        end
    endgenerate

    wire projection_repack_in_valid = run_endpoint_bank_r[6] &&
        projection_valid &&
        !projection_tag_empty;
    wire projection_repack_in_ready;
    wire projection_fire = projection_valid && projection_ready;
    assign projection_ready = run_endpoint_bank_r[7] &&
        !projection_tag_empty &&
        projection_repack_in_ready;

    wire projection_repack_out_valid;
    wire projection_repack_out_ready;
    wire signed [16*16*24-1:0] projection_repack_out_s24;
    wire [BLOCK_W-1:0] projection_repack_out_block;
    wire [1:0] projection_repack_out_record;
    wire projection_repack_out_matrix;
    wire [15:0] projection_repack_out_mask;
    wire projection_repack_out_last;
    wire [31:0] repack_input_count;
    wire [31:0] repack_output_count;
    wire projection_repack_error;

    hap_mlp_projection_repack12_to16_s24_history2 #(
        .ROWS(16), .MATRICES(2), .TAG_W(BLOCK_W)
    ) u_projection_repack (
        .clk(clk), .rst_n(rst_n), .clear(local_clear),
        .in_valid(projection_repack_in_valid),
        .in_ready(projection_repack_in_ready),
        .in_projection_s24xrowsx12(projection_s24x16x12),
        .in_block_tag(projection_tag_block[projection_tag_rd_ptr_r]),
        .in_pass_index(projection_tag_pass[projection_tag_rd_ptr_r]),
        .in_matrix(projection_tag_matrix[projection_tag_rd_ptr_r]),
        .in_col_valid_u12(projection_tag_mask[projection_tag_rd_ptr_r]),
        .in_last_pass(
            projection_tag_last_pass[projection_tag_rd_ptr_r]),
        .out_valid(projection_repack_out_valid),
        .out_ready(projection_repack_out_ready),
        .out_projection_s24xrowsx16(projection_repack_out_s24),
        .out_block_tag(projection_repack_out_block),
        .out_record_index(projection_repack_out_record),
        .out_matrix(projection_repack_out_matrix),
        .out_col_valid_u16(projection_repack_out_mask),
        .out_last_record(projection_repack_out_last),
        .input_pass_count(repack_input_count),
        .output_record_count(repack_output_count),
        .error(projection_repack_error)
    );

    wire swiglu_in_ready;
    wire swiglu_error;
    wire [31:0] swiglu_input_record_count;
    wire [31:0] swiglu_busy_cycles;
    wire [31:0] swiglu_format_error_count;
    wire swiglu_format_error;
    wire projection_record_fire = projection_repack_out_valid &&
        projection_repack_out_ready;
    assign projection_repack_out_ready = swiglu_in_ready;

    hap_mlp_swiglu_product_frontend16_q4 #(
        .SILU_LUT_FILE(SILU_LUT_FILE)
    ) u_swiglu (
        .clk(clk), .rst_n(rst_n), .clear(local_clear),
        .in_valid(projection_repack_out_valid),
        .in_ready(swiglu_in_ready),
        .in_is_up(projection_repack_out_matrix),
        .in_second_half(projection_pair_r[0]),
        .projection_s24x16x16(projection_repack_out_s24),
        .out_valid(activation_out_valid),
        .out_ready(activation_out_ready),
        .activation_u8x16x32(activation_out_u8x16x32),
        .activation_meta_u24x16(activation_out_meta_u24x16),
        .input_tile_count(swiglu_input_record_count),
        .product_group_count(product_group_count),
        .activation_group_count(activation_group_count),
        .frontend_busy_cycle_count(swiglu_busy_cycles),
        .format_error_count(swiglu_format_error_count),
        .format_error(swiglu_format_error),
        .error(swiglu_error)
    );

    wire activation_out_fire = activation_out_valid &&
        activation_out_ready;
    assign saturation_count = 32'd0;
    assign format_error = metadata_format_error_r || swiglu_format_error;
    assign error = sticky_error_r || gather_error ||
        projection_repack_error || swiglu_error;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            state_r <= S_IDLE;
            run_endpoint_bank_r <= 8'd0;
            active_bank_r <= 1'b0;
            source_block_r <= '0;
            source_record_r <= 2'd0;
            source_matrix_r <= 1'b0;
            source_group_r <= '0;
            request_wr_ptr_r <= '0;
            request_rd_ptr_r <= '0;
            request_count_r <= '0;
            projection_tag_wr_ptr_r <= '0;
            projection_tag_rd_ptr_r <= '0;
            projection_tag_count_r <= '0;
            projection_pair_r <= 11'd0;
            source_transaction_count <= 32'd0;
            cache_request_count <= 32'd0;
            compute_transaction_count <= 32'd0;
            internal_projection_pass_count <= 32'd0;
            external_projection_record_count <= 32'd0;
            sticky_error_r <= 1'b0;
            metadata_format_error_r <= 1'b0;
            done <= 1'b0;
        end else begin
            done <= 1'b0;
            if (command_fire) begin
                state_r <= S_CLEAR;
                run_endpoint_bank_r <= 8'd0;
                active_bank_r <= activation_bank;
                sticky_error_r <= 1'b0;
                metadata_format_error_r <= 1'b0;
            end else if (state_r == S_CLEAR) begin
                state_r <= S_RUN;
                run_endpoint_bank_r <= 8'hff;
                source_block_r <= '0;
                source_record_r <= 2'd0;
                source_matrix_r <= 1'b0;
                source_group_r <= '0;
                request_wr_ptr_r <= '0;
                request_rd_ptr_r <= '0;
                request_count_r <= '0;
                projection_tag_wr_ptr_r <= '0;
                projection_tag_rd_ptr_r <= '0;
                projection_tag_count_r <= '0;
                projection_pair_r <= 11'd0;
                source_transaction_count <= 32'd0;
                cache_request_count <= 32'd0;
                compute_transaction_count <= 32'd0;
                internal_projection_pass_count <= 32'd0;
                external_projection_record_count <= 32'd0;
            end

            if (source_fire) begin
                source_transaction_count <= source_transaction_count + 1'b1;
                if (source_group_r == GROUPS-1) begin
                    source_group_r <= '0;
                    if (!source_matrix_r) begin
                        source_matrix_r <= 1'b1;
                    end else begin
                        source_matrix_r <= 1'b0;
                        if (source_record_r + 1'b1 ==
                            (source_block_columns+15)/16) begin
                            source_record_r <= 2'd0;
                            if (source_block_r != BLOCKS-1)
                                source_block_r <= source_block_r + 1'b1;
                        end else begin
                            source_record_r <= source_record_r + 1'b1;
                        end
                    end
                end else begin
                    source_group_r <= source_group_r + 1'b1;
                end
            end

            if (gather_fire) begin
                request_weights[request_wr_ptr_r] <= gather_out_weights;
                request_meta[request_wr_ptr_r] <= gather_out_meta;
                request_block[request_wr_ptr_r] <= gather_out_block;
                request_matrix[request_wr_ptr_r] <= gather_out_matrix;
                request_pass[request_wr_ptr_r] <= gather_out_pass;
                request_group[request_wr_ptr_r] <= gather_out_group;
                request_first[request_wr_ptr_r] <= gather_out_first;
                request_last[request_wr_ptr_r] <= gather_out_last;
                request_last_pass[request_wr_ptr_r] <=
                    gather_out_last_pass;
                request_mask[request_wr_ptr_r] <= gather_out_mask;
                request_wr_ptr_r <= request_wr_ptr_r + 1'b1;
                cache_request_count <= cache_request_count + 1'b1;
            end

            if (compute_fire) begin
                request_rd_ptr_r <= request_rd_ptr_r + 1'b1;
                compute_transaction_count <=
                    compute_transaction_count + 1'b1;
                if (cache_rd_rsp_bank != active_bank_r ||
                    cache_rd_rsp_group != request_group[request_rd_ptr_r])
                    sticky_error_r <= 1'b1;
                for (metadata_row = 0; metadata_row < 16;
                     metadata_row = metadata_row + 1) begin
                    if (cache_rd_rsp_meta_u24x16[metadata_row*24+22 +: 2] != 0 ||
                        (cache_rd_rsp_meta_u24x16[metadata_row*24+8 +: 8] == 0 &&
                         cache_rd_rsp_meta_u24x16[metadata_row*24+16 +: 6] != 0)) begin
                        metadata_format_error_r <= 1'b1;
                        sticky_error_r <= 1'b1;
                    end
                end
                if (head_last) begin
                    projection_tag_block[projection_tag_wr_ptr_r] <=
                        request_block[request_rd_ptr_r];
                    projection_tag_matrix[projection_tag_wr_ptr_r] <=
                        request_matrix[request_rd_ptr_r];
                    projection_tag_pass[projection_tag_wr_ptr_r] <=
                        request_pass[request_rd_ptr_r];
                    projection_tag_last_pass[projection_tag_wr_ptr_r] <=
                        request_last_pass[request_rd_ptr_r];
                    projection_tag_mask[projection_tag_wr_ptr_r] <=
                        request_mask[request_rd_ptr_r];
                    projection_tag_wr_ptr_r <=
                        projection_tag_wr_ptr_r + 1'b1;
                end
            end

            case ({gather_fire, compute_fire})
                2'b10: request_count_r <= request_count_r + 1'b1;
                2'b01: request_count_r <= request_count_r - 1'b1;
                default: request_count_r <= request_count_r;
            endcase

            if (projection_fire) begin
                projection_tag_rd_ptr_r <= projection_tag_rd_ptr_r + 1'b1;
                internal_projection_pass_count <=
                    internal_projection_pass_count + 1'b1;
            end
            case ({compute_fire && head_last, projection_fire})
                2'b10: projection_tag_count_r <=
                    projection_tag_count_r + 1'b1;
                2'b01: projection_tag_count_r <=
                    projection_tag_count_r - 1'b1;
                default: projection_tag_count_r <= projection_tag_count_r;
            endcase

            if (projection_record_fire) begin
                external_projection_record_count <=
                    external_projection_record_count + 1'b1;
                if (projection_repack_out_matrix)
                    projection_pair_r <= projection_pair_r + 1'b1;
                if (projection_repack_out_mask != 16'hffff)
                    sticky_error_r <= 1'b1;
            end

            if (activation_out_fire &&
                activation_group_count + 1'b1 ==
                INTERMEDIATE_COLUMNS/32) begin
                state_r <= S_IDLE;
                run_endpoint_bank_r <= 8'd0;
                done <= 1'b1;
            end

            if (gather_input_count != source_transaction_count ||
                gather_output_count < compute_transaction_count ||
                repack_input_count < internal_projection_pass_count ||
                repack_output_count < external_projection_record_count ||
                request_count_r > REQUEST_FIFO_DEPTH ||
                projection_tag_count_r > PROJECTION_TAG_DEPTH ||
                source_transaction_count >
                    ((INTERMEDIATE_COLUMNS+15)/16)*2*GROUPS ||
                compute_transaction_count >
                    ((INTERMEDIATE_COLUMNS+11)/12)*2*GROUPS ||
                internal_projection_pass_count >
                    ((INTERMEDIATE_COLUMNS+11)/12)*2 ||
                external_projection_record_count >
                    ((INTERMEDIATE_COLUMNS+15)/16)*2)
                sticky_error_r <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear &&
            run_endpoint_bank_r != {8{run_endpoint_bank_r[0]}})
            $error("V5 gate RUN endpoint banks diverged");
        if (rst_n && !local_clear && compute_valid && !compute_ready &&
            cache_rd_rsp_ready)
            $error("V5 gate cache response advanced without compute");
        if (rst_n && !local_clear && projection_valid &&
            projection_tag_empty)
            $error("V5 gate projection arrived without ordered tag");
    end
`endif

    initial begin
        if (ENFORCE_PRODUCTION_SHAPE &&
            (INTERMEDIATE_COLUMNS != 14336 || GROUPS != 128))
            $error("V5 gate scheduler frozen shape is 14336xgroup128");
        if (INTERMEDIATE_COLUMNS <= 0 ||
            (INTERMEDIATE_COLUMNS & 31) != 0 || GROUPS <= 0)
            $error("V5 gate scheduler test shape must be group32 aligned");
        if (TAIL_COLUMNS <= 0 || TAIL_COLUMNS > 48)
            $error("V5 gate scheduler tail shape is invalid");
        if (REQUEST_FIFO_DEPTH < 2 ||
            (REQUEST_FIFO_DEPTH & (REQUEST_FIFO_DEPTH-1)) != 0)
            $error("V5 gate request FIFO depth must be power-of-two >=2");
        if (PROJECTION_TAG_DEPTH < 8 ||
            (PROJECTION_TAG_DEPTH & (PROJECTION_TAG_DEPTH-1)) != 0)
            $error("V5 gate tag FIFO depth must be power-of-two >=8");
    end

endmodule
