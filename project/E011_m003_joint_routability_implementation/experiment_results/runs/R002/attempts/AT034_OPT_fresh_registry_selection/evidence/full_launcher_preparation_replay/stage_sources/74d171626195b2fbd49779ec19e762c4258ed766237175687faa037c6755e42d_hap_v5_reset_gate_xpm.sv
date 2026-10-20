`timescale 1ns / 1ps

// V5 board-only reset/calibration gate.  base_aresetn assertion remains
// asynchronous while release and the unrelated ready level are synchronized
// by vendor-recognized XPM structures.  No user timing waiver is required.
module hap_v5_reset_gate_xpm (
    input  wire clk,
    input  wire base_aresetn,
    input  wire async_ready,
    output wire aresetn
);
    wire base_aresetn_sync;
    wire ready_sync;

    xpm_cdc_async_rst #(
        .DEST_SYNC_FF(4),
        .INIT_SYNC_FF(1),
        .RST_ACTIVE_HIGH(0)
    ) u_base_reset_cdc (
        .src_arst(base_aresetn),
        .dest_clk(clk),
        .dest_arst(base_aresetn_sync)
    );

    // Treat ready-low as an asynchronous reset assertion and synchronize only
    // its release.  This preserves the old reset-gate safety semantics while
    // avoiding both a stale-ready window and a user timing waiver.
    xpm_cdc_async_rst #(
        .DEST_SYNC_FF(4),
        .INIT_SYNC_FF(1),
        .RST_ACTIVE_HIGH(0)
    ) u_ready_cdc (
        .src_arst(async_ready),
        .dest_clk(clk),
        .dest_arst(ready_sync)
    );

    assign aresetn = base_aresetn_sync && ready_sync;
endmodule
