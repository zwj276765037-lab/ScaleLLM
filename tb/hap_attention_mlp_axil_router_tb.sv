`timescale 1ns/1ps
module hap_attention_mlp_axil_router_tb;
 reg clk=0,rst_n=0;always #3.333 clk=~clk;
 reg[11:0]s_awaddr=0,s_araddr=0;reg s_awvalid=0,s_wvalid=0,s_bready=0;
 reg[31:0]s_wdata=0;reg[3:0]s_wstrb=0;wire s_awready,s_wready;
 wire[1:0]s_bresp,s_rresp;wire s_bvalid,s_arready,s_rvalid;wire[31:0]s_rdata;
 reg s_arvalid=0,s_rready=0;
 wire[11:0]aa,ma,aar,mar;wire av,wav,arv,mav,mwv,mrv;
 wire[31:0]awd,mwd;wire[3:0]aws,mws;reg ardy=0,wrdy=0,mardy=0,mwrdy=0;
 reg[1:0]abresp=0,mbresp=0,arresp=0,mrresp=0;reg abvalid=0,mbvalid=0;
 wire abready,mbready;reg[31:0]ardata=0,mrdata=0;reg arrdy=0,mrrdy=0;
 reg arvalid=0,mrvalid=0;wire arready,mrready;
 integer checks=0;
 hap_attention_mlp_axil_router dut(.clk(clk),.rst_n(rst_n),
  .s_awaddr(s_awaddr),.s_awvalid(s_awvalid),.s_awready(s_awready),
  .s_wdata(s_wdata),.s_wstrb(s_wstrb),.s_wvalid(s_wvalid),.s_wready(s_wready),
  .s_bresp(s_bresp),.s_bvalid(s_bvalid),.s_bready(s_bready),
  .s_araddr(s_araddr),.s_arvalid(s_arvalid),.s_arready(s_arready),
  .s_rdata(s_rdata),.s_rresp(s_rresp),.s_rvalid(s_rvalid),.s_rready(s_rready),
  .attn_awaddr(aa),.attn_awvalid(av),.attn_awready(ardy),.attn_wdata(awd),
  .attn_wstrb(aws),.attn_wvalid(wav),.attn_wready(wrdy),
  .attn_bresp(abresp),.attn_bvalid(abvalid),.attn_bready(abready),
  .attn_araddr(aar),.attn_arvalid(arv),.attn_arready(arrdy),
  .attn_rdata(ardata),.attn_rresp(arresp),.attn_rvalid(arvalid),.attn_rready(arready),
  .mlp_awaddr(ma),.mlp_awvalid(mav),.mlp_awready(mardy),.mlp_wdata(mwd),
  .mlp_wstrb(mws),.mlp_wvalid(mwv),.mlp_wready(mwrdy),
  .mlp_bresp(mbresp),.mlp_bvalid(mbvalid),.mlp_bready(mbready),
  .mlp_araddr(mar),.mlp_arvalid(mrv),.mlp_arready(mrrdy),
  .mlp_rdata(mrdata),.mlp_rresp(mrresp),.mlp_rvalid(mrvalid),.mlp_rready(mrready));
 task tick;begin @(posedge clk);#1;end endtask
 task ck;input cond;input[255:0]msg;begin checks=checks+1;if(cond!==1'b1)begin
   $display("FAIL %0s",msg);$fatal(1);end end endtask
 initial begin
  repeat(4)tick();rst_n=1;tick();
  // AW first, W later: address must select Attention and remain stable.
  s_awaddr=12'h02c;s_awvalid=1;tick();s_awvalid=0;
  repeat(2)tick();s_wdata=32'ha5a55a5a;s_wstrb=4'hf;s_wvalid=1;tick();s_wvalid=0;
  tick();ck(av&&wav&&!mav&&!mwv,"AW-first selects attention");
  ck(aa==12'h02c&&awd==32'ha5a55a5a,"attention payload");
  wrdy=1;tick();wrdy=0;ck(av&&!wav,"independent W handshake");
  ardy=1;tick();ardy=0;abresp=2'b00;abvalid=1;s_bready=1;#1;
  ck(s_bvalid&&s_bresp==0&&abready&&!mbready,"attention B route");tick();
  abvalid=0;s_bready=0;tick();
  // W first, AW later: select MLP using captured AW, not W arrival time.
  s_wdata=32'h11223344;s_wstrb=4'h3;s_wvalid=1;tick();s_wvalid=0;
  repeat(2)tick();s_awaddr=12'h154;s_awvalid=1;tick();s_awvalid=0;tick();
  ck(mav&&mwv&&!av&&!wav,"W-first selects MLP");
  ck(ma==12'h154&&mwd==32'h11223344&&mws==4'h3,"MLP payload");
  mardy=1;mwrdy=1;tick();mardy=0;mwrdy=0;
  mbresp=2'b10;mbvalid=1;s_bready=1;#1;
  ck(s_bvalid&&s_bresp==2'b10&&mbready&&!abready,"MLP B route");tick();
  mbvalid=0;s_bready=0;tick();
  // Read routing and response backpressure.
  s_araddr=12'h040;s_arvalid=1;tick();s_arvalid=0;tick();
  ck(arv&&!mrv&&aar==12'h040,"attention AR route");arrdy=1;tick();arrdy=0;
  ardata=32'hcafe0001;arresp=0;arvalid=1;repeat(2)tick();
  ck(s_rvalid&&s_rdata==32'hcafe0001&&!arready,"attention R held");
  s_rready=1;tick();s_rready=0;arvalid=0;tick();
  s_araddr=12'h180;s_arvalid=1;tick();s_arvalid=0;tick();
  ck(mrv&&!arv&&mar==12'h180,"MLP AR route");mrrdy=1;tick();mrrdy=0;
  mrdata=32'hcafe0002;mrresp=2'b10;mrvalid=1;s_rready=1;#1;
  ck(s_rvalid&&s_rdata==32'hcafe0002&&s_rresp==2'b10&&mrready,"MLP R route");tick();
  mrvalid=0;s_rready=0;tick();
  $display("PASS hap_attention_mlp_axil_router checks=%0d",checks);$finish;
 end
endmodule
