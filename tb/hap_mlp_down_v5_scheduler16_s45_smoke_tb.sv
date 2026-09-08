`timescale 1ns / 1ps

// Production-congruent reduced-shape protocol smoke for the V5 down
// scheduler.  OUTPUT_COLUMNS=64 exercises one complete 48-column block and
// the production-like 16-column tail (12/4 kernel masks).  GROUPS=3 makes
// first, middle and last accumulation modes independently observable.
module hap_mlp_down_v5_scheduler16_s45_smoke_tb;
    localparam integer OUTPUT_COLUMNS = 64;
    localparam integer GROUPS = 3;
    localparam integer SOURCE_RECORDS = (OUTPUT_COLUMNS+15)/16;
    localparam integer COMPUTE_TILES = (OUTPUT_COLUMNS+11)/12;
    localparam integer BLOCKS = (OUTPUT_COLUMNS+47)/48;
    localparam integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS);
    localparam integer SOURCE_W =
        (SOURCE_RECORDS <= 2) ? 1 : $clog2(SOURCE_RECORDS);
    localparam integer TILE_W =
        (COMPUTE_TILES <= 2) ? 1 : $clog2(COMPUTE_TILES);
    localparam integer TOTAL_SOURCE = GROUPS*SOURCE_RECORDS;
    localparam integer TOTAL_COMPUTE = GROUPS*COMPUTE_TILES;
    localparam integer TIMEOUT_CYCLES = 20000;

    localparam [1:0] PH_IDLE = 2'd0;
    localparam [1:0] PH_NEGATIVE = 2'd1;
    localparam [1:0] PH_RUN = 2'd2;
    localparam [1:0] PH_POST = 2'd3;

    reg clk = 1'b0;
    always #3.333 clk = ~clk;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg enable = 1'b0;
    reg [1:0] phase = PH_IDLE;

    reg activation_valid = 1'b0;
    wire activation_ready;
    wire [16*32*8-1:0] activation_u8x16x32;
    wire [16*24-1:0] activation_meta_u24x16;

    reg weight_valid = 1'b0;
    wire weight_ready;
    wire signed [16*32*4-1:0] weights_s4x16x32;
    wire [223:0] weight_meta_u224;

    wire compute_valid;
    reg compute_ready = 1'b0;
    wire compute_first;
    wire compute_last;
    wire [TILE_W-1:0] compute_tile;
    wire signed [16*32*9-1:0] compute_activation_s9x16x32;
    wire signed [12*32*4-1:0] compute_weights_s4x12x32;
    wire [16*8-1:0] compute_activation_code_u8x16;
    wire [16*6-1:0] compute_activation_shift_u6x16;
    wire [12*8-1:0] compute_weight_code_u8x12;
    wire [12*6-1:0] compute_weight_shift_u6x12;
    wire [11:0] compute_column_valid_u12;

    reg projection_valid = 1'b0;
    wire projection_ready;
    wire [TILE_W-1:0] projection_tile;
    wire signed [16*12*24-1:0] projection_s24x16x12;

    wire out_valid;
    reg out_ready = 1'b0;
    wire [SOURCE_W-1:0] out_record_index;
    wire signed [16*16*24-1:0] out_projection_s24x16x16;
    wire busy;
    wire done;
    wire error;
    wire [31:0] activation_group_count;
    wire [31:0] source_record_count;
    wire [31:0] compute_transaction_count;
    wire [31:0] projection_pass_count;
    wire [31:0] output_record_count;

    integer activation_sent = 0;
    integer weight_sent = 0;
    integer projection_sent = 0;
    integer projection_available = 0;
    integer compute_seen = 0;
    integer output_seen = 0;
    integer done_pulses = 0;
    integer run_cycles = 0;
    integer mismatch_count = 0;
    integer runtime_error_seen = 0;
    integer activation_stall_checks = 0;
    integer weight_stall_checks = 0;
    integer compute_stall_checks = 0;
    integer projection_stall_checks = 0;
    integer output_stall_checks = 0;
    integer compute_backpressure_cycles = 0;
    integer output_backpressure_cycles = 0;
    integer boundary_stall_checks = 0;
    integer first_mode_count = 0;
    integer middle_mode_count = 0;
    integer last_mode_count = 0;
    integer source_bubble_cycles = 0;
    integer projection_bubble_cycles = 0;
    integer driver_cycle = 0;
    reg [31:0] lfsr = 32'h6d2b_79f5;
    reg boundary_hold_r = 1'b0;

    function automatic [7:0] expected_zero_point;
        input integer group_index;
        input integer row_index;
        begin
            expected_zero_point = 8'd80 + group_index*7 + row_index;
        end
    endfunction

    function automatic signed [8:0] expected_centered;
        input integer group_index;
        input integer row_index;
        input integer lane_index;
        integer value;
        begin
            value = ((group_index*13 + row_index*5 + lane_index*3) % 31)
                - 15;
            expected_centered = value;
        end
    endfunction

    function automatic [7:0] expected_activation_code;
        input integer group_index;
        input integer row_index;
        begin
            expected_activation_code = 8'h21 + group_index*8'h19 +
                row_index*8'h07;
        end
    endfunction

    function automatic [5:0] expected_activation_shift;
        input integer group_index;
        input integer row_index;
        begin
            expected_activation_shift =
                (group_index*11 + row_index*3 + 1) & 6'h3f;
        end
    endfunction

    function automatic [16*32*8-1:0] make_activation;
        input integer group_index;
        integer row_index;
        integer lane_index;
        integer sample;
        begin
            make_activation = '0;
            for (row_index = 0; row_index < 16; row_index = row_index+1)
                for (lane_index = 0; lane_index < 32;
                     lane_index = lane_index+1) begin
                    sample = expected_zero_point(group_index, row_index) +
                        expected_centered(group_index, row_index, lane_index);
                    make_activation[(row_index*32+lane_index)*8 +: 8] =
                        sample[7:0];
                end
        end
    endfunction

    function automatic [16*24-1:0] make_activation_meta;
        input integer group_index;
        integer row_index;
        begin
            make_activation_meta = '0;
            for (row_index = 0; row_index < 16; row_index = row_index+1) begin
                make_activation_meta[row_index*24 +: 8] =
                    expected_zero_point(group_index, row_index);
                make_activation_meta[row_index*24+8 +: 8] =
                    expected_activation_code(group_index, row_index);
                make_activation_meta[row_index*24+16 +: 6] =
                    expected_activation_shift(group_index, row_index);
                make_activation_meta[row_index*24+22 +: 2] = 2'b00;
            end
        end
    endfunction

    function automatic signed [3:0] expected_weight;
        input integer group_index;
        input integer column_index;
        input integer lane_index;
        integer value;
        begin
            value = (group_index*5 + column_index*3 + lane_index*7) % 16;
            expected_weight = value - 8;
        end
    endfunction

    function automatic [7:0] expected_weight_code;
        input integer group_index;
        input integer column_index;
        begin
            expected_weight_code = 8'h35 ^ (group_index*8'h29) ^
                (column_index*8'h13);
        end
    endfunction

    function automatic [5:0] expected_weight_shift;
        input integer group_index;
        input integer column_index;
        begin
            expected_weight_shift =
                (group_index*17 + column_index*5 + 2) & 6'h3f;
        end
    endfunction

    function automatic [16*32*4-1:0] make_weight_record;
        input integer transaction_index;
        integer group_index;
        integer record_index;
        integer column_index;
        integer lane_index;
        integer absolute_column;
        begin
            group_index = transaction_index / SOURCE_RECORDS;
            record_index = transaction_index % SOURCE_RECORDS;
            make_weight_record = '0;
            for (column_index = 0; column_index < 16;
                 column_index = column_index+1) begin
                absolute_column = record_index*16 + column_index;
                for (lane_index = 0; lane_index < 32;
                     lane_index = lane_index+1)
                    make_weight_record[(column_index*32+lane_index)*4 +: 4] =
                        expected_weight(group_index, absolute_column,
                                        lane_index);
            end
        end
    endfunction

    function automatic [223:0] make_weight_meta;
        input integer transaction_index;
        integer group_index;
        integer record_index;
        integer column_index;
        integer absolute_column;
        begin
            group_index = transaction_index / SOURCE_RECORDS;
            record_index = transaction_index % SOURCE_RECORDS;
            make_weight_meta = '0;
            for (column_index = 0; column_index < 16;
                 column_index = column_index+1) begin
                absolute_column = record_index*16 + column_index;
                make_weight_meta[column_index*8 +: 8] =
                    expected_weight_code(group_index, absolute_column);
                make_weight_meta[128+column_index*6 +: 6] =
                    expected_weight_shift(group_index, absolute_column);
            end
        end
    endfunction

    function automatic signed [23:0] expected_projection;
        input integer column_index;
        input integer row_index;
        integer value;
        begin
            value = 37 + column_index*1009 + row_index*131;
            if (((column_index + row_index) % 3) == 0)
                value = -value;
            expected_projection = value;
        end
    endfunction

    function automatic [16*12*24-1:0] make_projection_pass;
        input integer tile_index;
        integer row_index;
        integer lane_index;
        integer absolute_column;
        begin
            make_projection_pass = '0;
            for (row_index = 0; row_index < 16; row_index = row_index+1)
                for (lane_index = 0; lane_index < 12;
                     lane_index = lane_index+1) begin
                    absolute_column = tile_index*12 + lane_index;
                    if (absolute_column < OUTPUT_COLUMNS)
                        make_projection_pass[
                            (row_index*12+lane_index)*24 +: 24] =
                            expected_projection(absolute_column, row_index);
                    else
                        // Poison invalid final-pass lanes; a bad mask would
                        // make the numerical output check fail.
                        make_projection_pass[
                            (row_index*12+lane_index)*24 +: 24] =
                            24'h5a0000 + row_index*16 + lane_index;
                end
        end
    endfunction

    function automatic [11:0] expected_tile_mask;
        input integer tile_index;
        integer remaining;
        begin
            remaining = OUTPUT_COLUMNS - tile_index*12;
            if (remaining >= 12)
                expected_tile_mask = 12'hfff;
            else
                expected_tile_mask = (12'h001 << remaining) - 1'b1;
        end
    endfunction

    assign activation_u8x16x32 = make_activation(activation_sent);
    assign activation_meta_u24x16 = make_activation_meta(activation_sent);
    assign weights_s4x16x32 = make_weight_record(weight_sent);
    assign weight_meta_u224 = make_weight_meta(weight_sent);
    assign projection_tile = phase == PH_NEGATIVE ?
        {{(TILE_W-1){1'b0}}, 1'b1} : projection_sent[TILE_W-1:0];
    assign projection_s24x16x12 = make_projection_pass(projection_tile);

    hap_mlp_down_v5_scheduler16_s45 #(
        .OUTPUT_COLUMNS(OUTPUT_COLUMNS), .GROUPS(GROUPS),
        .ENFORCE_PRODUCTION_SHAPE(0)
    ) dut (
        .clk(clk), .rst_n(rst_n), .clear(clear), .enable(enable),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .weight_valid(weight_valid), .weight_ready(weight_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224),
        .compute_valid(compute_valid), .compute_ready(compute_ready),
        .compute_first(compute_first), .compute_last(compute_last),
        .compute_tile(compute_tile),
        .compute_activation_s9x16x32(compute_activation_s9x16x32),
        .compute_weights_s4x12x32(compute_weights_s4x12x32),
        .compute_activation_code_u8x16(compute_activation_code_u8x16),
        .compute_activation_shift_u6x16(compute_activation_shift_u6x16),
        .compute_weight_code_u8x12(compute_weight_code_u8x12),
        .compute_weight_shift_u6x12(compute_weight_shift_u6x12),
        .compute_column_valid_u12(compute_column_valid_u12),
        .projection_valid(projection_valid),
        .projection_ready(projection_ready),
        .projection_tile(projection_tile),
        .projection_s24x16x12(projection_s24x16x12),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_record_index(out_record_index),
        .out_projection_s24x16x16(out_projection_s24x16x16),
        .busy(busy), .done(done), .error(error),
        .activation_group_count(activation_group_count),
        .source_record_count(source_record_count),
        .compute_transaction_count(compute_transaction_count),
        .projection_pass_count(projection_pass_count),
        .output_record_count(output_record_count)
    );

    task automatic note_mismatch;
        input string reason;
        begin
            if (mismatch_count < 24)
                $display("MISMATCH: %s", reason);
            mismatch_count = mismatch_count + 1;
        end
    endtask

    task automatic check_compute_transaction;
        integer expected_group_index;
        integer expected_tile_index;
        integer row_index;
        integer column_index;
        integer lane_index;
        integer absolute_column;
        reg [11:0] mask_value;
        begin
            expected_group_index = compute_seen / COMPUTE_TILES;
            expected_tile_index = compute_seen % COMPUTE_TILES;
            mask_value = expected_tile_mask(expected_tile_index);
            if (compute_tile !== expected_tile_index[TILE_W-1:0])
                note_mismatch($sformatf(
                    "compute order got tile=%0d expected=%0d tx=%0d",
                    compute_tile, expected_tile_index, compute_seen));
            if (compute_first !== (expected_group_index == 0))
                note_mismatch($sformatf(
                    "compute_first group=%0d tile=%0d got=%0d",
                    expected_group_index, expected_tile_index, compute_first));
            if (compute_last !== (expected_group_index == GROUPS-1))
                note_mismatch($sformatf(
                    "compute_last group=%0d tile=%0d got=%0d",
                    expected_group_index, expected_tile_index, compute_last));
            if (compute_column_valid_u12 !== mask_value)
                note_mismatch($sformatf(
                    "compute mask group=%0d tile=%0d got=%h expected=%h",
                    expected_group_index, expected_tile_index,
                    compute_column_valid_u12, mask_value));

            for (row_index = 0; row_index < 16; row_index = row_index+1) begin
                if (compute_activation_code_u8x16[row_index*8 +: 8] !==
                    expected_activation_code(expected_group_index, row_index))
                    note_mismatch($sformatf(
                        "activation code group=%0d tile=%0d row=%0d",
                        expected_group_index, expected_tile_index, row_index));
                if (compute_activation_shift_u6x16[row_index*6 +: 6] !==
                    expected_activation_shift(expected_group_index, row_index))
                    note_mismatch($sformatf(
                        "activation shift group=%0d tile=%0d row=%0d",
                        expected_group_index, expected_tile_index, row_index));
                for (lane_index = 0; lane_index < 32;
                     lane_index = lane_index+1)
                    if (compute_activation_s9x16x32[
                            (row_index*32+lane_index)*9 +: 9] !==
                        expected_centered(expected_group_index, row_index,
                                          lane_index))
                        note_mismatch($sformatf(
                            "activation value group=%0d tile=%0d row=%0d lane=%0d",
                            expected_group_index, expected_tile_index,
                            row_index, lane_index));
            end

            for (column_index = 0; column_index < 12;
                 column_index = column_index+1) begin
                absolute_column = expected_tile_index*12 + column_index;
                if (absolute_column < OUTPUT_COLUMNS) begin
                    if (compute_weight_code_u8x12[column_index*8 +: 8] !==
                        expected_weight_code(expected_group_index,
                                             absolute_column))
                        note_mismatch($sformatf(
                            "weight code group=%0d tile=%0d column=%0d",
                            expected_group_index, expected_tile_index,
                            column_index));
                    if (compute_weight_shift_u6x12[column_index*6 +: 6] !==
                        expected_weight_shift(expected_group_index,
                                              absolute_column))
                        note_mismatch($sformatf(
                            "weight shift group=%0d tile=%0d column=%0d",
                            expected_group_index, expected_tile_index,
                            column_index));
                    for (lane_index = 0; lane_index < 32;
                         lane_index = lane_index+1)
                        if (compute_weights_s4x12x32[
                                (column_index*32+lane_index)*4 +: 4] !==
                            expected_weight(expected_group_index,
                                            absolute_column, lane_index))
                            note_mismatch($sformatf(
                                "weight value group=%0d tile=%0d column=%0d lane=%0d",
                                expected_group_index, expected_tile_index,
                                column_index, lane_index));
                end else begin
                    if (compute_weight_code_u8x12[column_index*8 +: 8] !== 0 ||
                        compute_weight_shift_u6x12[
                            column_index*6 +: 6] !== 0)
                        note_mismatch($sformatf(
                            "invalid tail metadata nonzero tile=%0d column=%0d",
                            expected_tile_index, column_index));
                    for (lane_index = 0; lane_index < 32;
                         lane_index = lane_index+1)
                        if (compute_weights_s4x12x32[
                                (column_index*32+lane_index)*4 +: 4] !== 0)
                            note_mismatch($sformatf(
                                "invalid tail weight nonzero tile=%0d column=%0d lane=%0d",
                                expected_tile_index, column_index, lane_index));
                end
            end
        end
    endtask

    task automatic check_output_record;
        integer row_index;
        integer column_index;
        integer absolute_column;
        begin
            if (out_record_index !== output_seen[SOURCE_W-1:0])
                note_mismatch($sformatf(
                    "output order got record=%0d expected=%0d",
                    out_record_index, output_seen));
            for (row_index = 0; row_index < 16; row_index = row_index+1)
                for (column_index = 0; column_index < 16;
                     column_index = column_index+1) begin
                    absolute_column = output_seen*16 + column_index;
                    if (out_projection_s24x16x16[
                            (row_index*16+column_index)*24 +: 24] !==
                        expected_projection(absolute_column, row_index))
                        note_mismatch($sformatf(
                            "output value record=%0d row=%0d column=%0d",
                            output_seen, row_index, column_index));
                end
        end
    endtask

    // All source payloads are functions of counters that advance only on a
    // handshake.  Random bubbles are inserted before asserting valid, and
    // valid remains asserted through any stall.
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            activation_valid <= 1'b0;
            weight_valid <= 1'b0;
            projection_valid <= 1'b0;
            activation_sent <= 0;
            weight_sent <= 0;
            projection_sent <= 0;
            driver_cycle <= 0;
            lfsr <= 32'h6d2b_79f5;
        end else if (phase == PH_NEGATIVE) begin
            activation_valid <= 1'b0;
            weight_valid <= 1'b0;
            projection_valid <= !error;
        end else if (phase == PH_RUN) begin
            driver_cycle <= driver_cycle + 1;
            lfsr <= {lfsr[30:0],
                lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
            if (activation_valid && activation_ready) begin
                activation_sent <= activation_sent + 1;
                activation_valid <= 1'b0;
            end else if (!activation_valid && activation_sent < GROUPS) begin
                if (lfsr[0] || lfsr[5])
                    activation_valid <= 1'b1;
                else
                    source_bubble_cycles <= source_bubble_cycles + 1;
            end

            if (weight_valid && weight_ready) begin
                weight_sent <= weight_sent + 1;
                weight_valid <= 1'b0;
            end else if (!weight_valid && weight_sent < TOTAL_SOURCE) begin
                if (lfsr[2] || lfsr[9])
                    weight_valid <= 1'b1;
                else
                    source_bubble_cycles <= source_bubble_cycles + 1;
            end

            if (projection_valid && projection_ready) begin
                projection_sent <= projection_sent + 1;
                projection_valid <= 1'b0;
            end else if (!projection_valid &&
                         projection_sent < projection_available) begin
                if (lfsr[3] || lfsr[12])
                    projection_valid <= 1'b1;
                else
                    projection_bubble_cycles <= projection_bubble_cycles + 1;
            end
        end else begin
            activation_valid <= 1'b0;
            weight_valid <= 1'b0;
            projection_valid <= 1'b0;
        end
    end

    // Independent pseudo-random sink backpressure.  Each last tile is also
    // forced to spend at least one complete cycle stalled; this makes every
    // group-state transition observable under pressure rather than relying
    // on the random seed to happen to hit a boundary.
    always @(negedge clk) begin
        if (!rst_n || clear || phase != PH_RUN) begin
            compute_ready <= 1'b0;
            out_ready <= 1'b0;
            boundary_hold_r <= 1'b0;
        end else begin
            out_ready <= lfsr[4] | lfsr[11];
            if (compute_valid && compute_tile == COMPUTE_TILES-1 &&
                !boundary_hold_r) begin
                compute_ready <= 1'b0;
                boundary_hold_r <= 1'b1;
            end else begin
                compute_ready <= lfsr[1] | lfsr[7];
                if (!(compute_valid && compute_tile == COMPUTE_TILES-1))
                    boundary_hold_r <= 1'b0;
            end
        end
    end

    reg activation_stalled_r = 1'b0;
    reg [16*32*8-1:0] stalled_activation_u8_r;
    reg [16*24-1:0] stalled_activation_meta_r;
    reg weight_stalled_r = 1'b0;
    reg signed [16*32*4-1:0] stalled_weight_r;
    reg [223:0] stalled_weight_meta_r;
    reg compute_stalled_r = 1'b0;
    reg stalled_compute_first_r;
    reg stalled_compute_last_r;
    reg [TILE_W-1:0] stalled_compute_tile_r;
    reg signed [16*32*9-1:0] stalled_compute_activation_r;
    reg signed [12*32*4-1:0] stalled_compute_weight_r;
    reg [16*8-1:0] stalled_compute_acode_r;
    reg [16*6-1:0] stalled_compute_ashift_r;
    reg [12*8-1:0] stalled_compute_wcode_r;
    reg [12*6-1:0] stalled_compute_wshift_r;
    reg [11:0] stalled_compute_mask_r;
    reg projection_stalled_r = 1'b0;
    reg [TILE_W-1:0] stalled_projection_tile_r;
    reg signed [16*12*24-1:0] stalled_projection_r;
    reg output_stalled_r = 1'b0;
    reg [SOURCE_W-1:0] stalled_output_record_r;
    reg signed [16*16*24-1:0] stalled_output_r;
    reg done_previous_r = 1'b0;

    // Independent monitor: exact payload checks, transaction conservation,
    // deadlock-visible counters and ready/valid stability on every boundary.
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            projection_available = 0;
            compute_seen = 0;
            output_seen = 0;
            done_pulses = 0;
            run_cycles = 0;
            mismatch_count = 0;
            runtime_error_seen = 0;
            activation_stall_checks = 0;
            weight_stall_checks = 0;
            compute_stall_checks = 0;
            projection_stall_checks = 0;
            output_stall_checks = 0;
            compute_backpressure_cycles = 0;
            output_backpressure_cycles = 0;
            boundary_stall_checks = 0;
            first_mode_count = 0;
            middle_mode_count = 0;
            last_mode_count = 0;
            source_bubble_cycles = 0;
            projection_bubble_cycles = 0;
            activation_stalled_r = 1'b0;
            weight_stalled_r = 1'b0;
            compute_stalled_r = 1'b0;
            projection_stalled_r = 1'b0;
            output_stalled_r = 1'b0;
            done_previous_r = 1'b0;
        end else if (phase == PH_RUN) begin
            run_cycles = run_cycles + 1;
            if (error)
                runtime_error_seen = 1;

            if (!compute_ready)
                compute_backpressure_cycles = compute_backpressure_cycles+1;
            if (!out_ready)
                output_backpressure_cycles = output_backpressure_cycles+1;
            if (compute_valid && !compute_ready &&
                compute_tile == COMPUTE_TILES-1)
                boundary_stall_checks = boundary_stall_checks + 1;

            if (activation_stalled_r) begin
                activation_stall_checks = activation_stall_checks + 1;
                if (!activation_valid ||
                    activation_u8x16x32 !== stalled_activation_u8_r ||
                    activation_meta_u24x16 !== stalled_activation_meta_r)
                    note_mismatch("activation source changed while stalled");
            end
            if (weight_stalled_r) begin
                weight_stall_checks = weight_stall_checks + 1;
                if (!weight_valid || weights_s4x16x32 !== stalled_weight_r ||
                    weight_meta_u224 !== stalled_weight_meta_r)
                    note_mismatch("weight source changed while stalled");
            end
            if (compute_stalled_r) begin
                compute_stall_checks = compute_stall_checks + 1;
                if (!compute_valid ||
                    compute_first !== stalled_compute_first_r ||
                    compute_last !== stalled_compute_last_r ||
                    compute_tile !== stalled_compute_tile_r ||
                    compute_activation_s9x16x32 !==
                        stalled_compute_activation_r ||
                    compute_weights_s4x12x32 !== stalled_compute_weight_r ||
                    compute_activation_code_u8x16 !== stalled_compute_acode_r ||
                    compute_activation_shift_u6x16 !==
                        stalled_compute_ashift_r ||
                    compute_weight_code_u8x12 !== stalled_compute_wcode_r ||
                    compute_weight_shift_u6x12 !== stalled_compute_wshift_r ||
                    compute_column_valid_u12 !== stalled_compute_mask_r)
                    note_mismatch("compute output changed while stalled");
            end
            if (projection_stalled_r) begin
                projection_stall_checks = projection_stall_checks + 1;
                if (!projection_valid ||
                    projection_tile !== stalled_projection_tile_r ||
                    projection_s24x16x12 !== stalled_projection_r)
                    note_mismatch("projection source changed while stalled");
            end
            if (output_stalled_r) begin
                output_stall_checks = output_stall_checks + 1;
                if (!out_valid || out_record_index !== stalled_output_record_r ||
                    out_projection_s24x16x16 !== stalled_output_r)
                    note_mismatch("tensor output changed while stalled");
            end

            if (compute_valid && compute_ready) begin
                if (compute_seen >= TOTAL_COMPUTE)
                    note_mismatch("extra compute transaction");
                else
                    check_compute_transaction();
                if (compute_first)
                    first_mode_count = first_mode_count + 1;
                else if (compute_last)
                    last_mode_count = last_mode_count + 1;
                else
                    middle_mode_count = middle_mode_count + 1;
                if (compute_last)
                    projection_available = projection_available + 1;
                compute_seen = compute_seen + 1;
            end

            if (projection_valid && projection_ready &&
                projection_sent >= projection_available)
                note_mismatch("projection accepted without completed last-group compute");

            if (out_valid && out_ready) begin
                if (output_seen >= SOURCE_RECORDS)
                    note_mismatch("extra output record");
                else
                    check_output_record();
                output_seen = output_seen + 1;
            end

            if (done) begin
                done_pulses = done_pulses + 1;
                if (done_previous_r)
                    note_mismatch("done held for more than one cycle");
                if (output_seen != SOURCE_RECORDS)
                    note_mismatch($sformatf(
                        "done before conserved outputs got=%0d expected=%0d",
                        output_seen, SOURCE_RECORDS));
            end
            done_previous_r = done;

            activation_stalled_r = activation_valid && !activation_ready;
            if (activation_stalled_r) begin
                stalled_activation_u8_r = activation_u8x16x32;
                stalled_activation_meta_r = activation_meta_u24x16;
            end
            weight_stalled_r = weight_valid && !weight_ready;
            if (weight_stalled_r) begin
                stalled_weight_r = weights_s4x16x32;
                stalled_weight_meta_r = weight_meta_u224;
            end
            compute_stalled_r = compute_valid && !compute_ready;
            if (compute_stalled_r) begin
                stalled_compute_first_r = compute_first;
                stalled_compute_last_r = compute_last;
                stalled_compute_tile_r = compute_tile;
                stalled_compute_activation_r = compute_activation_s9x16x32;
                stalled_compute_weight_r = compute_weights_s4x12x32;
                stalled_compute_acode_r = compute_activation_code_u8x16;
                stalled_compute_ashift_r = compute_activation_shift_u6x16;
                stalled_compute_wcode_r = compute_weight_code_u8x12;
                stalled_compute_wshift_r = compute_weight_shift_u6x12;
                stalled_compute_mask_r = compute_column_valid_u12;
            end
            projection_stalled_r = projection_valid && !projection_ready;
            if (projection_stalled_r) begin
                stalled_projection_tile_r = projection_tile;
                stalled_projection_r = projection_s24x16x12;
            end
            output_stalled_r = out_valid && !out_ready;
            if (output_stalled_r) begin
                stalled_output_record_r = out_record_index;
                stalled_output_r = out_projection_s24x16x16;
            end
        end else begin
            activation_stalled_r = 1'b0;
            weight_stalled_r = 1'b0;
            compute_stalled_r = 1'b0;
            projection_stalled_r = 1'b0;
            output_stalled_r = 1'b0;
            done_previous_r = 1'b0;
        end
    end

    initial begin
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (3) @(posedge clk);
        if (activation_ready || weight_ready || compute_valid ||
            projection_ready || out_valid || busy || done || error) begin
            $display("FAIL: disabled-mode interface was not quiescent");
            $fatal(1, "disabled-mode quiescence check");
        end

        // Directed negative protocol check: pass1 cannot start an inverse
        // repack sequence.  It must be rejected, latch error, and recover only
        // through clear.  No nominal transaction is allowed in this phase.
        @(negedge clk);
        enable = 1'b1;
        phase = PH_NEGATIVE;
        repeat (12) begin
            @(posedge clk);
            if (error)
                break;
        end
        if (!error) begin
            $display("FAIL: malformed projection did not latch error");
            $fatal(1, "negative protocol check");
        end

        @(negedge clk);
        phase = PH_IDLE;
        clear = 1'b1;
        @(posedge clk);
        @(negedge clk);
        clear = 1'b0;
        repeat (2) @(posedge clk);
        if (error || activation_group_count != 0 || source_record_count != 0 ||
            compute_transaction_count != 0 || projection_pass_count != 0 ||
            output_record_count != 0) begin
            $display("FAIL: clear did not recover negative protocol state");
            $fatal(1, "clear recovery check");
        end

        @(negedge clk);
        phase = PH_RUN;
        while (done_pulses == 0 && run_cycles < TIMEOUT_CYCLES)
            @(posedge clk);
        repeat (3) @(posedge clk);

        @(negedge clk);
        phase = PH_POST;
        enable = 1'b0;
        repeat (3) @(posedge clk);

        if (run_cycles >= TIMEOUT_CYCLES || mismatch_count != 0 ||
            runtime_error_seen != 0 || error || done_pulses != 1 || busy ||
            activation_sent != GROUPS || weight_sent != TOTAL_SOURCE ||
            projection_sent != COMPUTE_TILES ||
            projection_available != COMPUTE_TILES ||
            compute_seen != TOTAL_COMPUTE || output_seen != SOURCE_RECORDS ||
            activation_group_count != GROUPS ||
            source_record_count != TOTAL_SOURCE ||
            compute_transaction_count != TOTAL_COMPUTE ||
            projection_pass_count != COMPUTE_TILES ||
            output_record_count != SOURCE_RECORDS ||
            activation_stall_checks == 0 || weight_stall_checks == 0 ||
            compute_stall_checks == 0 || projection_stall_checks == 0 ||
            output_stall_checks == 0 || compute_backpressure_cycles == 0 ||
            output_backpressure_cycles == 0 || source_bubble_cycles == 0 ||
            projection_bubble_cycles == 0 || boundary_stall_checks == 0 ||
            first_mode_count != COMPUTE_TILES ||
            middle_mode_count != COMPUTE_TILES ||
            last_mode_count != COMPUTE_TILES ||
            activation_ready || weight_ready ||
            compute_valid || projection_ready || out_valid) begin
            $display("FAIL: down V5 smoke cycles=%0d mismatch=%0d runtime_error=%0d done=%0d busy=%0d act=%0d/%0d source=%0d/%0d compute=%0d/%0d projection=%0d/%0d output=%0d/%0d available=%0d stalls=%0d/%0d/%0d/%0d/%0d boundary=%0d modes=%0d/%0d/%0d bubbles=%0d/%0d",
                run_cycles, mismatch_count, runtime_error_seen, done_pulses,
                busy, activation_group_count, GROUPS, source_record_count,
                TOTAL_SOURCE, compute_transaction_count, TOTAL_COMPUTE,
                projection_pass_count, COMPUTE_TILES, output_record_count,
                SOURCE_RECORDS, projection_available,
                activation_stall_checks, weight_stall_checks,
                compute_stall_checks, projection_stall_checks,
                output_stall_checks, boundary_stall_checks,
                first_mode_count, middle_mode_count, last_mode_count,
                source_bubble_cycles,
                projection_bubble_cycles);
            $fatal(1, "down V5 scheduler smoke failed");
        end else begin
            $display("PASS: down V5 scheduler bit-exact conservation source=%0d compute=%0d projection=%0d output=%0d tail_columns=4 tail_mask=00f modes=%0d/%0d/%0d boundary_stalls=%0d stalls=%0d/%0d/%0d/%0d/%0d cycles=%0d",
                source_record_count, compute_transaction_count,
                projection_pass_count, output_record_count,
                first_mode_count, middle_mode_count, last_mode_count,
                boundary_stall_checks,
                activation_stall_checks, weight_stall_checks,
                compute_stall_checks, projection_stall_checks,
                output_stall_checks, run_cycles);
            $finish;
        end
    end
endmodule
