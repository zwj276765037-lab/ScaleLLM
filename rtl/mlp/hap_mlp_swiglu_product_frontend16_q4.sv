`timescale 1ns / 1ps

// Cohort16 SwiGLU frontend with two row-local producers and one central
// transform/quantization pipeline.  Each outer producer retains only its
// 8x16 Gate/Up tile store and one SiLU lane.  Products cross the physical
// boundary as a registered, tagged 32-bit stream.  A two-bank central row
// ring assembles complete 16x32 groups before the unique 64-DSP Hadamard and
// four robust quantizers consume them.
module hap_mlp_swiglu_product_frontend16_q4 #(
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input  wire                           clk,
    input  wire                           rst_n,
    input  wire                           clear,
    input  wire                           in_valid,
    output wire                           in_ready,
    input  wire                           in_is_up,
    input  wire                           in_second_half,
    input  wire signed [16*16*24-1:0]     projection_s24x16x16,
    output wire                           out_valid,
    input  wire                           out_ready,
    output wire [16*32*8-1:0]             activation_u8x16x32,
    output wire [16*24-1:0]               activation_meta_u24x16,
    output wire [31:0]                    input_tile_count,
    output wire [31:0]                    product_group_count,
    output wire [31:0]                    activation_group_count,
    output wire [31:0]                    frontend_busy_cycle_count,
    output wire                           error
);

    // Row-local producer interfaces.  These exact narrow signals are also
    // audited by the static architecture gate.
    wire signed [31:0] branch_product_s32_stream [0:1];
    wire [11:0] branch_group_seq_tag [0:1];
    wire [2:0] branch_row_tag [0:1];
    wire [4:0] branch_column_tag [0:1];
    wire [1:0] branch_stream_valid;
    wire [1:0] branch_stream_ready;
    wire [1:0] branch_in_ready;
    wire [1:0] branch_busy;
    wire [1:0] branch_error;

    reg [1:0] expected_input_phase_r;
    reg [31:0] input_tile_count_r;
    reg [31:0] product_group_count_r;
    reg [31:0] activation_group_count_r;
    reg [31:0] frontend_busy_cycle_count_r;
    reg sticky_error_r;

    // Terminate the command/abort clear at destination-local FFs.  The
    // one-cycle clear bubble closes every local ready/valid interface before
    // state is reused, while keeping the steady-state datapath unchanged.
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg control_clear_local_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg hadamard_clear_local_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [3:0] quantizer_clear_local_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            control_clear_local_r <= 1'b1;
            hadamard_clear_local_r <= 1'b1;
            quantizer_clear_local_r <= 4'hf;
        end else begin
            control_clear_local_r <= clear;
            hadamard_clear_local_r <= clear;
            quantizer_clear_local_r <= {4{clear}};
        end
    end

    wire input_tag_matches =
        in_is_up == expected_input_phase_r[0] &&
        in_second_half == expected_input_phase_r[1];
    assign in_ready = rst_n && !control_clear_local_r && input_tag_matches &&
        &branch_in_ready;
    wire input_fire = in_valid && in_ready;

    genvar row_branch;
    generate
        for (row_branch = 0; row_branch < 2;
             row_branch = row_branch + 1) begin : g_row_branch
            (* KEEP_HIERARCHY = "yes" *)
            hap_mlp_swiglu_row_stream8_q4 #(
                .SILU_LUT_FILE(SILU_LUT_FILE)
            ) u_branch_leaf (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(input_fire),
                .in_ready(branch_in_ready[row_branch]),
                .in_is_up(in_is_up),
                .in_second_half(in_second_half),
                .projection_s24x8x16(
                    projection_s24x16x16[
                        row_branch*8*16*24 +: 8*16*24]),
                .stream_valid(branch_stream_valid[row_branch]),
                .stream_ready(branch_stream_ready[row_branch]),
                .stream_product_s32(
                    branch_product_s32_stream[row_branch]),
                .stream_group_seq(branch_group_seq_tag[row_branch]),
                .stream_row(branch_row_tag[row_branch]),
                .stream_column(branch_column_tag[row_branch]),
                .busy(branch_busy[row_branch]),
                .error(branch_error[row_branch])
            );
        end
    endgenerate

    // Central two-bank group ring.  Payload has no reset; bank_valid and the
    // scoreboards make stale bits unobservable after reset/clear.
    reg signed [31:0] row_ring_s32_r [0:1][0:15][0:31];
    reg [15:0] row_complete_scoreboard_r [0:1];
    reg [11:0] bank_group_seq_r [0:1];
    reg [1:0] bank_valid_r;
    reg [1:0] bank_complete_r;
    reg [8:0] bank_branch_beat_count_r [0:1][0:1];

    generate
        for (row_branch = 0; row_branch < 2;
             row_branch = row_branch + 1) begin : g_stream_credit
            wire target_bank = branch_group_seq_tag[row_branch][0];
            assign branch_stream_ready[row_branch] = rst_n &&
                !control_clear_local_r &&
                !bank_complete_r[target_bank] &&
                (!bank_valid_r[target_bank] ||
                 bank_group_seq_r[target_bank] ==
                    branch_group_seq_tag[row_branch]);
        end
    endgenerate

    wire [1:0] branch_stream_fire =
        branch_stream_valid & branch_stream_ready;
    wire fire_b0_bank0 = branch_stream_fire[0] &&
        !branch_group_seq_tag[0][0];
    wire fire_b1_bank0 = branch_stream_fire[1] &&
        !branch_group_seq_tag[1][0];
    wire fire_b0_bank1 = branch_stream_fire[0] &&
        branch_group_seq_tag[0][0];
    wire fire_b1_bank1 = branch_stream_fire[1] &&
        branch_group_seq_tag[1][0];
    wire bank0_allocate = fire_b0_bank0 || fire_b1_bank0;
    wire bank1_allocate = fire_b0_bank1 || fire_b1_bank1;

    wire [15:0] bank0_row_mask =
        ((fire_b0_bank0 && branch_column_tag[0] == 5'd31) ?
            (16'h0001 << branch_row_tag[0]) : 16'd0) |
        ((fire_b1_bank0 && branch_column_tag[1] == 5'd31) ?
            (16'h0100 << branch_row_tag[1]) : 16'd0);
    wire [15:0] bank1_row_mask =
        ((fire_b0_bank1 && branch_column_tag[0] == 5'd31) ?
            (16'h0001 << branch_row_tag[0]) : 16'd0) |
        ((fire_b1_bank1 && branch_column_tag[1] == 5'd31) ?
            (16'h0100 << branch_row_tag[1]) : 16'd0);
    wire [15:0] bank0_scoreboard_next =
        row_complete_scoreboard_r[0] | bank0_row_mask;
    wire [15:0] bank1_scoreboard_next =
        row_complete_scoreboard_r[1] | bank1_row_mask;

    wire [8:0] bank0_b0_count_next =
        bank_branch_beat_count_r[0][0] + fire_b0_bank0;
    wire [8:0] bank0_b1_count_next =
        bank_branch_beat_count_r[0][1] + fire_b1_bank0;
    wire [8:0] bank1_b0_count_next =
        bank_branch_beat_count_r[1][0] + fire_b0_bank1;
    wire [8:0] bank1_b1_count_next =
        bank_branch_beat_count_r[1][1] + fire_b1_bank1;
    wire bank0_complete_next = (bank_valid_r[0] || bank0_allocate) &&
        bank0_scoreboard_next == 16'hffff &&
        bank0_b0_count_next == 9'd256 &&
        bank0_b1_count_next == 9'd256;
    wire bank1_complete_next = (bank_valid_r[1] || bank1_allocate) &&
        bank1_scoreboard_next == 16'hffff &&
        bank1_b0_count_next == 9'd256 &&
        bank1_b1_count_next == 9'd256;
    wire bank0_complete_event = !bank_complete_r[0] &&
        bank0_complete_next;
    wire bank1_complete_event = !bank_complete_r[1] &&
        bank1_complete_next;

    // One central consumer preserves the frozen arithmetic hierarchy.
    reg consume_active_r;
    reg consume_bank_r;
    reg [11:0] consume_group_seq_r;
    reg [4:0] source_row_r;
    reg [4:0] dispatch_row_r;
    reg [2:0] quant_output_wave_r [0:3];
    reg [5:0] completed_row_count_r;
    reg out_valid_r;
    reg [16*32*8-1:0] activation_u8_r;
    reg [16*24-1:0] activation_meta_r;

    wire hadamard_in_valid = consume_active_r && source_row_r < 16;
    wire hadamard_in_ready;
    wire hadamard_in_fire = hadamard_in_valid && hadamard_in_ready;
    wire [3:0] selected_source_row = source_row_r < 16 ?
        source_row_r[3:0] : 4'd0;
    wire [32*32-1:0] hadamard_in_s32;
    genvar hadamard_lane;
    generate
        for (hadamard_lane = 0; hadamard_lane < 32;
             hadamard_lane = hadamard_lane + 1) begin : g_hadamard_row_read
            assign hadamard_in_s32[hadamard_lane*32 +: 32] =
                row_ring_s32_r[consume_bank_r]
                    [selected_source_row][hadamard_lane];
        end
    endgenerate

    wire hadamard_out_valid;
    wire hadamard_out_ready;
    wire [32*35-1:0] hadamard_out_s35;
    wire hadamard_error;
    (* KEEP_HIERARCHY = "yes" *)
    hap_mlp_hadamard32_s32_norm_stream u_hadamard (
        .clk(clk), .rst_n(rst_n), .clear(hadamard_clear_local_r),
        .in_valid(hadamard_in_valid), .in_ready(hadamard_in_ready),
        .in_s32(hadamard_in_s32),
        .out_valid(hadamard_out_valid),
        .out_ready(hadamard_out_ready), .out_s35(hadamard_out_s35),
        .input_group_count(), .output_group_count(),
        .saturation_count(), .error(hadamard_error)
    );

    wire [3:0] quant_in_ready;
    wire [3:0] quant_out_valid;
    wire [3:0] quant_out_ready;
    wire [4*32*8-1:0] quant_out_u8;
    wire [4*24-1:0] quant_out_meta;
    wire [3:0] quant_error;
    wire [1:0] dispatch_quantizer = dispatch_row_r[1:0];
    wire hadamard_out_fire = hadamard_out_valid && hadamard_out_ready;
    assign hadamard_out_ready =
        quant_in_ready[dispatch_quantizer];
    wire [3:0] quant_out_fire = quant_out_valid & quant_out_ready;
    wire [2:0] quant_fire_count =
        {2'd0, quant_out_fire[0]} + {2'd0, quant_out_fire[1]} +
        {2'd0, quant_out_fire[2]} + {2'd0, quant_out_fire[3]};

    genvar quantizer;
    generate
        for (quantizer = 0; quantizer < 4;
             quantizer = quantizer + 1) begin : g_quantizer
            hap_mlp_robust_a8_quantizer_s35 u_quantizer (
                .clk(clk), .rst_n(rst_n),
                .clear(quantizer_clear_local_r[quantizer]),
                .in_valid(hadamard_out_valid &&
                    dispatch_quantizer == quantizer),
                .in_ready(quant_in_ready[quantizer]),
                .in_s35(hadamard_out_s35),
                .out_valid(quant_out_valid[quantizer]),
                .out_ready(quant_out_ready[quantizer]),
                .out_u8(quant_out_u8[quantizer*32*8 +: 32*8]),
                .out_meta(quant_out_meta[quantizer*24 +: 24]),
                .input_group_count(), .output_group_count(),
                .cycle_count(), .format_error_count(),
                .error(quant_error[quantizer])
            );
            assign quant_out_ready[quantizer] = consume_active_r &&
                quant_output_wave_r[quantizer] < 4;
        end
    endgenerate

    // A 256-bit data write and its 24-bit metadata write have independent
    // protected predicates, avoiding a 280-load quantizer retirement net.
    wire [3:0] quant_data_write;
    wire [3:0] quant_meta_write;
    generate
        for (quantizer = 0; quantizer < 4;
             quantizer = quantizer + 1) begin : g_quant_write_leaf
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT1 #(.INIT(2'h2)) u_data_write_leaf (
                .I0(quant_out_fire[quantizer]),
                .O(quant_data_write[quantizer]));
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT1 #(.INIT(2'h2)) u_meta_write_leaf (
                .I0(quant_out_fire[quantizer]),
                .O(quant_meta_write[quantizer]));
        end
    endgenerate

    wire out_fire = out_valid && out_ready;
    wire internal_busy = |branch_busy || |bank_valid_r ||
        consume_active_r || out_valid_r;
    assign out_valid = rst_n && !control_clear_local_r && out_valid_r;
    assign activation_u8x16x32 = activation_u8_r;
    assign activation_meta_u24x16 = activation_meta_r;
    assign input_tile_count = input_tile_count_r;
    assign product_group_count = product_group_count_r;
    assign activation_group_count = activation_group_count_r;
    assign frontend_busy_cycle_count = frontend_busy_cycle_count_r;
    assign error = sticky_error_r || |branch_error ||
        hadamard_error || |quant_error;

    integer bank_index;
    integer branch_index;
    integer q;
    integer output_row;
    always @(posedge clk) begin
        if (!rst_n) begin
            expected_input_phase_r <= 2'd0;
            input_tile_count_r <= 32'd0;
            product_group_count_r <= 32'd0;
            activation_group_count_r <= 32'd0;
            frontend_busy_cycle_count_r <= 32'd0;
            sticky_error_r <= 1'b0;
            bank_valid_r <= 2'd0;
            bank_complete_r <= 2'd0;
            consume_active_r <= 1'b0;
            consume_bank_r <= 1'b0;
            consume_group_seq_r <= 12'd0;
            source_row_r <= 5'd0;
            dispatch_row_r <= 5'd0;
            completed_row_count_r <= 6'd0;
            out_valid_r <= 1'b0;
            for (bank_index = 0; bank_index < 2;
                 bank_index = bank_index + 1) begin
                row_complete_scoreboard_r[bank_index] <= 16'd0;
                bank_group_seq_r[bank_index] <= 12'd0;
                for (branch_index = 0; branch_index < 2;
                     branch_index = branch_index + 1)
                    bank_branch_beat_count_r[bank_index]
                        [branch_index] <= 9'd0;
            end
            for (q = 0; q < 4; q = q + 1)
                quant_output_wave_r[q] <= 3'd0;
        end else if (control_clear_local_r) begin
            expected_input_phase_r <= 2'd0;
            input_tile_count_r <= 32'd0;
            product_group_count_r <= 32'd0;
            activation_group_count_r <= 32'd0;
            frontend_busy_cycle_count_r <= 32'd0;
            sticky_error_r <= 1'b0;
            bank_valid_r <= 2'd0;
            bank_complete_r <= 2'd0;
            consume_active_r <= 1'b0;
            consume_bank_r <= 1'b0;
            consume_group_seq_r <= 12'd0;
            source_row_r <= 5'd0;
            dispatch_row_r <= 5'd0;
            completed_row_count_r <= 6'd0;
            out_valid_r <= 1'b0;
            for (bank_index = 0; bank_index < 2;
                 bank_index = bank_index + 1) begin
                row_complete_scoreboard_r[bank_index] <= 16'd0;
                bank_group_seq_r[bank_index] <= 12'd0;
                for (branch_index = 0; branch_index < 2;
                     branch_index = branch_index + 1)
                    bank_branch_beat_count_r[bank_index]
                        [branch_index] <= 9'd0;
            end
            for (q = 0; q < 4; q = q + 1)
                quant_output_wave_r[q] <= 3'd0;
        end else begin
            if (internal_busy)
                frontend_busy_cycle_count_r <=
                    frontend_busy_cycle_count_r + 32'd1;

            if (in_valid && !input_tag_matches)
                sticky_error_r <= 1'b1;
            if (input_fire) begin
                input_tile_count_r <= input_tile_count_r + 32'd1;
                expected_input_phase_r <= expected_input_phase_r + 2'd1;
            end

            if (branch_stream_valid[0] && branch_stream_valid[1] &&
                branch_group_seq_tag[0] != branch_group_seq_tag[1])
                sticky_error_r <= 1'b1;

            // Each branch owns disjoint rows, so both narrow writes may
            // retire in the same cycle without a multi-writer collision.
            if (branch_stream_fire[0]) begin
                row_ring_s32_r[branch_group_seq_tag[0][0]]
                    [branch_row_tag[0]][branch_column_tag[0]] <=
                        branch_product_s32_stream[0];
                if (bank_branch_beat_count_r
                        [branch_group_seq_tag[0][0]][0] >= 9'd256 ||
                    branch_row_tag[0] != bank_branch_beat_count_r
                        [branch_group_seq_tag[0][0]][0][6:4] ||
                    branch_column_tag[0] !=
                        {bank_branch_beat_count_r
                            [branch_group_seq_tag[0][0]][0][7],
                         bank_branch_beat_count_r
                            [branch_group_seq_tag[0][0]][0][3:0]})
                    sticky_error_r <= 1'b1;
            end
            if (branch_stream_fire[1]) begin
                row_ring_s32_r[branch_group_seq_tag[1][0]]
                    [8 + branch_row_tag[1]][branch_column_tag[1]] <=
                        branch_product_s32_stream[1];
                if (bank_branch_beat_count_r
                        [branch_group_seq_tag[1][0]][1] >= 9'd256 ||
                    branch_row_tag[1] != bank_branch_beat_count_r
                        [branch_group_seq_tag[1][0]][1][6:4] ||
                    branch_column_tag[1] !=
                        {bank_branch_beat_count_r
                            [branch_group_seq_tag[1][0]][1][7],
                         bank_branch_beat_count_r
                            [branch_group_seq_tag[1][0]][1][3:0]})
                    sticky_error_r <= 1'b1;
            end

            if (bank0_allocate) begin
                if (!bank_valid_r[0]) begin
                    bank_valid_r[0] <= 1'b1;
                    bank_group_seq_r[0] <= fire_b0_bank0 ?
                        branch_group_seq_tag[0] :
                        branch_group_seq_tag[1];
                end
                if (fire_b0_bank0 && fire_b1_bank0 &&
                    branch_group_seq_tag[0] != branch_group_seq_tag[1])
                    sticky_error_r <= 1'b1;
                row_complete_scoreboard_r[0] <= bank0_scoreboard_next;
                bank_branch_beat_count_r[0][0] <= bank0_b0_count_next;
                bank_branch_beat_count_r[0][1] <= bank0_b1_count_next;
                if (bank0_complete_event)
                    bank_complete_r[0] <= 1'b1;
            end
            if (bank1_allocate) begin
                if (!bank_valid_r[1]) begin
                    bank_valid_r[1] <= 1'b1;
                    bank_group_seq_r[1] <= fire_b0_bank1 ?
                        branch_group_seq_tag[0] :
                        branch_group_seq_tag[1];
                end
                if (fire_b0_bank1 && fire_b1_bank1 &&
                    branch_group_seq_tag[0] != branch_group_seq_tag[1])
                    sticky_error_r <= 1'b1;
                row_complete_scoreboard_r[1] <= bank1_scoreboard_next;
                bank_branch_beat_count_r[1][0] <= bank1_b0_count_next;
                bank_branch_beat_count_r[1][1] <= bank1_b1_count_next;
                if (bank1_complete_event)
                    bank_complete_r[1] <= 1'b1;
            end
            if (bank0_complete_event || bank1_complete_event)
                product_group_count_r <= product_group_count_r +
                    bank0_complete_event + bank1_complete_event;

            // Consume complete banks strictly in group sequence order.
            if (!consume_active_r && !out_valid_r &&
                bank_complete_r[consume_group_seq_r[0]] &&
                bank_group_seq_r[consume_group_seq_r[0]] ==
                    consume_group_seq_r) begin
                consume_active_r <= 1'b1;
                consume_bank_r <= consume_group_seq_r[0];
                source_row_r <= 5'd0;
                dispatch_row_r <= 5'd0;
                completed_row_count_r <= 6'd0;
                for (q = 0; q < 4; q = q + 1)
                    quant_output_wave_r[q] <= 3'd0;
            end

            if (hadamard_in_fire)
                source_row_r <= source_row_r + 1'b1;
            if (hadamard_out_fire)
                dispatch_row_r <= dispatch_row_r + 1'b1;

            for (q = 0; q < 4; q = q + 1) begin
                if (quant_out_fire[q]) begin
                    output_row = q + 4*quant_output_wave_r[q];
                    if (quant_data_write[q])
                        activation_u8_r[output_row*32*8 +: 32*8] <=
                            quant_out_u8[q*32*8 +: 32*8];
                    if (quant_meta_write[q])
                        activation_meta_r[output_row*24 +: 24] <=
                            quant_out_meta[q*24 +: 24];
                    quant_output_wave_r[q] <=
                        quant_output_wave_r[q] + 1'b1;
                end
            end
            if (quant_fire_count != 0) begin
                completed_row_count_r <= completed_row_count_r +
                    quant_fire_count;
                if (completed_row_count_r + quant_fire_count == 16)
                    out_valid_r <= 1'b1;
            end

            if (out_fire) begin
                out_valid_r <= 1'b0;
                consume_active_r <= 1'b0;
                bank_valid_r[consume_bank_r] <= 1'b0;
                bank_complete_r[consume_bank_r] <= 1'b0;
                row_complete_scoreboard_r[consume_bank_r] <= 16'd0;
                bank_branch_beat_count_r[consume_bank_r][0] <= 9'd0;
                bank_branch_beat_count_r[consume_bank_r][1] <= 9'd0;
                consume_group_seq_r <= consume_group_seq_r + 12'd1;
                activation_group_count_r <=
                    activation_group_count_r + 32'd1;
            end

            if (source_row_r > 16 || dispatch_row_r > 16 ||
                completed_row_count_r > 16 ||
                product_group_count_r < activation_group_count_r)
                sticky_error_r <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !control_clear_local_r && input_fire &&
            !(branch_in_ready[0] && branch_in_ready[1]))
            $error("row-local input was not accepted atomically");
        if (rst_n && !control_clear_local_r && out_valid && !out_ready &&
            !consume_active_r)
            $error("central output lost its owning bank while stalled");
        if (rst_n && !control_clear_local_r) begin
            if (in_valid && !input_tag_matches)
                $display("ROWLOCAL_STICKY_REASON input_tag phase=%0d tag=%0d/%0d",
                    expected_input_phase_r, in_is_up, in_second_half);
            if (branch_stream_valid[0] && branch_stream_valid[1] &&
                branch_group_seq_tag[0] != branch_group_seq_tag[1])
                $display("ROWLOCAL_STICKY_REASON branch_seq %0d/%0d",
                    branch_group_seq_tag[0], branch_group_seq_tag[1]);
            if (branch_stream_fire[0] &&
                (bank_branch_beat_count_r
                    [branch_group_seq_tag[0][0]][0] >= 9'd256 ||
                 branch_row_tag[0] != bank_branch_beat_count_r
                    [branch_group_seq_tag[0][0]][0][6:4] ||
                 branch_column_tag[0] !=
                    {bank_branch_beat_count_r
                        [branch_group_seq_tag[0][0]][0][7],
                     bank_branch_beat_count_r
                        [branch_group_seq_tag[0][0]][0][3:0]}))
                $display("ROWLOCAL_STICKY_REASON b0_order seq=%0d row=%0d col=%0d count=%0d",
                    branch_group_seq_tag[0], branch_row_tag[0],
                    branch_column_tag[0], bank_branch_beat_count_r
                        [branch_group_seq_tag[0][0]][0]);
            if (branch_stream_fire[1] &&
                (bank_branch_beat_count_r
                    [branch_group_seq_tag[1][0]][1] >= 9'd256 ||
                 branch_row_tag[1] != bank_branch_beat_count_r
                    [branch_group_seq_tag[1][0]][1][6:4] ||
                 branch_column_tag[1] !=
                    {bank_branch_beat_count_r
                        [branch_group_seq_tag[1][0]][1][7],
                     bank_branch_beat_count_r
                        [branch_group_seq_tag[1][0]][1][3:0]}))
                $display("ROWLOCAL_STICKY_REASON b1_order seq=%0d row=%0d col=%0d count=%0d",
                    branch_group_seq_tag[1], branch_row_tag[1],
                    branch_column_tag[1], bank_branch_beat_count_r
                        [branch_group_seq_tag[1][0]][1]);
            if (source_row_r > 16 || dispatch_row_r > 16 ||
                completed_row_count_r > 16 ||
                product_group_count_r < activation_group_count_r)
                $display("ROWLOCAL_STICKY_REASON counters src=%0d dispatch=%0d completed=%0d product=%0d activation=%0d",
                    source_row_r, dispatch_row_r, completed_row_count_r,
                    product_group_count_r, activation_group_count_r);
        end
    end
`endif

endmodule


// One physical 8-row producer.  The only retained wide state is the local
// Gate/Up S24 tile pair.  Product values leave immediately through a tagged
// 32-bit ready/valid stream; there is no branch-level product-group buffer.
module hap_mlp_swiglu_row_stream8_q4 #(
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_is_up,
    input  wire                         in_second_half,
    input  wire signed [8*16*24-1:0]    projection_s24x8x16,
    output wire                         stream_valid,
    input  wire                         stream_ready,
    output wire signed [31:0]           stream_product_s32,
    output wire [11:0]                  stream_group_seq,
    output wire [2:0]                   stream_row,
    output wire [4:0]                   stream_column,
    output wire                         busy,
    output reg                          error
);

    localparam [2:0] EXPECT_GATE0 = 3'd0;
    localparam [2:0] EXPECT_UP0   = 3'd1;
    localparam [2:0] COMPUTE0     = 3'd2;
    localparam [2:0] EXPECT_GATE1 = 3'd3;
    localparam [2:0] EXPECT_UP1   = 3'd4;
    localparam [2:0] COMPUTE1     = 3'd5;

    reg [2:0] state_r;
    reg signed [8*16*24-1:0] gate_tile_r;
    reg signed [8*16*24-1:0] up_tile_r;
    reg [7:0] issue_element_r;
    reg [7:0] output_element_r;
    reg [11:0] group_seq_r;

    // Each physical row producer receives only one central clear sink and
    // fans out a protected local copy inside its own placement hierarchy.
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg clear_local_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            clear_local_r <= 1'b1;
        else
            clear_local_r <= clear;
    end

    wire expecting_tile = state_r == EXPECT_GATE0 ||
        state_r == EXPECT_UP0 || state_r == EXPECT_GATE1 ||
        state_r == EXPECT_UP1;
    wire expected_is_up = state_r == EXPECT_UP0 ||
        state_r == EXPECT_UP1;
    wire expected_second_half = state_r == EXPECT_GATE1 ||
        state_r == EXPECT_UP1;
    wire input_tag_matches = in_is_up == expected_is_up &&
        in_second_half == expected_second_half;
    assign in_ready = rst_n && !clear_local_r && expecting_tile &&
        input_tag_matches;
    wire in_fire = in_valid && in_ready;

    wire gate_capture = in_fire && !in_is_up;
    wire up_capture = in_fire && in_is_up;
    wire [11:0] gate_capture_bank;
    wire [11:0] up_capture_bank;
    genvar tile_bank;
    generate
        for (tile_bank = 0; tile_bank < 12;
             tile_bank = tile_bank + 1) begin : g_tile_capture_bank
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT1 #(.INIT(2'h2)) u_gate_capture_leaf (
                .I0(gate_capture), .O(gate_capture_bank[tile_bank]));
            (* DONT_TOUCH = "yes", KEEP = "yes" *)
            LUT1 #(.INIT(2'h2)) u_up_capture_leaf (
                .I0(up_capture), .O(up_capture_bank[tile_bank]));
        end
    endgenerate

    integer capture_bank;
    always @(posedge clk) begin
        for (capture_bank = 0; capture_bank < 12;
             capture_bank = capture_bank + 1) begin
            if (gate_capture_bank[capture_bank])
                gate_tile_r[capture_bank*256 +: 256] <=
                    projection_s24x8x16[capture_bank*256 +: 256];
            if (up_capture_bank[capture_bank])
                up_tile_r[capture_bank*256 +: 256] <=
                    projection_s24x8x16[capture_bank*256 +: 256];
        end
    end

    wire computing = state_r == COMPUTE0 || state_r == COMPUTE1;
    wire compute_second_half = state_r == COMPUTE1;
    wire silu_in_valid = computing && issue_element_r < 8'd128;
    wire silu_in_ready;
    wire silu_input_fire = silu_in_valid && silu_in_ready;
    wire signed [23:0] gate_s24 =
        gate_tile_r[issue_element_r[6:0]*24 +: 24];
    wire signed [23:0] up_s24 =
        up_tile_r[issue_element_r[6:0]*24 +: 24];
    wire silu_out_valid;
    wire signed [31:0] silu_product_s32;
    wire silu_output_fire = silu_out_valid && stream_ready;

    hap_mlp_silu_mul #(.LUT_FILE(SILU_LUT_FILE)) u_silu (
        .clk(clk), .rst_n(rst_n), .clear(clear_local_r),
        .in_valid(silu_in_valid), .in_ready(silu_in_ready),
        .gate_s24(gate_s24), .up_s24(up_s24),
        .out_valid(silu_out_valid), .out_ready(stream_ready),
        .out_product_s32(silu_product_s32)
    );

    assign stream_valid = silu_out_valid;
    assign stream_product_s32 = silu_product_s32;
    assign stream_group_seq = group_seq_r;
    assign stream_row = output_element_r[6:4];
    assign stream_column =
        {compute_second_half, output_element_r[3:0]};
    assign busy = state_r != EXPECT_GATE0;

    always @(posedge clk) begin
        if (!rst_n) begin
            state_r <= EXPECT_GATE0;
            issue_element_r <= 8'd0;
            output_element_r <= 8'd0;
            group_seq_r <= 12'd0;
            error <= 1'b0;
        end else if (clear_local_r) begin
            state_r <= EXPECT_GATE0;
            issue_element_r <= 8'd0;
            output_element_r <= 8'd0;
            group_seq_r <= 12'd0;
            error <= 1'b0;
        end else begin
            if (in_valid && expecting_tile && !input_tag_matches)
                error <= 1'b1;
            if (in_fire) begin
                case (state_r)
                    EXPECT_GATE0: state_r <= EXPECT_UP0;
                    EXPECT_UP0: begin
                        state_r <= COMPUTE0;
                        issue_element_r <= 8'd0;
                        output_element_r <= 8'd0;
                    end
                    EXPECT_GATE1: state_r <= EXPECT_UP1;
                    EXPECT_UP1: begin
                        state_r <= COMPUTE1;
                        issue_element_r <= 8'd0;
                        output_element_r <= 8'd0;
                    end
                    default: error <= 1'b1;
                endcase
            end

            if (silu_input_fire)
                issue_element_r <= issue_element_r + 1'b1;
            if (silu_output_fire) begin
                if (output_element_r == 8'd127) begin
                    issue_element_r <= 8'd0;
                    output_element_r <= 8'd0;
                    if (state_r == COMPUTE0)
                        state_r <= EXPECT_GATE1;
                    else if (state_r == COMPUTE1) begin
                        state_r <= EXPECT_GATE0;
                        group_seq_r <= group_seq_r + 12'd1;
                    end else
                        error <= 1'b1;
                end else begin
                    output_element_r <= output_element_r + 1'b1;
                end
            end
        end
    end

`ifndef SYNTHESIS
    reg stalled_r;
    reg signed [31:0] stalled_product_r;
    reg [20:0] stalled_tag_r;
    always @(posedge clk) begin
        if (!rst_n || clear_local_r) begin
            stalled_r <= 1'b0;
        end else begin
            if (stalled_r &&
                (stream_product_s32 !== stalled_product_r ||
                 {stream_group_seq, stream_row, stream_column,
                  stream_valid} !== stalled_tag_r))
                $error("row-local S32 stream changed while stalled");
            stalled_r <= stream_valid && !stream_ready;
            if (stream_valid && !stream_ready) begin
                stalled_product_r <= stream_product_s32;
                stalled_tag_r <= {stream_group_seq, stream_row,
                    stream_column, stream_valid};
            end
        end
    end
`endif

endmodule
