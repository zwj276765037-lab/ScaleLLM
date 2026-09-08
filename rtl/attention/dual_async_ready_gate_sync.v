`timescale 1ns/1ps

// Assert reset asynchronously through base_aresetn and release it only after
// two unrelated ready indications have each been synchronized into clk.
// Synchronizing before the AND avoids combinational CDC reconvergence/glitch
// sampling between the two independent MIG calibration domains.
module dual_async_ready_gate_sync (
    input  wire clk,
    input  wire base_aresetn,
    input  wire async_ready0,
    input  wire async_ready1,
    output wire aresetn
);
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [3:0] ready0_sync = 0;
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [3:0] ready1_sync = 0;

    always @(posedge clk or negedge base_aresetn) begin
        if (!base_aresetn) begin
            ready0_sync <= 0;
            ready1_sync <= 0;
        end else begin
            ready0_sync <= {ready0_sync[2:0], async_ready0};
            ready1_sync <= {ready1_sync[2:0], async_ready1};
        end
    end

    assign aresetn = ready0_sync[3] & ready1_sync[3];
endmodule
