`timescale 1ns / 1ps

// Narrow-port physical wrapper for OOC implementation. The production
// core's wide payloads are on-chip tile buses, not package IO terminals.
module hap_mlp_product_frontend16_q4_ooc_wrapper (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire         load_valid,
    output wire         load_ready,
    input  wire [31:0]  load_product_s32,
    output wire         result_valid,
    input  wire         result_ready,
    output wire [31:0]  result_data,
    output wire         result_last,
    output wire [31:0]  busy_cycle_count,
    output wire         error
);
    localparam [1:0] ST_LOAD = 2'd0;
    localparam [1:0] ST_START = 2'd1;
    localparam [1:0] ST_WAIT = 2'd2;
    localparam [1:0] ST_DRAIN = 2'd3;
    reg [1:0] state_r;
    reg [8:0] load_word_r;
    reg [7:0] result_word_r;
    reg [16*32*32-1:0] product_buffer_r;
    wire core_in_ready;
    wire core_out_valid;
    wire core_out_ready;
    wire [16*32*8-1:0] core_activation_u8;
    wire [16*24-1:0] core_activation_meta;
    wire [31:0] core_busy_cycle_count;
    wire core_error;
    wire [16*32*8+16*24-1:0] result_payload =
        {core_activation_meta, core_activation_u8};
    wire load_fire = load_valid && load_ready;
    wire result_fire = result_valid && result_ready;

    assign load_ready = rst_n && !clear && state_r == ST_LOAD;
    assign result_valid = rst_n && !clear && state_r == ST_DRAIN &&
        core_out_valid;
    assign result_data = result_payload[result_word_r*32 +: 32];
    assign result_last = result_word_r == 8'd139;
    assign core_out_ready = result_fire && result_last;
    assign busy_cycle_count = core_busy_cycle_count;
    assign error = core_error;

    hap_mlp_product_frontend16_q4 u_core (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(state_r == ST_START), .in_ready(core_in_ready),
        .product_s32x16x32(product_buffer_r),
        .out_valid(core_out_valid), .out_ready(core_out_ready),
        .activation_u8x16x32(core_activation_u8),
        .activation_meta_u24x16(core_activation_meta),
        .input_group_count(), .output_group_count(),
        .busy_cycle_count(core_busy_cycle_count), .error(core_error)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            state_r <= ST_LOAD;
            load_word_r <= '0;
            result_word_r <= '0;
        end else begin
            case (state_r)
                ST_LOAD: if (load_fire) begin
                    product_buffer_r[load_word_r*32 +: 32] <=
                        load_product_s32;
                    if (load_word_r == 9'd511) begin
                        load_word_r <= '0;
                        state_r <= ST_START;
                    end else load_word_r <= load_word_r + 1'b1;
                end
                ST_START: if (core_in_ready) state_r <= ST_WAIT;
                ST_WAIT: if (core_out_valid) begin
                    result_word_r <= '0;
                    state_r <= ST_DRAIN;
                end
                ST_DRAIN: if (result_fire) begin
                    if (result_last) begin
                        result_word_r <= '0;
                        state_r <= ST_LOAD;
                    end else result_word_r <= result_word_r + 1'b1;
                end
                default: state_r <= ST_LOAD;
            endcase
        end
    end
endmodule
