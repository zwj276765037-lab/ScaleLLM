`timescale 1ns / 1ps

// Core-domain V4 mode controller for the paired Attention/MLP DDR leaf.
//
// The controller deliberately contains no DDR-domain state and no owner mux.
// A one-entry pending register blocks new engine launches while the current
// engines and paired leaf drain.  The active mode changes atomically only
// after every quiescence input is true and maintenance is inactive.
//
// Mode encoding is frozen by the V4 architecture specification:
//   0 = IDLE, 1 = ATTN_ONLY, 2 = MLP_ONLY, 3 = SHARED.
module hap_v4_ddr_mode_controller (
    input  wire         core_clk,
    input  wire         core_rst_n,

    input  wire         mode_request_valid,
    output wire         mode_request_ready,
    input  wire [1:0]   mode_request,

    input  wire         attention_quiescent,
    input  wire         mlp_quiescent,
    input  wire         paired_leaf_quiescent,
    input  wire         paired_leaf_error,
    input  wire         maintenance_busy,

    output reg  [1:0]   active_mode,
    output wire         attention_launch_enable,
    output wire         mlp_launch_enable,
    output wire         core_enable,
    output wire         ddr0_enable,
    output wire         ddr1_enable,
    output wire         switch_pending,
    output reg          request_done,
    output wire         error
);
    localparam [1:0] MODE_IDLE      = 2'd0;
    localparam [1:0] MODE_ATTN_ONLY = 2'd1;
    localparam [1:0] MODE_MLP_ONLY  = 2'd2;
    localparam [1:0] MODE_SHARED    = 2'd3;

    reg [1:0] pending_mode_r;
    reg       pending_r;
    reg       error_r;

    wire error_any = error_r || paired_leaf_error;
    wire request_fire = mode_request_valid && mode_request_ready;
    wire all_quiescent = attention_quiescent && mlp_quiescent &&
        paired_leaf_quiescent;
    wire mode_running = active_mode != MODE_IDLE;
    wire launch_blocked = pending_r || request_fire || maintenance_busy ||
        error_any;

    // A request may be queued whenever no older request, maintenance operation
    // or fatal paired-leaf error owns the controller.  All four 2-bit encodings
    // are legal, so no wide request decoder is required.
    assign mode_request_ready = core_rst_n && !pending_r &&
        !maintenance_busy && !error_any;

    assign switch_pending = pending_r;
    assign error = error_any;

    // Keep the paired datapath running while a non-IDLE mode drains.  In
    // particular, a request to IDLE must not withdraw these enables before the
    // leaf reports quiescent.  They change only as a decode of active_mode.
    assign core_enable = mode_running;
    assign ddr0_enable = mode_running;
    assign ddr1_enable = mode_running;

    // request_fire closes the same-cycle launch/request race.  SHARED is the
    // only mode that opens both engines concurrently.
    assign attention_launch_enable = !launch_blocked &&
        (active_mode == MODE_ATTN_ONLY || active_mode == MODE_SHARED);
    assign mlp_launch_enable = !launch_blocked &&
        (active_mode == MODE_MLP_ONLY || active_mode == MODE_SHARED);

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            active_mode <= MODE_IDLE;
            pending_mode_r <= MODE_IDLE;
            pending_r <= 1'b0;
            request_done <= 1'b0;
            error_r <= 1'b0;
        end else begin
            request_done <= 1'b0;

            // Paired-leaf protocol/data errors are fatal for ownership.  Keep
            // a pending request frozen for post-mortem visibility; hard reset
            // is the only recovery and no mode can commit while error_any=1.
            if (paired_leaf_error)
                error_r <= 1'b1;

            if (request_fire) begin
                if (mode_request == active_mode) begin
                    // Idempotent requests do not change ownership and complete
                    // in the acceptance cycle.
                    request_done <= 1'b1;
                end else begin
                    pending_mode_r <= mode_request;
                    pending_r <= 1'b1;
                end
            end else if (pending_r && all_quiescent && !maintenance_busy &&
                !error_any) begin
                active_mode <= pending_mode_r;
                pending_r <= 1'b0;
                request_done <= 1'b1;
            end
        end
    end
endmodule
