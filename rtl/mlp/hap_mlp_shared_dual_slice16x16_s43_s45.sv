`timescale 1ns / 1ps

// Cohort16 wrapper around exactly two physical shared 8x16 kernels.  The W4
// payload is captured once and registered into one local copy per slice.
module hap_mlp_shared_dual_slice16x16_s43_s45 #(
    parameter integer DOWN_TILES=256,
    parameter integer DOWN_GROUPS=448,
    parameter integer TILE_W=(DOWN_TILES<=2)?1:$clog2(DOWN_TILES)
) (
    input wire clk,input wire rst_n,input wire clear,
    input wire in_valid,output wire in_ready,input wire in_down,
    input wire in_first,input wire in_last,input wire [TILE_W-1:0] in_tile,
    input wire signed [4607:0] activation_s9x16x32,
    input wire signed [2047:0] weights_s4x16x32,
    input wire [127:0] activation_code_u8x16,
    input wire [95:0] activation_shift_u6x16,
    input wire [127:0] weight_code_u8x16,
    input wire [95:0] weight_shift_u6x16,
    output wire gate_valid,input wire gate_ready,
    output wire signed [6143:0] gate_s24x16x16,
    output wire down_valid,input wire down_ready,
    output wire [TILE_W-1:0] down_tile,
    output wire signed [6143:0] down_s24x16x16,
    output wire [31:0] gate_saturation,output wire [31:0] down_saturation,
    output reg [31:0] input_transaction_count,
    output reg [31:0] gate_output_tile_count,
    output reg [31:0] down_output_tile_count,output reg error
);
    wire ready0,ready1,gvalid0,gvalid1,dvalid0,dvalid1;
    wire gready0=gate_ready&&gvalid1;
    wire gready1=gate_ready&&gvalid0;
    wire dready0=down_ready&&dvalid1;
    wire dready1=down_ready&&dvalid0;
    wire [TILE_W-1:0] dtile0,dtile1;
    wire signed [3071:0] gout0,gout1,dout0,dout1;
    wire [31:0] gs0,gs1,ds0,ds1;wire err0,err1;
    wire in_fire=in_valid&&in_ready;
    // Each outer SLR owns a local depth-2 payload FIFO.  Valid is presented
    // to one side only when the other side also has credit, making the dual
    // push atomic while keeping ready independent of both compute pipelines.
    assign in_ready=rst_n&&!clear&&ready0&&ready1;
    assign gate_valid=rst_n&&!clear&&gvalid0&&gvalid1;
    assign down_valid=rst_n&&!clear&&dvalid0&&dvalid1;
    assign gate_s24x16x16={gout1,gout0};
    assign down_s24x16x16={dout1,dout0};assign down_tile=dtile0;
    assign gate_saturation=gs0+gs1;assign down_saturation=ds0+ds1;

    (* keep_hierarchy="yes" *)hap_mlp_shared_slice8x16_s43_s45 #(
      .DOWN_TILES(DOWN_TILES),.DOWN_GROUPS(DOWN_GROUPS),.TILE_W(TILE_W))u0(
      .clk(clk),.rst_n(rst_n),.clear(clear),
      .in_valid(in_valid&&ready1),.in_ready(ready0),.in_down(in_down),
      .in_first(in_first),.in_last(in_last),.in_tile(in_tile),
      .activation_s9x8x32(activation_s9x16x32[0+:2304]),
      .weights_s4x16x32(weights_s4x16x32),
      .activation_code_u8x8(activation_code_u8x16[0+:64]),
      .activation_shift_u6x8(activation_shift_u6x16[0+:48]),
      .weight_code_u8x16(weight_code_u8x16),
      .weight_shift_u6x16(weight_shift_u6x16),
      .gate_valid(gvalid0),.gate_ready(gready0),.gate_s24x8x16(gout0),
      .down_valid(dvalid0),.down_ready(dready0),.down_tile(dtile0),
      .down_s24x8x16(dout0),.gate_saturation(gs0),.down_saturation(ds0),
      .error(err0));
    (* keep_hierarchy="yes" *)hap_mlp_shared_slice8x16_s43_s45 #(
      .DOWN_TILES(DOWN_TILES),.DOWN_GROUPS(DOWN_GROUPS),.TILE_W(TILE_W))u1(
      .clk(clk),.rst_n(rst_n),.clear(clear),
      .in_valid(in_valid&&ready0),.in_ready(ready1),.in_down(in_down),
      .in_first(in_first),.in_last(in_last),.in_tile(in_tile),
      .activation_s9x8x32(activation_s9x16x32[2304+:2304]),
      .weights_s4x16x32(weights_s4x16x32),
      .activation_code_u8x8(activation_code_u8x16[64+:64]),
      .activation_shift_u6x8(activation_shift_u6x16[48+:48]),
      .weight_code_u8x16(weight_code_u8x16),
      .weight_shift_u6x16(weight_shift_u6x16),
      .gate_valid(gvalid1),.gate_ready(gready1),.gate_s24x8x16(gout1),
      .down_valid(dvalid1),.down_ready(dready1),.down_tile(dtile1),
      .down_s24x8x16(dout1),.gate_saturation(gs1),.down_saturation(ds1),
      .error(err1));
    always @(posedge clk)begin
      if(!rst_n||clear)begin input_transaction_count<=0;gate_output_tile_count<=0;
        down_output_tile_count<=0;error<=0;end else begin
        if(in_fire)input_transaction_count<=input_transaction_count+1;
        if(gate_valid&&gate_ready)gate_output_tile_count<=gate_output_tile_count+1;
        if(down_valid&&down_ready)down_output_tile_count<=down_output_tile_count+1;
        if(err0||err1||(down_valid&&dtile0!=dtile1))error<=1;
      end
    end
endmodule
