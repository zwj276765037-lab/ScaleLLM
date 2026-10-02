`timescale 1ns / 1ps
module m3_s42_fifo #(
    parameter integer DEPTH=16
) (
    input wire clk, rst_n, clear,
    input wire push,
    input wire signed [41:0] push_data,
    output wire full,
    output wire out_valid,
    input wire out_ready,
    output wire signed [41:0] out_data,
    output reg [31:0] output_count,
    output reg error
);
    localparam PTR_W=$clog2(DEPTH), COUNT_W=$clog2(DEPTH+1);
    reg signed [41:0] mem[0:DEPTH-1];
    reg [PTR_W-1:0] wr, rd;
    reg [COUNT_W-1:0] count;
    wire pop=out_valid&&out_ready;
    wire commit=push&&(!full||pop);
    assign full=(count==DEPTH);
    assign out_valid=rst_n&&!clear&&(count!=0);
    assign out_data=mem[rd];
    always @(posedge clk) if (commit) mem[wr]<=push_data;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin wr<=0;rd<=0;count<=0;output_count<=0;error<=0; end
        else if(clear) begin wr<=0;rd<=0;count<=0;output_count<=0;error<=0; end
        else begin
            if(push&&full&&!pop) error<=1;
            if(commit) wr<=wr+1'b1;
            if(pop) begin rd<=rd+1'b1;output_count<=output_count+1;end
            case({commit,pop})
              2'b10:count<=count+1'b1; 2'b01:count<=count-1'b1;
              default:count<=count;
            endcase
        end
    end
endmodule

