`timescale 1ns / 1ps

// Preserve independent asynchronous assertion / four-edge release for each
// condition, then qualify their reconvergence through a final four-edge chain.
// The public reset has no combinational logic after that final XPM stage.
module hap_scalellm_final_reset_gate_xpm (
    input  wire clk,
    input  wire base_aresetn,
    input  wire async_ready,
    output wire aresetn
);
    wire base_aresetn_sync;
    wire ready_sync;
    wire combined_aresetn;

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
        .DEST_SYNC_FF(4),
        .INIT_SYNC_FF(1),
        .RST_ACTIVE_HIGH(0)
    ) u_ready_cdc (
        .src_arst(async_ready),
        .dest_clk(clk),
        .dest_arst(ready_sync)
    );

    assign combined_aresetn = base_aresetn_sync && ready_sync;

    xpm_cdc_async_rst #(
        .DEST_SYNC_FF(4),
        .INIT_SYNC_FF(1),
        .RST_ACTIVE_HIGH(0)
    ) u_combined_reset_cdc (
        .src_arst(combined_aresetn),
        .dest_clk(clk),
        .dest_arst(aresetn)
    );
endmodule
