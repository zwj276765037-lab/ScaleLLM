`timescale 1ns / 1ps
module hap_m002_weight_memory_bfm #(parameter integer ENGINE=0)(
 input wire clk,input wire rst_n,input wire arvalid,output wire arready,
 input wire[31:0]araddr,input wire[7:0]arlen,input wire[2:0]arsize,input wire[1:0]arburst,
 output reg rvalid=0,input wire rready,output reg[511:0]rdata=0,
 output wire[1:0]rresp,output reg rlast=0,
 output integer physical_bursts=0,output integer physical_beats=0,output integer r_stalls=0);
 integer qrd=0,beat=0;reg[31:0]qaddr[0:255];
 reg[31:0]random_r=32'h7261ca13+ENGINE;
 localparam integer BURSTS=ENGINE==0?16:8;
 function automatic[511:0]payload(input[31:0]addr,input integer n);
 integer w;begin for(w=0;w<16;w=w+1)
 payload[w*32+:32]=(addr+n*64+w*4)^32'h5ac31f07^(w*32'h01010101);end endfunction
 assign arready=random_r[3]||random_r[7];assign rresp=0;
 always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin qrd<=0;beat<=0;rvalid<=0;rlast<=0;
 physical_bursts<=0;physical_beats<=0;r_stalls<=0;random_r<=32'h7261ca13+ENGINE;end
 else begin
 random_r<={random_r[30:0],random_r[31]^random_r[21]^random_r[1]^random_r[0]};
 if(arvalid&&arready)begin
 if(arlen!==15||arsize!==6||arburst!==1||
 araddr!==(32'h00100000+ENGINE*32'h04000000+(physical_bursts%2)*32'h01000000+(physical_bursts/2)*1024))
 $fatal(1,"native frontend DDR%0d physical AR target/order mismatch count%0d addr%h",ENGINE,physical_bursts,araddr);
 qaddr[physical_bursts]<=araddr;physical_bursts<=physical_bursts+1;end
 if(rvalid&&!rready)r_stalls<=r_stalls+1;
 if(!rvalid&&qrd<physical_bursts&&random_r[11])begin
 rvalid<=1;beat<=0;rdata<=payload(qaddr[qrd],0);rlast<=0;end
 else if(rvalid&&rready)begin
 physical_beats<=physical_beats+1;
 if(rlast)begin rvalid<=0;qrd<=qrd+1;end
 else begin beat<=beat+1;rdata<=payload(qaddr[qrd],beat+1);rlast<=beat==14;end end
 end end
endmodule

module hap_m002_dedicated_frontends_tb;
 reg core_clk=0,ddr0_clk=0,ddr1_clk=0;
 always #5 core_clk=~core_clk;
 always #2.5 ddr0_clk=~ddr0_clk;
 initial begin #0.625;forever #2.5 ddr1_clk=~ddr1_clk;end
 reg core_rst_n=0,ddr0_rst_n=0,ddr1_rst_n=0;
 reg core_clear=0;wire core_enable=1,ddr0_enable=1,ddr1_enable=1;
 wire maintenance_pause_sources,maintenance_drain_active,maintenance_soft_clear_pulse;
 wire core_quiescent,error;wire[31:0]accepted_attn_bursts,accepted_mlp_bursts,both_eligible_cycles;
 wire[31:0]p0_hol_cycles,p1_hol_cycles,p0_tag_high_watermark,p1_tag_high_watermark;
 reg[1:0]command_valid=0;wire[1:0]command_ready,busy,frontend_error;
 reg block_output=1;reg[31:0]random_r=32'hfe123bc7;
 wire[1:0]out_valid,out_ready,meta_ready;
 wire[1:0]meta_valid={random_r[9]||random_r[10],random_r[12]||random_r[15]};
 integer metadata_a=0,metadata_m=0,groups_a=0,groups_m=0,checks=0,soft_count=0;
 wire[4095:0]weights_a;wire[2047:0]weights_m;
 wire[255:0]meta_a;wire[223:0]meta_m;wire[9:0]tile_a;wire[6:0]group_a;
 wire[31:0]a_meta_word=32'h71380000+metadata_a,m_meta_word=32'h71390000+metadata_m;
 wire mlp_done;wire[31:0]mbeats0,mbeats1,mbursts0,mbursts1,m_useful_groups;
 wire[63:0]m_physical_bytes,m_useful_bytes;
 assign out_ready[0]=!block_output&&(random_r[2]||random_r[4]);
 assign out_ready[1]=!block_output&&(random_r[6]||random_r[8]);
 wire a0_arvalid;
 wire a0_arready;
 wire [31:0]a0_araddr;
 wire [7:0]a0_arlen;
 wire [2:0]a0_arsize;
 wire [1:0]a0_arburst;
 wire a0_rvalid;
 wire a0_rready;
 wire [511:0]a0_rdata;
 wire [1:0]a0_rresp;
 wire a0_rlast;
 wire a1_arvalid;
 wire a1_arready;
 wire [31:0]a1_araddr;
 wire [7:0]a1_arlen;
 wire [2:0]a1_arsize;
 wire [1:0]a1_arburst;
 wire a1_rvalid;
 wire a1_rready;
 wire [511:0]a1_rdata;
 wire [1:0]a1_rresp;
 wire a1_rlast;
 wire m0_arvalid;
 wire m0_arready;
 wire [31:0]m0_araddr;
 wire [7:0]m0_arlen;
 wire [2:0]m0_arsize;
 wire [1:0]m0_arburst;
 wire m0_rvalid;
 wire m0_rready;
 wire [511:0]m0_rdata;
 wire [1:0]m0_rresp;
 wire m0_rlast;
 wire m1_arvalid;
 wire m1_arready;
 wire [31:0]m1_araddr;
 wire [7:0]m1_arlen;
 wire [2:0]m1_arsize;
 wire [1:0]m1_arburst;
 wire m1_rvalid;
 wire m1_rready;
 wire [511:0]m1_rdata;
 wire [1:0]m1_rresp;
 wire m1_rlast;
 wire p0_arvalid;
 wire p0_arready;
 wire [31:0]p0_araddr;
 wire [7:0]p0_arlen;
 wire [2:0]p0_arsize;
 wire [1:0]p0_arburst;
 wire p0_rvalid;
 wire p0_rready;
 wire [511:0]p0_rdata;
 wire [1:0]p0_rresp;
 wire p0_rlast;
 wire p1_arvalid;
 wire p1_arready;
 wire [31:0]p1_araddr;
 wire [7:0]p1_arlen;
 wire [2:0]p1_arsize;
 wire [1:0]p1_arburst;
 wire p1_rvalid;
 wire p1_rready;
 wire [511:0]p1_rdata;
 wire [1:0]p1_rresp;
 wire p1_rlast;
 hap_axi512_dual_engine_dedicated_read dut(
 .attn_source_quiescent(!busy[0]&&!command_valid[0]),
 .mlp_source_quiescent(!busy[1]&&!command_valid[1]),.*);
 hap_dual_ddr_weight_frontend attention(
 .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(maintenance_soft_clear_pulse),
 .command_valid(command_valid[0]),.command_ready(command_ready[0]),
 .ddr0_base_addr(32'h00100000),.ddr1_base_addr(32'h01100000),.group_count(17'd64),
 .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),.ddr1_clk(ddr0_clk),.ddr1_rst_n(ddr0_rst_n),
 .ddr0_axi_arvalid(a0_arvalid),
 .ddr0_axi_arready(a0_arready),
 .ddr0_axi_araddr(a0_araddr),
 .ddr0_axi_arlen(a0_arlen),
 .ddr0_axi_arsize(a0_arsize),
 .ddr0_axi_arburst(a0_arburst),
 .ddr0_axi_rvalid(a0_rvalid),
 .ddr0_axi_rready(a0_rready),
 .ddr0_axi_rdata(a0_rdata),
 .ddr0_axi_rresp(a0_rresp),
 .ddr0_axi_rlast(a0_rlast),
 .ddr1_axi_arvalid(a1_arvalid),
 .ddr1_axi_arready(a1_arready),
 .ddr1_axi_araddr(a1_araddr),
 .ddr1_axi_arlen(a1_arlen),
 .ddr1_axi_arsize(a1_arsize),
 .ddr1_axi_arburst(a1_arburst),
 .ddr1_axi_rvalid(a1_rvalid),
 .ddr1_axi_rready(a1_rready),
 .ddr1_axi_rdata(a1_rdata),
 .ddr1_axi_rresp(a1_rresp),
 .ddr1_axi_rlast(a1_rlast),
 .meta_valid(meta_valid[0]),.meta_ready(meta_ready[0]),
 .meta_tile(10'(metadata_a/128)),.meta_group(7'(metadata_a%128)),.meta16({8{a_meta_word}}),
 .out_valid(out_valid[0]),.out_ready(out_ready[0]),.out_tile(tile_a),.out_group(group_a),
 .out_weight_s8(weights_a),.out_meta16(meta_a),.busy(busy[0]),.error(frontend_error[0]));
 hap_mlp_w4_dual_ddr_frontend mlp(
 .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(maintenance_soft_clear_pulse),
 .command_valid(command_valid[1]),.command_ready(command_ready[1]),
 .ddr0_base_addr(32'h04100000),.ddr1_base_addr(32'h05100000),.group_count(20'd64),
 .ddr0_clk(ddr1_clk),.ddr0_rst_n(ddr1_rst_n),.ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),
 .ddr0_axi_arvalid(m0_arvalid),
 .ddr0_axi_arready(m0_arready),
 .ddr0_axi_araddr(m0_araddr),
 .ddr0_axi_arlen(m0_arlen),
 .ddr0_axi_arsize(m0_arsize),
 .ddr0_axi_arburst(m0_arburst),
 .ddr0_axi_rvalid(m0_rvalid),
 .ddr0_axi_rready(m0_rready),
 .ddr0_axi_rdata(m0_rdata),
 .ddr0_axi_rresp(m0_rresp),
 .ddr0_axi_rlast(m0_rlast),
 .ddr1_axi_arvalid(m1_arvalid),
 .ddr1_axi_arready(m1_arready),
 .ddr1_axi_araddr(m1_araddr),
 .ddr1_axi_arlen(m1_arlen),
 .ddr1_axi_arsize(m1_arsize),
 .ddr1_axi_arburst(m1_arburst),
 .ddr1_axi_rvalid(m1_rvalid),
 .ddr1_axi_rready(m1_rready),
 .ddr1_axi_rdata(m1_rdata),
 .ddr1_axi_rresp(m1_rresp),
 .ddr1_axi_rlast(m1_rlast),
 .meta_valid(meta_valid[1]),.meta_ready(meta_ready[1]),.meta_u224({7{m_meta_word}}),
 .out_valid(out_valid[1]),.out_ready(out_ready[1]),.weights_s4x16x32(weights_m),
 .weight_meta_u224(meta_m),.busy(busy[1]),.done(mlp_done),.error(frontend_error[1]),
 .ddr0_raw_beat_snapshot(mbeats0),.ddr1_raw_beat_snapshot(mbeats1),
 .ddr0_burst_snapshot(mbursts0),.ddr1_burst_snapshot(mbursts1),
 .physical_read_byte_count(m_physical_bytes),.useful_weight_byte_count(m_useful_bytes),.useful_group_count(m_useful_groups));
 wire signed[31:0]physical0,beats0,stalls0;
 hap_m002_weight_memory_bfm #(.ENGINE(0)) memory0(.clk(ddr0_clk),.rst_n(core_rst_n&&ddr0_rst_n&&ddr1_rst_n),
 .arvalid(p0_arvalid),
 .arready(p0_arready),
 .araddr(p0_araddr),
 .arlen(p0_arlen),
 .arsize(p0_arsize),
 .arburst(p0_arburst),
 .rvalid(p0_rvalid),
 .rready(p0_rready),
 .rdata(p0_rdata),
 .rresp(p0_rresp),
 .rlast(p0_rlast),
 .physical_bursts(physical0),.physical_beats(beats0),.r_stalls(stalls0));
 wire signed[31:0]physical1,beats1,stalls1;
 hap_m002_weight_memory_bfm #(.ENGINE(1)) memory1(.clk(ddr1_clk),.rst_n(core_rst_n&&ddr0_rst_n&&ddr1_rst_n),
 .arvalid(p1_arvalid),
 .arready(p1_arready),
 .araddr(p1_araddr),
 .arlen(p1_arlen),
 .arsize(p1_arsize),
 .arburst(p1_arburst),
 .rvalid(p1_rvalid),
 .rready(p1_rready),
 .rdata(p1_rdata),
 .rresp(p1_rresp),
 .rlast(p1_rlast),
 .physical_bursts(physical1),.physical_beats(beats1),.r_stalls(stalls1));
 function automatic[511:0]reference_beat(input integer engine,input integer stream,input integer n);
 integer w;reg[31:0]addr;begin addr=32'h00100000+engine*32'h04000000+stream*32'h01000000+n*64;
 for(w=0;w<16;w=w+1)reference_beat[w*32+:32]=(addr+w*4)^32'h5ac31f07^(w*32'h01010101);end endfunction
 reg[4095:0]expected_a;reg[2047:0]expected_m;
 always_comb begin
 for(integer stream=0;stream<2;stream=stream+1)begin
 for(integer b=0;b<4;b=b+1)expected_a[stream*2048+b*512+:512]=reference_beat(0,stream,groups_a*4+b);
 for(integer b=0;b<2;b=b+1)expected_m[stream*1024+b*512+:512]=reference_beat(1,stream,groups_m*2+b);
 end end
 always @(posedge core_clk or negedge core_rst_n)begin
 if(!core_rst_n)begin metadata_a<=0;metadata_m<=0;groups_a<=0;groups_m<=0;random_r<=32'hfe123bc7;end
 else begin
 random_r<={random_r[30:0],random_r[31]^random_r[21]^random_r[1]^random_r[0]};
 if(error||frontend_error!=0)$fatal(1,"native frontend/adapter error");
 if(meta_valid[0]&&meta_ready[0])metadata_a<=metadata_a+1;
 if(meta_valid[1]&&meta_ready[1])metadata_m<=metadata_m+1;
 if(out_valid[0]&&out_ready[0])begin
 if($isunknown(expected_a))$fatal(1,"uninitialized Attention independent oracle");
 if(weights_a!==expected_a||meta_a!=={8{32'h71380000+groups_a}}||tile_a!==10'(groups_a/128)||group_a!==7'(groups_a%128))
 $fatal(1,"native Attention full-group/meta/identity mismatch %0d",groups_a);
 groups_a<=groups_a+1;end
 if(out_valid[1]&&out_ready[1])begin
 if($isunknown(expected_m))$fatal(1,"uninitialized MLP independent oracle");
 if(weights_m!==expected_m||meta_m!=={7{32'h71390000+groups_m}})begin
 $display("MLP_DIAGNOSTIC group=%0d data_equal=%b expected_unknown=%b got=%h expected=%h meta=%h expected_meta=%h metadata_sent=%0d",groups_m,weights_m===expected_m,$isunknown(expected_m),weights_m,expected_m,meta_m,{7{32'h71390000+groups_m}},metadata_m);
 $fatal(1,"native MLP full-group/meta mismatch %0d",groups_m);end
 groups_m<=groups_m+1;end
 if(maintenance_soft_clear_pulse)begin
 if(groups_a!=64||groups_m!=64||busy!=0)$fatal(1,"native maintenance cleared before frontend command drain");
 soft_count<=soft_count+1;end
 end end
 task automatic check(input condition,input string message);
 begin checks=checks+1;if(condition!==1'b1)$fatal(1,"%s",message);end endtask
 task automatic start_commands;
 begin
 wait(command_ready==3);@(negedge core_clk);command_valid=3;
 @(posedge core_clk);check(command_ready==3,"native command handshake");
 @(negedge core_clk);command_valid=0;
 end endtask
 integer t;
 initial begin
 repeat(10)@(negedge core_clk);core_rst_n=1;ddr0_rst_n=1;ddr1_rst_n=1;
 repeat(60)@(negedge core_clk);start_commands();
 repeat(100)@(negedge core_clk);core_clear=1;
 @(negedge core_clk);core_clear=0;
 repeat(200)@(negedge core_clk);
 check(groups_a==0&&groups_m==0,"output-block test did not hold groups");
 check(stalls0>0&&stalls1>0,"native finite halfgroup FIFO backpressure missing");
 block_output=0;t=0;
 while(soft_count==0&&t<20000)begin @(negedge core_clk);t=t+1;end
 check(t<20000&&soft_count==1,"native frontend maintenance drain timeout");
 check(physical0==32&&physical1==16&&beats0==512&&beats1==256,"native complete physical burst/beat counts");
 check(groups_a==64&&groups_m==64,"native complete logical group counts");
 $display("COVERAGE native frontend groups=%0d/%0d physical bursts=%0d/%0d bytes=%0d/%0d FIFO_R_stalls=%0d/%0d",groups_a,groups_m,physical0,physical1,beats0*64,beats1*64,stalls0,stalls1);
 repeat(80)@(negedge core_clk);check(core_quiescent&&!error,"native post-maintenance quiescent");
 $display("PASS hap_m002_dedicated_frontends checks=%0d",checks);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
 initial begin #2000000;$fatal(1,"native frontend global timeout");end
endmodule
