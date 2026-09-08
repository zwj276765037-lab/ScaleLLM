`timescale 1ns / 1ps

// Simulation-only transaction stub. It preserves the cohort16 projection
// handshake, descriptor, count, and wave order while returning zero tiles.
module hap_projection_core16x16_w8_reuse_stub (
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
    output reg  [31:0]           consumed_wave_group_count,
    output reg  [31:0]           released_weight_group_count,
    output reg  [31:0]           output_wave_tile_count,
    output wire [31:0]           saturation_count,
    output reg  [1:0]            weight_fifo_high_watermark,
    output wire                  busy,
    output wire                  error
);
    localparam [2:0] ST_FILL = 3'd0;
    localparam [2:0] ST_READY = 3'd1;
    localparam [2:0] ST_WEIGHT = 3'd2;
    localparam [2:0] ST_OUT0 = 3'd3;
    localparam [2:0] ST_OUT1 = 3'd4;
    localparam [2:0] ST_ERROR = 3'd7;

    reg [2:0] state_r;
    reg expected_activation_wave_r;
    reg [6:0] expected_activation_group_r;
    reg [6:0] expected_weight_group_r;
    reg [31:0] descriptor_request_id_r;
    reg [15:0] descriptor_cohort_id_r;
    reg [5:0] descriptor_layer_id_r;
    reg [2:0] descriptor_op_id_r;
    reg [9:0] descriptor_tile_id_r;
    reg [6:0] descriptor_query_start_r;
    reg [7:0] descriptor_valid_key_count_r;
    reg control_error_r;

    wire activation_fire = activation_valid && activation_ready;
    wire project_fire = project_start && project_ready;
    wire weight_fire = weight_valid && weight_ready;
    wire output_fire = out_valid && out_ready;

    assign activation_ready = state_r == ST_FILL &&
        activation_wave == expected_activation_wave_r &&
        activation_group == expected_activation_group_r;
    assign activation_cached = state_r != ST_FILL && state_r != ST_ERROR;
    assign activation_release_ready = state_r == ST_READY;
    assign project_ready = state_r == ST_READY;
    assign weight_ready = state_r == ST_WEIGHT &&
        weight_group == expected_weight_group_r;
    assign out_valid = state_r == ST_OUT0 || state_r == ST_OUT1;
    assign out_wave = state_r == ST_OUT1;
    assign out_s24 = '0;
    assign out_request_id = descriptor_request_id_r;
    assign out_cohort_id = descriptor_cohort_id_r;
    assign out_layer_id = descriptor_layer_id_r;
    assign out_op_id = descriptor_op_id_r;
    assign out_tile_id = descriptor_tile_id_r;
    assign out_query_start = descriptor_query_start_r;
    assign out_valid_key_count = descriptor_valid_key_count_r;
    assign saturation_count = 32'd0;
    assign busy = state_r == ST_WEIGHT || state_r == ST_OUT0 ||
        state_r == ST_OUT1;
    assign error = control_error_r || state_r == ST_ERROR;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_FILL;
            expected_activation_wave_r <= 1'b0;
            expected_activation_group_r <= 7'd0;
            expected_weight_group_r <= 7'd0;
            descriptor_request_id_r <= 32'd0;
            descriptor_cohort_id_r <= 16'd0;
            descriptor_layer_id_r <= 6'd0;
            descriptor_op_id_r <= 3'd0;
            descriptor_tile_id_r <= 10'd0;
            descriptor_query_start_r <= 7'd0;
            descriptor_valid_key_count_r <= 8'd0;
            accepted_weight_group_count <= 32'd0;
            consumed_wave_group_count <= 32'd0;
            released_weight_group_count <= 32'd0;
            output_wave_tile_count <= 32'd0;
            weight_fifo_high_watermark <= 2'd0;
            project_done <= 1'b0;
            activation_released <= 1'b0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            state_r <= ST_FILL;
            expected_activation_wave_r <= 1'b0;
            expected_activation_group_r <= 7'd0;
            expected_weight_group_r <= 7'd0;
            accepted_weight_group_count <= 32'd0;
            consumed_wave_group_count <= 32'd0;
            released_weight_group_count <= 32'd0;
            output_wave_tile_count <= 32'd0;
            weight_fifo_high_watermark <= 2'd0;
            project_done <= 1'b0;
            activation_released <= 1'b0;
            control_error_r <= 1'b0;
        end else begin
            project_done <= 1'b0;
            activation_released <= 1'b0;
            if (activation_fire) begin
                if (expected_activation_group_r == 7'd127) begin
                    expected_activation_group_r <= 7'd0;
                    if (!expected_activation_wave_r)
                        expected_activation_wave_r <= 1'b1;
                    else begin
                        expected_activation_wave_r <= 1'b0;
                        state_r <= ST_READY;
                    end
                end else begin
                    expected_activation_group_r <=
                        expected_activation_group_r + 1'b1;
                end
            end
            if (project_fire) begin
                state_r <= ST_WEIGHT;
                expected_weight_group_r <= 7'd0;
                descriptor_request_id_r <= project_request_id;
                descriptor_cohort_id_r <= project_cohort_id;
                descriptor_layer_id_r <= project_layer_id;
                descriptor_op_id_r <= project_op_id;
                descriptor_tile_id_r <= project_tile_id;
                descriptor_query_start_r <= project_query_start;
                descriptor_valid_key_count_r <= project_valid_key_count;
            end
            if (activation_release && activation_release_ready) begin
                state_r <= ST_FILL;
                expected_activation_wave_r <= 1'b0;
                expected_activation_group_r <= 7'd0;
                activation_released <= 1'b1;
            end
            if (weight_fire) begin
                accepted_weight_group_count <=
                    accepted_weight_group_count + 1'b1;
                consumed_wave_group_count <=
                    consumed_wave_group_count + 2;
                released_weight_group_count <=
                    released_weight_group_count + 1'b1;
                weight_fifo_high_watermark <= 2'd1;
                if (expected_weight_group_r == 7'd127) begin
                    expected_weight_group_r <= 7'd0;
                    state_r <= ST_OUT0;
                end else begin
                    expected_weight_group_r <=
                        expected_weight_group_r + 1'b1;
                end
            end
            if (output_fire) begin
                output_wave_tile_count <= output_wave_tile_count + 1'b1;
                if (state_r == ST_OUT0) begin
                    state_r <= ST_OUT1;
                end else begin
                    state_r <= ST_READY;
                    project_done <= 1'b1;
                end
            end
            if (activation_valid && state_r == ST_FILL &&
                    ((activation_wave != expected_activation_wave_r) ||
                     (activation_group != expected_activation_group_r)))
                control_error_r <= 1'b1;
            if (weight_valid && state_r == ST_WEIGHT &&
                    weight_group != expected_weight_group_r)
                control_error_r <= 1'b1;
            if (project_fire && activation_release &&
                    activation_release_ready)
                control_error_r <= 1'b1;
            if (control_error_r)
                state_r <= ST_ERROR;
        end
    end

    wire unused = &{1'b0, activation_s24, weight_s8, weight_meta16};
endmodule
