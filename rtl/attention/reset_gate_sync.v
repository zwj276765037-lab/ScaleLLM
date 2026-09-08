`timescale 1ns/1ps
module reset_gate_sync(input wire clk,input wire base_aresetn,input wire async_ready,output wire aresetn);
 (* ASYNC_REG="TRUE",SHREG_EXTRACT="NO" *) reg[3:0] sync=0;
 always@(posedge clk or negedge base_aresetn)if(!base_aresetn)sync<=0;else sync<={sync[2:0],async_ready};
 assign aresetn=sync[3];
endmodule
