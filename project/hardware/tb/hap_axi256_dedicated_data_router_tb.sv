`timescale 1ns / 1ps
module hap_m002_data_client_bfm #(parameter integer CLIENT=0)(
 input wire clk,input wire rst_n,input integer target,output reg req=0,
 output reg arvalid=0,input wire arready,output wire[31:0]araddr,
 output wire[7:0]arlen,output wire[2:0]arsize,output wire[1:0]arburst,
 input wire rvalid,output wire rready,input wire[255:0]rdata,
 input wire[1:0]rresp,input wire rlast,
 output reg awvalid=0,input wire awready,output wire[31:0]awaddr,
 output wire[7:0]awlen,output wire[2:0]awsize,output wire[1:0]awburst,
 output reg wvalid=0,input wire wready,output wire[255:0]wdata,
 output wire[31:0]wstrb,output wire wlast,input wire bvalid,
 output wire bready,input wire[1:0]bresp,output integer completed=0);
 integer state=0,beat=0,wbeat=0;reg[31:0]random_r=32'h873169ab+CLIENT;
 function automatic[255:0] payload(input[31:0]addr,input integer n,input bit wr);
 integer i;begin for(i=0;i<8;i=i+1)
 payload[32*i+:32]=(addr+n*32+i*4)^32'h7aca5106^(wr?32'hfefe1212:0);
 end endfunction
 assign araddr=(CLIENT+1)*65536+completed*256;
 assign awaddr=araddr+128;
 assign arlen=3;assign awlen=3;assign arsize=5;assign awsize=5;
 assign arburst=1;assign awburst=1;assign wstrb=32'hffffffff;
 assign rready=random_r[0]||random_r[3];assign bready=random_r[1]||random_r[4];
 assign wdata=payload(awaddr,wbeat,1);assign wlast=wbeat==3;
 always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin state<=0;beat<=0;wbeat<=0;completed<=0;req<=0;
 arvalid<=0;awvalid<=0;wvalid<=0;random_r<=32'h873169ab+CLIENT;end
 else begin
 random_r<={random_r[30:0],random_r[31]^random_r[21]^random_r[1]^random_r[0]};
 case(state)
 0:if(completed<target)begin req<=1;arvalid<=1;state<=1;beat<=0;wbeat<=0;end
 1:if(arvalid&&arready)begin arvalid<=0;state<=2;end
 2:if(rvalid&&rready)begin
   if(rdata!==payload(araddr,beat,0)||rresp!==0||rlast!==(beat==3))
     $fatal(1,"data client%0d R mismatch cmd%0d beat%0d",CLIENT,completed,beat);
   if(beat==3)begin awvalid<=1;state<=3;end else beat<=beat+1;
 end
 3:if(awvalid&&awready)begin awvalid<=0;wvalid<=1;state<=4;end
 4:if(wvalid&&wready)begin
   if(wbeat==3)begin wvalid<=0;state<=5;end else wbeat<=wbeat+1;
 end
 5:if(bvalid&&bready)begin
   if(bresp!==0)$fatal(1,"data client%0d B response mismatch",CLIENT);
   req<=0;completed<=completed+1;state<=0;
 end
 default:$fatal(1,"client BFM state");
 endcase
 end end
endmodule

module hap_m002_data_memory_bfm #(parameter integer DDR=0)(
 input wire clk,input wire rst_n,input wire block_ar,
 input wire arvalid,output wire arready,input wire[31:0]araddr,
 input wire[7:0]arlen,input wire[2:0]arsize,input wire[1:0]arburst,
 output reg rvalid=0,input wire rready,output reg[255:0]rdata=0,
 output wire[1:0]rresp,output reg rlast=0,
 input wire awvalid,output wire awready,input wire[31:0]awaddr,
 input wire[7:0]awlen,input wire[2:0]awsize,input wire[1:0]awburst,
 input wire wvalid,output wire wready,input wire[255:0]wdata,
 input wire[31:0]wstrb,input wire wlast,output reg bvalid=0,
 input wire bready,output wire[1:0]bresp,
 output integer read_commands=0,output integer write_commands=0,
 output integer checked_write_beats=0,output integer stalls=0);
 reg[31:0]random_r=32'h109823ab+DDR;
 reg read_pending=0,write_pending=0;reg[31:0]read_addr,write_addr;
 integer read_beat=0,write_beat=0;
 reg ar_stall=0,aw_stall=0,w_stall=0;
 reg[44:0]ar_hold,aw_hold;reg[288:0]w_hold;
 function automatic[255:0] payload(input[31:0]addr,input integer n,input bit wr);
 integer i;begin for(i=0;i<8;i=i+1)
 payload[32*i+:32]=(addr+n*32+i*4)^32'h7aca5106^(wr?32'hfefe1212:0);
 end endfunction
 function automatic affinity(input[31:0]addr);
 affinity=DDR==0?addr[23:16]==1:(addr[23:16]==2||addr[23:16]==3);
 endfunction
 assign arready=!block_ar&&!read_pending&&!rvalid&&(random_r[2]||random_r[5]);
 assign awready=!write_pending&&!bvalid&&(random_r[6]||random_r[9]);
 assign wready=write_pending&&(random_r[10]||random_r[12]);
 assign rresp=0;assign bresp=0;
 always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin read_pending<=0;write_pending<=0;rvalid<=0;rlast<=0;bvalid<=0;
 read_commands<=0;write_commands<=0;checked_write_beats<=0;stalls<=0;
 ar_stall<=0;aw_stall<=0;w_stall<=0;random_r<=32'h109823ab+DDR;end
 else begin
 random_r<={random_r[30:0],random_r[31]^random_r[21]^random_r[1]^random_r[0]};
 if(ar_stall&&(!arvalid||{araddr,arlen,arsize,arburst}!==ar_hold))$fatal(1,"DDR%0d AR unstable",DDR);
 if(aw_stall&&(!awvalid||{awaddr,awlen,awsize,awburst}!==aw_hold))$fatal(1,"DDR%0d AW unstable",DDR);
 if(w_stall&&(!wvalid||{wlast,wstrb,wdata}!==w_hold))$fatal(1,"DDR%0d W unstable",DDR);
 ar_stall<=arvalid&&!arready;aw_stall<=awvalid&&!awready;w_stall<=wvalid&&!wready;
 ar_hold<={araddr,arlen,arsize,arburst};aw_hold<={awaddr,awlen,awsize,awburst};w_hold<={wlast,wstrb,wdata};
 if((arvalid&&!arready)||(awvalid&&!awready)||(wvalid&&!wready)||(rvalid&&!rready)||(bvalid&&!bready))stalls<=stalls+1;
 if(arvalid&&arready)begin
 if(!affinity(araddr)||arlen!==3||arsize!==5||arburst!==1)$fatal(1,"DDR%0d wrong physical read target/framing %h",DDR,araddr);
 read_addr<=araddr;read_beat<=0;read_pending<=1;read_commands<=read_commands+1;end
 if(read_pending&&!rvalid&&random_r[15])begin
 rvalid<=1;rdata<=payload(read_addr,0,0);rlast<=0;end
 else if(rvalid&&rready)begin
 if(rlast)begin rvalid<=0;read_pending<=0;end
 else begin read_beat<=read_beat+1;rdata<=payload(read_addr,read_beat+1,0);rlast<=read_beat==2;end end
 if(awvalid&&awready)begin
 if(!affinity(awaddr)||awlen!==3||awsize!==5||awburst!==1)$fatal(1,"DDR%0d wrong physical write target/framing",DDR);
 write_addr<=awaddr;write_pending<=1;write_beat<=0;write_commands<=write_commands+1;end
 if(wvalid&&wready)begin
 if(wdata!==payload(write_addr,write_beat,1)||wstrb!==32'hffffffff||wlast!==(write_beat==3))
 $fatal(1,"DDR%0d write data/strb/last mismatch",DDR);
 checked_write_beats<=checked_write_beats+1;
 if(wlast)begin write_pending<=0;bvalid<=1;end else write_beat<=write_beat+1;end
 if(bvalid&&bready)bvalid<=0;
 end end
endmodule

module hap_axi256_dedicated_data_router_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,clear=0;integer target=0,checks=0;
 reg block0=0;wire conflict_error;wire[1:0]active_client;
 wire c0_req;wire signed[31:0]completed0;
 wire c0_arvalid;
 wire c0_arready;
 wire [31:0]c0_araddr;
 wire [7:0]c0_arlen;
 wire [2:0]c0_arsize;
 wire [1:0]c0_arburst;
 wire c0_rvalid;
 wire c0_rready;
 wire [255:0]c0_rdata;
 wire [1:0]c0_rresp;
 wire c0_rlast;
 wire c0_awvalid;
 wire c0_awready;
 wire [31:0]c0_awaddr;
 wire [7:0]c0_awlen;
 wire [2:0]c0_awsize;
 wire [1:0]c0_awburst;
 wire c0_wvalid;
 wire c0_wready;
 wire [255:0]c0_wdata;
 wire [31:0]c0_wstrb;
 wire c0_wlast;
 wire c0_bvalid;
 wire c0_bready;
 wire [1:0]c0_bresp;
 wire c1_req;wire signed[31:0]completed1;
 wire c1_arvalid;
 wire c1_arready;
 wire [31:0]c1_araddr;
 wire [7:0]c1_arlen;
 wire [2:0]c1_arsize;
 wire [1:0]c1_arburst;
 wire c1_rvalid;
 wire c1_rready;
 wire [255:0]c1_rdata;
 wire [1:0]c1_rresp;
 wire c1_rlast;
 wire c1_awvalid;
 wire c1_awready;
 wire [31:0]c1_awaddr;
 wire [7:0]c1_awlen;
 wire [2:0]c1_awsize;
 wire [1:0]c1_awburst;
 wire c1_wvalid;
 wire c1_wready;
 wire [255:0]c1_wdata;
 wire [31:0]c1_wstrb;
 wire c1_wlast;
 wire c1_bvalid;
 wire c1_bready;
 wire [1:0]c1_bresp;
 wire c2_req;wire signed[31:0]completed2;
 wire c2_arvalid;
 wire c2_arready;
 wire [31:0]c2_araddr;
 wire [7:0]c2_arlen;
 wire [2:0]c2_arsize;
 wire [1:0]c2_arburst;
 wire c2_rvalid;
 wire c2_rready;
 wire [255:0]c2_rdata;
 wire [1:0]c2_rresp;
 wire c2_rlast;
 wire c2_awvalid;
 wire c2_awready;
 wire [31:0]c2_awaddr;
 wire [7:0]c2_awlen;
 wire [2:0]c2_awsize;
 wire [1:0]c2_awburst;
 wire c2_wvalid;
 wire c2_wready;
 wire [255:0]c2_wdata;
 wire [31:0]c2_wstrb;
 wire c2_wlast;
 wire c2_bvalid;
 wire c2_bready;
 wire [1:0]c2_bresp;
 wire data_axi_arvalid;
 wire data_axi_arready;
 wire [31:0]data_axi_araddr;
 wire [7:0]data_axi_arlen;
 wire [2:0]data_axi_arsize;
 wire [1:0]data_axi_arburst;
 wire data_axi_rvalid;
 wire data_axi_rready;
 wire [255:0]data_axi_rdata;
 wire [1:0]data_axi_rresp;
 wire data_axi_rlast;
 wire data_axi_awvalid;
 wire data_axi_awready;
 wire [31:0]data_axi_awaddr;
 wire [7:0]data_axi_awlen;
 wire [2:0]data_axi_awsize;
 wire [1:0]data_axi_awburst;
 wire data_axi_wvalid;
 wire data_axi_wready;
 wire [255:0]data_axi_wdata;
 wire [31:0]data_axi_wstrb;
 wire data_axi_wlast;
 wire data_axi_bvalid;
 wire data_axi_bready;
 wire [1:0]data_axi_bresp;
 wire mlp_data_axi_arvalid;
 wire mlp_data_axi_arready;
 wire [31:0]mlp_data_axi_araddr;
 wire [7:0]mlp_data_axi_arlen;
 wire [2:0]mlp_data_axi_arsize;
 wire [1:0]mlp_data_axi_arburst;
 wire mlp_data_axi_rvalid;
 wire mlp_data_axi_rready;
 wire [255:0]mlp_data_axi_rdata;
 wire [1:0]mlp_data_axi_rresp;
 wire mlp_data_axi_rlast;
 wire mlp_data_axi_awvalid;
 wire mlp_data_axi_awready;
 wire [31:0]mlp_data_axi_awaddr;
 wire [7:0]mlp_data_axi_awlen;
 wire [2:0]mlp_data_axi_awsize;
 wire [1:0]mlp_data_axi_awburst;
 wire mlp_data_axi_wvalid;
 wire mlp_data_axi_wready;
 wire [255:0]mlp_data_axi_wdata;
 wire [31:0]mlp_data_axi_wstrb;
 wire mlp_data_axi_wlast;
 wire mlp_data_axi_bvalid;
 wire mlp_data_axi_bready;
 wire [1:0]mlp_data_axi_bresp;
 hap_axi256_dedicated_data_router dut(.*);
 hap_m002_data_client_bfm #(.CLIENT(0)) client0(.clk(clk),.rst_n(rst_n),.target(target),.req(c0_req),.completed(completed0),
 .arvalid(c0_arvalid),
 .arready(c0_arready),
 .araddr(c0_araddr),
 .arlen(c0_arlen),
 .arsize(c0_arsize),
 .arburst(c0_arburst),
 .rvalid(c0_rvalid),
 .rready(c0_rready),
 .rdata(c0_rdata),
 .rresp(c0_rresp),
 .rlast(c0_rlast),
 .awvalid(c0_awvalid),
 .awready(c0_awready),
 .awaddr(c0_awaddr),
 .awlen(c0_awlen),
 .awsize(c0_awsize),
 .awburst(c0_awburst),
 .wvalid(c0_wvalid),
 .wready(c0_wready),
 .wdata(c0_wdata),
 .wstrb(c0_wstrb),
 .wlast(c0_wlast),
 .bvalid(c0_bvalid),
 .bready(c0_bready),
 .bresp(c0_bresp));
 hap_m002_data_client_bfm #(.CLIENT(1)) client1(.clk(clk),.rst_n(rst_n),.target(target),.req(c1_req),.completed(completed1),
 .arvalid(c1_arvalid),
 .arready(c1_arready),
 .araddr(c1_araddr),
 .arlen(c1_arlen),
 .arsize(c1_arsize),
 .arburst(c1_arburst),
 .rvalid(c1_rvalid),
 .rready(c1_rready),
 .rdata(c1_rdata),
 .rresp(c1_rresp),
 .rlast(c1_rlast),
 .awvalid(c1_awvalid),
 .awready(c1_awready),
 .awaddr(c1_awaddr),
 .awlen(c1_awlen),
 .awsize(c1_awsize),
 .awburst(c1_awburst),
 .wvalid(c1_wvalid),
 .wready(c1_wready),
 .wdata(c1_wdata),
 .wstrb(c1_wstrb),
 .wlast(c1_wlast),
 .bvalid(c1_bvalid),
 .bready(c1_bready),
 .bresp(c1_bresp));
 hap_m002_data_client_bfm #(.CLIENT(2)) client2(.clk(clk),.rst_n(rst_n),.target(target),.req(c2_req),.completed(completed2),
 .arvalid(c2_arvalid),
 .arready(c2_arready),
 .araddr(c2_araddr),
 .arlen(c2_arlen),
 .arsize(c2_arsize),
 .arburst(c2_arburst),
 .rvalid(c2_rvalid),
 .rready(c2_rready),
 .rdata(c2_rdata),
 .rresp(c2_rresp),
 .rlast(c2_rlast),
 .awvalid(c2_awvalid),
 .awready(c2_awready),
 .awaddr(c2_awaddr),
 .awlen(c2_awlen),
 .awsize(c2_awsize),
 .awburst(c2_awburst),
 .wvalid(c2_wvalid),
 .wready(c2_wready),
 .wdata(c2_wdata),
 .wstrb(c2_wstrb),
 .wlast(c2_wlast),
 .bvalid(c2_bvalid),
 .bready(c2_bready),
 .bresp(c2_bresp));
 wire signed[31:0]reads0,writes0,beats0,stalls0;
 hap_m002_data_memory_bfm #(.DDR(0)) mem0(.clk(clk),.rst_n(rst_n),.block_ar(block0),.read_commands(reads0),.write_commands(writes0),.checked_write_beats(beats0),.stalls(stalls0),
 .arvalid(data_axi_arvalid),
 .arready(data_axi_arready),
 .araddr(data_axi_araddr),
 .arlen(data_axi_arlen),
 .arsize(data_axi_arsize),
 .arburst(data_axi_arburst),
 .rvalid(data_axi_rvalid),
 .rready(data_axi_rready),
 .rdata(data_axi_rdata),
 .rresp(data_axi_rresp),
 .rlast(data_axi_rlast),
 .awvalid(data_axi_awvalid),
 .awready(data_axi_awready),
 .awaddr(data_axi_awaddr),
 .awlen(data_axi_awlen),
 .awsize(data_axi_awsize),
 .awburst(data_axi_awburst),
 .wvalid(data_axi_wvalid),
 .wready(data_axi_wready),
 .wdata(data_axi_wdata),
 .wstrb(data_axi_wstrb),
 .wlast(data_axi_wlast),
 .bvalid(data_axi_bvalid),
 .bready(data_axi_bready),
 .bresp(data_axi_bresp));
 wire signed[31:0]reads1,writes1,beats1,stalls1;
 hap_m002_data_memory_bfm #(.DDR(1)) mem1(.clk(clk),.rst_n(rst_n),.block_ar(1'b0),.read_commands(reads1),.write_commands(writes1),.checked_write_beats(beats1),.stalls(stalls1),
 .arvalid(mlp_data_axi_arvalid),
 .arready(mlp_data_axi_arready),
 .araddr(mlp_data_axi_araddr),
 .arlen(mlp_data_axi_arlen),
 .arsize(mlp_data_axi_arsize),
 .arburst(mlp_data_axi_arburst),
 .rvalid(mlp_data_axi_rvalid),
 .rready(mlp_data_axi_rready),
 .rdata(mlp_data_axi_rdata),
 .rresp(mlp_data_axi_rresp),
 .rlast(mlp_data_axi_rlast),
 .awvalid(mlp_data_axi_awvalid),
 .awready(mlp_data_axi_awready),
 .awaddr(mlp_data_axi_awaddr),
 .awlen(mlp_data_axi_awlen),
 .awsize(mlp_data_axi_awsize),
 .awburst(mlp_data_axi_awburst),
 .wvalid(mlp_data_axi_wvalid),
 .wready(mlp_data_axi_wready),
 .wdata(mlp_data_axi_wdata),
 .wstrb(mlp_data_axi_wstrb),
 .wlast(mlp_data_axi_wlast),
 .bvalid(mlp_data_axi_bvalid),
 .bready(mlp_data_axi_bready),
 .bresp(mlp_data_axi_bresp));
 task automatic check(input condition,input string message);
 begin checks=checks+1;if(condition!==1'b1)$fatal(1,"%s",message);end endtask
 task automatic wait_done;
 integer t;begin t=0;
 while((completed0!=target||completed1!=target||completed2!=target||active_client!=0)&&t<20000)begin @(negedge clk);t=t+1;end
 check(t<20000,"data DMA routing timeout");check(!conflict_error,"data router protocol error");end endtask
 integer t;
 initial begin
 repeat(8)@(negedge clk);rst_n=1;block0=1;target=12;
 t=0;while((completed1!=target||completed2!=target)&&t<15000)begin @(negedge clk);t=t+1;end
 check(t<15000&&completed0==0,"MLP tensor/meta did not progress with DDR0 blocked");
 block0=0;wait_done();
 check(reads0==12&&writes0==12&&reads1==24&&writes1==24,"physical read/write command counts");
 check(beats0==48&&beats1==96,"write byte/beat completeness");
 check(stalls0>0&&stalls1>0,"data backpressure not covered");
 $display("COVERAGE data reads=%0d/%0d writes=%0d/%0d bytes=%0d/%0d stalls=%0d/%0d",reads0,reads1,writes0,writes1,beats0*32,beats1*32,stalls0,stalls1);
 clear=1;@(negedge clk);clear=0;target=16;wait_done();
 target=0;rst_n=0;repeat(8)@(negedge clk);rst_n=1;target=4;wait_done();
 check(reads0==4&&reads1==8&&writes0==4&&writes1==8,"post-reset data routing restart");
 $display("PASS hap_axi256_dedicated_data_router checks=%0d",checks);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
 initial begin #2000000;$fatal(1,"data router global timeout");end
endmodule
