`timescale 1ns / 1ps

// Fixed-latency sideband pipeline for the nonblocking AMD Floating-Point IP.
module m13_delay_bus #(
    parameter integer WIDTH = 1,
    parameter integer DEPTH = 1
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    input  wire [WIDTH-1:0]     in_data,
    output wire                 out_valid,
    output wire [WIDTH-1:0]     out_data
);
    reg [DEPTH-1:0] valid_r;
    reg [WIDTH-1:0] data_r [0:DEPTH-1];
    integer index;

    assign out_valid = valid_r[DEPTH-1];
    assign out_data = data_r[DEPTH-1];

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            valid_r <= '0;
        end else begin
            valid_r[0] <= in_valid;
            data_r[0] <= in_data;
            for (index = 1; index < DEPTH; index = index + 1) begin
                valid_r[index] <= valid_r[index-1];
                data_r[index] <= data_r[index-1];
            end
        end
    end

    initial begin
        if (WIDTH <= 0 || DEPTH <= 0)
            $error("m13_delay_bus requires positive WIDTH and DEPTH");
    end
endmodule
