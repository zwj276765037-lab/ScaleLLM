`timescale 1ns / 1ps
module hap_mlp_axil_control_tb;
    reg clk=0,rst_n=0;
    reg [11:0] awaddr=0,araddr=0;reg awvalid=0,wvalid=0,bready=0;
    reg [31:0] wdata=0;reg [3:0] wstrb=0;wire awready,wready;
    wire [1:0] bresp,rresp;wire bvalid,arready,rvalid;wire[31:0]rdata;
    reg arvalid=0,rready=0;
    wire owner_request_valid;reg owner_request_ready=1;wire[1:0]owner_request;
    reg owner_request_done=0;reg[1:0]active_owner=0;reg owner_switch_pending=0;
    reg admission_pause=0;
    reg attention_launch_enable=0,mlp_launch_enable=0,owner_protocol_error=0;
    reg[7:0]d0o=0,d1o=0;wire mlp_command_valid;reg mlp_command_ready=1;
    reg maintenance_busy=0,paired_quiescent=1,mlp_abort_complete=0;
    reg maintenance_request_pending=0;
    reg[31:0]paired_attn_bursts=0,paired_mlp_bursts=0,paired_both_cycles=0;
    reg[31:0]paired_hol0=0,paired_hol1=0,paired_hwm0=0,paired_hwm1=0;
    wire mlp_clear_pulse,mlp_abort_pending,mlp_command_bank;
    wire[31:0]g0,g1,d0,d1,ib,ob,cid,lid;
    reg[1:0]input_bank_ready=2'b10;reg mlp_busy=0,mlp_done=0,mlp_error=0;
    reg[2:0]phase=0;reg[1567:0]telemetry=0;wire load_valid;reg load_ready=1;
    wire load_bank,commit_valid;reg commit_ready=1;wire commit_bank;
    wire[31:0]commit_gen;reg active_bank=1;reg[31:0]active_gen=32'h55;
    reg[1:0]bank_valid=2'b10,bank_loading=0;reg[31:0]gw0=0,gw1=10,dw0=0,dw1=20;
    reg meta_error=0;wire irq,done_sticky,error_sticky;integer checks=0;
    wire tensor_load_valid,tensor_store_valid;reg tensor_load_ready=0;
    reg tensor_store_ready=0,tensor_store_armed=0,tensor_dma_busy=0;
    reg tensor_dma_done=0,tensor_dma_error=0;reg[2:0]tensor_dma_phase=0;
    reg[31:0]tensor_input_beat_count=0,tensor_input_group_count=0;
    reg[31:0]tensor_output_beat_count=0,tensor_output_tile_count=0;
    wire[31:0]meta_gate_base_addr,meta_down_base_addr;
    reg meta_dma_busy=0,meta_dma_done=0,meta_dma_error=0;
    reg[2:0]meta_dma_phase=0;reg[31:0]meta_dma_gate_record_count=0;
    reg[31:0]meta_dma_down_record_count=0;reg[63:0]meta_dma_physical_bytes=0;
    integer owner_pulses=0,clear_pulses=0,command_pulses=0,guard=0;
    integer load_pulses=0,commit_pulses=0;
    always #3.333 clk=~clk;
    always @(posedge clk) begin
      if(owner_request_valid)owner_pulses<=owner_pulses+1;
      if(mlp_clear_pulse)clear_pulses<=clear_pulses+1;
      if(mlp_command_valid)command_pulses<=command_pulses+1;
      if(load_valid)load_pulses<=load_pulses+1;
      if(commit_valid)commit_pulses<=commit_pulses+1;
    end
    hap_mlp_axil_control #(.COMMAND_TIMEOUT_CYCLES(64)) dut(.*,
      .s_axil_awaddr(awaddr),.s_axil_awvalid(awvalid),
      .s_axil_awready(awready),.s_axil_wdata(wdata),.s_axil_wstrb(wstrb),
      .s_axil_wvalid(wvalid),.s_axil_wready(wready),.s_axil_bresp(bresp),
      .s_axil_bvalid(bvalid),.s_axil_bready(bready),.s_axil_araddr(araddr),
      .s_axil_arvalid(arvalid),.s_axil_arready(arready),.s_axil_rdata(rdata),
      .s_axil_rresp(rresp),.s_axil_rvalid(rvalid),.s_axil_rready(rready),
      .ddr0_outstanding(d0o),.ddr1_outstanding(d1o),
      .mlp_gate_ddr0_base_addr(g0),.mlp_gate_ddr1_base_addr(g1),
      .mlp_down_ddr0_base_addr(d0),.mlp_down_ddr1_base_addr(d1),
      .mlp_input_base_addr(ib),.mlp_output_base_addr(ob),
      .mlp_command_id(cid),.mlp_layer_id(lid),.mlp_input_bank_ready(input_bank_ready),
      .mlp_phase(phase),.mlp_telemetry(telemetry),
      .meta_load_begin_valid(load_valid),.meta_load_begin_ready(load_ready),
      .meta_load_bank(load_bank),.meta_commit_valid(commit_valid),
      .meta_commit_ready(commit_ready),.meta_commit_bank(commit_bank),
      .meta_commit_generation(commit_gen),.meta_active_bank(active_bank),
      .meta_active_generation(active_gen),.meta_bank_valid(bank_valid),
      .meta_bank_loading(bank_loading),.meta_gate_write_count_bank0(gw0),
      .meta_gate_write_count_bank1(gw1),.meta_down_write_count_bank0(dw0),
      .meta_down_write_count_bank1(dw1));
    task tick;begin @(posedge clk);#1;end endtask
    task check;input c;input[8*80-1:0]m;begin checks=checks+1;if(!c)begin
      $display("FAIL %0s",m);$fatal(1);end end endtask
    task wr;input[11:0]a;input[31:0]v;input[1:0]expected;
      begin while(!awready||!wready)tick();awaddr=a;wdata=v;wstrb=4'hf;
      awvalid=1;wvalid=1;tick();awvalid=0;wvalid=0;while(!bvalid)tick();
      check(bresp==expected,"write response");bready=1;tick();bready=0;end endtask
    task rd;input[11:0]a;input[31:0]expected;begin while(!arready)tick();
      araddr=a;arvalid=1;tick();arvalid=0;while(!rvalid)tick();
      if(rresp!=0||rdata!=expected)begin
        $display("FAIL read addr=%03h actual=%08h expected=%08h rresp=%0d",a,rdata,expected,rresp);
        $fatal(1);
      end
      checks=checks+1;rready=1;tick();rready=0;end endtask
    initial begin telemetry[3*32+:32]=32'h12345678;repeat(4)tick();rst_n=1;tick();
      rd(12'h100,32'h48384603);rd(12'h104,32'h00040003);
      wr(12'h108,2,0);check(owner_pulses==1&&owner_request==2,"owner request");tick();
      owner_request_done=1;tick();owner_request_done=0;
      rd(12'h10c,32'h00000060);
      wr(12'h13c,1,0);wr(12'h140,32'h55,0);
      // start rejected without MLP owner
      wr(12'h110,1,2);check(error_sticky,"invalid start not sticky");
      active_owner=2;mlp_launch_enable=1;wr(12'h110,2,0);check(clear_pulses==1,"clear pulse");tick();
      maintenance_busy=1;mlp_busy=1;wr(12'h110,2,2);
      check(clear_pulses==1,"repeated maintenance clear accepted");
      maintenance_busy=0;maintenance_request_pending=1;wr(12'h110,2,2);
      check(clear_pulses==1,"pending maintenance clear accepted");
      maintenance_request_pending=0;wr(12'h110,2,0);
      check(clear_pulses==2,"busy maintenance clear missing");mlp_busy=0;tick();
      owner_protocol_error=1;wr(12'h110,2,2);
      check(clear_pulses==2,"fatal maintenance clear accepted");
      owner_protocol_error=0;
      check(error_sticky&&irq&&!done_sticky,"idle owner error sticky status");
      rd(12'h29c,32'h00000000);
      wr(12'h110,2,0);check(clear_pulses==3,"owner error clear missing");
      wr(12'h150,0,0);wr(12'h158,32'h99,0);wr(12'h154,1,0);
      check(load_pulses==1&&!load_bank,"load begin");tick();wr(12'h154,2,0);
      check(commit_pulses==1&&!commit_bank&&commit_gen==32'h99,"meta commit");tick();
      rd(12'h18c,32'h12345678);

      // A command freezes its identity at the command handshake. Later AXI-Lite
      // writes prepare the next command and cannot relabel this completion.
      wr(12'h118,32'h11223344,0);wr(12'h11c,32'd31,0);
      wr(12'h280,32'hdeadbeef,0);wr(12'h284,32'h55aa0123,0);
      rd(12'h280,32'hdeadbeef);rd(12'h284,32'h55aa0123);
      wr(12'h110,1,0);check(command_pulses==1,"valid start missing");
      rd(12'h29c,32'h00000002);
      wr(12'h118,32'h55667788,0);wr(12'h11c,32'd7,0);
      wr(12'h280,32'hcafef00d,0);wr(12'h284,32'ha5a54567,0);
      mlp_done=1;tick();mlp_done=0;check(done_sticky&&irq,"done sticky irq");
      rd(12'h288,32'hdeadbeef);rd(12'h28c,32'h11223344);
      rd(12'h290,32'h55aa0123);rd(12'h294,32'd31);
      rd(12'h298,32'h000155aa);rd(12'h29c,32'h00000001);
      wr(12'h2a0,32'h55667788,2);
      rd(12'h29c,32'h00000001);
      wr(12'h2a0,32'h11223344,0);
      check(clear_pulses==3,"completion ack triggered maintenance");
      check(!done_sticky&&!irq,"success completion ack failed");
      rd(12'h29c,32'h00000000);rd(12'h2a0,32'h00000000);

      // A tied compute error completes the captured command with nonzero
      // status. A later stray done pulse must not overwrite that completion.
      wr(12'h110,1,0);check(command_pulses==2,"error command missing");
      mlp_error=1;tick();mlp_error=0;
      check(error_sticky&&irq&&!done_sticky,"command error sticky status");
      rd(12'h288,32'hcafef00d);rd(12'h28c,32'h55667788);
      rd(12'h290,32'ha5a54567);rd(12'h294,32'd7);
      rd(12'h298,32'h0019a5a5);rd(12'h29c,32'h00000001);
      mlp_done=1;tick();mlp_done=0;
      check(!done_sticky,"stray done completed an inactive command");
      rd(12'h28c,32'h55667788);rd(12'h298,32'h0019a5a5);
      wr(12'h2a0,32'h55667788,0);
      check(clear_pulses==3,"error completion ack triggered maintenance");
      check(!error_sticky&&!irq,"error completion ack failed");
      rd(12'h29c,32'h00000000);

      // Idle metadata faults raise the diagnostic IRQ but do not manufacture
      // a successful or failed MLP command completion.
      meta_error=1;tick();meta_error=0;
      check(error_sticky&&irq&&!done_sticky,"idle metadata error status");
      rd(12'h29c,32'h00000000);rd(12'h28c,32'h55667788);
      rd(12'h2a0,32'h00000001);
      wr(12'h110,2,0);check(clear_pulses==4,"diagnostic clear missing");
      rd(12'h2a0,32'h00000000);

      // Watchdog expiry requests maintenance but preserves the active identity
      // until the production integration confirms a bus-safe local MLP clear.
      wr(12'h118,32'h33334444,0);wr(12'h11c,32'd9,0);
      wr(12'h280,32'h11112222,0);wr(12'h284,32'h1234abcd,0);
      wr(12'h110,1,0);check(command_pulses==3,"timeout command missing");
      tick();check(dut.command_cycle_count_r!=0,"watchdog counter did not advance");
      wr(12'h118,32'h77778888,0);wr(12'h11c,32'd10,0);
      wr(12'h280,32'h55556666,0);wr(12'h284,32'h5678dcba,0);
      guard=0;while(!mlp_abort_pending&&guard<128)begin tick();guard=guard+1;end
      check(mlp_abort_pending&&guard<128,"watchdog abort did not become pending");
      tick();
      check(clear_pulses==5,"watchdog did not issue one maintenance request");
      rd(12'h29c,32'h00000002);rd(12'h2a8,32'h00000001);
      wr(12'h2a0,32'h33334444,2);
      check(mlp_abort_pending,"pending timeout accepted an early ACK");
      maintenance_request_pending=1;maintenance_busy=1;
      rd(12'h2a8,32'h00000003);
      mlp_abort_complete=1;tick();mlp_abort_complete=0;
      check(!mlp_abort_pending&&error_sticky&&irq&&!done_sticky,
        "timeout completion state");
      rd(12'h288,32'h11112222);rd(12'h28c,32'h33334444);
      rd(12'h290,32'h1234abcd);rd(12'h294,32'd9);
      rd(12'h298,32'h00211234);rd(12'h148,32'h00020000);
      rd(12'h29c,32'h00000001);rd(12'h2a8,32'h00000002);
      wr(12'h2a0,32'h33334444,0);
      check(!error_sticky&&!irq,"timeout completion ACK failed");
      maintenance_request_pending=0;maintenance_busy=0;

      // An active software clear follows the same safe-abort protocol and
      // returns maintenance-abort status without adopting next-command fields.
      wr(12'h118,32'hbbbbcccc,0);wr(12'h11c,32'd11,0);
      wr(12'h280,32'h9999aaaa,0);wr(12'h284,32'h24681357,0);
      wr(12'h110,1,0);check(command_pulses==4,"maintenance command missing");
      wr(12'h110,2,0);
      check(mlp_abort_pending&&clear_pulses==6,
        "active maintenance clear did not enter abort pending");
      maintenance_request_pending=1;maintenance_busy=1;
      rd(12'h29c,32'h00000002);rd(12'h2a8,32'h00000003);
      wr(12'h110,2,2);check(clear_pulses==6,"repeated abort clear accepted");
      wr(12'h2a0,32'hbbbbcccc,2);
      wr(12'h118,32'hddddeeee,0);wr(12'h11c,32'd12,0);
      wr(12'h280,32'hffff0000,0);wr(12'h284,32'h4321beef,0);
      mlp_abort_complete=1;tick();mlp_abort_complete=0;
      check(!mlp_abort_pending&&error_sticky&&irq&&!done_sticky,
        "maintenance-abort completion state");
      rd(12'h288,32'h9999aaaa);rd(12'h28c,32'hbbbbcccc);
      rd(12'h290,32'h24681357);rd(12'h294,32'd11);
      rd(12'h298,32'h00292468);rd(12'h148,32'h00010000);
      rd(12'h29c,32'h00000001);rd(12'h2a8,32'h00000002);
      wr(12'h2a0,32'hbbbbcccc,0);
      check(!error_sticky&&!irq,"maintenance-abort ACK failed");
      maintenance_request_pending=0;maintenance_busy=0;
      rd(12'h29c,32'h00000000);rd(12'h2a8,32'h00000000);
      $display("PASS hap_mlp_axil_control checks=%0d",checks);$finish;end
endmodule
