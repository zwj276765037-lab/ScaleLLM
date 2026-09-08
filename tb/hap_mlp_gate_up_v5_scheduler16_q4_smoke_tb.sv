`timescale 1ns / 1ps

// Reduced-shape protocol, conservation and numerical smoke for the V5 gate
// scheduler.  Every ready/valid source is elastic: once valid rises its
// payload remains stable until the handshake.  Cache requests are retained
// in a real FIFO, and a projection pass becomes eligible only after the
// matching compute_last transaction has been accepted.
//
// The six 12-column projection passes are deinterleaved from the first four
// known-good SwiGLU tiles.  The scheduler must reconstruct the original four
// 16-column records, so its final A8 activation and metadata can be checked
// bit-for-bit against the independent frontend golden vectors.
module hap_mlp_gate_up_v5_scheduler16_q4_smoke_tb;
    localparam integer COLUMNS = 32;
    localparam integer GROUPS = 2;
    localparam integer SOURCE_TX =
        2*((COLUMNS+15)/16)*GROUPS;
    localparam integer COMPUTE_TX =
        2*((COLUMNS+11)/12)*GROUPS;
    localparam integer PASS_COUNT = 2*((COLUMNS+11)/12);
    localparam integer RECORD_COUNT = 2*((COLUMNS+15)/16);
    localparam integer CACHE_FIFO_DEPTH = 16;
    localparam integer COMPUTE_PAYLOAD_W =
        2 + 16*32*9 + 12*32*4 + 16*8 + 16*6 +
        12*8 + 12*6 + 12;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg command_valid = 1'b0;
    wire command_ready;
    reg activation_bank = 1'b0;
    reg activation_bank_ready = 1'b1;

    wire cache_rd_req_valid;
    reg cache_rd_req_ready = 1'b0;
    wire cache_rd_req_bank;
    wire [0:0] cache_rd_req_group;
    reg cache_rd_rsp_valid = 1'b0;
    wire cache_rd_rsp_ready;
    reg cache_rd_rsp_bank = 1'b0;
    reg [0:0] cache_rd_rsp_group = 1'b0;
    reg [16*32*8-1:0] cache_rd_rsp_u8 = '0;
    reg [16*24-1:0] cache_rd_rsp_meta = '0;

    reg weight_valid = 1'b0;
    wire weight_ready;
    reg signed [16*32*4-1:0] weights = '0;
    reg [223:0] weight_meta = '0;

    wire compute_valid;
    reg compute_ready = 1'b0;
    wire compute_first;
    wire compute_last;
    wire signed [16*32*9-1:0] compute_activation;
    wire signed [12*32*4-1:0] compute_weights;
    wire [16*8-1:0] compute_acode;
    wire [16*6-1:0] compute_ashift;
    wire [12*8-1:0] compute_wcode;
    wire [12*6-1:0] compute_wshift;
    wire [11:0] compute_mask;
    reg projection_valid = 1'b0;
    wire projection_ready;
    reg signed [16*12*24-1:0] projection = '0;

    wire activation_out_valid;
    reg activation_out_ready = 1'b0;
    wire [16*32*8-1:0] activation_out_u8;
    wire [16*24-1:0] activation_out_meta;
    wire busy;
    wire done;
    wire error;
    wire [31:0] source_count;
    wire [31:0] cache_count;
    wire [31:0] compute_count;
    wire [31:0] pass_count;
    wire [31:0] record_count;
    wire [31:0] product_count;
    wire [31:0] activation_count;

    hap_mlp_gate_up_v5_scheduler16_q4 #(
        .INTERMEDIATE_COLUMNS(COLUMNS), .GROUPS(GROUPS),
        .ENFORCE_PRODUCTION_SHAPE(0), .REQUEST_FIFO_DEPTH(4),
        .PROJECTION_TAG_DEPTH(8)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .command_valid(command_valid), .command_ready(command_ready),
        .activation_bank(activation_bank),
        .activation_bank_ready(activation_bank_ready),
        .cache_rd_req_valid(cache_rd_req_valid),
        .cache_rd_req_ready(cache_rd_req_ready),
        .cache_rd_req_bank(cache_rd_req_bank),
        .cache_rd_req_group(cache_rd_req_group),
        .cache_rd_rsp_valid(cache_rd_rsp_valid),
        .cache_rd_rsp_ready(cache_rd_rsp_ready),
        .cache_rd_rsp_bank(cache_rd_rsp_bank),
        .cache_rd_rsp_group(cache_rd_rsp_group),
        .cache_rd_rsp_u8x16x32(cache_rd_rsp_u8),
        .cache_rd_rsp_meta_u24x16(cache_rd_rsp_meta),
        .weight_valid(weight_valid), .weight_ready(weight_ready),
        .weights_s4x16x32(weights), .weight_meta_u224(weight_meta),
        .compute_valid(compute_valid), .compute_ready(compute_ready),
        .compute_first(compute_first), .compute_last(compute_last),
        .compute_activation_s9x16x32(compute_activation),
        .compute_weights_s4x12x32(compute_weights),
        .compute_activation_code_u8x16(compute_acode),
        .compute_activation_shift_u6x16(compute_ashift),
        .compute_weight_code_u8x12(compute_wcode),
        .compute_weight_shift_u6x12(compute_wshift),
        .compute_column_valid_u12(compute_mask),
        .projection_valid(projection_valid),
        .projection_ready(projection_ready),
        .projection_s24x16x12(projection),
        .activation_out_valid(activation_out_valid),
        .activation_out_ready(activation_out_ready),
        .activation_out_u8x16x32(activation_out_u8),
        .activation_out_meta_u24x16(activation_out_meta),
        .busy(busy), .done(done), .error(error),
        .source_transaction_count(source_count),
        .cache_request_count(cache_count),
        .compute_transaction_count(compute_count),
        .internal_projection_pass_count(pass_count),
        .external_projection_record_count(record_count),
        .product_group_count(product_count),
        .activation_group_count(activation_count), .saturation_count()
    );

    function automatic [3:0] weight_value;
        input integer matrix_index;
        input integer column_index;
        input integer group_index;
        input integer lane_index;
        begin
            weight_value = matrix_index*5 + column_index*7 +
                group_index*11 + lane_index*13 + 4'h1;
        end
    endfunction

    function automatic [7:0] weight_code_value;
        input integer matrix_index;
        input integer column_index;
        input integer group_index;
        begin
            weight_code_value = 8'h31 ^ (matrix_index*8'ha7) ^
                (column_index*8'h13) ^ (group_index*8'h25);
        end
    endfunction

    function automatic [5:0] weight_shift_value;
        input integer matrix_index;
        input integer column_index;
        input integer group_index;
        begin
            weight_shift_value = matrix_index*9 + column_index*3 +
                group_index*7 + 6'h0b;
        end
    endfunction

    function automatic [7:0] cache_u8_value;
        input integer row_index;
        input integer group_index;
        input integer lane_index;
        begin
            cache_u8_value = row_index*17 + group_index*29 +
                lane_index*7 + 8'h65;
        end
    endfunction

    function automatic [7:0] cache_zero_value;
        input integer row_index;
        input integer group_index;
        begin
            cache_zero_value = row_index*5 + group_index*11 + 8'h25;
        end
    endfunction

    function automatic [7:0] cache_code_value;
        input integer row_index;
        input integer group_index;
        begin
            cache_code_value = 8'h53 ^ (row_index*8'h17) ^
                (group_index*8'hc1);
        end
    endfunction

    function automatic [5:0] cache_shift_value;
        input integer row_index;
        input integer group_index;
        begin
            cache_shift_value = row_index*3 + group_index*7 + 6'h09;
        end
    endfunction

    task automatic make_weight_transaction;
        input integer transaction_index;
        output reg signed [16*32*4-1:0] payload;
        output reg [223:0] metadata;
        integer group_index;
        integer matrix_index;
        integer record_index;
        integer column_index;
        integer lane_index;
        integer global_column;
        begin
            group_index = transaction_index % GROUPS;
            matrix_index = (transaction_index/GROUPS) % 2;
            record_index = transaction_index/(2*GROUPS);
            payload = '0;
            metadata = '0;
            for (column_index = 0; column_index < 16;
                 column_index = column_index + 1) begin
                global_column = record_index*16 + column_index;
                metadata[column_index*8 +: 8] = weight_code_value(
                    matrix_index, global_column, group_index);
                metadata[128+column_index*6 +: 6] = weight_shift_value(
                    matrix_index, global_column, group_index);
                for (lane_index = 0; lane_index < 32;
                     lane_index = lane_index + 1)
                    payload[(column_index*32+lane_index)*4 +: 4] =
                        weight_value(matrix_index, global_column,
                            group_index, lane_index);
            end
        end
    endtask

    task automatic make_cache_response;
        input integer group_index;
        output reg [16*32*8-1:0] payload;
        output reg [16*24-1:0] metadata;
        integer row_index;
        integer lane_index;
        begin
            payload = '0;
            metadata = '0;
            for (row_index = 0; row_index < 16;
                 row_index = row_index + 1) begin
                metadata[row_index*24 +: 8] = cache_zero_value(
                    row_index, group_index);
                metadata[row_index*24+8 +: 8] = cache_code_value(
                    row_index, group_index);
                metadata[row_index*24+16 +: 6] = cache_shift_value(
                    row_index, group_index);
                metadata[row_index*24+22 +: 2] = 2'b00;
                for (lane_index = 0; lane_index < 32;
                     lane_index = lane_index + 1)
                    payload[(row_index*32+lane_index)*8 +: 8] =
                        cache_u8_value(row_index, group_index, lane_index);
            end
        end
    endtask

    integer mismatches = 0;
    task automatic check_compute_transaction;
        input integer transaction_index;
        integer pass_index;
        integer matrix_index;
        integer group_index;
        integer column_index;
        integer lane_index;
        integer row_index;
        integer global_column;
        integer valid_columns;
        integer bad;
        reg [11:0] expected_mask;
        reg [7:0] expected_u8;
        reg [7:0] expected_zero;
        reg signed [8:0] expected_activation;
        begin
            pass_index = transaction_index/(2*GROUPS);
            matrix_index = (transaction_index/GROUPS) % 2;
            group_index = transaction_index % GROUPS;
            valid_columns = COLUMNS-pass_index*12;
            if (valid_columns > 12)
                valid_columns = 12;
            expected_mask = (12'h001 << valid_columns) - 1'b1;
            bad = 0;

            if (compute_first !== (group_index == 0) ||
                compute_last !== (group_index == GROUPS-1) ||
                compute_mask !== expected_mask)
                bad = 1;

            for (column_index = 0; column_index < 12;
                 column_index = column_index + 1) begin
                global_column = pass_index*12 + column_index;
                if (column_index < valid_columns) begin
                    if (compute_wcode[column_index*8 +: 8] !==
                            weight_code_value(matrix_index, global_column,
                                group_index) ||
                        compute_wshift[column_index*6 +: 6] !==
                            weight_shift_value(matrix_index, global_column,
                                group_index))
                        bad = 1;
                    for (lane_index = 0; lane_index < 32;
                         lane_index = lane_index + 1)
                        if (compute_weights[
                                (column_index*32+lane_index)*4 +: 4] !==
                            weight_value(matrix_index, global_column,
                                group_index, lane_index))
                            bad = 1;
                end else begin
                    if (compute_wcode[column_index*8 +: 8] !== 8'd0 ||
                        compute_wshift[column_index*6 +: 6] !== 6'd0)
                        bad = 1;
                    for (lane_index = 0; lane_index < 32;
                         lane_index = lane_index + 1)
                        if (compute_weights[
                                (column_index*32+lane_index)*4 +: 4] !==
                            4'd0)
                            bad = 1;
                end
            end

            for (row_index = 0; row_index < 16;
                 row_index = row_index + 1) begin
                if (compute_acode[row_index*8 +: 8] !==
                        cache_code_value(row_index, group_index) ||
                    compute_ashift[row_index*6 +: 6] !==
                        cache_shift_value(row_index, group_index))
                    bad = 1;
                expected_zero = cache_zero_value(row_index, group_index);
                for (lane_index = 0; lane_index < 32;
                     lane_index = lane_index + 1) begin
                    expected_u8 = cache_u8_value(
                        row_index, group_index, lane_index);
                    expected_activation =
                        $signed({1'b0, expected_u8}) -
                        $signed({1'b0, expected_zero});
                    if (compute_activation[
                            (row_index*32+lane_index)*9 +: 9] !==
                        expected_activation)
                        bad = 1;
                end
            end

            if (bad) begin
                mismatches = mismatches + 1;
                $display("MISMATCH: compute transaction=%0d pass=%0d matrix=%0d group=%0d mask=%03x",
                    transaction_index, pass_index, matrix_index,
                    group_index, compute_mask);
            end
        end
    endtask

    // Independent known-good projection/frontend vectors.  The first four
    // tiles describe one 32-column gate/up group in gate0,up0,gate1,up1
    // order.  The six pass vectors below are built once at time zero.
    reg [16*16*24-1:0] golden_tile_mem [0:11];
    reg [16*32*8-1:0] golden_activation_mem [0:2];
    reg [16*24-1:0] golden_meta_mem [0:2];
    reg signed [16*12*24-1:0] projection_mem [0:PASS_COUNT-1];
    integer init_pass;
    integer init_matrix;
    integer init_row;
    integer init_lane;
    integer init_column;
    integer init_tile;
    initial begin
        $readmemh(
            "data/mlp_swiglu_product_frontend16_q4/projection_tiles_s24x16x16.mem",
            golden_tile_mem);
        $readmemh(
            "data/mlp_swiglu_product_frontend16_q4/expected_u8x16x32.mem",
            golden_activation_mem);
        $readmemh(
            "data/mlp_swiglu_product_frontend16_q4/expected_meta_u24x16.mem",
            golden_meta_mem);
        for (init_pass = 0; init_pass < PASS_COUNT;
             init_pass = init_pass + 1) begin
            projection_mem[init_pass] = '1;
            init_matrix = init_pass % 2;
            for (init_row = 0; init_row < 16;
                 init_row = init_row + 1)
                for (init_lane = 0; init_lane < 12;
                     init_lane = init_lane + 1) begin
                    init_column = (init_pass/2)*12 + init_lane;
                    if (init_column < COLUMNS) begin
                        init_tile = init_matrix +
                            2*(init_column/16);
                        projection_mem[init_pass][
                            (init_row*12+init_lane)*24 +: 24] =
                            golden_tile_mem[init_tile][
                                (init_row*16+(init_column%16))*24 +: 24];
                    end
                end
        end
    end

    // Deterministic pseudo-random backpressure.  The forced output stall
    // guarantees that the single final activation also exercises stability.
    reg [31:0] lfsr = 32'h6d2b79f5;
    integer cycles = 0;
    integer activation_stall_cycles = 0;
    integer cache_pending_count = 0;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            lfsr <= 32'h6d2b79f5;
            cache_rd_req_ready <= 1'b0;
            compute_ready <= 1'b0;
            activation_out_ready <= 1'b0;
        end else begin
            lfsr <= {lfsr[30:0],
                lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
            cache_rd_req_ready <=
                (cache_pending_count < CACHE_FIFO_DEPTH) &&
                (lfsr[0] || lfsr[5]);
            compute_ready <= lfsr[3] || lfsr[11];
            if (activation_stall_cycles < 3)
                activation_out_ready <= 1'b0;
            else
                activation_out_ready <= lfsr[7] || lfsr[19];
        end
    end

    // Elastic weight producer.  The first item is deliberately presented
    // before command acceptance, proving payload stability while ready=0.
    integer weight_sent = 0;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            weight_valid <= 1'b0;
            weight_sent <= 0;
            weights <= '0;
            weight_meta <= '0;
        end else begin
            if (weight_valid && weight_ready) begin
                weight_valid <= 1'b0;
                weight_sent <= weight_sent + 1;
            end else if (!weight_valid && weight_sent < SOURCE_TX &&
                (weight_sent == 0 || lfsr[2] || lfsr[14])) begin
                make_weight_transaction(weight_sent, weights, weight_meta);
                weight_valid <= 1'b1;
            end
        end
    end

    // FIFO-backed activation-cache responder.  A request remains queued
    // until its registered response is actually consumed; no request can be
    // overwritten by a later one.
    reg pending_bank_mem [0:CACHE_FIFO_DEPTH-1];
    reg [0:0] pending_group_mem [0:CACHE_FIFO_DEPTH-1];
    integer cache_pending_wr = 0;
    integer cache_pending_rd = 0;
    wire cache_request_fire = cache_rd_req_valid && cache_rd_req_ready;
    wire cache_response_fire = cache_rd_rsp_valid && cache_rd_rsp_ready;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cache_pending_count <= 0;
            cache_pending_wr <= 0;
            cache_pending_rd <= 0;
            cache_rd_rsp_valid <= 1'b0;
            cache_rd_rsp_bank <= 1'b0;
            cache_rd_rsp_group <= 1'b0;
            cache_rd_rsp_u8 <= '0;
            cache_rd_rsp_meta <= '0;
        end else begin
            if (cache_request_fire) begin
                pending_bank_mem[cache_pending_wr] <= cache_rd_req_bank;
                pending_group_mem[cache_pending_wr] <= cache_rd_req_group;
                cache_pending_wr <=
                    (cache_pending_wr + 1) % CACHE_FIFO_DEPTH;
            end
            if (cache_response_fire) begin
                cache_rd_rsp_valid <= 1'b0;
                cache_pending_rd <=
                    (cache_pending_rd + 1) % CACHE_FIFO_DEPTH;
            end
            case ({cache_request_fire, cache_response_fire})
                2'b10: cache_pending_count <= cache_pending_count + 1;
                2'b01: cache_pending_count <= cache_pending_count - 1;
                default: cache_pending_count <= cache_pending_count;
            endcase

            if (!cache_rd_rsp_valid && cache_pending_count != 0 &&
                (lfsr[4] || lfsr[16])) begin
                cache_rd_rsp_bank <=
                    pending_bank_mem[cache_pending_rd];
                cache_rd_rsp_group <=
                    pending_group_mem[cache_pending_rd];
                make_cache_response(
                    pending_group_mem[cache_pending_rd],
                    cache_rd_rsp_u8, cache_rd_rsp_meta);
                cache_rd_rsp_valid <= 1'b1;
            end
        end
    end

    // Ordered projection completion queue.  completed_pass_count advances
    // only on compute_last acceptance, and the producer may load only an
    // already-completed pass.  Payload remains registered through stalls.
    integer completed_pass_count = 0;
    integer projection_sent = 0;
    wire projection_fire = projection_valid && projection_ready;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            projection_valid <= 1'b0;
            projection_sent <= 0;
            projection <= '0;
        end else begin
            if (projection_fire) begin
                projection_valid <= 1'b0;
                projection_sent <= projection_sent + 1;
            end else if (!projection_valid &&
                projection_sent < completed_pass_count &&
                (lfsr[6] || lfsr[23])) begin
                projection <= projection_mem[projection_sent];
                projection_valid <= 1'b1;
            end
        end
    end

    wire compute_fire = compute_valid && compute_ready;
    wire activation_fire = activation_out_valid && activation_out_ready;
    integer request_seen = 0;
    integer response_seen = 0;
    integer compute_seen = 0;
    integer activation_seen = 0;
    reg done_seen = 1'b0;
    reg error_seen = 1'b0;

    integer weight_stalls = 0;
    integer request_stalls = 0;
    integer response_stalls = 0;
    integer compute_stalls = 0;
    integer projection_stalls = 0;
    integer activation_stalls = 0;
    integer weight_stability = 0;
    integer request_stability = 0;
    integer response_stability = 0;
    integer compute_stability = 0;
    integer projection_stability = 0;
    integer activation_stability = 0;

    reg weight_stalled_r = 1'b0;
    reg request_stalled_r = 1'b0;
    reg response_stalled_r = 1'b0;
    reg compute_stalled_r = 1'b0;
    reg projection_stalled_r = 1'b0;
    reg activation_stalled_r = 1'b0;
    reg [16*32*4+224-1:0] held_weight;
    reg [1:0] held_request;
    reg [1+1+16*32*8+16*24-1:0] held_response;
    reg [COMPUTE_PAYLOAD_W-1:0] held_compute;
    reg [16*12*24-1:0] held_projection;
    reg [16*32*8+16*24-1:0] held_activation;

    wire [16*32*4+224-1:0] weight_payload =
        {weights, weight_meta};
    wire [1:0] request_payload =
        {cache_rd_req_bank, cache_rd_req_group};
    wire [1+1+16*32*8+16*24-1:0] response_payload =
        {cache_rd_rsp_bank, cache_rd_rsp_group,
         cache_rd_rsp_u8, cache_rd_rsp_meta};
    wire [COMPUTE_PAYLOAD_W-1:0] compute_payload =
        {compute_first, compute_last, compute_activation, compute_weights,
         compute_acode, compute_ashift, compute_wcode, compute_wshift,
         compute_mask};
    wire [16*12*24-1:0] projection_payload = projection;
    wire [16*32*8+16*24-1:0] activation_payload =
        {activation_out_u8, activation_out_meta};

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            cycles <= 0;
            request_seen <= 0;
            response_seen <= 0;
            compute_seen <= 0;
            completed_pass_count <= 0;
            activation_seen <= 0;
            done_seen <= 1'b0;
            error_seen <= 1'b0;
            activation_stall_cycles <= 0;
            weight_stalls <= 0;
            request_stalls <= 0;
            response_stalls <= 0;
            compute_stalls <= 0;
            projection_stalls <= 0;
            activation_stalls <= 0;
            weight_stability <= 0;
            request_stability <= 0;
            response_stability <= 0;
            compute_stability <= 0;
            projection_stability <= 0;
            activation_stability <= 0;
            weight_stalled_r <= 1'b0;
            request_stalled_r <= 1'b0;
            response_stalled_r <= 1'b0;
            compute_stalled_r <= 1'b0;
            projection_stalled_r <= 1'b0;
            activation_stalled_r <= 1'b0;
        end else begin
            cycles <= cycles + 1;
            if (error)
                error_seen <= 1'b1;
            if (done)
                done_seen <= 1'b1;

            if (cache_request_fire) begin
                if (cache_rd_req_bank !== activation_bank ||
                    cache_rd_req_group !== request_seen % GROUPS) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: cache request=%0d bank=%0d group=%0d",
                        request_seen, cache_rd_req_bank,
                        cache_rd_req_group);
                end
                request_seen <= request_seen + 1;
            end
            if (cache_response_fire)
                response_seen <= response_seen + 1;
            if (compute_fire) begin
                check_compute_transaction(compute_seen);
                compute_seen <= compute_seen + 1;
                if (compute_last)
                    completed_pass_count <= completed_pass_count + 1;
            end
            if (activation_fire) begin
                if (activation_seen != 0 ||
                    activation_out_u8 !== golden_activation_mem[0] ||
                    activation_out_meta !== golden_meta_mem[0]) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: final activation index=%0d",
                        activation_seen);
                end
                activation_seen <= activation_seen + 1;
            end

            if (weight_stalled_r) begin
                weight_stability <= weight_stability + 1;
                if (!weight_valid || weight_payload !== held_weight) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: weight source changed while stalled");
                end
            end
            if (request_stalled_r) begin
                request_stability <= request_stability + 1;
                if (!cache_rd_req_valid ||
                    request_payload !== held_request) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: cache request changed while stalled");
                end
            end
            if (response_stalled_r) begin
                response_stability <= response_stability + 1;
                if (!cache_rd_rsp_valid ||
                    response_payload !== held_response) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: cache response changed while stalled");
                end
            end
            if (compute_stalled_r) begin
                compute_stability <= compute_stability + 1;
                if (!compute_valid || compute_payload !== held_compute) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: compute output changed while stalled");
                end
            end
            if (projection_stalled_r) begin
                projection_stability <= projection_stability + 1;
                if (!projection_valid ||
                    projection_payload !== held_projection) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: projection source changed while stalled");
                end
            end
            if (activation_stalled_r) begin
                activation_stability <= activation_stability + 1;
                if (!activation_out_valid ||
                    activation_payload !== held_activation) begin
                    mismatches = mismatches + 1;
                    $display("MISMATCH: activation output changed while stalled");
                end
            end

            weight_stalled_r <= weight_valid && !weight_ready;
            request_stalled_r <= cache_rd_req_valid &&
                !cache_rd_req_ready;
            response_stalled_r <= cache_rd_rsp_valid &&
                !cache_rd_rsp_ready;
            compute_stalled_r <= compute_valid && !compute_ready;
            projection_stalled_r <= projection_valid && !projection_ready;
            activation_stalled_r <= activation_out_valid &&
                !activation_out_ready;
            if (weight_valid && !weight_ready) begin
                held_weight <= weight_payload;
                weight_stalls <= weight_stalls + 1;
            end
            if (cache_rd_req_valid && !cache_rd_req_ready) begin
                held_request <= request_payload;
                request_stalls <= request_stalls + 1;
            end
            if (cache_rd_rsp_valid && !cache_rd_rsp_ready) begin
                held_response <= response_payload;
                response_stalls <= response_stalls + 1;
            end
            if (compute_valid && !compute_ready) begin
                held_compute <= compute_payload;
                compute_stalls <= compute_stalls + 1;
            end
            if (projection_valid && !projection_ready) begin
                held_projection <= projection_payload;
                projection_stalls <= projection_stalls + 1;
            end
            if (activation_out_valid && !activation_out_ready) begin
                held_activation <= activation_payload;
                activation_stalls <= activation_stalls + 1;
                activation_stall_cycles <= activation_stall_cycles + 1;
            end
        end
    end

    initial begin
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (6) @(posedge clk);
        command_valid <= 1'b1;
        do @(posedge clk); while (!command_ready);
        command_valid <= 1'b0;

        wait (done_seen || cycles >= 200000);
        @(negedge clk);
        if (!done_seen || error_seen || error || mismatches != 0 ||
            weight_sent != SOURCE_TX || request_seen != COMPUTE_TX ||
            response_seen != COMPUTE_TX || compute_seen != COMPUTE_TX ||
            completed_pass_count != PASS_COUNT ||
            projection_sent != PASS_COUNT || activation_seen != 1 ||
            cache_pending_count != 0 || cache_rd_rsp_valid ||
            source_count != SOURCE_TX || cache_count != COMPUTE_TX ||
            compute_count != COMPUTE_TX || pass_count != PASS_COUNT ||
            record_count != RECORD_COUNT || product_count != 1 ||
            activation_count != 1 || weight_stalls == 0 ||
            request_stalls == 0 || response_stalls == 0 ||
            compute_stalls == 0 || projection_stalls == 0 ||
            activation_stalls == 0 || weight_stability == 0 ||
            request_stability == 0 || response_stability == 0 ||
            compute_stability == 0 || projection_stability == 0 ||
            activation_stability == 0) begin
            $display("FAIL: gate V5 smoke done=%0d err=%0d mism=%0d weights=%0d/%0d req/rsp/compute=%0d/%0d/%0d expected=%0d completed/projection=%0d/%0d expected=%0d source/cache/compute/pass/record=%0d/%0d/%0d/%0d/%0d product/activation=%0d/%0d pending=%0d stalls=%0d/%0d/%0d/%0d/%0d/%0d stable=%0d/%0d/%0d/%0d/%0d/%0d cycles=%0d",
                done_seen, error_seen || error, mismatches,
                weight_sent, SOURCE_TX, request_seen, response_seen,
                compute_seen, COMPUTE_TX, completed_pass_count,
                projection_sent, PASS_COUNT, source_count, cache_count,
                compute_count, pass_count, record_count, product_count,
                activation_count, cache_pending_count, weight_stalls,
                request_stalls, response_stalls, compute_stalls,
                projection_stalls, activation_stalls, weight_stability,
                request_stability, response_stability, compute_stability,
                projection_stability, activation_stability, cycles);
            $fatal(1, "gate V5 scheduler smoke failed");
        end else begin
            $display("PASS: gate V5 scheduler bit-exact conservation source=%0d internal=%0d passes=%0d records=%0d activation=%0d stalls=%0d/%0d/%0d/%0d/%0d/%0d stable=%0d/%0d/%0d/%0d/%0d/%0d cycles=%0d mismatches=0",
                source_count, compute_count, pass_count, record_count,
                activation_count, weight_stalls, request_stalls,
                response_stalls, compute_stalls, projection_stalls,
                activation_stalls, weight_stability, request_stability,
                response_stability, compute_stability,
                projection_stability, activation_stability, cycles);
            $finish;
        end
    end
endmodule
