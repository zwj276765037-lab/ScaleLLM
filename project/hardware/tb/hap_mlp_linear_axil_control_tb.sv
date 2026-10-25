`timescale 1ns/1ps
// W0 revision2 AXI-Lite boundary test. The job side is an explicit external
// stimulus source: result codes/latencies are test vectors, not a second DUT.
// This test covers CSR transport and mapping, not real job/DMA execution.
module hap_mlp_linear_axil_control_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0;
    reg [11:0] awaddr=0,araddr=0;
    reg [31:0] wdata=0;
    reg [3:0] wstrb=0;
    reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
    wire awready,wready,bvalid,arready,rvalid;
    wire [1:0] bresp,rresp;
    wire [31:0] rdata;
    wire owner_request_valid,mlp_clear_pulse,mlp_command_valid;
    wire tensor_load_valid,tensor_store_valid;
    wire submit_valid,submit_result_ready;
    reg submit_ready=0,submit_result_valid=0;
    reg [31:0] submit_error=0;
    wire [543:0] submit_descriptor,config_descriptor;
    wire epoch_valid,ack_valid,abort_valid;
    wire [31:0] epoch_id,ack_id,abort_id;
    reg epoch_result_valid=0,ack_result_valid=0,abort_result_valid=0;
    reg [31:0] epoch_error=0;
    reg ack_error=0,abort_error=0;
    reg job_busy=0,job_completion_valid=0,job_quiescent=1,job_reset_required=0;
    reg [7:0] job_phase=0;
    reg [543:0] done_descriptor=0;
    reg [31:0] done_error=0,done_input_bytes=0,done_output_bytes=0,done_records=0;
    reg [31:0] job_load_cycles=0,job_compute_cycles=0,job_store_cycles=0,job_stall_cycles=0;
    reg [31:0] active_epoch=0;
    wire irq,done_sticky,error_sticky;
    integer checks=0,cycles=0,aw_count=0,w_count=0,b_count=0;
    integer submit_count=0,epoch_count=0,ack_count=0,abort_count=0,clear_count=0;
    integer w_stall_cycles=0;
    reg [543:0] captured_descriptor=0;
    reg previous_b_stall=0,previous_r_stall=0,previous_submit_stall=0;
    reg [1:0] held_bresp=0,held_rresp=0;
    reg [31:0] held_rdata=0;
    reg [543:0] held_submit_descriptor=0;
    reg [11:0] descriptor_csr[0:16];
    reg [11:0] readonly_csr[0:63];
    integer readonly_count=0;
    reg [543:0] expected_config=0,expected_first=0;
    reg [31:0] pattern,before_value;
    integer index,strobe_index,before_count;

    hap_mlp_linear_axil_control dut(
      .clk(clk),.rst_n(rst_n),
      .s_axil_awaddr(awaddr),.s_axil_awvalid(awvalid),.s_axil_awready(awready),
      .s_axil_wdata(wdata),.s_axil_wstrb(wstrb),.s_axil_wvalid(wvalid),.s_axil_wready(wready),
      .s_axil_bresp(bresp),.s_axil_bvalid(bvalid),.s_axil_bready(bready),
      .s_axil_araddr(araddr),.s_axil_arvalid(arvalid),.s_axil_arready(arready),
      .s_axil_rdata(rdata),.s_axil_rresp(rresp),.s_axil_rvalid(rvalid),.s_axil_rready(rready),
      .owner_request_valid(owner_request_valid),.owner_request_ready(1'b1),
      .admission_pause(1'b0),.owner_request(),.owner_request_done(1'b0),
      .active_owner(2'd3),.owner_switch_pending(1'b0),
      .attention_launch_enable(1'b1),.mlp_launch_enable(1'b1),.owner_protocol_error(1'b0),
      .ddr0_outstanding(8'd0),.ddr1_outstanding(8'd0),
      .maintenance_busy(1'b0),.maintenance_request_pending(1'b0),.mlp_abort_complete(1'b0),
      .paired_quiescent(1'b1),.paired_attn_bursts(32'd0),.paired_mlp_bursts(32'd0),
      .paired_both_cycles(32'd0),.paired_hol0(32'd0),.paired_hol1(32'd0),
      .paired_hwm0(32'd0),.paired_hwm1(32'd0),
      .mlp_command_valid(mlp_command_valid),.mlp_command_ready(1'b1),
      .mlp_clear_pulse(mlp_clear_pulse),.mlp_abort_pending(),.mlp_command_bank(),
      .mlp_gate_ddr0_base_addr(),.mlp_gate_ddr1_base_addr(),
      .mlp_down_ddr0_base_addr(),.mlp_down_ddr1_base_addr(),
      .mlp_input_base_addr(),.mlp_output_base_addr(),.mlp_command_id(),.mlp_layer_id(),
      .mlp_input_bank_ready(2'd0),.mlp_busy(1'b0),.mlp_done(1'b0),.mlp_error(1'b0),
      .mlp_phase(3'd0),.mlp_telemetry(1568'd0),
      .mlp_down_output_saturation_count(32'd0),.mlp_total_shift_format_count(32'd0),.mlp_numeric_status(32'd0),
      .tensor_load_valid(tensor_load_valid),.tensor_load_ready(1'b1),
      .tensor_store_valid(tensor_store_valid),.tensor_store_ready(1'b1),
      .tensor_store_armed(1'b0),.tensor_dma_busy(1'b0),.tensor_dma_done(1'b0),
      .tensor_dma_error(1'b0),.tensor_dma_phase(3'd0),
      .tensor_input_beat_count(32'd0),.tensor_input_group_count(32'd0),
      .tensor_output_beat_count(32'd0),.tensor_output_tile_count(32'd0),
      .meta_gate_base_addr(),.meta_down_base_addr(),.meta_dma_busy(1'b0),
      .meta_dma_done(1'b0),.meta_dma_error(1'b0),.meta_dma_phase(3'd0),
      .meta_dma_gate_record_count(32'd0),.meta_dma_down_record_count(32'd0),.meta_dma_physical_bytes(64'd0),
      .meta_load_begin_valid(),.meta_load_begin_ready(1'b1),.meta_load_bank(),
      .meta_commit_valid(),.meta_commit_ready(1'b1),.meta_commit_bank(),.meta_commit_generation(),
      .meta_active_bank(1'b0),.meta_active_generation(32'd7),
      .meta_bank_valid(2'b01),.meta_bank_loading(2'b00),
      .meta_gate_write_count_bank0(32'd0),.meta_gate_write_count_bank1(32'd0),
      .meta_down_write_count_bank0(32'd0),.meta_down_write_count_bank1(32'd0),.meta_error(1'b0),
      .submit_valid(submit_valid),.submit_ready(submit_ready),.submit_descriptor(submit_descriptor),
      .submit_result_valid(submit_result_valid),.submit_result_ready(submit_result_ready),.submit_error(submit_error),
      .epoch_valid(epoch_valid),.epoch_id(epoch_id),.config_descriptor(config_descriptor),
      .epoch_result_valid(epoch_result_valid),.epoch_error(epoch_error),
      .ack_valid(ack_valid),.ack_id(ack_id),.ack_result_valid(ack_result_valid),.ack_error(ack_error),
      .abort_valid(abort_valid),.abort_id(abort_id),.abort_result_valid(abort_result_valid),.abort_error(abort_error),
      .job_busy(job_busy),.job_completion_valid(job_completion_valid),.job_quiescent(job_quiescent),
      .job_reset_required(job_reset_required),.job_phase(job_phase),
      .done_descriptor(done_descriptor),.done_error(done_error),
      .done_input_bytes(done_input_bytes),.done_output_bytes(done_output_bytes),.done_records(done_records),
      .job_load_cycles(job_load_cycles),.job_compute_cycles(job_compute_cycles),
      .job_store_cycles(job_store_cycles),.job_stall_cycles(job_stall_cycles),.active_epoch(active_epoch),
      .irq(irq),.done_sticky(done_sticky),.error_sticky(error_sticky));

    task check(input bit condition,input string message);
      begin
        checks=checks+1;
        if(!condition)$fatal(1,"CSR check: %s (cycle %0d)",message,cycles);
      end
    endtask

    // Drivers change on falling edges; the monitor samples actual handshakes
    // before nonblocking DUT updates, avoiding testbench/DUT sampling races.
    always @(posedge clk) begin
      cycles<=cycles+1;
      if(cycles>50000)$fatal(1,"CSR bounded watchdog; no completed test result");
      if(rst_n) begin
        if(awvalid&&awready)aw_count<=aw_count+1;
        if(wvalid&&wready)w_count<=w_count+1;
        if(bvalid&&bready)b_count<=b_count+1;
        if(wvalid&&!wready)w_stall_cycles<=w_stall_cycles+1;
        if(submit_valid&&submit_ready)begin
          submit_count<=submit_count+1;captured_descriptor<=submit_descriptor;
        end
        if(epoch_valid)epoch_count<=epoch_count+1;
        if(ack_valid)ack_count<=ack_count+1;
        if(abort_valid)abort_count<=abort_count+1;
        if(mlp_clear_pulse)clear_count<=clear_count+1;
        if(previous_b_stall&&(bvalid!==1'b1||bresp!==held_bresp))
          $fatal(1,"B response changed or disappeared under backpressure");
        if(previous_r_stall&&(rvalid!==1'b1||rdata!==held_rdata||rresp!==held_rresp))
          $fatal(1,"R response changed or disappeared under backpressure");
        if(previous_submit_stall&&(submit_valid!==1'b1||submit_descriptor!==held_submit_descriptor))
          $fatal(1,"submit payload changed before job accepted it");
        if(mlp_command_valid||tensor_load_valid||tensor_store_valid)
          $fatal(1,"CSR block drove obsolete direct launch path");
      end
      previous_b_stall<=rst_n&&bvalid&&!bready;held_bresp<=bresp;
      previous_r_stall<=rst_n&&rvalid&&!rready;held_rdata<=rdata;held_rresp<=rresp;
      previous_submit_stall<=rst_n&&submit_valid&&!submit_ready;held_submit_descriptor<=submit_descriptor;
    end

    task send_aw(input [11:0] address);
      begin
        @(negedge clk);awaddr=address;awvalid=1;
        @(posedge clk);while(!awready)@(posedge clk);
        @(negedge clk);awvalid=0;
      end
    endtask
    task send_w(input [31:0] value,input [3:0] strobe);
      begin
        @(negedge clk);wdata=value;wstrb=strobe;wvalid=1;
        @(posedge clk);while(!wready)@(posedge clk);
        @(negedge clk);wvalid=0;
      end
    endtask
    task issue_write(input [11:0] address,input [31:0] value,input [3:0] strobe,input integer order);
      begin
        if(order==1)begin
          send_aw(address);
          repeat(3)begin @(negedge clk);check(!bvalid,"AW alone cannot complete write");end
          send_w(value,strobe);
        end else if(order==2)begin
          send_w(value,strobe);
          repeat(3)begin @(negedge clk);check(!bvalid,"W alone cannot complete write");end
          send_aw(address);
        end else begin
          fork send_aw(address);send_w(value,strobe);join
        end
      end
    endtask
    task finish_b(input [1:0] response,input integer hold_cycles);
      begin
        while(!bvalid)@(negedge clk);
        check(bresp===response,"write response matches independent expected code");
        repeat(hold_cycles)begin @(negedge clk);check(bvalid&&bresp===response,"B held while BREADY low");end
        bready=1;@(negedge clk);bready=0;
      end
    endtask
    task write_reg(input [11:0] address,input [31:0] value,input [3:0] strobe,input [1:0] response,input integer order);
      begin issue_write(address,value,strobe,order);finish_b(response,2);end
    endtask
    task send_ar(input [11:0] address);
      begin
        @(negedge clk);araddr=address;arvalid=1;
        @(posedge clk);while(!arready)@(posedge clk);
        @(negedge clk);arvalid=0;
      end
    endtask
    task finish_r(input [31:0] value,input [1:0] response,input integer hold_cycles);
      begin
        while(!rvalid)@(negedge clk);
        if(rdata!==value||rresp!==response)
          $fatal(1,"CSR read address=%03h actual=%08h/%0d expected=%08h/%0d",araddr,rdata,rresp,value,response);
        checks=checks+1;
        repeat(hold_cycles)begin @(negedge clk);check(rvalid&&rdata===value&&rresp===response,"R held while RREADY low");end
        rready=1;@(negedge clk);rready=0;
      end
    endtask
    task read_reg(input [11:0] address,input [31:0] value,input [1:0] response);
      begin send_ar(address);finish_r(value,response,2);end
    endtask
    task clear_admission;
      begin write_reg(12'h374,32'd1,4'hf,0,0);read_reg(12'h370,0,0);end
    endtask

    task submit_vector(input [543:0] expected,input [31:0] job_result);
      begin
        submit_ready=0;
        issue_write(12'h320,1,4'hf,1);
        while(!submit_valid)@(negedge clk);
        repeat(4)begin
          @(negedge clk);
          check(submit_valid&&submit_descriptor===expected,"START holds exact descriptor while job stalls");
          check(!bvalid,"START cannot produce B before job result");
        end
        submit_ready=1;@(negedge clk);submit_ready=0;
        check(captured_descriptor===expected,"job handshake captures the submitted descriptor");
        repeat(5)begin @(negedge clk);check(!bvalid,"accepted submit still awaits validation result");end
        check(submit_result_ready,"result channel is ready during validation wait");
        submit_error=job_result;submit_result_valid=1;
        @(negedge clk);submit_result_valid=0;
        finish_b(job_result==0?2'b00:2'b10,4);
      end
    endtask

    // Each vector supplies a result explicitly. No job-admission algorithm is
    // reproduced here; the standalone job-control TB checks that algorithm.
    task action_result(input integer kind,input [31:0] value,input bit rejected,input [31:0] error_code);
      begin
        if(kind==0)issue_write(12'h36c,value,4'hf,2);
        else if(kind==1)issue_write(12'h2a0,value,4'hf,0);
        else issue_write(12'h320,4,4'hf,0);
        if(kind==0)begin
          while(!epoch_valid)@(negedge clk);
          check(epoch_id===value,"epoch request ID");
          check(config_descriptor===expected_config,"epoch observes the programmed binding descriptor");
        end else if(kind==1)begin
          while(!ack_valid)@(negedge clk);
          check(ack_id===value,"ACK request identity comes from write data");
        end else begin
          while(!abort_valid)@(negedge clk);
          check(abort_id===expected_config[0+:32],"ABORT snapshots configured command ID");
        end
        repeat(4)begin @(negedge clk);check(!bvalid,"action B waits for external result");end
        if(kind==0)begin epoch_error=error_code;epoch_result_valid=1;end
        else if(kind==1)begin ack_error=rejected;ack_result_valid=1;end
        else begin abort_error=rejected;abort_result_valid=1;end
        @(negedge clk);
        epoch_result_valid=0;ack_result_valid=0;abort_result_valid=0;
        finish_b(rejected?2'b10:2'b00,3);
      end
    endtask

    task legacy_status_vector(input [31:0] error_code,input [7:0] status_code);
      begin
        @(negedge clk);done_error=error_code;
        read_reg(12'h350,error_code,0);read_reg(12'h148,error_code,0);
        read_reg(12'h298,(32'(status_code)<<19)|32'h00010003,0);
      end
    endtask

    initial begin
      // Descriptor word order comes from W0 abi.json, not RTL branch order.
      descriptor_csr[0]=12'h118;descriptor_csr[1]=12'h280;descriptor_csr[2]=12'h284;
      descriptor_csr[3]=12'h11c;descriptor_csr[4]=12'h30c;descriptor_csr[5]=12'h120;
      descriptor_csr[6]=12'h124;descriptor_csr[7]=12'h128;descriptor_csr[8]=12'h310;
      descriptor_csr[9]=12'h314;descriptor_csr[10]=12'h318;descriptor_csr[11]=12'h140;
      descriptor_csr[12]=12'h31c;descriptor_csr[13]=12'h12c;descriptor_csr[14]=12'h130;
      descriptor_csr[15]=12'h134;descriptor_csr[16]=12'h138;
      // All schema entries classified RO/LEGACY_RO/COMPAT_RO/RESERVED plus
      // 0x174; the obsolete tensor action is checked for every strobe below.
      readonly_csr[0]=12'h100;readonly_csr[1]=12'h104;readonly_csr[2]=12'h10c;
      readonly_csr[3]=12'h114;readonly_csr[4]=12'h144;readonly_csr[5]=12'h148;
      readonly_csr[6]=12'h14c;readonly_csr[7]=12'h15c;readonly_csr[8]=12'h160;
      readonly_csr[9]=12'h164;readonly_csr[10]=12'h168;readonly_csr[11]=12'h178;
      readonly_csr[12]=12'h17c;readonly_csr[13]=12'h244;readonly_csr[14]=12'h248;
      readonly_csr[15]=12'h24c;readonly_csr[16]=12'h250;readonly_csr[17]=12'h254;
      readonly_csr[18]=12'h258;readonly_csr[19]=12'h25c;readonly_csr[20]=12'h260;
      readonly_csr[21]=12'h264;readonly_csr[22]=12'h268;readonly_csr[23]=12'h26c;
      readonly_csr[24]=12'h270;readonly_csr[25]=12'h274;readonly_csr[26]=12'h278;
      readonly_csr[27]=12'h27c;readonly_csr[28]=12'h288;readonly_csr[29]=12'h28c;
      readonly_csr[30]=12'h290;readonly_csr[31]=12'h294;readonly_csr[32]=12'h298;
      readonly_csr[33]=12'h29c;readonly_csr[34]=12'h2a4;readonly_csr[35]=12'h2a8;
      readonly_csr[36]=12'h2ac;readonly_csr[37]=12'h2b0;readonly_csr[38]=12'h2b4;
      readonly_csr[39]=12'h2b8;readonly_csr[40]=12'h300;readonly_csr[41]=12'h304;
      readonly_csr[42]=12'h308;readonly_csr[43]=12'h324;readonly_csr[44]=12'h328;
      readonly_csr[45]=12'h32c;readonly_csr[46]=12'h330;readonly_csr[47]=12'h334;
      readonly_csr[48]=12'h338;readonly_csr[49]=12'h33c;readonly_csr[50]=12'h340;
      readonly_csr[51]=12'h344;readonly_csr[52]=12'h348;readonly_csr[53]=12'h34c;
      readonly_csr[54]=12'h350;readonly_csr[55]=12'h354;readonly_csr[56]=12'h358;
      readonly_csr[57]=12'h35c;readonly_csr[58]=12'h360;readonly_csr[59]=12'h364;
      readonly_csr[60]=12'h368;readonly_csr[61]=12'h370;readonly_csr[62]=12'h378;
      readonly_csr[63]=12'h37c;readonly_count=64;
      repeat(4)@(negedge clk);rst_n=1;
      read_reg(12'h100,32'h48384605,0);read_reg(12'h104,32'h00060000,0);
      read_reg(12'h300,32'h4d4c0001,0);read_reg(12'h304,32'h1f,0);
      read_reg(12'h308,1,0);read_reg(12'h2b8,32'h4d303032,0);
      read_reg(12'h324,8,0);read_reg(12'h370,0,0);

      // All descriptor fields: full, byte merge, and zero-strobe no-op.
      for(index=0;index<17;index=index+1)begin
        pattern=32'h11223344+index*32'h01010101;
        write_reg(descriptor_csr[index],pattern,4'hf,0,index%3);
        read_reg(descriptor_csr[index],pattern,0);
        write_reg(descriptor_csr[index],32'haabbccdd,4'h5,0,(index+1)%3);
        pattern={pattern[31:24],8'hbb,pattern[15:8],8'hdd};
        expected_config[index*32+:32]=pattern;
        read_reg(descriptor_csr[index],pattern,0);
        write_reg(descriptor_csr[index],32'hffffffff,4'h0,0,0);
        read_reg(descriptor_csr[index],pattern,0);
      end
      check(config_descriptor===expected_config,"all17 words independently map to the544-bit descriptor");

      // Hold a second complete AW/W transaction behind an unconsumed B.
      issue_write(12'h118,32'h01020304,4'hf,0);
      while(!bvalid)@(negedge clk);
      before_count=w_stall_cycles;
      fork
        send_aw(12'h118);
        send_w(32'h55667788,4'hf);
        finish_b(0,5);
      join
      finish_b(0,3);
      expected_config[0+:32]=32'h55667788;
      read_reg(12'h118,32'h55667788,0);
      check(w_stall_cycles>before_count,"WVALID exercised while WREADY was backpressured");

      // RO writes reject even zero WSTRB. Mutable job inputs remain unchanged.
      for(index=0;index<readonly_count;index=index+1)begin
        write_reg(readonly_csr[index],32'hdeadbeef,4'hf,2,index%3);
        write_reg(readonly_csr[index],32'hdeadbeef,4'h5,2,0);
        write_reg(readonly_csr[index],32'hdeadbeef,4'h0,2,0);
      end
      for(index=12'h180;index<=12'h240;index=index+4)begin
        read_reg(12'(index),0,0);write_reg(12'(index),32'hffffffff,4'h0,2,0);
      end
      read_reg(12'h378,0,0);read_reg(12'h37c,0,0);
      read_reg(12'h101,0,2);write_reg(12'h119,32'hffffffff,4'hf,2,0);
      read_reg(12'h3fc,0,2);write_reg(12'h3fc,0,4'h0,2,0);
      check(config_descriptor===expected_config,"RO/unknown/unaligned writes did not alter descriptor");

      // New action/strobe validation and sticky first-rejection diagnostic.
      clear_admission();
      before_count=submit_count;
      write_reg(12'h320,0,4'hf,2,0);read_reg(12'h370,32'h1001,0);read_reg(12'h2a0,1,0);
      write_reg(12'h320,1,4'h7,2,0);read_reg(12'h370,32'h1001,0);
      write_reg(12'h320,5,4'hf,2,0);write_reg(12'h320,1,4'h0,2,0);
      check(submit_count==before_count&&!submit_valid,"invalid START produces no request");
      write_reg(12'h374,1,4'h1,2,0);write_reg(12'h374,0,4'hf,2,0);
      read_reg(12'h370,32'h1001,0);clear_admission();read_reg(12'h2a0,0,0);
      write_reg(12'h320,1,4'h7,2,0);read_reg(12'h370,32'h1002,0);clear_admission();

      // Legacy START|maintenance must reject atomically, without clear pulse.
      before_count=clear_count;
      write_reg(12'h110,3,4'hf,2,1);write_reg(12'h110,1,4'hf,2,2);
      check(clear_count==before_count,"legacy START composite cannot trigger maintenance");
      for(strobe_index=0;strobe_index<3;strobe_index=strobe_index+1)
        write_reg(12'h174,1,strobe_index==0?4'hf:strobe_index==1?4'h5:4'h0,2,0);
      read_reg(12'h174,0,0);read_reg(12'h370,32'h1003,0);
      write_reg(12'h110,2,4'hf,0,0);
      check(clear_count==before_count+1,"maintenance-only legacy action remains available");
      clear_admission();
      write_reg(12'h13c,0,4'hf,0,0);write_reg(12'h13c,1,4'h0,0,0);
      write_reg(12'h13c,1,4'h1,2,0);read_reg(12'h13c,0,0);

      // Binding/ACK/ABORT requests are checked before an explicit mock result.
      before_count=epoch_count;
      write_reg(12'h36c,9,4'h7,2,0);check(epoch_count==before_count,"partial epoch write has no pulse");
      read_reg(12'h370,32'h1002,0);clear_admission();
      action_result(0,32'h12345678,0,0);
      active_epoch=32'h12345678;read_reg(12'h368,32'h12345678,0);
      action_result(0,0,1,32'h1025);read_reg(12'h370,32'h1025,0);
      action_result(1,32'hbad0bad0,1,0);read_reg(12'h370,32'h1025,0);
      action_result(2,0,1,0);read_reg(12'h370,32'h1025,0);
      clear_admission();

      // START's descriptor survives request stalls and later configuration writes.
      expected_first=expected_config;
      submit_vector(expected_first,0);
      before_value=captured_descriptor[0+:32];
      write_reg(12'h118,32'ha1a2a3a4,4'hf,0,2);
      expected_config[0+:32]=32'ha1a2a3a4;
      check(captured_descriptor===expected_first,"later CSR write cannot relabel accepted job");
      check(before_value==32'h55667788,"first command identity is independently known");
      submit_vector(expected_config,32'h1013);
      read_reg(12'h370,32'h1013,0);
      action_result(0,0,1,32'h1025);read_reg(12'h370,32'h1013,0);
      clear_admission();

      // Mock completion data verifies CSR projection and legacy aliases. No
      // claim is made that this mock checks the job's real drain/freeze logic.
      @(negedge clk);
      done_descriptor=0;
      done_descriptor[0+:32]=32'h12345678;done_descriptor[32+:32]=32'h90abcdef;
      done_descriptor[64+:32]=32'h00030001;done_descriptor[96+:32]=31;
      done_descriptor[128+:32]=2;done_descriptor[320+:32]=99;
      done_descriptor[352+:32]=7;done_descriptor[384+:32]=32'h12345678;
      done_input_bytes=258048;done_output_bytes=262144;done_records=256;
      job_compute_cycles=32'h10001;job_load_cycles=32'h20002;
      job_store_cycles=32'h30003;job_stall_cycles=32'h40004;
      job_completion_valid=1;job_phase=6;
      read_reg(12'h328,2,0);read_reg(12'h32c,99,0);read_reg(12'h330,32'h12345678,0);
      read_reg(12'h334,7,0);read_reg(12'h338,32'h12345678,0);read_reg(12'h33c,32'h90abcdef,0);
      read_reg(12'h340,32'h00030001,0);read_reg(12'h344,31,0);
      read_reg(12'h348,258048,0);read_reg(12'h34c,262144,0);read_reg(12'h364,256,0);
      read_reg(12'h354,32'h10001,0);read_reg(12'h358,32'h20002,0);
      read_reg(12'h35c,32'h30003,0);read_reg(12'h360,32'h40004,0);
      read_reg(12'h288,32'h90abcdef,0);read_reg(12'h28c,32'h12345678,0);
      read_reg(12'h290,32'h00030001,0);read_reg(12'h294,31,0);
      read_reg(12'h29c,1,0);read_reg(12'h2a4,32'h10001,0);read_reg(12'h324,32'h60a,0);
      check(irq&&done_sticky&&!error_sticky,"successful DONE status/IRQ");
      legacy_status_vector(0,0);legacy_status_vector(32'h2001,1);
      legacy_status_vector(32'h2103,2);legacy_status_vector(32'h2051,3);
      legacy_status_vector(32'h2200,4);legacy_status_vector(32'h2201,5);
      check(error_sticky,"failed DONE raises error diagnostic");

      // Change mock inputs after AR acceptance: already issued R is atomic.
      send_ar(12'h338);while(!rvalid)@(negedge clk);
      done_descriptor[0+:32]=32'hfeedcafe;
      finish_r(32'h12345678,0,5);read_reg(12'h338,32'hfeedcafe,0);
      before_count=ack_count;
      write_reg(12'h2a0,32'hfeedcafe,4'h0,2,0);
      write_reg(12'h2a0,32'hfeedcafe,4'h7,2,0);
      check(ack_count==before_count,"invalid ACK strobe causes no job-side request");
      action_result(1,32'hfeedcafe,0,0);
      @(negedge clk);job_completion_valid=0;done_error=0;
      read_reg(12'h29c,0,0);read_reg(12'h370,0,0);
      action_result(2,0,0,0);read_reg(12'h370,0,0);
      check(!irq&&!error_sticky,"ACKed mock completion does not retain live error diagnostic");
      check(ack_count==2&&abort_count==2&&epoch_count==3&&submit_count==2,"exactly one request per accepted action");
      check(aw_count==w_count&&w_count==b_count,"all AXI writes retired exactly once");
      check(!bvalid&&!rvalid&&!submit_valid,"no outstanding CSR response at test end");
      $display("CSR checks=%0d writes=%0d submits=%0d epochs=%0d ACKs=%0d aborts=%0d Wstalls=%0d",checks,b_count,submit_count,epoch_count,ack_count,abort_count,w_stall_cycles);
      $display("HARDWARE_AGENT_SIM_PASS");
      $finish;
    end
endmodule
