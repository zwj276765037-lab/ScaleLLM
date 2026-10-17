`timescale 1ns/1ps
module hap_mlp_meta_dma_loader_tb;
 localparam G=5,D=3;reg clk=0,rst_n=0,clear=0,start_valid=0,target_bank=1;
 wire start_ready;reg[31:0]gate_base_addr=32'h1000,down_base_addr=32'h3000;
 wire lbv,lbb;reg lbr=1;wire gv,gb;reg gr=1;wire[2:0]ga;wire[223:0]gm;
 wire dv,db;reg drdy=1;wire[1:0]da;wire[223:0]dm;wire busy,done,error;
 wire[2:0]phase;wire[31:0]gc,dc;wire[63:0]bytes;
 wire arv,arr;wire[31:0]ara;wire[7:0]arl;wire[2:0]ars;wire[1:0]arb;
 wire rv,rr;wire[255:0]rd;wire[1:0]rresp;wire rlast;
 wire awv,awr;wire[31:0]awa;wire[7:0]awl;wire[2:0]aws;wire[1:0]awb;
 wire wv,wr;wire[255:0]wd;wire[31:0]ws;wire wl;wire bv,br;wire[1:0]bresp;
 integer idx=0,remain=0,checks=0,cycles=0;reg active=0;
 wire [31:0] expected_ar_base = idx<G ? gate_base_addr : down_base_addr;
 assign arr=!active;assign rv=active;assign rd={32'd0,192'd0,idx};
 assign rresp=0;assign rlast=active&&(remain==1);assign awr=1;assign wr=1;
 assign bv=0;assign bresp=0;always #3.333 clk=~clk;
 hap_mlp_meta_dma_loader #(.GATE_RECORDS(G),.DOWN_RECORDS(D),.GATE_ADDR_W(3),
  .DOWN_ADDR_W(2),.PRODUCTION_SHAPE(0))dut(.clk(clk),.rst_n(rst_n),.clear(clear),
  .start_valid(start_valid),.start_ready(start_ready),.target_bank(target_bank),
  .gate_base_addr(gate_base_addr),.down_base_addr(down_base_addr),
  .bank_load_begin_valid(lbv),.bank_load_begin_ready(lbr),.bank_load_begin_bank(lbb),
  .gate_wr_valid(gv),.gate_wr_ready(gr),.gate_wr_bank(gb),.gate_wr_addr(ga),
  .gate_wr_meta(gm),.down_wr_valid(dv),.down_wr_ready(drdy),.down_wr_bank(db),
  .down_wr_addr(da),.down_wr_meta(dm),.busy(busy),.done(done),.error(error),
  .phase(phase),.gate_record_count(gc),.down_record_count(dc),.physical_bytes(bytes),
  .m_axi_arvalid(arv),.m_axi_arready(arr),.m_axi_araddr(ara),.m_axi_arlen(arl),
  .m_axi_arsize(ars),.m_axi_arburst(arb),.m_axi_rvalid(rv),.m_axi_rready(rr),
  .m_axi_rdata(rd),.m_axi_rresp(rresp),.m_axi_rlast(rlast),.m_axi_awvalid(awv),
  .m_axi_awready(awr),.m_axi_awaddr(awa),.m_axi_awlen(awl),.m_axi_awsize(aws),
  .m_axi_awburst(awb),.m_axi_wvalid(wv),.m_axi_wready(wr),.m_axi_wdata(wd),
  .m_axi_wstrb(ws),.m_axi_wlast(wl),.m_axi_bvalid(bv),.m_axi_bready(br),.m_axi_bresp(bresp));
 task tick;begin @(posedge clk);#1;end endtask
 task check;
  input c;
  input [8*80-1:0] m;
  begin
   checks=checks+1;
   if(!c)begin
    $display("FAIL %0s",m);
    $fatal(1);
   end
  end
 endtask
 always @(posedge clk) begin
  cycles <= cycles + 1;
  if (cycles == 1000) begin
   $display("FAIL timeout phase=%0d",phase);
   $finish;
  end
  if (arv && arr) begin
   if ((ara != expected_ar_base) || (ars != 5) || (arb != 1)) begin
    $display("FAIL AR idx=%0d addr=%h",idx,ara);
    $fatal(1);
   end
   active <= 1;
   remain <= arl + 1;
  end
  if (rv && rr) begin
   idx <= idx + 1;
   remain <= remain - 1;
   if (remain == 1) active <= 0;
  end
  if (gv && gr) begin
   if ((!gb) || (ga != gc[2:0]) || (gm !== {192'd0,idx})) begin
    $display("FAIL gate meta");
    $fatal(1);
   end
  end
  if (dv && drdy) begin
   if ((!db) || (da != dc[1:0]) || (dm !== {192'd0,idx})) begin
    $display("FAIL down meta");
    $fatal(1);
   end
  end
 end
 initial begin repeat(4)tick();rst_n=1;tick();start_valid=1;while(!start_ready)tick();tick();start_valid=0;
  while(!done)begin gr=(cycles%5)!=0;drdy=(cycles%4)!=0;tick();end
  check(gc==G&&dc==D&&idx==G+D,"record counts");check(bytes==(G+D)*32,"byte count");
  check(!error&&lbb,"loader status");$display("PASS hap_mlp_meta_dma_loader checks=%0d cycles=%0d",checks,cycles);
  $display("HARDWARE_AGENT_SIM_PASS");$finish;end
endmodule
