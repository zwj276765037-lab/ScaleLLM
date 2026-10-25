`timescale 1ns/1ps
module hap_mlp_linear_tensor_dma_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,job_clear=0,load_valid=0,store_valid=0;
 reg [1:0] load_opcode=1,store_opcode=1;reg [31:0] load_base=32'h10000fc0,load_bytes=73728,store_base=32'h10100fc0,store_bytes=1376256;
 wire load_ready,store_ready,load_done,store_armed,store_done,cache_wr_valid;
 reg cache_wr_ready=1;wire [8:0] cache_wr_group;wire [4095:0] cache_wr_u8x16x32;wire [383:0] cache_wr_meta_u24x16;
 reg gu_valid=0,down_valid=0;wire gu_ready,down_ready;
 reg [6143:0] gu_s24x16x16;reg [9:0] gu_tile=0;reg gu_matrix=0,gu_last=0;
 reg [8191:0] down_s32x16x16;reg [7:0] down_tile=0;reg down_last=0;
 wire busy,quiescent,transport_quiescent,axi_active,error;wire [31:0] error_code,input_bytes,output_bytes,record_count,read_beat_count,write_beat_count;
wire  m_axi_arvalid;
reg  m_axi_arready=0;
wire [32-1:0] m_axi_araddr;
wire [7:0] m_axi_arlen;
wire [2:0] m_axi_arsize;
wire [1:0] m_axi_arburst;
reg  m_axi_rvalid=0;
wire  m_axi_rready;
reg [255:0] m_axi_rdata=0;
reg [1:0] m_axi_rresp=0;
reg  m_axi_rlast=0;
wire  m_axi_awvalid;
reg  m_axi_awready=0;
wire [32-1:0] m_axi_awaddr;
wire [7:0] m_axi_awlen;
wire [2:0] m_axi_awsize;
wire [1:0] m_axi_awburst;
wire  m_axi_wvalid;
reg  m_axi_wready=0;
wire [255:0] m_axi_wdata;
wire [31:0] m_axi_wstrb;
wire  m_axi_wlast;
reg  m_axi_bvalid=0;
wire  m_axi_bready;
reg [1:0] m_axi_bresp=0;
 hap_mlp_linear_tensor_dma dut(.*);
 integer cycles=0,reads=0,writes=0,groups=0,ars=0,aws=0,seed=19,mode=0;
 integer rleft=0,rtotal=0,wleft=0,bdelay=-1,final_bdelay=0;
 reg [31:0] read_address=0;
 function [7:0] input_byte(input integer offset);
 integer g,record_offset,row,lane,mb;
 begin
 g=offset/576;record_offset=offset%576;row=record_offset/32;lane=record_offset%32;
 if(record_offset<512)input_byte=(g*17+row*13+lane)&255;
 else if(record_offset<560)begin row=(record_offset-512)/3;mb=(record_offset-512)%3;input_byte=mb==0?row:mb==1?(g%255+1):10;end
 else input_byte=(mode==1&&g==0&&record_offset==560)?1:0;
 end endfunction
 function [255:0] input_beat(input integer address);begin
 for(integer b=0;b<32;b=b+1)input_beat[b*8+:8]=input_byte(address-load_base+b);
 end endfunction
 function [7:0] output_byte(input integer record_id,beat,byte_id);output_byte=(record_id*11+beat*7+byte_id)&255;endfunction
 always @(negedge clk)begin
 if(rst_n&&!job_clear)begin
 m_axi_arready=(cycles%7)!=0;m_axi_awready=(cycles%11)>2;m_axi_wready=(cycles%9)>1;cache_wr_ready=(cycles%13)>4;
 if(!m_axi_rvalid&&rleft>0&&cycles%5!=0)begin m_axi_rvalid=1;m_axi_rdata=input_beat(read_address);m_axi_rlast=rleft==1;m_axi_rresp=mode==3?2:0;end
 if(bdelay==0)begin m_axi_bvalid=1;m_axi_bresp=mode==2?2:0;bdelay=-1;end
 else if(bdelay>0)bdelay=bdelay-1;
 end
 end
 always @(posedge clk)begin
 cycles<=cycles+1;if(cycles>400000)$fatal(1,"watchdog");
 if(job_clear)begin
 rleft=0;wleft=0;bdelay=-1;m_axi_rvalid<=0;m_axi_bvalid<=0;
 reads=0;writes=0;groups=0;ars=0;aws=0;
 end else if(rst_n)begin
 if(m_axi_arvalid&&m_axi_arready)begin
 if(rleft||m_axi_arlen>=16||m_axi_araddr[11:0]+(m_axi_arlen+1)*32>4096||m_axi_arsize!=5||m_axi_arburst!=1)$fatal(1,"AR burst contract");
 rleft=m_axi_arlen+1;read_address=m_axi_araddr;ars=ars+1;
 end
 if(m_axi_rvalid&&m_axi_rready)begin rleft=rleft-1;read_address=read_address+32;reads=reads+1;m_axi_rvalid<=0;end
 if(cache_wr_valid&&cache_wr_ready)begin
 if(mode==1)$fatal(1,"malformed input committed");
 if(cache_wr_group!=groups)$fatal(1,"cache group tag");
 for(integer r=0;r<16;r=r+1)begin
 for(integer l=0;l<32;l=l+1)if(cache_wr_u8x16x32[r*256+l*8+:8]!==input_byte(groups*576+r*32+l))$fatal(1,"cache payload");
 for(integer b=0;b<3;b=b+1)if(cache_wr_meta_u24x16[r*24+b*8+:8]!==input_byte(groups*576+512+r*3+b))$fatal(1,"cache metadata");
 end
 groups=groups+1;
 end
 if(m_axi_awvalid&&m_axi_awready)begin
 if(wleft||m_axi_bvalid||m_axi_awlen>=16||m_axi_awaddr[11:0]+(m_axi_awlen+1)*32>4096||m_axi_awsize!=5||m_axi_awburst!=1)$fatal(1,"AW burst contract");
 if(m_axi_awaddr!=store_base+writes*32)$fatal(1,"AW address");
 wleft=m_axi_awlen+1;aws=aws+1;
 end
 if(m_axi_wvalid&&m_axi_wready)begin
 if(wleft<=0||m_axi_wlast!=(wleft==1)||m_axi_wstrb!=32'hffffffff)$fatal(1,"W burst contract");
 for(integer b=0;b<32;b=b+1)if(m_axi_wdata[b*8+:8]!==output_byte(writes/(store_opcode==1?24:32),writes%(store_opcode==1?24:32),b))$fatal(1,"W data beat%0d",writes);
 wleft=wleft-1;writes=writes+1;
 if(m_axi_wlast)bdelay=(writes*32==store_bytes)?50:3;
 end
 if(m_axi_bvalid&&m_axi_bready)m_axi_bvalid<=0;
 if(store_done&&writes*32!=store_bytes)$fatal(1,"store done count");
 end
 end
 task clear_job;begin
 @(negedge clk);job_clear=1;load_valid=0;store_valid=0;gu_valid=0;down_valid=0;
 @(negedge clk);job_clear=0;
 end endtask
 task load(input integer op);begin
 load_opcode=op;load_bytes=op==1?73728:258048;
 @(negedge clk);load_valid=1;while(!load_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);load_valid=0;
 wait(load_done);@(negedge clk);
 if(mode==0&&(error||groups!=(op==1?128:448)||input_bytes!=load_bytes||reads*32!=load_bytes))$fatal(1,"load final counts");
 end endtask
 task arm(input integer op);begin
 store_opcode=op;store_bytes=op==1?1376256:262144;
 @(negedge clk);store_valid=1;while(!store_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);store_valid=0;
 repeat(21)begin @(negedge clk);if(m_axi_awvalid||aws)$fatal(1,"arm emitted AW before payload");end
 end endtask
 task send_record(input integer n,input integer op);begin
 @(negedge clk);
 if(op==1)begin
 for(integer b=0;b<768;b=b+1)gu_s24x16x16[b*8+:8]=output_byte(n,b/32,b%32);
 gu_tile=n/2;gu_matrix=n%2;gu_last=n==1791;gu_valid=1;while(!gu_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);gu_valid=0;
 end else begin
 for(integer b=0;b<1024;b=b+1)down_s32x16x16[b*8+:8]=output_byte(n,b/32,b%32);
 down_tile=n;down_last=n==255;down_valid=1;while(!down_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);down_valid=0;
 end
 end endtask
 initial begin
 repeat(3)@(negedge clk);rst_n=1;
 for(integer op=1;op<=2;op=op+1)begin
 load(op);arm(op);
 for(integer n=0;n<(op==1?1792:256);n=n+1)send_record(n,op);
 wait(writes*32==store_bytes);
 repeat(20)begin @(negedge clk);if(store_done||output_bytes==store_bytes)$fatal(1,"completion before final B");end
 wait(store_done);@(negedge clk);
 if(error||!quiescent||output_bytes!=store_bytes||record_count!=(op==1?1792:256))$fatal(1,"store final counts");
 clear_job();
 end
 mode=1;load(1);if(!error||error_code!=32'h2001||groups||input_bytes||!quiescent)$fatal(1,"malformed drain");clear_job();
 mode=2;arm(1);send_record(0,1);wait(error);repeat(25)@(negedge clk);
 if(error_code!=32'h2103||aws!=1||quiescent||store_done||!transport_quiescent||axi_active)$fatal(1,"BRESP fatal freeze");clear_job();
 mode=3;load_opcode=1;load_bytes=73728;load_valid=1;@(posedge clk);@(negedge clk);load_valid=0;
 wait(error);repeat(50)@(negedge clk);
 if(error_code!=32'h2101||ars!=1||quiescent||load_done||!transport_quiescent||axi_active)$fatal(1,"RRESP fatal freeze");
 $display("tensor DMA both production sizes, 4KiB/burst/backpressure/B-drain and malformed/AXI-response coverage");
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
