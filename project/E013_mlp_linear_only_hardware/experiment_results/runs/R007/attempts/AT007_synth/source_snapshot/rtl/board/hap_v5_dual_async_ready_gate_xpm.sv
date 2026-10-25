`timescale 1ns / 1ps

// Core-domain V5 board reset release.  The two MIG calibration indications
// are synchronized independently before reconvergence, and PCIe reset uses
// the XPM asynchronous-assert/synchronous-release reset primitive.
module hap_v5_dual_async_ready_gate_xpm (
    input  wire clk,
    input  wire base_aresetn,
    input  wire async_ready0,
    input  wire async_ready1,
    output wire aresetn
);
    wire base_aresetn_sync;
    wire ready0_sync;
    wire ready1_sync;

    xpm_cdc_async_rst #(
        .DEST_SYNC_FF(4),
        .INIT_SYNC_FF(1),
        .RST_ACTIVE_HIGH(0)
    ) u_base_reset_cdc (
        .src_arst(base_aresetn),
        .dest_clk(clk),
        .dest_arst(base_aresetn_sync)
    );

    xpm_cdc_async_rst #(
        .DEST_SYNC_FF(4), .INIT_SYNC_FF(1), .RST_ACTIVE_HIGH(0)
    ) u_ready0_cdc (
        .src_arst(async_ready0), .dest_clk(clk),
        .dest_arst(ready0_sync)
    );

    xpm_cdc_async_rst #(
        .DEST_SYNC_FF(4), .INIT_SYNC_FF(1), .RST_ACTIVE_HIGH(0)
    ) u_ready1_cdc (
        .src_arst(async_ready1), .dest_clk(clk),
        .dest_arst(ready1_sync)
    );

    assign aresetn = base_aresetn_sync && ready0_sync && ready1_sync;
endmodule
