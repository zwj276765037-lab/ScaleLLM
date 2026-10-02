`timescale 1ns / 1ps
module m4_tile_tb #(
    parameter integer CASE_ID=0,
    parameter integer BACKPRESSURE=1,
    parameter string DATA_DIR="data",
    parameter integer CLOCK_PERIOD_PS=6667,
    parameter integer USE_OOC_WRAPPER=0
);
    localparam N=128;
    reg clk=0,rst_n=0,clear=0,out_ready=0;
    integer cycle=0,sent=0,mismatch=0,wait_input=0,wait_output=0;
    integer check_lane;
    integer first_accept=-1,last_accept=-1,first_output=-1,prev_accept=-1;
    integer ii_min=999999,ii_max=0,interval,total_cycles;
    reg[2047:0]act_mem[0:N-1];reg[4095:0]wgt_mem[0:N-1];
    reg[63:0]zp_mem[0:N-1];reg[383:0]meta16_mem[0:N-1];
    reg[767:0]meta32_mem[0:N-1];reg[3071:0]expected[0:0];
    wire in_valid=rst_n&&(sent<N);wire in_ready,out_valid;
    wire[3071:0]out_s24;wire[31:0]accepted,accumulated,outputs,saturations;
    wire error;
    always #(CLOCK_PERIOD_PS / 2000.0) clk=~clk;
    generate
      if(!USE_OOC_WRAPPER) begin : g_matched
        m4_matched_tile #(.CASE_ID(CASE_ID)) dut(
          .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(in_ready),
          .in_act_u8(act_mem[sent]),.in_wgt_s8(wgt_mem[sent]),.in_zp_rows(zp_mem[sent]),
          .in_meta16(meta16_mem[sent]),.in_meta32(meta32_mem[sent]),
          .out_valid(out_valid),.out_ready(out_ready),.out_s24(out_s24),
          .accepted_group_count(accepted),.accumulated_group_count(accumulated),
          .output_tile_count(outputs),.saturation_count(saturations),.error(error));
      end else if(CASE_ID==1) begin : g_sc_ooc
        m4_scalecode_tile dut(
          .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(in_ready),
          .in_act_u8(act_mem[sent]),.in_wgt_s8(wgt_mem[sent]),.in_zp_rows(zp_mem[sent]),
          .in_meta16(meta16_mem[sent]),.in_meta32(meta32_mem[sent]),
          .out_valid(out_valid),.out_ready(out_ready),.out_s24(out_s24),
          .accepted_group_count(accepted),.accumulated_group_count(accumulated),
          .output_tile_count(outputs),.saturation_count(saturations),.error(error));
      end else if(CASE_ID==2) begin : g_fp16_ooc
        m4_fp16_tile dut(
          .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(in_ready),
          .in_act_u8(act_mem[sent]),.in_wgt_s8(wgt_mem[sent]),.in_zp_rows(zp_mem[sent]),
          .in_meta16(meta16_mem[sent]),.in_meta32(meta32_mem[sent]),
          .out_valid(out_valid),.out_ready(out_ready),.out_s24(out_s24),
          .accepted_group_count(accepted),.accumulated_group_count(accumulated),
          .output_tile_count(outputs),.saturation_count(saturations),.error(error));
      end else begin : g_fp32_ooc
        m4_fp32_tile dut(
          .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(in_ready),
          .in_act_u8(act_mem[sent]),.in_wgt_s8(wgt_mem[sent]),.in_zp_rows(zp_mem[sent]),
          .in_meta16(meta16_mem[sent]),.in_meta32(meta32_mem[sent]),
          .out_valid(out_valid),.out_ready(out_ready),.out_s24(out_s24),
          .accepted_group_count(accepted),.accumulated_group_count(accumulated),
          .output_tile_count(outputs),.saturation_count(saturations),.error(error));
      end
    endgenerate
    initial begin
      $readmemh({DATA_DIR,"/act_u8.mem"},act_mem);
      $readmemh({DATA_DIR,"/weight_s8.mem"},wgt_mem);
      $readmemh({DATA_DIR,"/zp_rows.mem"},zp_mem);
      if(CASE_ID==1)$readmemh({DATA_DIR,"/scalecode_meta.mem"},meta16_mem);
      else if(CASE_ID==2)$readmemh({DATA_DIR,"/fp16_meta.mem"},meta16_mem);
      else meta16_mem='{default:'0};
      if(CASE_ID==3)$readmemh({DATA_DIR,"/fp32_meta.mem"},meta32_mem);
      else meta32_mem='{default:'0};
      if(CASE_ID==0)$readmemh({DATA_DIR,"/expected_mac_s24.mem"},expected);
      else if(CASE_ID==1)$readmemh({DATA_DIR,"/expected_scalecode_s24.mem"},expected);
      else if(CASE_ID==2)$readmemh({DATA_DIR,"/expected_fp16_s24.mem"},expected);
      else $readmemh({DATA_DIR,"/expected_fp32_s24.mem"},expected);
      repeat(8)@(posedge clk);rst_n<=1;
    end
    always@(negedge clk)begin
      if(BACKPRESSURE==0)out_ready<=1'b1;
      else out_ready<=!((cycle%31)>=24&&(cycle%31)<=27);
    end
    always@(posedge clk)begin
      if(!rst_n)cycle<=0;else begin
        cycle<=cycle+1;
        if(in_valid&&in_ready)begin
          if(first_accept<0)first_accept=cycle;
          if(prev_accept>=0)begin interval=cycle-prev_accept;
            if(interval<ii_min)ii_min=interval;if(interval>ii_max)ii_max=interval;end
          prev_accept=cycle;last_accept=cycle;sent<=sent+1;
        end else if(in_valid)wait_input=wait_input+1;
        if(out_valid&&!out_ready)wait_output=wait_output+1;
        if(error)begin $display("FAIL: M4 error case=%0d cycle=%0d sent=%0d accum=%0d",CASE_ID,cycle,sent,accumulated);$finish;end
        if(out_valid&&out_ready)begin
          first_output=cycle;total_cycles=cycle-first_accept+1;
          if(out_s24!==expected[0])begin
            mismatch=1;$display("FAIL: M4 mismatch case=%0d",CASE_ID);
            for(check_lane=0;check_lane<128;check_lane=check_lane+1)
              if(out_s24[check_lane*24 +: 24]!==expected[0][check_lane*24 +: 24])
                $display("M4_LANE_MISMATCH lane=%0d exp=%h got=%h",check_lane,
                  expected[0][check_lane*24 +: 24],out_s24[check_lane*24 +: 24]);
          end
          if(mismatch==0&&accepted==128&&accumulated==128&&outputs==0)begin
            $display("M4_TILE_METRIC_JSON: {\"case_id\":%0d,\"groups\":128,\"lanes\":128,\"mismatches\":0,\"ii_min\":%0d,\"ii_max\":%0d,\"first_output_latency\":%0d,\"last_accept_cycle\":%0d,\"wait_input_cycles\":%0d,\"wait_output_cycles\":%0d,\"mac_active_cycles\":256,\"total_cycles\":%0d,\"pe_utilization\":%0f,\"effective_gops_150mhz\":%0f,\"saturations\":%0d}",CASE_ID,ii_min,ii_max,first_output-first_accept,last_accept-first_accept,wait_input,wait_output,total_cycles,256.0/total_cycles,(1048576.0/total_cycles)*0.15,saturations);
            $display("PASS: M4 matched tile case=%0d",CASE_ID);
          end else $display("FAIL: M4 counters case=%0d accepted=%0d accum=%0d out=%0d mismatch=%0d",CASE_ID,accepted,accumulated,outputs,mismatch);
          $finish;
        end
        if(cycle>10000)begin $display("FAIL: M4 timeout case=%0d sent=%0d accum=%0d out=%0d",CASE_ID,sent,accumulated,outputs);$finish;end
      end
    end
endmodule
