`timescale 1ns/1ps
module hap_mlp_gu_compute16_tb;
 wire flow_stall; // observation only
 localparam AXI_ADDR_W=32;
 reg [23:0] gu_gold[0:4095];
 reg  core_clk=0;
 reg  core_rst_n=0;
 reg  core_clear=0;
 reg  command_pause=0;
 wire  weight_source_quiescent;
 reg  command_valid=0;
 wire  command_ready;
 reg [1:0] command_opcode=0;
 reg  cache_sealed=0;
 reg [AXI_ADDR_W-1:0] gate_ddr0_base_addr=0;
 reg [AXI_ADDR_W-1:0] gate_ddr1_base_addr=0;
 wire  cache_rd_req_valid;
 reg  cache_rd_req_ready=0;
 wire  cache_rd_req_bank;
 wire [8:0] cache_rd_req_group;
 reg  cache_rd_rsp_valid=0;
 wire  cache_rd_rsp_ready;
 reg  cache_rd_rsp_bank=0;
 reg [8:0] cache_rd_rsp_group=0;
 reg [16*32*8-1:0] cache_rd_rsp_u8x16x32=0;
 reg [16*24-1:0] cache_rd_rsp_meta_u24x16=0;
 reg  gate_meta_valid=0;
 wire  gate_meta_ready;
 reg [223:0] gate_meta_u224=0;
 reg  ddr0_clk=0;
 reg  ddr0_rst_n=0;
 wire  ddr0_axi_arvalid;
 reg  ddr0_axi_arready=0;
 wire [AXI_ADDR_W-1:0] ddr0_axi_araddr;
 wire [7:0] ddr0_axi_arlen;
 wire [2:0] ddr0_axi_arsize;
 wire [1:0] ddr0_axi_arburst;
 reg  ddr0_axi_rvalid=0;
 wire  ddr0_axi_rready;
 reg [511:0] ddr0_axi_rdata=0;
 reg [1:0] ddr0_axi_rresp=0;
 reg  ddr0_axi_rlast=0;
 reg  ddr1_clk=0;
 reg  ddr1_rst_n=0;
 wire  ddr1_axi_arvalid;
 reg  ddr1_axi_arready=0;
 wire [AXI_ADDR_W-1:0] ddr1_axi_araddr;
 wire [7:0] ddr1_axi_arlen;
 wire [2:0] ddr1_axi_arsize;
 wire [1:0] ddr1_axi_arburst;
 reg  ddr1_axi_rvalid=0;
 wire  ddr1_axi_rready;
 reg [511:0] ddr1_axi_rdata=0;
 reg [1:0] ddr1_axi_rresp=0;
 reg  ddr1_axi_rlast=0;
 wire  gu_out_valid;
 reg  gu_out_ready=0;
 wire [6143:0] gu_out_s24x16x16;
 wire [9:0] gu_out_tile;
 wire  gu_out_matrix;
 wire  gu_out_last;
 wire  compute_quiescent;
 wire  busy;
 wire  done;
 wire  error;
 wire [2:0] phase;
 wire [31:0] gate_ddr0_raw_beats;
 wire [31:0] gate_ddr1_raw_beats;
 wire [31:0] gate_ddr0_elapsed_cycles;
 wire [31:0] gate_ddr1_elapsed_cycles;
 wire [31:0] gate_ddr0_bursts;
 wire [31:0] gate_ddr1_bursts;
 wire [31:0] gate_ddr0_ar_stalls;
 wire [31:0] gate_ddr1_ar_stalls;
 wire [31:0] gate_ddr0_r_backpressure;
 wire [31:0] gate_ddr1_r_backpressure;
 wire [31:0] gate_ddr0_response_idle;
 wire [31:0] gate_ddr1_response_idle;
 wire [31:0] gate_ddr0_max_outstanding;
 wire [31:0] gate_ddr1_max_outstanding;
 wire [63:0] gate_physical_bytes;
 wire [63:0] gate_useful_bytes;
 wire [31:0] gate_cache_request_count;
 wire [31:0] gate_weight_group_count;
 wire [31:0] gate_projection_tile_count;
 wire [31:0] saturation_count;
 wire [31:0] total_shift_format_count;
 wire [31:0] numeric_status;
 always #5 core_clk=~core_clk;
 always #2.5 ddr0_clk=~ddr0_clk;
 initial begin #1;forever #2.5 ddr1_clk=~ddr1_clk;end
 hap_mlp_gu_compute16_s44 #(.INTERMEDIATE_COLUMNS(128),.HIDDEN_COLUMNS(4096),.ENFORCE_PRODUCTION_SHAPE(0))dut(.*);
 integer test_opcode=1,cycles=0,outputs=0,meta_g=0,reqs=0,gate_fires=0;
 integer left0=0,left1=0;reg [31:0] addr0=0,addr1=0;
 function integer activation_value(input integer g,r,k);activation_value=(g*3+r*5+k*7)%31-15;endfunction
 function integer weight_value(input integer g,c,m,k);weight_value=(g*7+c*3+m*5+k*11)%16-8;endfunction
 function [511:0] memory_beat(input integer channel,input [31:0] address);
 integer base,raw,source,half_beat,tile,m,col,g,k;
 begin
 base=channel==0?0:32'h100000;
 raw=(address-base)/64;source=raw/2;half_beat=raw%2;
 tile=(source/128)/2;m=(source/128)%2;g=source%128;
 for(integer n=0;n<128;n=n+1)begin
 col=tile*16+channel*8+(half_beat*128+n)/32;
 k=(half_beat*128+n)%32;memory_beat[n*4+:4]=weight_value(g,col,m,k);
 end
 end endfunction
 always @(negedge ddr0_clk)begin
 ddr0_axi_arready=left0==0&&!ddr0_axi_rvalid;
 if(!ddr0_axi_rvalid&&left0>0)begin ddr0_axi_rvalid=1;ddr0_axi_rdata=memory_beat(0,addr0);ddr0_axi_rlast=left0==1;end
 end
 always @(posedge ddr0_clk)begin
 if(ddr0_axi_arvalid&&ddr0_axi_arready)begin left0=ddr0_axi_arlen+1;addr0=ddr0_axi_araddr;end
 if(ddr0_axi_rvalid&&ddr0_axi_rready)begin left0=left0-1;addr0=addr0+64;ddr0_axi_rvalid<=0;end
 end
 always @(negedge ddr1_clk)begin
 ddr1_axi_arready=left1==0&&!ddr1_axi_rvalid;
 if(!ddr1_axi_rvalid&&left1>0)begin ddr1_axi_rvalid=1;ddr1_axi_rdata=memory_beat(1,addr1);ddr1_axi_rlast=left1==1;end
 end
 always @(posedge ddr1_clk)begin
 if(ddr1_axi_arvalid&&ddr1_axi_arready)begin left1=ddr1_axi_arlen+1;addr1=ddr1_axi_araddr;end
 if(ddr1_axi_rvalid&&ddr1_axi_rready)begin left1=left1-1;addr1=addr1+64;ddr1_axi_rvalid<=0;end
 end
 always_comb begin
 for(integer c=0;c<16;c=c+1)begin
 gate_meta_u224[c*8+:8]=1+((meta_g/256)*16+c)%7;gate_meta_u224[128+c*6+:6]=10+((meta_g/256)*16+c)%2;
 end
 end
 always @(negedge core_clk)begin
 cache_rd_req_ready=!cache_rd_rsp_valid;
 gu_out_ready=cycles%53>21;
 end
 always @(posedge core_clk)begin
 cycles<=cycles+1;if(cycles>150000)$fatal(1,"watchdog");
 if(core_rst_n&&!core_clear)begin
 if(cache_rd_rsp_valid&&cache_rd_rsp_ready)cache_rd_rsp_valid<=0;
 if(cache_rd_req_valid&&cache_rd_req_ready)begin
 cache_rd_rsp_valid<=1;cache_rd_rsp_group<=cache_rd_req_group;reqs=reqs+1;
 if(cache_rd_req_bank||cache_rd_req_group>=128)$fatal(1,"cache request range");
 for(integer r=0;r<16;r=r+1)begin
 cache_rd_rsp_meta_u24x16[r*24+:24]<={2'b0,6'(10+r%2),8'(r+1),8'd128};
 for(integer k=0;k<32;k=k+1)cache_rd_rsp_u8x16x32[(r*32+k)*8+:8]<=128+activation_value(cache_rd_req_group,r,k);
 end
 end
 if(dut.gate_compute_valid&&dut.gate_compute_ready)begin
 if(gate_fires<128)begin
 for(integer k=0;k<32;k=k+1)begin
 if($signed(dut.gate_compute_activation[k*9+:9])!=activation_value(gate_fires,0,k))$fatal(1,"GU ingress activation g%0d k%0d actual%0d expected%0d",gate_fires,k,$signed(dut.gate_compute_activation[k*9+:9]),activation_value(gate_fires,0,k));
 if($signed(dut.gate_compute_weights[k*4+:4])!=weight_value(gate_fires,0,0,k))$fatal(1,"GU ingress weight g%0d k%0d actual%0d expected%0d",gate_fires,k,$signed(dut.gate_compute_weights[k*4+:4]),weight_value(gate_fires,0,0,k));
 end
 if(dut.gate_compute_acode[7:0]!=1||dut.gate_compute_ashift[5:0]!=10||dut.gate_compute_wcode[7:0]!=1||dut.gate_compute_wshift[5:0]!=10)$fatal(1,"GU ingress scale g%0d ac%0d as%0d wc%0d ws%0d",gate_fires,dut.gate_compute_acode[7:0],dut.gate_compute_ashift[5:0],dut.gate_compute_wcode[7:0],dut.gate_compute_wshift[5:0]);
 end
 gate_fires=gate_fires+1;
 end
 if(gate_meta_valid&&gate_meta_ready)meta_g=meta_g+1;
 if(gu_out_valid&&gu_out_ready)begin
 if(test_opcode!=1||gu_out_tile!=outputs/2||gu_out_matrix!=outputs%2||gu_out_last!=(outputs==15))$fatal(1,"GU output tag");
 for(integer r=0;r<16;r=r+1)for(integer c=0;c<16;c=c+1)
 if($signed(gu_out_s24x16x16[(r*16+c)*24+:24])!==$signed(gu_gold[(outputs%2)*2048+r*128+(outputs/2)*16+c]))$fatal(1,"GU value rec%0d row%0d col%0d actual%0d expected%0d",outputs,r,c,$signed(gu_out_s24x16x16[(r*16+c)*24+:24]),$signed(gu_gold[(outputs%2)*2048+r*128+(outputs/2)*16+c]));
 outputs=outputs+1;
 end
 if(error||numeric_status!=0)$fatal(1,"compute error numeric%h",numeric_status);
 end
 end
 initial begin
 $readmemh("data/mlp_linear_compute/gu128_gold.mem",gu_gold);
 core_clear=1;repeat(5)@(negedge core_clk);core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
 repeat(10)@(negedge core_clk);core_clear=0;cache_sealed=1;
 gate_ddr0_base_addr=0;gate_ddr1_base_addr=32'h100000;
 for(integer op=1;op<=1;op=op+1)begin
 test_opcode=op;command_opcode=op;outputs=0;meta_g=0;reqs=0;
 gate_meta_valid=1;
 @(negedge core_clk);command_valid=1;while(!command_ready)@(negedge core_clk);
 @(posedge core_clk);@(negedge core_clk);command_valid=0;command_opcode=0;
 gate_ddr0_base_addr=32'hbad00000;
 wait(done);@(negedge core_clk);
 if(!compute_quiescent||!weight_source_quiescent||outputs!=16||meta_g!=2048||reqs!=2816||gate_fires!=2816)
  $fatal(1,"GU compute final counts outputs%0d meta%0d req%0d MAC%0d",outputs,meta_g,reqs,gate_fires);
 if(!compute_quiescent||!weight_source_quiescent||outputs!=(op==1?16:4)||meta_g!=(op==1?2048:0)||meta_d!=(op==2?1792:0)||reqs!=(op==1?2816:448))$fatal(1,"compute final counts outputs%0d Gmeta%0d Dmeta%0d req%0d",outputs,meta_g,meta_d,reqs);
 core_clear=1;repeat(12)@(negedge core_clk);core_clear=0;
 end
 $display("GU-only true37 dual8x12 S44 N128 fullK128 all16row independent integer gold and async readers");
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
