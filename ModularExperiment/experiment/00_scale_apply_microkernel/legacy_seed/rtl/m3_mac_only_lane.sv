`timescale 1ns / 1ps
module m3_mac_only_lane(
    input wire clk,rst_n,clear,in_valid,
    output wire in_ready,
    input wire [255:0] in_act_u8,in_wgt_s8,
    input wire [7:0] in_act_zero_point,
    output wire out_valid,input wire out_ready,
    output wire signed [41:0] out_guard_s42,
    output reg [31:0] input_group_count,
    output wire [31:0] output_group_count,
    output wire error
);
    reg [4:0] used;
    wire corr_valid;
    wire signed [20:0] corr;
    wire fifo_full,fifo_error;
    wire in_fire=in_valid&&in_ready, out_fire=out_valid&&out_ready;
    m3_precenter_mac_group32 #(.META_W(1)) mac(
      .clk(clk),.rst_n(rst_n),.clear(clear),.allow_input(used<16),
      .in_valid(in_valid),.in_ready(in_ready),.in_act_u8(in_act_u8),
      .in_wgt_s8(in_wgt_s8),.in_zero_point(in_act_zero_point),.in_meta(1'b0),
      .out_valid(corr_valid),.out_corr_s21(corr),.out_meta());
    m3_s42_fifo fifo(.clk(clk),.rst_n(rst_n),.clear(clear),.push(corr_valid),
      .push_data({{21{corr[20]}},corr}),.full(fifo_full),.out_valid(out_valid),
      .out_ready(out_ready),.out_data(out_guard_s42),
      .output_count(output_group_count),.error(fifo_error));
    assign error=fifo_error;
    always @(posedge clk or negedge rst_n) begin
      if(!rst_n) begin used<=0;input_group_count<=0;end
      else if(clear) begin used<=0;input_group_count<=0;end
      else begin
        if(in_fire)input_group_count<=input_group_count+1;
        case({in_fire,out_fire}) 2'b10:used<=used+1;2'b01:used<=used-1;default:used<=used;endcase
      end
    end
endmodule

