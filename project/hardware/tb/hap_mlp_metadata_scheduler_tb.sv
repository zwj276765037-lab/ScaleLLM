`timescale 1ns/1ps
module hap_mlp_metadata_scheduler_tb;
 localparam G=5,D=3;reg clk=0,rst_n=0,clear=0,start=0,finish_cmd=0;
 always #3.333 clk=~clk;reg ge=0,de=0;wire grdy,drdy;
 wire grv,drv;wire[2:0]gra;wire[1:0]dra;reg grspv=0,drspv=0;
 wire grspr,drspr;reg[223:0]grspd=0,drspd=0;wire gmv,dmv;reg gmr=1,dmr=1;
 wire[223:0]gm,dm;wire active,done,error;wire[31:0]gi,gd,di,dd;
 integer checks=0;reg gp=0,dp=0;reg[2:0]ga=0;reg[1:0]da=0;
 integer gexpect=0,dexpect=0;
 hap_mlp_metadata_scheduler #(.GATE_RECORDS(G),.DOWN_RECORDS(D),
  .GATE_ADDR_W(3),.DOWN_ADDR_W(2),.PRODUCTION_SHAPE(0))dut(
  .clk(clk),.rst_n(rst_n),.clear(clear),.command_start(start),.command_done(finish_cmd),
  .gate_enable(ge),.down_enable(de),.gate_rd_valid(grv),.gate_rd_ready(grdy),
  .gate_rd_addr(gra),.gate_rsp_valid(grspv),.gate_rsp_ready(grspr),
  .gate_rsp_meta(grspd),.gate_meta_valid(gmv),.gate_meta_ready(gmr),.gate_meta(gm),
  .down_rd_valid(drv),.down_rd_ready(drdy),.down_rd_addr(dra),
  .down_rsp_valid(drspv),.down_rsp_ready(drspr),.down_rsp_meta(drspd),
  .down_meta_valid(dmv),.down_meta_ready(dmr),.down_meta(dm),.active(active),
  .gate_issue_count(gi),.gate_delivery_count(gd),.down_issue_count(di),
  .down_delivery_count(dd),.done(done),.error(error));
 task tick;begin @(posedge clk);#1;end endtask
 assign grdy=!gp&&!grspv;assign drdy=!dp&&!drspv;
 task ck;input cond;input[255:0]msg;begin checks=checks+1;if(cond!==1'b1)begin
  $display("FAIL %0s",msg);$fatal(1);end end endtask
 always @(posedge clk)begin
  if(!rst_n||clear)begin gp<=0;dp<=0;grspv<=0;drspv<=0;end else begin
   if(grspv&&grspr)grspv<=0;if(drspv&&drspr)drspv<=0;
   if(grv&&grdy)begin ga<=gra;gp<=1;end
   if(drv&&drdy)begin da<=dra;dp<=1;end
   if(gp&&!grspv)begin grspv<=1;grspd<=224'h100+ga;gp<=0;end
   if(dp&&!drspv)begin drspv<=1;drspd<=224'h200+da;dp<=0;end
   if(gmv&&gmr)begin
    if(gm!==224'h100+gexpect)begin $display("FAIL gate FIFO order");$fatal(1);end
    gexpect<=gexpect+1;end
   if(dmv&&dmr)begin
    if(dm!==224'h200+dexpect)begin $display("FAIL down FIFO order");$fatal(1);end
    dexpect<=dexpect+1;end
  end
 end
 initial begin repeat(4)tick();rst_n=1;tick();start=1;tick();start=0;ge=1;
  repeat(3)tick();gmr=0;repeat(4)tick();ck(gd<gi,"gate backpressure holds response");
  ck(!grspr,"depth-2 FIFO eventually backpressures resident response");
  gmr=1'b1;#0.1;ck(!grspr,"consumer ready cannot combinationally reach URAM ready");
  clear=1;tick();ck(!gmv&&!dmv&&!active&&gi==0&&gd==0,
   "clear occupancy masks resetless FIFO payload");clear=0;tick();
  // Restart from a clean occupancy state; stale memory data must never appear.
  gexpect=0;dexpect=0;gmr=1;start=1;tick();start=0;ge=1;
  while(gd<G)tick();ge=0;de=1;while(dd<D)tick();
  ck(gi==G&&gd==G&&di==D&&dd==D,"exact metadata counts");
  ck(gexpect==G&&dexpect==D,"FIFO metadata order/count");
  finish_cmd=1;tick();finish_cmd=0;ck(done&&!error&&!active,"clean scheduler done");
 $display("PASS hap_mlp_metadata_scheduler checks=%0d",checks);$finish;end
 initial begin #100000;$display("FAIL metadata scheduler timeout");$fatal(1);end
endmodule
