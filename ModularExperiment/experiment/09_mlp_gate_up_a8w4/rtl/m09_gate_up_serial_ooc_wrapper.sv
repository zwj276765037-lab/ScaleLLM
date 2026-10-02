`timescale 1ns / 1ps

// Narrow-port physical harness for the full 16x12 Gate/Up tile.  The core
// remains unchanged; only the on-chip group payload and tile result buses are
// serialized so OOC placement does not model thousands of package terminals.
module m09_gate_up_serial_ooc_wrapper #(
    parameter integer VARIANT = 0
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          clear,
    input  wire          load_valid,
    output wire          load_ready,
    input  wire [255:0]  load_data,
    output wire          result_valid,
    input  wire          result_ready,
    output wire [255:0]  result_data,
    output wire          result_last,
    output wire [31:0]   input_group_count,
    output wire [31:0]   output_tile_count,
    output wire          error
);
    localparam [1:0] ST_LOAD  = 2'd0;
    localparam [1:0] ST_SEND  = 2'd1;
    localparam [1:0] ST_WAIT  = 2'd2;
    localparam [1:0] ST_DRAIN = 2'd3;
    localparam integer INPUT_BITS = VARIANT == 0 ? 6550 :
        (VARIANT == 1 ? 6606 : 7054);
    localparam integer LOAD_WORDS = (INPUT_BITS+255)/256;
    localparam integer PAYLOAD_W = LOAD_WORDS*256;
    localparam integer RESULT_WORDS = 18;

    reg [1:0] state_r;
    reg [4:0] load_word_r;
    reg [4:0] result_word_r;
    reg [PAYLOAD_W-1:0] load_payload_r;
    wire load_fire = load_valid && load_ready;
    wire result_fire = result_valid && result_ready;
    wire core_in_ready;
    wire core_out_valid;
    wire core_out_ready;
    wire signed [16*12*24-1:0] core_projection_s24;
    wire core_error;
    wire payload_last_group = VARIANT == 0 ? load_payload_r[6549] :
        (VARIANT == 1 ? load_payload_r[6605] : load_payload_r[7053]);

    assign load_ready = rst_n && !clear && state_r == ST_LOAD;
    assign result_valid = rst_n && !clear && state_r == ST_DRAIN &&
        core_out_valid;
    assign result_data = core_projection_s24[result_word_r*256 +: 256];
    assign result_last = result_word_r == RESULT_WORDS-1;
    assign core_out_ready = result_fire && result_last;
    assign error = core_error;

    generate
        if (VARIANT == 0) begin : g_sc
            m09_sc_gate_up_tile u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(state_r == ST_SEND), .in_ready(core_in_ready),
                .in_first_group(load_payload_r[6548]),
                .in_last_group(load_payload_r[6549]),
                .activation_s9x16x32(load_payload_r[0 +: 4608]),
                .weights_s4x12x32(load_payload_r[4608 +: 1536]),
                .activation_code_u8x16(load_payload_r[6144 +: 128]),
                .activation_shift_u6x16(load_payload_r[6272 +: 96]),
                .weight_code_u8x12(load_payload_r[6368 +: 96]),
                .weight_shift_u6x12(load_payload_r[6464 +: 72]),
                .column_valid_u12(load_payload_r[6536 +: 12]),
                .out_valid(core_out_valid), .out_ready(core_out_ready),
                .projection_s24x16x12(core_projection_s24),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(), .error(core_error));
        end else if (VARIANT == 1) begin : g_fp16
            m09_fp16_gate_up_tile u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(state_r == ST_SEND), .in_ready(core_in_ready),
                .in_first_group(load_payload_r[6604]),
                .in_last_group(load_payload_r[6605]),
                .activation_s9x16x32(load_payload_r[0 +: 4608]),
                .weights_s4x12x32(load_payload_r[4608 +: 1536]),
                .activation_scale_fpx16(load_payload_r[6144 +: 256]),
                .weight_scale_fpx12(load_payload_r[6400 +: 192]),
                .column_valid_u12(load_payload_r[6592 +: 12]),
                .out_valid(core_out_valid), .out_ready(core_out_ready),
                .projection_s24x16x12(core_projection_s24),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count), .error(core_error));
        end else begin : g_fp32
            m09_fp32_gate_up_tile u_core (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(state_r == ST_SEND), .in_ready(core_in_ready),
                .in_first_group(load_payload_r[7052]),
                .in_last_group(load_payload_r[7053]),
                .activation_s9x16x32(load_payload_r[0 +: 4608]),
                .weights_s4x12x32(load_payload_r[4608 +: 1536]),
                .activation_scale_fpx16(load_payload_r[6144 +: 512]),
                .weight_scale_fpx12(load_payload_r[6656 +: 384]),
                .column_valid_u12(load_payload_r[7040 +: 12]),
                .out_valid(core_out_valid), .out_ready(core_out_ready),
                .projection_s24x16x12(core_projection_s24),
                .input_group_count(input_group_count),
                .output_tile_count(output_tile_count), .error(core_error));
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            state_r <= ST_LOAD;
            load_word_r <= '0;
            result_word_r <= '0;
        end else begin
            case (state_r)
                ST_LOAD: if (load_fire) begin
                    load_payload_r[load_word_r*256 +: 256] <= load_data;
                    if (load_word_r == LOAD_WORDS-1) begin
                        load_word_r <= '0;
                        state_r <= ST_SEND;
                    end else begin
                        load_word_r <= load_word_r + 1'b1;
                    end
                end
                ST_SEND: if (core_in_ready) begin
                    if (payload_last_group)
                        state_r <= ST_WAIT;
                    else
                        state_r <= ST_LOAD;
                end
                ST_WAIT: if (core_out_valid) begin
                    result_word_r <= '0;
                    state_r <= ST_DRAIN;
                end
                ST_DRAIN: if (result_fire) begin
                    if (result_last) begin
                        result_word_r <= '0;
                        state_r <= ST_LOAD;
                    end else begin
                        result_word_r <= result_word_r + 1'b1;
                    end
                end
                default: state_r <= ST_LOAD;
            endcase
        end
    end

    initial begin
        if (VARIANT < 0 || VARIANT > 2)
            $error("M09 serial OOC wrapper VARIANT must be 0, 1, or 2");
    end
endmodule

module m09_sc_gate_up_serial_ooc_wrapper (
    input wire clk, rst_n, clear, load_valid,
    output wire load_ready,
    input wire [255:0] load_data,
    output wire result_valid,
    input wire result_ready,
    output wire [255:0] result_data,
    output wire result_last,
    output wire [31:0] input_group_count, output_tile_count,
    output wire error
);
    m09_gate_up_serial_ooc_wrapper #(.VARIANT(0)) u_wrapper (.*);
endmodule

module m09_fp16_gate_up_serial_ooc_wrapper (
    input wire clk, rst_n, clear, load_valid,
    output wire load_ready,
    input wire [255:0] load_data,
    output wire result_valid,
    input wire result_ready,
    output wire [255:0] result_data,
    output wire result_last,
    output wire [31:0] input_group_count, output_tile_count,
    output wire error
);
    m09_gate_up_serial_ooc_wrapper #(.VARIANT(1)) u_wrapper (.*);
endmodule

module m09_fp32_gate_up_serial_ooc_wrapper (
    input wire clk, rst_n, clear, load_valid,
    output wire load_ready,
    input wire [255:0] load_data,
    output wire result_valid,
    input wire result_ready,
    output wire [255:0] result_data,
    output wire result_last,
    output wire [31:0] input_group_count, output_tile_count,
    output wire error
);
    m09_gate_up_serial_ooc_wrapper #(.VARIANT(2)) u_wrapper (.*);
endmodule
