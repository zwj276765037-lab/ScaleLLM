`timescale 1ns / 1ps
module hap_mlp_tensor_dma_bridge_tb;
 localparam IG=2,OT=3;reg clk=0,rst_n=0,clear=0;
 reg load_valid=0,load_bank=1;wire load_ready;reg[31:0]input_base_addr=32'h1000;
 reg store_valid=0;wire store_ready;reg[31:0]output_base_addr=32'h4000;
 wire iv;reg ir=0;wire ib;wire[6:0]ig;wire[12287:0]idata;
 reg ov=0;wire ory;reg[7:0]otile=0;reg[6143:0]odata=0;
 wire busy,done,load_done,store_done,store_armed,axi_active,error;
 wire[2:0]phase;wire[31:0]ibc,igc,obc,otc;
 wire arv,arr;wire[31:0]ara;wire[7:0]arl;wire[2:0]ars;wire[1:0]arb;
 wire rv,rr;wire[255:0]rd;wire[1:0]rresp;wire rlast;
 wire awv,awr;wire[31:0]awa;wire[7:0]awl;wire[2:0]aws;wire[1:0]awb;
 wire wv,wr;wire[255:0]wd;wire[31:0]ws;wire wl;
 reg bv=0;wire br;wire[1:0]bresp;integer checks=0,read_index=0,write_index=0;
 integer rremain=0,wremain=0,i,t,cycles=0;reg ractive=0,wactive=0;
 always #3.333 clk=~clk;
 hap_mlp_tensor_dma_bridge #(.INPUT_GROUPS(IG),.OUTPUT_TILES(OT),.PRODUCTION_SHAPE(0))dut(
  .clk(clk),.rst_n(rst_n),.clear(clear),.load_valid(load_valid),.load_ready(load_ready),
  .load_bank(load_bank),.input_base_addr(input_base_addr),.store_valid(store_valid),
  .store_ready(store_ready),.output_base_addr(output_base_addr),.mlp_input_valid(iv),
  .mlp_input_ready(ir),.mlp_input_bank(ib),.mlp_input_group(ig),
  .mlp_input_s24x16x32(idata),.mlp_out_valid(ov),.mlp_out_ready(ory),
  .mlp_out_tile(otile),.mlp_out_s24x16x16(odata),.busy(busy),.done(done),
  .load_done(load_done),.store_done(store_done),.store_armed(store_armed),
  .axi_active(axi_active),.error(error),
  .phase(phase),.input_beat_count(ibc),.input_group_count(igc),
  .output_beat_count(obc),.output_tile_count(otc),.m_axi_arvalid(arv),
  .m_axi_arready(arr),.m_axi_araddr(ara),.m_axi_arlen(arl),.m_axi_arsize(ars),
  .m_axi_arburst(arb),.m_axi_rvalid(rv),.m_axi_rready(rr),.m_axi_rdata(rd),
  .m_axi_rresp(rresp),.m_axi_rlast(rlast),.m_axi_awvalid(awv),.m_axi_awready(awr),
  .m_axi_awaddr(awa),.m_axi_awlen(awl),.m_axi_awsize(aws),.m_axi_awburst(awb),
  .m_axi_wvalid(wv),.m_axi_wready(wr),.m_axi_wdata(wd),.m_axi_wstrb(ws),
  .m_axi_wlast(wl),.m_axi_bvalid(bv),.m_axi_bready(br),.m_axi_bresp(bresp));
 task tick;begin @(posedge clk);#1;end endtask
 task check;input c;input[8*96-1:0]m;begin checks=checks+1;if(!c)begin
  $display("FAIL %0s",m);$fatal(1);end end endtask
 assign arr=!ractive;assign rv=ractive;assign rd={224'd0,read_index};
 assign rresp=0;assign rlast=ractive&&(rremain==1);
 assign awr=!wactive&&!bv;assign wr=wactive;assign bresp=0;
 always @(posedge clk)begin
  cycles<=cycles+1;if(cycles==3001)begin
   $display("FAIL timeout phase=%0d busy=%0d done=%0d error=%0d read=%0d ibc=%0d igc=%0d iv=%0d ir=%0d dma_done=%0d dma_state=%0d arv=%0d arr=%0d ara=%h ractive=%0d rremain=%0d write=%0d obc=%0d otc=%0d ov=%0d ory=%0d dma_busy=%0d",
    phase,busy,done,error,read_index,ibc,igc,iv,ir,dut.dma_done,
    dut.u_dma.state_r,arv,arr,ara,ractive,rremain,write_index,obc,otc,ov,ory,
    dut.dma_busy);$finish;end
  if(arv&&arr)begin
   if(ars!=5||arb!=1||ara!=input_base_addr+read_index*32)begin
    $display("FAIL read command");$fatal(1);end
   ractive<=1;rremain<=arl+1;end
  if(rv&&rr)begin read_index<=read_index+1;rremain<=rremain-1;
   if(rremain==1)ractive<=0;end
  if(awv&&awr)begin
   if(aws!=5||awb!=1||awa!=output_base_addr+write_index*32)begin
    $display("FAIL write command");$fatal(1);end
   wactive<=1;wremain<=awl+1;end
  if(wv&&wr)begin
   if(wd[31:0]!==write_index||ws!==32'hffffffff||wl!==(wremain==1))begin
    $display("FAIL write beat idx=%0d data=%h last=%0d rem=%0d",write_index,wd[31:0],wl,wremain);$fatal(1);end
   write_index<=write_index+1;wremain<=wremain-1;
   if(wremain==1)begin wactive<=0;bv<=1;end end
  if(bv&&br)bv<=0;
 end
 always @(posedge clk)if(iv&&ir)begin
  if(!ib||ig!==igc[6:0])begin $display("FAIL input tag");$fatal(1);end
  for(i=0;i<48;i=i+1)if(idata[i*256+:32]!==(ig*48+i))begin
   $display("FAIL input payload group=%0d beat=%0d actual=%0d",ig,i,idata[i*256+:32]);$fatal(1);end
 end
 initial begin repeat(4)tick();rst_n=1;tick();
  // Resetless payload is intentionally unknown/stale here, but the reset
  // valid contract must keep every payload-facing interface inactive.
  check(!iv&&!ory&&!wv&&!busy&&!done&&!load_done&&!store_done&&!store_armed&&!axi_active,
   "reset masks stale payload");
  clear=1;tick();check(!iv&&!ory&&!wv&&!busy&&!done&&!load_done&&!store_done,
   "clear masks stale payload");clear=0;tick();
  load_valid=1;while(!load_ready)tick();tick();load_valid=0;
  // deterministic group-level consumer backpressure
  while(!done)begin ir=(cycles%4)!=0;tick();end ir=0;
  check(load_done,"load done pulse");
  check(ibc==IG*48&&igc==IG&&read_index==IG*48,"load counts");check(!error,"load error");
  store_valid=1;while(!store_ready)tick();tick();store_valid=0;
  for(t=0;t<OT;t=t+1)begin
   otile=t;for(i=0;i<24;i=i+1)odata[i*256+:256]={224'd0,t*24+i};
   ov=1;while(!ory)tick();tick();ov=0;
  end
  while(!done)tick();
  check(store_done,"store done pulse");
  check(obc==OT*24&&otc==OT&&write_index==OT*24,"store counts");check(!error,"store error");
  $display("PASS hap_mlp_tensor_dma_bridge checks=%0d cycles=%0d",checks,cycles);$finish;end
endmodule
