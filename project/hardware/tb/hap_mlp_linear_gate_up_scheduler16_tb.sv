`timescale 1ns/1ps
`ifndef TEST_COLUMNS
`define TEST_COLUMNS 128
`endif
module hap_mlp_linear_gate_up_scheduler16_tb;
 localparam integer COLS=`TEST_COLUMNS,GROUPS=128,RECORDS=2*(COLS/16),TX=2*((COLS+11)/12)*GROUPS;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,clear=0,command_valid=0;
 wire command_ready,cache_rd_req_valid,cache_rd_req_bank,cache_rd_rsp_ready;
 wire [6:0] cache_rd_req_group;
 reg rsp_valid=0;reg [6:0] rsp_group=0;reg [4095:0] rsp_data;reg [383:0] rsp_meta;
 wire req_ready=!rsp_valid;
 integer sent=0,computes=0,received=0,cycles=0;
 wire weight_valid=sent<RECORDS*GROUPS;
 wire weight_ready;
 reg [2047:0] weights;reg [223:0] weight_meta;
 wire compute_valid,compute_ready,compute_first,compute_last;
 wire [4607:0] activation;wire [1535:0] compute_weight;
 wire [127:0] acode;wire [95:0] ashift,wcode;wire [71:0] wshift;wire [11:0] mask;
 reg proj_valid=0;wire proj_ready;reg [4607:0] proj_data;
 wire out_valid,out_matrix,out_last,busy,done,error,quiescent,format_error;
 wire [6143:0] out_data;wire [9:0] out_tile;
 wire out_ready=cycles%31>14;
 wire [31:0] source_count,cache_count,compute_count,internal_count,external_count,saturation;
 assign compute_ready=!proj_valid;
 function integer wv(input integer col,m,g,k);wv=(col*3+m*5+g*7+k)%16-8;endfunction
 function integer pv(input integer col,m,r);pv=m*100000+r*1000+col;endfunction
 always @*begin
 weights=0;weight_meta=0;
 for(integer c=0;c<16;c=c+1)begin
 weight_meta[c*14+:14]={6'd10,8'd1};
 for(integer k=0;k<32;k=k+1)weights[(c*32+k)*4+:4]=wv((sent/(2*GROUPS))*16+c,(sent/GROUPS)%2,sent%GROUPS,k);
 end
 end
 hap_mlp_linear_gate_up_scheduler16_s24 #(.INTERMEDIATE_COLUMNS(COLS),.GROUPS(GROUPS),.ENFORCE_PRODUCTION_SHAPE(0)) dut(
 .clk(clk),.rst_n(rst_n),.clear(clear),.command_valid(command_valid),.command_ready(command_ready),.activation_bank(1'b0),.activation_bank_ready(1'b1),
 .cache_rd_req_valid(cache_rd_req_valid),.cache_rd_req_ready(req_ready),.cache_rd_req_bank(cache_rd_req_bank),.cache_rd_req_group(cache_rd_req_group),
 .cache_rd_rsp_valid(rsp_valid),.cache_rd_rsp_ready(cache_rd_rsp_ready),.cache_rd_rsp_bank(1'b0),.cache_rd_rsp_group(rsp_group),.cache_rd_rsp_u8x16x32(rsp_data),.cache_rd_rsp_meta_u24x16(rsp_meta),
 .weight_valid(weight_valid),.weight_ready(weight_ready),.weights_s4x16x32(weights),.weight_meta_u224(weight_meta),
 .compute_valid(compute_valid),.compute_ready(compute_ready),.compute_first(compute_first),.compute_last(compute_last),.compute_activation_s9x16x32(activation),.compute_weights_s4x12x32(compute_weight),.compute_activation_code_u8x16(acode),.compute_activation_shift_u6x16(ashift),.compute_weight_code_u8x12(wcode),.compute_weight_shift_u6x12(wshift),.compute_column_valid_u12(mask),
 .projection_valid(proj_valid),.projection_ready(proj_ready),.projection_s24x16x12(proj_data),
 .out_valid(out_valid),.out_ready(out_ready),.out_s24x16x16(out_data),.out_tile(out_tile),.out_matrix(out_matrix),.out_last(out_last),.quiescent(quiescent),.busy(busy),.done(done),.error(error),
 .source_transaction_count(source_count),.cache_request_count(cache_count),.compute_transaction_count(compute_count),.internal_projection_pass_count(internal_count),.external_projection_record_count(external_count),.saturation_count(saturation),.format_error(format_error));
 always @(posedge clk)begin : model
 integer block_id,pass_id,matrix_id,group_id,col;
 cycles<=cycles+1;
 if(rst_n&&!clear)begin
 if(weight_valid&&weight_ready)sent<=sent+1;
 if(rsp_valid&&cache_rd_rsp_ready)rsp_valid<=0;
 if(cache_rd_req_valid&&req_ready)begin
 rsp_valid<=1;rsp_group<=cache_rd_req_group;
 if(cache_rd_req_bank)$fatal(1,"bank not zero");
 for(integer r=0;r<16;r=r+1)begin
 rsp_meta[r*24+:24]<={2'b0,6'd10,8'd1,8'd128};
 for(integer k=0;k<32;k=k+1)rsp_data[r*256+k*8+:8]<=128+((cache_rd_req_group+r+k)%31)-15;
 end
 end
 if(proj_valid&&proj_ready)proj_valid<=0;
 if(compute_valid&&compute_ready)begin
 block_id=computes/(8*GROUPS);pass_id=(computes%(8*GROUPS))/(2*GROUPS);matrix_id=(computes/GROUPS)%2;group_id=computes%GROUPS;
 if(compute_first!=(group_id==0)||compute_last!=(group_id==GROUPS-1))$fatal(1,"first last");
 for(integer c=0;c<12;c=c+1)begin
 col=block_id*48+pass_id*12+c;
 if(mask[c]!=(col<COLS))$fatal(1,"mask");
 if(col<COLS)for(integer k=0;k<32;k=k+1)if($signed(compute_weight[(c*32+k)*4+:4])!=wv(col,matrix_id,group_id,k))$fatal(1,"weight order col%0d",col);
 end
 for(integer r=0;r<16;r=r+1)for(integer k=0;k<32;k=k+1)if($signed(activation[(r*32+k)*9+:9])!=((group_id+r+k)%31)-15)$fatal(1,"cache activation");
 if(compute_last)begin
 proj_valid<=1;
 for(integer r=0;r<16;r=r+1)for(integer c=0;c<12;c=c+1)proj_data[(r*12+c)*24+:24]<=pv(block_id*48+pass_id*12+c,matrix_id,r);
 end
 computes<=computes+1;
 end
 if(out_valid&&out_ready)begin
 if(out_tile!=received/2||out_matrix!=received%2||out_last!=(received==RECORDS-1))$fatal(1,"output tag %0d %0d %0d",received,out_tile,out_matrix);
 for(integer r=0;r<16;r=r+1)for(integer c=0;c<16;c=c+1)if($signed(out_data[(r*16+c)*24+:24])!=pv((received/2)*16+c,received%2,r))$fatal(1,"output data %0d",received);
 received<=received+1;
 end
 if(error||format_error)$fatal(1,"scheduler sticky");
 end
 if(cycles>COLS*GROUPS*3+10000)$fatal(1,"watchdog");
 end
 initial begin
 repeat(3)@(negedge clk);rst_n=1;command_valid=1;
 @(posedge clk);@(negedge clk);command_valid=0;
 wait(done);@(negedge clk);
 if(!quiescent||received!=RECORDS||sent!=RECORDS*GROUPS||computes!=TX||source_count!=sent||cache_count!=computes||compute_count!=computes||external_count!=received)$fatal(1,"final counts");
 $display("GU columns=%0d source=%0d compute=%0d output=%0d cycles=%0d",COLS,sent,computes,received,cycles);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
