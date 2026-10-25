`timescale 1ns / 1ps

// Cohort16 Attention projection boundary.  Two 8-row activation-cache banks
// share each accepted W8 group.  The single A8W8 lane array consumes wave0 and
// wave1 alternately while two SLR-local accumulator contexts preserve the two
// independent output tiles.
module hap_projection_core16x16_w8_reuse (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,

    input  wire                  activation_valid,
    output wire                  activation_ready,
    input  wire                  activation_wave,
    input  wire [8*32*24-1:0]    activation_s24,
    input  wire [6:0]            activation_group,
    output wire                  activation_cached,
    input  wire                  activation_release,
    output wire                  activation_release_ready,
    output reg                   activation_released,

    input  wire                  project_start,
    output wire                  project_ready,
    output reg                   project_done,
    input  wire [31:0]           project_request_id,
    input  wire [15:0]           project_cohort_id,
    input  wire [5:0]            project_layer_id,
    input  wire [2:0]            project_op_id,
    input  wire [9:0]            project_tile_id,
    input  wire [6:0]            project_query_start,
    input  wire [7:0]            project_valid_key_count,

    output wire                  weight_ready,
    input  wire                  weight_valid,
    input  wire [6:0]            weight_group,
    input  wire [16*32*8-1:0]    weight_s8,
    input  wire [16*16-1:0]      weight_meta16,

    output wire                  out_valid,
    input  wire                  out_ready,
    output wire                  out_wave,
    output wire [8*16*24-1:0]    out_s24,
    output wire [31:0]           out_request_id,
    output wire [15:0]           out_cohort_id,
    output wire [5:0]            out_layer_id,
    output wire [2:0]            out_op_id,
    output wire [9:0]            out_tile_id,
    output wire [6:0]            out_query_start,
    output wire [7:0]            out_valid_key_count,

    output reg  [31:0]           accepted_weight_group_count,
    output wire [31:0]           consumed_wave_group_count,
    output reg  [31:0]           released_weight_group_count,
    output wire [31:0]           output_wave_tile_count,
    output wire [31:0]           saturation_count,
    output reg  [1:0]            weight_fifo_high_watermark,
    output wire                  busy,
    output wire                  error
);

    localparam [2:0] ST_FILL = 3'd0;
    localparam [2:0] ST_READY = 3'd1;
    localparam [2:0] ST_PROJECT = 3'd2;
    localparam [2:0] ST_RELEASE0 = 3'd3;
    localparam [2:0] ST_RELEASE1 = 3'd4;
    localparam [2:0] ST_ERROR = 3'd7;

    reg [2:0] state_r;
    reg control_error_r;

    wire frontend_in_ready;
    wire frontend_rd_req_ready;
    wire frontend_rd_rsp_valid;
    wire frontend_rd_rsp_bank;
    wire [6:0] frontend_rd_rsp_group;
    wire [8*32*8-1:0] frontend_rd_rsp_u8;
    wire [8*24-1:0] frontend_rd_rsp_meta;
    wire frontend_release_ready;
    wire [1:0] frontend_bank_ready;
    wire frontend_error;

    wire [31:0] frontend_input_count_unused;
    wire [31:0] frontend_write_count_unused;
    wire [31:0] frontend_read_count_unused;
    wire [31:0] frontend_release_count_unused;
    wire [31:0] frontend_hadamard_sat_unused;

    reg weight_wr_ptr_r;
    reg weight_rd_ptr_r;
    reg [1:0] weight_count_r;
    reg [6:0] next_accept_group_r;
    reg [6:0] next_consume_group_r;
    reg all_weights_accepted_r;
    (* DONT_TOUCH = "yes", ram_style = "registers", shreg_extract = "no" *)
    reg [6:0] weight_group_mem [0:1];
    (* DONT_TOUCH = "yes", ram_style = "registers", shreg_extract = "no" *)
    reg [16*32*8-1:0] weight_s8_mem [0:1];
    (* DONT_TOUCH = "yes", ram_style = "registers", shreg_extract = "no" *)
    reg [16*16-1:0] weight_meta16_mem [0:1];

    wire [6:0] weight_head_group = weight_group_mem[weight_rd_ptr_r];
    wire [16*32*8-1:0] weight_head_s8 = weight_s8_mem[weight_rd_ptr_r];
    wire [16*16-1:0] weight_head_meta16 =
        weight_meta16_mem[weight_rd_ptr_r];

    reg consume_wave_r;
    reg read_pending_r;
    reg read_pending_wave_r;
    reg [6:0] read_pending_group_r;
    reg tile_input_complete_r;
    reg expected_output_wave_r;

    reg group_stage_valid_r;
    (* DONT_TOUCH = "yes" *) reg group_stage_wave_r;
    (* DONT_TOUCH = "yes" *) reg [6:0] group_stage_group_r;
    (* DONT_TOUCH = "yes" *) reg [8*24-1:0] group_stage_act_meta_r;
    (* DONT_TOUCH = "yes" *) reg [8*4*32*8-1:0]
        group_stage_act_u8_region_r;
    (* DONT_TOUCH = "yes" *) reg [8*4*8-1:0]
        group_stage_act_zero_point_region_r;
    wire [8*16*8-1:0] group_stage_act_zero_point_lane;
    (* DONT_TOUCH = "yes" *) reg [16*32*8-1:0]
        group_stage_weight_s8_r;
    (* DONT_TOUCH = "yes" *) reg [16*16-1:0]
        group_stage_weight_meta16_r;

    wire array_in_ready;
    wire array_out_valid;
    wire array_out_wave;
    wire [16*16*24-1:0] array_out_s24;
    wire [31:0] array_accumulated_group_count_unused;
    wire array_error;

    reg [31:0] descriptor_request_id_r;
    reg [15:0] descriptor_cohort_id_r;
    reg [5:0] descriptor_layer_id_r;
    reg [2:0] descriptor_op_id_r;
    reg [9:0] descriptor_tile_id_r;
    reg [6:0] descriptor_query_start_r;
    reg [7:0] descriptor_valid_key_count_r;

    wire project_start_fire = project_start && project_ready;
    wire activation_release_fire = activation_release &&
        activation_release_ready;
    wire frontend_release_valid = (state_r == ST_RELEASE0) ||
        (state_r == ST_RELEASE1);
    wire frontend_release_bank = state_r == ST_RELEASE1;
    wire frontend_release_fire = frontend_release_valid &&
        frontend_release_ready;

    wire weight_push = weight_valid && weight_ready;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire weight_push_control;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [1:0] weight_group_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [1:0] weight_meta_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [31:0] weight_data_capture_enable;
    wire issue_group = group_stage_valid_r && array_in_ready;
    wire read_request_slot = !read_pending_r &&
        (!group_stage_valid_r || issue_group);
    wire weight_head_legal = (weight_count_r != 0) &&
        (weight_head_group == next_consume_group_r);
    wire frontend_rd_req_valid = (state_r == ST_PROJECT) &&
        weight_head_legal && read_request_slot && !tile_input_complete_r;
    wire frontend_rd_req_fire = frontend_rd_req_valid &&
        frontend_rd_req_ready;
    wire capture_group = frontend_rd_rsp_valid && read_pending_r &&
        (!group_stage_valid_r || issue_group);
    wire weight_pop = capture_group && read_pending_wave_r;
    wire array_output_fire = out_valid && out_ready;

    // The two-entry FIFO stores 4359 bits per entry.  A single inferred write
    // enable previously drove 7170 placed loads and was promoted onto a BUFG.
    // Preserve explicit bank- and 256-bit-column-local enables so the raw
    // handshake predicate only reaches this small LUT fanout tree.
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    LUT1 #(.INIT(2'h2)) u_weight_push_control (
        .I0(weight_push),
        .O(weight_push_control)
    );

    genvar weight_capture_bank;
    genvar weight_capture_region;
    generate
        for (weight_capture_bank = 0; weight_capture_bank < 2;
             weight_capture_bank = weight_capture_bank + 1) begin :
                g_weight_capture_bank
            if (weight_capture_bank == 0) begin : g_bank0_enable
                (* DONT_TOUCH = "yes", KEEP = "yes" *)
                LUT2 #(.INIT(4'h2)) u_group_capture_enable (
                    .I0(weight_push), .I1(weight_wr_ptr_r),
                    .O(weight_group_capture_enable[weight_capture_bank])
                );
                (* DONT_TOUCH = "yes", KEEP = "yes" *)
                LUT2 #(.INIT(4'h2)) u_meta_capture_enable (
                    .I0(weight_push), .I1(weight_wr_ptr_r),
                    .O(weight_meta_capture_enable[weight_capture_bank])
                );
            end else begin : g_bank1_enable
                (* DONT_TOUCH = "yes", KEEP = "yes" *)
                LUT2 #(.INIT(4'h8)) u_group_capture_enable (
                    .I0(weight_push), .I1(weight_wr_ptr_r),
                    .O(weight_group_capture_enable[weight_capture_bank])
                );
                (* DONT_TOUCH = "yes", KEEP = "yes" *)
                LUT2 #(.INIT(4'h8)) u_meta_capture_enable (
                    .I0(weight_push), .I1(weight_wr_ptr_r),
                    .O(weight_meta_capture_enable[weight_capture_bank])
                );
            end

            for (weight_capture_region = 0; weight_capture_region < 16;
                 weight_capture_region = weight_capture_region + 1) begin :
                    g_weight_data_capture
                localparam integer CAPTURE_INDEX =
                    weight_capture_bank*16 + weight_capture_region;
                if (weight_capture_bank == 0) begin : g_bank0_enable
                    (* DONT_TOUCH = "yes", KEEP = "yes" *)
                    LUT2 #(.INIT(4'h2)) u_capture_enable (
                        .I0(weight_push), .I1(weight_wr_ptr_r),
                        .O(weight_data_capture_enable[CAPTURE_INDEX])
                    );
                end else begin : g_bank1_enable
                    (* DONT_TOUCH = "yes", KEEP = "yes" *)
                    LUT2 #(.INIT(4'h8)) u_capture_enable (
                        .I0(weight_push), .I1(weight_wr_ptr_r),
                        .O(weight_data_capture_enable[CAPTURE_INDEX])
                    );
                end

                always @(posedge clk) begin
                    if (weight_data_capture_enable[CAPTURE_INDEX])
                        weight_s8_mem[weight_capture_bank][
                            weight_capture_region*32*8 +: 32*8] <=
                            weight_s8[weight_capture_region*32*8 +: 32*8];
                end
            end

            always @(posedge clk) begin
                if (weight_group_capture_enable[weight_capture_bank])
                    weight_group_mem[weight_capture_bank] <= weight_group;
                if (weight_meta_capture_enable[weight_capture_bank])
                    weight_meta16_mem[weight_capture_bank] <= weight_meta16;
            end
        end
    endgenerate

    assign activation_ready = (state_r == ST_FILL) && frontend_in_ready &&
        !frontend_bank_ready[activation_wave];
    assign activation_cached = ((state_r == ST_READY) ||
        (state_r == ST_PROJECT)) && (&frontend_bank_ready);
    assign activation_release_ready = (state_r == ST_READY) &&
        (&frontend_bank_ready);
    assign project_ready = (state_r == ST_READY) &&
        (&frontend_bank_ready);
    assign weight_ready = (state_r == ST_PROJECT) &&
        (weight_count_r < 2) && !all_weights_accepted_r &&
        (weight_group == next_accept_group_r);
    assign out_valid = (state_r == ST_PROJECT) && array_out_valid;
    assign out_wave = array_out_wave;
    assign out_s24 = array_out_s24[8*16*24-1:0];
    assign out_request_id = descriptor_request_id_r;
    assign out_cohort_id = descriptor_cohort_id_r;
    assign out_layer_id = descriptor_layer_id_r;
    assign out_op_id = descriptor_op_id_r;
    assign out_tile_id = descriptor_tile_id_r;
    assign out_query_start = descriptor_query_start_r;
    assign out_valid_key_count = descriptor_valid_key_count_r;
    assign busy = state_r != ST_FILL && state_r != ST_READY;
    assign error = control_error_r | frontend_error | array_error;

    hap_attention_frontend_8row u_frontend (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(activation_valid && (state_r == ST_FILL) &&
            !frontend_bank_ready[activation_wave]),
        .in_ready(frontend_in_ready), .in_bank(activation_wave),
        .in_group(activation_group), .in_s24(activation_s24),
        .rd_req_valid(frontend_rd_req_valid),
        .rd_req_ready(frontend_rd_req_ready),
        .rd_req_bank(consume_wave_r),
        .rd_req_group(weight_head_group),
        .rd_rsp_valid(frontend_rd_rsp_valid),
        .rd_rsp_ready(capture_group),
        .rd_rsp_bank(frontend_rd_rsp_bank),
        .rd_rsp_group(frontend_rd_rsp_group),
        .rd_rsp_u8(frontend_rd_rsp_u8),
        .rd_rsp_meta(frontend_rd_rsp_meta),
        .release_valid(frontend_release_valid),
        .release_ready(frontend_release_ready),
        .release_bank(frontend_release_bank),
        .bank_ready(frontend_bank_ready),
        .input_group_count(frontend_input_count_unused),
        .cache_write_count(frontend_write_count_unused),
        .cache_read_count(frontend_read_count_unused),
        .cache_release_count(frontend_release_count_unused),
        .hadamard_saturation_count(frontend_hadamard_sat_unused),
        .error(frontend_error)
    );

    wire [16*8-1:0] row_scale_code;
    wire [16*6-1:0] row_scale_shift;
    wire [16*8-1:0] col_scale_code;
    wire [16*6-1:0] col_scale_shift;
    genvar row;
    genvar zero_row;
    genvar zero_col;
    generate
        for (row = 0; row < 16; row = row + 1) begin : g_row_meta
            if (row < 8) begin
                assign row_scale_code[row*8 +: 8] =
                    group_stage_act_meta_r[row*24+8 +: 8];
                assign row_scale_shift[row*6 +: 6] =
                    group_stage_act_meta_r[row*24+16 +: 6];
            end else begin
                assign row_scale_code[row*8 +: 8] = 8'd0;
                assign row_scale_shift[row*6 +: 6] = 6'd0;
            end
        end
        genvar col;
        for (col = 0; col < 16; col = col + 1) begin : g_col_meta
            assign col_scale_code[col*8 +: 8] =
                group_stage_weight_meta16_r[col*16 +: 8];
            assign col_scale_shift[col*6 +: 6] =
                group_stage_weight_meta16_r[col*16+8 +: 6];
        end
        for (zero_row = 0; zero_row < 8;
             zero_row = zero_row + 1) begin : g_zero_point_row
            for (zero_col = 0; zero_col < 16;
                 zero_col = zero_col + 1) begin : g_zero_point_col
                assign group_stage_act_zero_point_lane[
                    (zero_row*16+zero_col)*8 +: 8] =
                    group_stage_act_zero_point_region_r[
                    (zero_row*4+(zero_col/4))*8 +: 8];
            end
        end
    endgenerate

    hap_a8w8_array_16x16_s42_col3 #(
        .DUAL_CONTEXT(1)
    ) u_array (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(issue_group), .in_ready(array_in_ready),
        .in_first_group(group_stage_group_r == 0),
        .in_last_group(group_stage_group_r == 7'd127),
        .in_wave(group_stage_wave_r),
        .region_act_u8(group_stage_act_u8_region_r),
        .lane_act_zero_point(group_stage_act_zero_point_lane),
        .row_act_scale_code(row_scale_code),
        .row_act_scale_shift(row_scale_shift),
        .col_wgt_s8(group_stage_weight_s8_r),
        .col_wgt_scale_code(col_scale_code),
        .col_wgt_scale_shift(col_scale_shift),
        .out_valid(array_out_valid),
        .out_ready(out_ready && (state_r == ST_PROJECT)),
        .out_wave(array_out_wave), .out_s24(array_out_s24),
        .accepted_group_count(consumed_wave_group_count),
        .accumulated_group_count(array_accumulated_group_count_unused),
        .output_tile_count(output_wave_tile_count),
        .saturation_count(saturation_count), .error(array_error)
    );

    localparam integer CAPTURE_ACT_BASE = 0;
    localparam integer CAPTURE_WEIGHT_BASE = 32;
    localparam integer CAPTURE_ACT_META = 48;
    localparam integer CAPTURE_ACT_ZERO = 49;
    localparam integer CAPTURE_WEIGHT_META = 50;
    localparam integer CAPTURE_GROUP_TAG = 51;
    localparam integer CAPTURE_WAVE_TAG = 52;
    wire [52:0] capture_group_local;
    genvar capture_control;
    generate
        for (capture_control = 0; capture_control < 53;
             capture_control = capture_control + 1) begin : g_capture_control
            (* DONT_TOUCH = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(capture_group),
                .O(capture_group_local[capture_control])
            );
        end
    endgenerate

    integer activation_copy_row;
    integer activation_copy_region;
    always @(posedge clk) begin
        if (capture_group_local[CAPTURE_GROUP_TAG])
            group_stage_group_r <= read_pending_group_r;
        if (capture_group_local[CAPTURE_WAVE_TAG])
            group_stage_wave_r <= read_pending_wave_r;
        if (capture_group_local[CAPTURE_ACT_META])
            group_stage_act_meta_r <= frontend_rd_rsp_meta;
        for (activation_copy_row = 0; activation_copy_row < 8;
             activation_copy_row = activation_copy_row + 1)
            for (activation_copy_region = 0; activation_copy_region < 4;
                 activation_copy_region = activation_copy_region + 1)
                if (capture_group_local[CAPTURE_ACT_BASE +
                    activation_copy_row*4 + activation_copy_region])
                    group_stage_act_u8_region_r[
                        (activation_copy_row*4+activation_copy_region)*32*8
                        +: 32*8] <= frontend_rd_rsp_u8[
                        activation_copy_row*32*8 +: 32*8];
        if (capture_group_local[CAPTURE_ACT_ZERO]) begin
            for (activation_copy_row = 0; activation_copy_row < 8;
                 activation_copy_row = activation_copy_row + 1)
                for (activation_copy_region = 0; activation_copy_region < 4;
                     activation_copy_region = activation_copy_region + 1)
                    group_stage_act_zero_point_region_r[
                        (activation_copy_row*4+activation_copy_region)*8
                        +: 8] <= frontend_rd_rsp_meta[
                        activation_copy_row*24 +: 8];
        end
        for (activation_copy_region = 0; activation_copy_region < 16;
             activation_copy_region = activation_copy_region + 1)
            if (capture_group_local[CAPTURE_WEIGHT_BASE +
                activation_copy_region])
                group_stage_weight_s8_r[
                    activation_copy_region*32*8 +: 32*8] <=
                    weight_head_s8[
                    activation_copy_region*32*8 +: 32*8];
        if (capture_group_local[CAPTURE_WEIGHT_META])
            group_stage_weight_meta16_r <= weight_head_meta16;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_FILL;
            control_error_r <= 1'b0;
            weight_wr_ptr_r <= 1'b0;
            weight_rd_ptr_r <= 1'b0;
            weight_count_r <= 2'd0;
            next_accept_group_r <= 7'd0;
            next_consume_group_r <= 7'd0;
            all_weights_accepted_r <= 1'b0;
            consume_wave_r <= 1'b0;
            read_pending_r <= 1'b0;
            read_pending_wave_r <= 1'b0;
            read_pending_group_r <= 7'd0;
            tile_input_complete_r <= 1'b0;
            expected_output_wave_r <= 1'b0;
            group_stage_valid_r <= 1'b0;
            descriptor_request_id_r <= 32'd0;
            descriptor_cohort_id_r <= 16'd0;
            descriptor_layer_id_r <= 6'd0;
            descriptor_op_id_r <= 3'd0;
            descriptor_tile_id_r <= 10'd0;
            descriptor_query_start_r <= 7'd0;
            descriptor_valid_key_count_r <= 8'd0;
            accepted_weight_group_count <= 32'd0;
            released_weight_group_count <= 32'd0;
            weight_fifo_high_watermark <= 2'd0;
            project_done <= 1'b0;
            activation_released <= 1'b0;
        end else if (clear) begin
            state_r <= ST_FILL;
            control_error_r <= 1'b0;
            weight_wr_ptr_r <= 1'b0;
            weight_rd_ptr_r <= 1'b0;
            weight_count_r <= 2'd0;
            next_accept_group_r <= 7'd0;
            next_consume_group_r <= 7'd0;
            all_weights_accepted_r <= 1'b0;
            consume_wave_r <= 1'b0;
            read_pending_r <= 1'b0;
            tile_input_complete_r <= 1'b0;
            expected_output_wave_r <= 1'b0;
            group_stage_valid_r <= 1'b0;
            accepted_weight_group_count <= 32'd0;
            released_weight_group_count <= 32'd0;
            weight_fifo_high_watermark <= 2'd0;
            project_done <= 1'b0;
            activation_released <= 1'b0;
        end else begin
            project_done <= 1'b0;
            activation_released <= 1'b0;

            case (state_r)
                ST_FILL: begin
                    if (&frontend_bank_ready)
                        state_r <= ST_READY;
                end
                ST_READY: begin
                    if (project_start_fire && activation_release_fire) begin
                        control_error_r <= 1'b1;
                    end else if (project_start_fire) begin
                        state_r <= ST_PROJECT;
                        weight_wr_ptr_r <= 1'b0;
                        weight_rd_ptr_r <= 1'b0;
                        weight_count_r <= 2'd0;
                        next_accept_group_r <= 7'd0;
                        next_consume_group_r <= 7'd0;
                        all_weights_accepted_r <= 1'b0;
                        consume_wave_r <= 1'b0;
                        read_pending_r <= 1'b0;
                        tile_input_complete_r <= 1'b0;
                        expected_output_wave_r <= 1'b0;
                        group_stage_valid_r <= 1'b0;
                        descriptor_request_id_r <= project_request_id;
                        descriptor_cohort_id_r <= project_cohort_id;
                        descriptor_layer_id_r <= project_layer_id;
                        descriptor_op_id_r <= project_op_id;
                        descriptor_tile_id_r <= project_tile_id;
                        descriptor_query_start_r <= project_query_start;
                        descriptor_valid_key_count_r <=
                            project_valid_key_count;
                    end else if (activation_release_fire) begin
                        state_r <= ST_RELEASE0;
                    end
                end
                ST_PROJECT: begin
                    if (array_output_fire) begin
                        if (array_out_wave != expected_output_wave_r)
                            control_error_r <= 1'b1;
                        expected_output_wave_r <= ~expected_output_wave_r;
                        if (array_out_wave) begin
                            if (!tile_input_complete_r ||
                                (weight_count_r != 0) || read_pending_r ||
                                group_stage_valid_r)
                                control_error_r <= 1'b1;
                            project_done <= 1'b1;
                            state_r <= ST_READY;
                        end
                    end
                end
                ST_RELEASE0: begin
                    if (frontend_release_fire)
                        state_r <= ST_RELEASE1;
                end
                ST_RELEASE1: begin
                    if (frontend_release_fire) begin
                        activation_released <= 1'b1;
                        state_r <= ST_FILL;
                    end
                end
                default: state_r <= ST_ERROR;
            endcase

            if (weight_push_control) begin
                weight_wr_ptr_r <= weight_wr_ptr_r + 1'b1;
                accepted_weight_group_count <=
                    accepted_weight_group_count + 32'd1;
                if (weight_group == 7'd127) begin
                    next_accept_group_r <= 7'd0;
                    all_weights_accepted_r <= 1'b1;
                end else begin
                    next_accept_group_r <= weight_group + 1'b1;
                end
            end
            if (weight_pop) begin
                weight_rd_ptr_r <= weight_rd_ptr_r + 1'b1;
                released_weight_group_count <=
                    released_weight_group_count + 32'd1;
            end
            case ({weight_push_control, weight_pop})
                2'b10: weight_count_r <= weight_count_r + 1'b1;
                2'b01: weight_count_r <= weight_count_r - 1'b1;
                default: weight_count_r <= weight_count_r;
            endcase
            if (weight_push_control && !weight_pop &&
                ((weight_count_r + 1'b1) > weight_fifo_high_watermark))
                weight_fifo_high_watermark <= weight_count_r + 1'b1;

            if (frontend_rd_req_fire) begin
                read_pending_r <= 1'b1;
                read_pending_wave_r <= consume_wave_r;
                read_pending_group_r <= weight_head_group;
            end
            if (issue_group)
                group_stage_valid_r <= 1'b0;
            if (capture_group) begin
                read_pending_r <= 1'b0;
                group_stage_valid_r <= 1'b1;
                if ((frontend_rd_rsp_bank != read_pending_wave_r) ||
                    (frontend_rd_rsp_group != read_pending_group_r) ||
                    (weight_head_group != read_pending_group_r))
                    control_error_r <= 1'b1;
                if (read_pending_wave_r) begin
                    consume_wave_r <= 1'b0;
                    if (read_pending_group_r == 7'd127) begin
                        next_consume_group_r <= 7'd0;
                        tile_input_complete_r <= 1'b1;
                    end else begin
                        next_consume_group_r <=
                            read_pending_group_r + 1'b1;
                    end
                end else begin
                    consume_wave_r <= 1'b1;
                end
            end

            if ((weight_count_r != 0) &&
                (weight_head_group != next_consume_group_r))
                control_error_r <= 1'b1;
            if (frontend_rd_rsp_valid && !read_pending_r)
                control_error_r <= 1'b1;
            if (array_out_valid && (state_r != ST_PROJECT))
                control_error_r <= 1'b1;
            if (frontend_error || array_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

endmodule
