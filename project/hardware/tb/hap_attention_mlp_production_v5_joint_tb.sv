`timescale 1ns / 1ps

// One full layer, two distinct fresh-prefill cohorts, four real commands.
// Immutable packet files are producer-owned; CPU feedback is report output.
module hap_attention_mlp_production_v5_joint_tb;
  `include "tb/rebuild_v5_joint_axi_bfm.svh"
  hap_attention_mlp_production_core dut (`REBUILD_V5_JOINT_PORTS);
  `undef REBUILD_V5_JOINT_PORTS

  // Candidate deadlock bound, NOT throughput: kernel service allowance plus
  // finite frontend/group and stalled metadata/tensor transport allowances.
  localparam integer JOINT_COMMAND_LIMIT = 64*459136 + 6000*(128+448) +
    16*(81920+256+229376+114688+26624);
  localparam integer JOINT_RUN_LIMIT = 4*JOINT_COMMAND_LIMIT + 200000;
  string joint_packet_dir, joint_report_dir;
  integer joint_layer = 0, joint_boundary_index = 0;
  integer joint_attn_in[0:1], joint_attn_out[0:1];
  integer joint_mlp_in[0:1], joint_mlp_out[0:1];
  bfm_identity_t joint_attn_id[0:1], joint_mlp_id[0:1];
  semaphore joint_boundary_lock = new(1);
  integer joint_events_fd;

  task automatic joint_write(input bit [11:0] address, input bit [31:0] value);
    bfm_axil_write(address, value, 4'hf, 2'b00);
  endtask

  task automatic joint_wait(input bit [11:0] address, input bit [31:0] mask,
      input bit [31:0] expected_value);
    integer started;
    logic [31:0] value;
    started = bfm_core_cycles;
    do begin
      bfm_axil_read(address, value, 2'b00);
      if ((value & mask) === expected_value) return;
      bfm_check(bfm_core_cycles-started < JOINT_COMMAND_LIMIT,
        $sformatf("CSR wait timeout address=%03h actual=%08h mask=%08h expected=%08h",
          address,value,mask,expected_value));
      repeat (32) @(negedge core_clk);
    end while (1);
  endtask

  task automatic joint_wait_completion(input bit mlp);
    integer started;
    logic [31:0] value;
    started = bfm_core_cycles;
    do begin
      bfm_axil_read(mlp ? 12'h29c : 12'h00c, value, 2'b00);
      if (mlp ? value[0] === 1'b1 : (value & 6) != 0) return;
      bfm_check(bfm_core_cycles-started < JOINT_COMMAND_LIMIT, "full command completion timeout");
      repeat (32) @(negedge core_clk);
    end while (1);
  endtask

  task automatic joint_telemetry(input bit mlp, input bfm_identity_t id);
    integer fd, address;
    logic [31:0] value;
    string telemetry_kind;
    if (mlp) telemetry_kind = "mlp";
    else telemetry_kind = "attention";
    fd = $fopen($sformatf("%s/telemetry_%s_cohort%0d.csv", joint_report_dir,
      telemetry_kind, id.cohort_id), "w");
    bfm_check(fd != 0, "cannot open completion telemetry");
    $fdisplay(fd, "address,value,core_cycle,request,command,cohort,layer,buffer,bank,generation");
    for (address = mlp ? 'h180 : 'h038;
         address <= (mlp ? 'h240 : 'h06c); address = address + 4) begin
      bfm_axil_read(address[11:0], value, 2'b00);
      $fdisplay(fd, "%03h,%08h,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d", address, value,
        bfm_core_cycles,id.request_id,id.command_id,id.cohort_id,id.layer_id,id.buffer_id,id.bank,id.generation);
    end
    if (mlp) begin
      for (address = 'h244; address <= 'h2b4; address = address + 4) begin
        // Action/config offsets are readable; 0x24C through 0x2B4 is current ABI.
        bfm_axil_read(address[11:0], value, 2'b00);
        $fdisplay(fd, "%03h,%08h,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d", address, value,
          bfm_core_cycles,id.request_id,id.command_id,id.cohort_id,id.layer_id,id.buffer_id,id.bank,id.generation);
      end
      bfm_axil_read(12'h148, value, 2'b00);
      $fdisplay(fd, "148,%08h,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d", value,
        bfm_core_cycles,id.request_id,id.command_id,id.cohort_id,id.layer_id,id.buffer_id,id.bank,id.generation);
    end
    $fclose(fd);
  endtask

  // run -all returns on $stop. Tcl asks the persistent Host process to verify
  // the captured bytes and call the real public boundary op before resuming.
  task automatic joint_host_boundary(input bit mlp, input bfm_identity_t id, input integer output_plan);
    integer fd;
    string raw_name, raw_kind, stage_name;
    joint_boundary_lock.get(1);
    joint_boundary_index = joint_boundary_index + 1;
    if (mlp) begin
      raw_kind = "mlp";
      stage_name = "after_mlp";
    end else begin
      raw_kind = "attention";
      stage_name = "after_attention";
    end
    raw_name = $sformatf("raw_%s_cohort%0d.bin", raw_kind, id.cohort_id);
    bfm_dump_output(output_plan, {joint_report_dir,"/",raw_name});
    fd = $fopen($sformatf("%s/boundary_%0d.json", joint_report_dir,joint_boundary_index), "w");
    bfm_check(fd != 0, "cannot publish Host boundary");
    $fdisplay(fd, "{\"sequence\":%0d,\"stage\":\"%s\",\"raw\":\"%s\",\"request\":%0d,\"command\":%0d,\"cohort\":%0d,\"layer\":%0d,\"buffer\":%0d,\"bank\":%0d,\"generation\":%0d,\"core_cycle\":%0d}",
      joint_boundary_index,stage_name,raw_name,
      id.request_id,id.command_id,id.cohort_id,id.layer_id,id.buffer_id,id.bank,id.generation,bfm_core_cycles);
    $fclose(fd);
    $fflush(joint_events_fd); $fflush(bfm_trace_fd);
    $display("JOINT_BOUNDARY_READY %0d", joint_boundary_index);
    $stop;
    if (!mlp) bfm_load_image(0, BFM_MLP_INPUT, joint_mlp_id[id.cohort_id],
      $sformatf("%s/feedback_before_mlp_cohort%0d.bin",joint_report_dir,id.cohort_id));
    joint_boundary_lock.put(1);
  endtask

  task automatic joint_attention_start(input integer cohort, input bit reload);
    bfm_identity_t id;
    integer unused;
    id = joint_attn_id[cohort];
    if (reload) begin
      bfm_add_plan(0, BFM_ATTN_META, id, unused);
      bfm_add_plan(0, BFM_ROPE, id, unused);
    end
    bfm_add_plan(0, BFM_ATTN_INPUT, id, joint_attn_in[cohort]);
    bfm_add_plan(0, BFM_ATTN_OUTPUT, id, joint_attn_out[cohort]);
    bfm_add_plan(1, BFM_ATTN_WEIGHT, id, unused);
    bfm_add_plan(2, BFM_ATTN_WEIGHT, id, unused);
    bfm_load_image(0, BFM_ATTN_INPUT, id,
      $sformatf("%s/initial_before_attention_cohort%0d.bin",joint_report_dir,cohort));
    joint_wait(12'h00c, 7, 0);
    joint_write(12'h010, id.command_id); joint_write(12'h014, id.layer_id);
    joint_write(12'h018, 32'h00101000); // count16, keys16, position0, no history
    joint_write(12'h01c, 32'h48384103);
    joint_write(12'h020, bfm_kind_base(BFM_ATTN_INPUT,id));
    joint_write(12'h024, bfm_kind_base(BFM_ATTN_OUTPUT,id));
    joint_write(12'h028, bfm_kind_base(BFM_ATTN_WEIGHT,id));
    joint_write(12'h02c, bfm_kind_base(BFM_ATTN_WEIGHT,id));
    joint_write(12'h030, bfm_kind_base(BFM_ATTN_META,id));
    joint_write(12'h034, bfm_kind_base(BFM_ROPE,id));
    joint_write(12'h070, id.request_id);
    joint_write(12'h074, (id.buffer_id << 16) | id.cohort_id);
    $fdisplay(joint_events_fd, "attention_start,%0d,%0d,%0d,%0d",bfm_core_cycles,
      id.request_id,id.command_id,id.cohort_id);
    joint_write(12'h008, reload ? 13 : 1);
  endtask

  task automatic joint_attention_finish(input integer cohort);
    bfm_identity_t id;
    id = joint_attn_id[cohort];
    joint_wait_completion(0);
    joint_telemetry(0,id); // Save before any status/identity refusal or ACK.
    bfm_check_completion(0,id,0);
    bfm_check(integration_error === 1'b0, "Attention integration health not known zero");
    bfm_expect_register(12'h04c,0);
    bfm_expect_register(12'h03c,81920);
    bfm_expect_register(12'h040,640);
    bfm_expect_register(12'h044,512);
    bfm_expect_register(12'h048,256);
    bfm_check_plan(joint_attn_in[cohort]);
    bfm_check_plan(joint_attn_out[cohort]);
    joint_host_boundary(0,id,joint_attn_out[cohort]);
    joint_write(12'h008,2);
    joint_wait(12'h00c,6,0);
    $fdisplay(joint_events_fd, "attention_ack,%0d,%0d,%0d,%0d",bfm_core_cycles,
      id.request_id,id.command_id,id.cohort_id);
  endtask

  task automatic joint_load_mlp_metadata;
    bfm_identity_t id;
    integer gate_plan, down_plan;
    id = joint_mlp_id[0]; id.bank = 1;
    bfm_add_plan(0, BFM_GATE_META, id, gate_plan);
    bfm_add_plan(0, BFM_DOWN_META, id, down_plan);
    bfm_load_image(0,BFM_GATE_META,id,{joint_packet_dir,"/mlp_gate_meta.bin"});
    bfm_load_image(0,BFM_DOWN_META,id,{joint_packet_dir,"/mlp_down_meta.bin"});
    joint_write(12'h150,1);
    joint_write(12'h16c,bfm_kind_base(BFM_GATE_META,id));
    joint_write(12'h170,bfm_kind_base(BFM_DOWN_META,id));
    joint_write(12'h154,1);
    joint_wait(12'h14c,16,16);
    joint_wait(12'h178,20,0);
    bfm_expect_register(12'h160,229376);
    bfm_expect_register(12'h168,114688);
    bfm_check_plan(gate_plan); bfm_check_plan(down_plan);
    joint_write(12'h158,joint_layer+1); joint_write(12'h154,2);
    joint_wait(12'h114,'h700,'h500); // active bank1 and bank1 valid
    bfm_expect_register(12'h144,joint_layer+1);
  endtask

  task automatic joint_mlp_start(input integer cohort);
    bfm_identity_t id;
    integer unused, ready_started;
    logic [31:0] ready_status, dma_status, ready_mask;
    id = joint_mlp_id[cohort];
    joint_wait(12'h29c,3,0);
    bfm_add_plan(0, BFM_MLP_INPUT, id, joint_mlp_in[cohort]);
    bfm_add_plan(0, BFM_MLP_OUTPUT, id, joint_mlp_out[cohort]);
    bfm_add_plan(1,BFM_GATE_WEIGHT,id,unused); bfm_add_plan(2,BFM_GATE_WEIGHT,id,unused);
    bfm_add_plan(1,BFM_DOWN_WEIGHT,id,unused); bfm_add_plan(2,BFM_DOWN_WEIGHT,id,unused);
    joint_write(12'h118,id.command_id); joint_write(12'h11c,id.layer_id);
    joint_write(12'h120,32'h48384605);
    joint_write(12'h124,bfm_kind_base(BFM_MLP_INPUT,id));
    joint_write(12'h128,bfm_kind_base(BFM_MLP_OUTPUT,id));
    joint_write(12'h12c,bfm_kind_base(BFM_GATE_WEIGHT,id));
    joint_write(12'h130,bfm_kind_base(BFM_GATE_WEIGHT,id));
    joint_write(12'h134,bfm_kind_base(BFM_DOWN_WEIGHT,id));
    joint_write(12'h138,bfm_kind_base(BFM_DOWN_WEIGHT,id));
    joint_write(12'h13c,id.bank); joint_write(12'h140,id.generation);
    joint_write(12'h280,id.request_id);
    joint_write(12'h284,(id.buffer_id << 16)|id.cohort_id);
    joint_write(12'h174,1);
    joint_wait(12'h178,9,0);
    bfm_expect_register(12'h17c,6144); bfm_expect_register(12'h244,128);
    bfm_check_plan(joint_mlp_in[cohort]);
    ready_mask = 32'h40 << id.bank;
    ready_started = bfm_core_cycles;
    do begin
      bfm_axil_read(12'h178,dma_status,2'b00);
      bfm_axil_read(12'h114,ready_status,2'b00);
      bfm_check(integration_error === 1'b0,"MLP integration fault while waiting for activation bank");
      bfm_check(dma_status[3] === 1'b0,"MLP tensor DMA fault while waiting for activation bank");
      bfm_check((ready_status & 32'h1804) === 32'b0,
        $sformatf("MLP status fault while waiting for activation bank: %08h",ready_status));
      if ((ready_status & ready_mask) === ready_mask) break;
      bfm_check(bfm_core_cycles-ready_started < JOINT_COMMAND_LIMIT,
        $sformatf("MLP activation bank %0d readiness timeout: status=%08h",id.bank,ready_status));
      repeat (32) @(negedge core_clk);
    end while (1);
    joint_write(12'h174,2); joint_wait(12'h178,2,2);
    $fdisplay(joint_events_fd, "mlp_start,%0d,%0d,%0d,%0d",bfm_core_cycles,
      id.request_id,id.command_id,id.cohort_id);
    joint_write(12'h110,1);
  endtask

  task automatic joint_mlp_finish(input integer cohort);
    bfm_identity_t id;
    id = joint_mlp_id[cohort];
    joint_wait_completion(1);
    joint_telemetry(1,id);
    bfm_check_completion(1,id,0);
    bfm_check_healthy_mlp();
    bfm_check_plan(joint_mlp_out[cohort]);
    joint_host_boundary(1,id,joint_mlp_out[cohort]);
    joint_write(12'h2a0,id.command_id);
    joint_wait(12'h29c,1,0);
    $fdisplay(joint_events_fd, "mlp_ack,%0d,%0d,%0d,%0d",bfm_core_cycles,
      id.request_id,id.command_id,id.cohort_id);
  endtask

  always @(negedge core_clk) if (core_rst_n === 1'b1) begin
    bfm_check(bfm_core_cycles < JOINT_RUN_LIMIT,"whole joint run cycle timeout");
  end

  initial begin : joint_run
    integer cohort;
    logic [31:0] shared_count;
    bfm_identity_t id;
    bfm_check($value$plusargs("JOINT_PACKET_DIR=%s",joint_packet_dir),"missing immutable packet directory");
    bfm_check($value$plusargs("JOINT_REPORT_DIR=%s",joint_report_dir),"missing report directory");
    if ($value$plusargs("JOINT_LAYER=%d",joint_layer)) begin end
    bfm_check(joint_layer == 0,"first native candidate is exactly layer0, not a full-model claim");
    bfm_check(BFM_AXIL_LIMIT > 0 && BFM_CORE_PHASE_NS >= 0 &&
      BFM_DDR0_PHASE_NS >= 0 && BFM_DDR1_PHASE_NS >= 0,"invalid BFM limits/phases");
    bfm_open_trace({joint_report_dir,"/axi_trace.csv"});
    joint_events_fd = $fopen({joint_report_dir,"/command_events.csv"},"w");
    bfm_check(joint_events_fd != 0,"cannot open command events");
    $fdisplay(joint_events_fd,"event,core_cycle,request,command,cohort");
    for (cohort = 0; cohort < 2; cohort = cohort + 1) begin
      id = '0; id.request_id = 100+cohort; id.command_id = cohort == 0 ? 1 : 3;
      id.cohort_id = cohort; id.layer_id = joint_layer; id.buffer_id = cohort*3;
      joint_attn_id[cohort] = id;
      id.command_id = cohort == 0 ? 2 : 4;
      id.bank = id.buffer_id & 1; id.generation = joint_layer+1;
      joint_mlp_id[cohort] = id;
    end
    bfm_load_image(0,BFM_ATTN_META,joint_attn_id[0],{joint_packet_dir,"/attention_meta.bin"});
    bfm_load_image(0,BFM_ROPE,joint_attn_id[0],{joint_packet_dir,"/rope.bin"});
    for (integer bus = 1; bus <= 2; bus = bus + 1) begin
      bfm_load_image(bus,BFM_ATTN_WEIGHT,joint_attn_id[0],
        $sformatf("%s/attention_c%0d.bin",joint_packet_dir,bus-1));
      bfm_load_image(bus,BFM_GATE_WEIGHT,joint_mlp_id[0],
        $sformatf("%s/mlp_gate_up_c%0d.bin",joint_packet_dir,bus-1));
      bfm_load_image(bus,BFM_DOWN_WEIGHT,joint_mlp_id[0],
        $sformatf("%s/mlp_down_c%0d.bin",joint_packet_dir,bus-1));
    end
    bfm_release_reset();
    bfm_expect_register(12'h000,32'h48384103); bfm_expect_register(12'h004,32'h00020000);
    bfm_expect_register(12'h100,32'h48384605); bfm_expect_register(12'h104,32'h00050000);
    joint_wait(12'h10c,32,32); joint_write(12'h108,3); joint_wait(12'h10c,31,27);
    joint_attention_start(0,1); joint_attention_finish(0);
    joint_load_mlp_metadata(); joint_mlp_start(0); joint_attention_start(1,0);
    fork
      joint_mlp_finish(0);
      joint_attention_finish(1);
    join
    joint_mlp_start(1); joint_mlp_finish(1);
    joint_wait(12'h260,56,32);
    bfm_axil_read(12'h26c,shared_count,2'b00);
    bfm_check(shared_count != 0,"no jointly eligible paired work observed");
    for (integer bus = 1; bus <= 2; bus = bus + 1) begin
      bfm_check(bfm_ddr_overlap_edges[bus] > 0,
        $sformatf("no accepted concurrent outstanding Attention/MLP work DDR%0d",bus-1));
      bfm_check(bfm_ddr_overlap_attn[bus] === joint_attn_id[1] &&
        bfm_ddr_overlap_mlp[bus] === joint_mlp_id[0],
        $sformatf("accepted overlap has wrong command/cohort identity DDR%0d",bus-1));
    end
    bfm_check(joint_boundary_index == 4,"missing/duplicate Host boundary");
    bfm_check_drained();
    // Real public maintenance after success: no accepted response is discarded.
    @(negedge core_clk); core_clear = 1;
    @(negedge core_clk); core_clear = 0;
    joint_wait(12'h260,56,32);
    bfm_check(integration_error === 1'b0,"post-maintenance integration health not known zero");
    bfm_finish_transport(); $fclose(joint_events_fd);
    $display("JOINT_DIAGNOSTIC checks=%0d core_cycles=%0d boundaries=%0d eligible_cycles=%0d overlap_ddr0_edges=%0d overlap_ddr1_edges=%0d",
      bfm_checks,bfm_core_cycles,joint_boundary_index,shared_count,
      bfm_ddr_overlap_edges[1],bfm_ddr_overlap_edges[2]);
    $display("HARDWARE_AGENT_SIM_PASS");
    $finish;
  end
endmodule
