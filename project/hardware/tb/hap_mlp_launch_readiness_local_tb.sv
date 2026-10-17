`timescale 1ns / 1ps

// Focused launch diagnostic. All readiness, DMA, cache and command signals
// below come from production RTL; only metadata residency and owner admission
// are legal controller-boundary fixtures. Stop at the first command handshake.
module hap_mlp_launch_readiness_local_tb;
  localparam integer BEATS = 128*48;
  reg core_clk=0, ddr0_clk=0, ddr1_clk=0, rst_n=0;
  always #5 core_clk=~core_clk;
  initial begin #1.25; forever #2.5 ddr0_clk=~ddr0_clk; end
  initial begin #2.5; forever #2.5 ddr1_clk=~ddr1_clk; end
  integer cycle=0, case_id=0, selected_bank=0, gap_cycles=0;
  integer last_beat_cycle=-1, last_input_cycle=-1, last_rows_cycle=-1;
  integer last_cache_write_cycle=-1, ready_rise_cycle=-1;
  integer start_evals=0, command_fires=0, negative_refusals=0;
  integer positive_fires=0, negative_inconclusive=0;
  reg [1:0] previous_bank_ready=0;
  reg [7:0] tensor_bytes [0:196607];
  string tensor_path;
  integer tensor_fd, bytes_read;

  reg [11:0] awaddr=0, araddr=0;
  reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
  reg [31:0] wdata=0;
  reg [3:0] wstrb=4'hf;
  wire awready,wready,bvalid,arready,rvalid;
  wire [1:0] bresp,rresp;
  wire [31:0] rdata;

  wire command_valid,command_ready,command_bank,ctrl_clear;
  wire [31:0] gate0,gate1,down0,down1,input_base,output_base,command_id,layer_id;
  wire [1:0] bank_ready;
  wire wrapper_busy,wrapper_done,wrapper_error;
  wire [2:0] wrapper_phase;
  wire [31:0] frontend_group_count;
  wire tensor_load_valid,tensor_load_ready,tensor_store_valid,tensor_store_ready;
  wire tensor_store_armed,tensor_busy,tensor_done,tensor_load_done;
  wire tensor_store_done,tensor_axi_active,tensor_error;
  wire [2:0] tensor_phase;
  wire [31:0] input_beats,input_groups,output_beats,output_tiles;
  wire input_valid,input_ready,input_bank,output_valid,output_ready;
  wire [6:0] input_group;
  wire [12287:0] input_data;
  wire [7:0] output_tile;
  wire signed [8191:0] output_data;
  wire [31:0] meta_gate_base,meta_down_base;
  wire irq,done_sticky,error_sticky;
  wire owner_request_valid,owner_request_done,owner_switch_pending;
  wire [1:0] owner_request;
  wire meta_load_begin_valid,meta_load_bank,meta_commit_valid,meta_commit_bank;
  wire [31:0] meta_commit_generation;
  wire abort_pending;

  // A full-size legal tensor read BFM. The original saved feedback file is
  // loaded as bytes, never changed; 256-bit R payloads use AXI little lanes.
  wire d_arvalid,d_arready,d_rvalid,d_rready,d_rlast;
  wire [31:0] d_araddr;
  wire [7:0] d_arlen;
  wire [2:0] d_arsize;
  wire [1:0] d_arburst,d_rresp;
  reg [255:0] rdata_tensor;
  wire awvalid_data,awready_data,wvalid_data,wready_data,wlast_data;
  wire [31:0] awaddr_data,wstrb_data;
  wire [7:0] awlen_data;
  wire [2:0] awsize_data;
  wire [1:0] awburst_data,bresp_data;
  wire [255:0] wdata_data;
  wire bvalid_data,bready_data;
  reg read_active=0;
  reg rvalid_pending=0;
  integer read_index=0, burst_remaining=0;
  assign d_arready = rst_n && !read_active && cycle%5!=0;
  assign d_rvalid = read_active && rvalid_pending;
  assign d_rlast = burst_remaining==1;
  assign d_rresp = 2'b00;
  // Choose deterministic gaps only between transfers. Once offered, the
  // beat, its payload and RLAST remain asserted until the accepting edge.
  always @(posedge core_clk) begin
    if (!rst_n || !read_active) rvalid_pending <= 1'b0;
    else if (!rvalid_pending || d_rready)
      rvalid_pending <= cycle%7!=3;
  end
  assign awready_data=1'b0;
  assign wready_data=1'b0;
  assign bvalid_data=1'b0;
  assign bresp_data=2'b00;
  always @* for (integer lane=0;lane<32;lane=lane+1)
    rdata_tensor[lane*8+:8] = read_index<BEATS ?
      tensor_bytes[read_index*32+lane] : 8'h00;

  hap_mlp_tensor_dma_bridge u_tensor (
    .clk(core_clk),.rst_n(rst_n),.clear(1'b0),
    .load_valid(tensor_load_valid),.load_ready(tensor_load_ready),
    .load_bank(command_bank),.input_base_addr(input_base),
    .store_valid(tensor_store_valid),.store_ready(tensor_store_ready),
    .output_base_addr(output_base),.mlp_input_valid(input_valid),
    .mlp_input_ready(input_ready),.mlp_input_bank(input_bank),
    .mlp_input_group(input_group),.mlp_input_s24x16x32(input_data),
    .mlp_out_valid(output_valid),.mlp_out_ready(output_ready),
    .mlp_out_tile(output_tile),.mlp_out_s32x16x16(output_data),
    .busy(tensor_busy),.done(tensor_done),.load_done(tensor_load_done),
    .store_done(tensor_store_done),.store_armed(tensor_store_armed),
    .axi_active(tensor_axi_active),.error(tensor_error),.phase(tensor_phase),
    .input_beat_count(input_beats),.input_group_count(input_groups),
    .output_beat_count(output_beats),.output_tile_count(output_tiles),
    .m_axi_arvalid(d_arvalid),.m_axi_arready(d_arready),.m_axi_araddr(d_araddr),
    .m_axi_arlen(d_arlen),.m_axi_arsize(d_arsize),.m_axi_arburst(d_arburst),
    .m_axi_rvalid(d_rvalid),.m_axi_rready(d_rready),.m_axi_rdata(rdata_tensor),
    .m_axi_rresp(d_rresp),.m_axi_rlast(d_rlast),
    .m_axi_awvalid(awvalid_data),.m_axi_awready(awready_data),
    .m_axi_awaddr(awaddr_data),.m_axi_awlen(awlen_data),
    .m_axi_awsize(awsize_data),.m_axi_awburst(awburst_data),
    .m_axi_wvalid(wvalid_data),.m_axi_wready(wready_data),
    .m_axi_wdata(wdata_data),.m_axi_wstrb(wstrb_data),
    .m_axi_wlast(wlast_data),.m_axi_bvalid(bvalid_data),
    .m_axi_bready(bready_data),.m_axi_bresp(bresp_data));

  hap_mlp_full_command16_s54 u_wrapper (
    .core_clk(core_clk),.core_rst_n(rst_n),.core_clear(1'b0),
    .command_pause(1'b0),.weight_source_quiescent(),
    .input_valid(input_valid),.input_ready(input_ready),
    .input_bank(input_bank),.input_group(input_group),
    .input_s24x16x32(input_data),.input_bank_ready(bank_ready),
    .command_valid(command_valid),.command_ready(command_ready),
    .command_bank(command_bank),.gate_ddr0_base_addr(gate0),
    .gate_ddr1_base_addr(gate1),.down_ddr0_base_addr(down0),
    .down_ddr1_base_addr(down1),.gate_meta_valid(1'b0),
    .gate_meta_ready(),.gate_meta_u224(224'd0),
    .down_meta_valid(1'b0),.down_meta_ready(),.down_meta_u224(224'd0),
    .ddr0_clk(ddr0_clk),.ddr0_rst_n(rst_n),
    .ddr0_axi_arvalid(),.ddr0_axi_arready(1'b0),
    .ddr0_axi_araddr(),.ddr0_axi_arlen(),.ddr0_axi_arsize(),
    .ddr0_axi_arburst(),.ddr0_axi_rvalid(1'b0),
    .ddr0_axi_rready(),.ddr0_axi_rdata(512'd0),
    .ddr0_axi_rresp(2'b00),.ddr0_axi_rlast(1'b0),
    .ddr1_clk(ddr1_clk),.ddr1_rst_n(rst_n),
    .ddr1_axi_arvalid(),.ddr1_axi_arready(1'b0),
    .ddr1_axi_araddr(),.ddr1_axi_arlen(),.ddr1_axi_arsize(),
    .ddr1_axi_arburst(),.ddr1_axi_rvalid(1'b0),
    .ddr1_axi_rready(),.ddr1_axi_rdata(512'd0),
    .ddr1_axi_rresp(2'b00),.ddr1_axi_rlast(1'b0),
    .out_valid(output_valid),.out_ready(output_ready),
    .out_tile_index(output_tile),.projection_s32x16x16(output_data),
    .busy(wrapper_busy),.done(wrapper_done),.error(wrapper_error),
    .phase(wrapper_phase),.input_group_count(frontend_group_count));

  hap_mlp_axil_control #(.PRODUCTION_INTEGRATION(1)) u_ctrl (
    .clk(core_clk),.rst_n(rst_n),
    .s_axil_awaddr(awaddr),.s_axil_awvalid(awvalid),.s_axil_awready(awready),
    .s_axil_wdata(wdata),.s_axil_wstrb(wstrb),.s_axil_wvalid(wvalid),
    .s_axil_wready(wready),.s_axil_bresp(bresp),.s_axil_bvalid(bvalid),
    .s_axil_bready(bready),.s_axil_araddr(araddr),.s_axil_arvalid(arvalid),
    .s_axil_arready(arready),.s_axil_rdata(rdata),.s_axil_rresp(rresp),
    .s_axil_rvalid(rvalid),.s_axil_rready(rready),
    .owner_request_valid(owner_request_valid),.owner_request_ready(1'b1),
    .admission_pause(1'b0),.owner_request(owner_request),
    .owner_request_done(1'b0),.active_owner(2'd2),
    .owner_switch_pending(1'b0),.attention_launch_enable(1'b0),
    .mlp_launch_enable(1'b1),.owner_protocol_error(1'b0),
    .ddr0_outstanding(8'd0),.ddr1_outstanding(8'd0),
    .maintenance_busy(1'b0),.maintenance_request_pending(1'b0),
    .mlp_abort_complete(1'b0),.paired_quiescent(1'b1),
    .paired_attn_bursts(32'd0),.paired_mlp_bursts(32'd0),
    .paired_both_cycles(32'd0),.paired_hol0(32'd0),.paired_hol1(32'd0),
    .paired_hwm0(32'd0),.paired_hwm1(32'd0),
    .mlp_command_valid(command_valid),.mlp_command_ready(command_ready),
    .mlp_clear_pulse(ctrl_clear),.mlp_abort_pending(abort_pending),
    .mlp_command_bank(command_bank),
    .mlp_gate_ddr0_base_addr(gate0),.mlp_gate_ddr1_base_addr(gate1),
    .mlp_down_ddr0_base_addr(down0),.mlp_down_ddr1_base_addr(down1),
    .mlp_input_base_addr(input_base),.mlp_output_base_addr(output_base),
    .mlp_command_id(command_id),.mlp_layer_id(layer_id),
    .mlp_input_bank_ready(bank_ready),.mlp_busy(wrapper_busy),
    .mlp_done(wrapper_done),.mlp_error(wrapper_error),
    .mlp_phase(wrapper_phase),.mlp_telemetry(1568'd0),
    .mlp_down_output_saturation_count(32'd0),
    .mlp_total_shift_format_count(32'd0),.mlp_numeric_status(32'd0),
    .tensor_load_valid(tensor_load_valid),.tensor_load_ready(tensor_load_ready),
    .tensor_store_valid(tensor_store_valid),.tensor_store_ready(tensor_store_ready),
    .tensor_store_armed(tensor_store_armed),.tensor_dma_busy(tensor_busy),
    .tensor_dma_done(tensor_done),.tensor_dma_error(tensor_error),
    .tensor_dma_phase(tensor_phase),.tensor_input_beat_count(input_beats),
    .tensor_input_group_count(input_groups),.tensor_output_beat_count(output_beats),
    .tensor_output_tile_count(output_tiles),
    .meta_gate_base_addr(meta_gate_base),.meta_down_base_addr(meta_down_base),
    .meta_dma_busy(1'b0),.meta_dma_done(1'b0),.meta_dma_error(1'b0),
    .meta_dma_phase(3'd0),.meta_dma_gate_record_count(32'd0),
    .meta_dma_down_record_count(32'd0),.meta_dma_physical_bytes(64'd0),
    .meta_load_begin_valid(meta_load_begin_valid),.meta_load_begin_ready(1'b0),
    .meta_load_bank(meta_load_bank),.meta_commit_valid(meta_commit_valid),
    .meta_commit_ready(1'b0),.meta_commit_bank(meta_commit_bank),
    .meta_commit_generation(meta_commit_generation),
    .meta_active_bank(1'b1),.meta_active_generation(32'd1),
    .meta_bank_valid(2'b10),.meta_bank_loading(2'b00),
    .meta_gate_write_count_bank0(32'd0),.meta_gate_write_count_bank1(32'd0),
    .meta_down_write_count_bank0(32'd0),.meta_down_write_count_bank1(32'd0),
    .meta_error(1'b0),.irq(irq),.done_sticky(done_sticky),
    .error_sticky(error_sticky));

  task automatic check(input bit condition,input string message);
    if (!condition) begin $display("LOCAL_FAIL %s cycle=%0d time=%0t",message,cycle,$time); $fatal(1); end
  endtask

  // Sample protocol edges before NBA; sample the idle/readiness gap at the
  // falling edge, after the DUT's sequential state has settled.
  always @(posedge core_clk) begin
    cycle <= cycle+1;
    if (rst_n) begin
      if (cycle>200000) begin $display("LOCAL_FAIL watchdog case=%0d",case_id); $fatal(1); end
      if (d_arvalid && d_arready) begin
        check(d_arsize===3'd5 && d_arburst===2'b01,
          "tensor AR size/burst");
        check(d_araddr===input_base+read_index*32 &&
              read_index+d_arlen+1<=BEATS,"tensor AR address/length");
        read_active <= 1'b1;
        burst_remaining <= d_arlen+1;
      end
      if (d_rvalid && d_rready) begin
        if (read_index==BEATS-1) begin
          last_beat_cycle <= cycle;
          $display("LOCAL_EVENT case=%0d final_axi_beat cycle=%0d time=%0t",case_id,cycle,$time);
        end
        read_index <= read_index+1;
        burst_remaining <= burst_remaining-1;
        if (burst_remaining==1) read_active<=1'b0;
      end
      if (input_valid && input_ready && input_group==7'd127) begin
        last_input_cycle<=cycle;
        $display("LOCAL_EVENT case=%0d final_frontend_in_fire cycle=%0d time=%0t",case_id,cycle,$time);
      end
      if (u_wrapper.u_input_frontend.completed_row_count_r==16 &&
          u_wrapper.u_input_frontend.active_group_r==7'd127 && last_rows_cycle<0) begin
        last_rows_cycle<=cycle;
        $display("LOCAL_EVENT case=%0d completed_rows16 cycle=%0d time=%0t",case_id,cycle,$time);
      end
      if (u_wrapper.u_input_frontend.cache_write_fire &&
          u_wrapper.u_input_frontend.active_group_r==7'd127) begin
        last_cache_write_cycle<=cycle;
        $display("LOCAL_EVENT case=%0d final_cache_write cycle=%0d time=%0t",case_id,cycle,$time);
      end
      if (u_ctrl.write_execute && u_ctrl.awaddr_r==12'h110 && u_ctrl.wdata_r[0]) begin
        start_evals<=start_evals+1;
        $display("LOCAL_EVENT case=%0d start_evaluate cycle=%0d time=%0t selected_ready=%b config_valid=%b armed=%b owner=%0d meta_valid=%b gen=%0d",
          case_id,cycle,$time,bank_ready[selected_bank],u_ctrl.command_config_valid,
          tensor_store_armed,2'd2,2'b10,32'd1);
        check(tensor_store_armed===1'b1 && tensor_error===1'b0 &&
              wrapper_error===1'b0 && input_beats===BEATS &&
              input_groups===128 && u_ctrl.run_format_id_r===32'h48384605 &&
              u_ctrl.active_owner===2'd2 && u_ctrl.mlp_launch_enable===1'b1 &&
              u_ctrl.admission_pause===1'b0 && wrapper_busy===1'b0 &&
              u_ctrl.command_active_r===1'b0 &&
              u_ctrl.completion_valid_r===1'b0 &&
              u_ctrl.command_source_error===1'b0 &&
              u_ctrl.meta_bank_valid[u_ctrl.meta_active_bank]===1'b1 &&
              u_ctrl.meta_active_generation===u_ctrl.expected_meta_generation_r &&
              u_ctrl.expected_meta_generation_r===32'd1 &&
              u_ctrl.mlp_layer_id[31:5]===0 &&
              u_ctrl.mlp_input_base_addr[4:0]===0 &&
              u_ctrl.mlp_output_base_addr[4:0]===0 &&
              u_ctrl.mlp_gate_ddr0_base_addr[9:0]===0 &&
              u_ctrl.mlp_gate_ddr1_base_addr[9:0]===0 &&
              u_ctrl.mlp_down_ddr0_base_addr[9:0]===0 &&
              u_ctrl.mlp_down_ddr1_base_addr[9:0]===0 &&
              u_wrapper.state_r===3'd0 && command_bank===selected_bank &&
              u_ctrl.error_sticky_r===1'b0,
              "start fixture other predicates illegal");
        if (case_id==0) begin
          if (bank_ready[selected_bank]===1'b0) begin
            check(u_ctrl.command_config_valid===1'b0,
              "old start config must refuse only unready bank");
            negative_refusals<=negative_refusals+1;
          end else negative_inconclusive<=1;
        end else check(bank_ready[selected_bank]===1'b1 &&
                       u_ctrl.command_config_valid===1'b1,
                       "corrected start not ready/configured");
      end
      if (command_valid && command_ready) begin
        command_fires<=command_fires+1;
        $display("LOCAL_EVENT case=%0d command_fire cycle=%0d time=%0t bank=%0d ready=%b",
          case_id,cycle,$time,command_bank,bank_ready[command_bank]);
        check(case_id!=0 || negative_inconclusive,
          "old refused start unexpectedly fired");
        check(bank_ready[command_bank]===1'b1,"command fired without real bank readiness");
        if (case_id!=0) positive_fires<=positive_fires+1;
      end
    end
  end

  always @(negedge core_clk) if (rst_n) begin
    if (input_beats==BEATS && input_groups==128 && !tensor_busy &&
        bank_ready[selected_bank]===1'b0) gap_cycles=gap_cycles+1;
    if (bank_ready[selected_bank]===1'b1 &&
        previous_bank_ready[selected_bank]===1'b0) begin
      ready_rise_cycle=cycle;
      $display("LOCAL_EVENT case=%0d bank_ready_rise cycle=%0d time=%0t bank=%0d",
        case_id,cycle,$time,selected_bank);
    end
    previous_bank_ready=bank_ready;
    if (case_id!=0 && bank_ready[selected_bank]===1'b0) begin
      check(start_evals==0 && command_fires==0,
        "corrected caller started during unready gap");
    end
  end

  task automatic write_csr(input reg [11:0] address,
                           input reg [31:0] value,output reg [1:0] response);
    integer started;
    started=cycle;
    @(negedge core_clk);
    awaddr=address;wdata=value;wstrb=4'hf;awvalid=1;wvalid=1;
    do @(posedge core_clk); while (!(awready && wready));
    @(negedge core_clk);awvalid=0;wvalid=0;
    while (bvalid!==1'b1) begin
      check(cycle-started<200,"AXIL B timeout");
      @(negedge core_clk);
    end
    response=bresp;
    bready=1;
    @(negedge core_clk);bready=0;
    $display("LOCAL_EVENT case=%0d axil_write addr=%03h value=%08h bresp=%0d cycle=%0d",
      case_id,address,value,response,cycle);
  endtask

  task automatic write_ok(input reg [11:0] address,input reg [31:0] value);
    reg [1:0] response;
    write_csr(address,value,response);
    check(response===2'b00,$sformatf("AXIL write %03h refused",address));
  endtask

  task automatic read_csr(input reg [11:0] address,output reg [31:0] value);
    integer started;
    started=cycle;
    @(negedge core_clk); araddr=address; arvalid=1;
    do @(posedge core_clk); while (!arready);
    @(negedge core_clk); arvalid=0;
    while (rvalid!==1'b1) begin
      check(cycle-started<200,"AXIL R timeout");
      @(negedge core_clk);
    end
    check(rresp===2'b00,$sformatf("AXIL read %03h refused",address));
    value=rdata;rready=1;
    @(negedge core_clk);rready=0;
    if (address==12'h114 && value[6+selected_bank]===1'b1)
      $display("LOCAL_EVENT case=%0d csr_selected_ready cycle=%0d time=%0t status=%08h",
        case_id,cycle,$time,value);
  endtask

  task automatic reset_case(input integer new_case,input integer new_bank);
    rst_n=0;
    awvalid=0;wvalid=0;bready=0;arvalid=0;rready=0;
    case_id=new_case;selected_bank=new_bank;
    read_active=0;read_index=0;burst_remaining=0;
    gap_cycles=0;last_beat_cycle=-1;last_input_cycle=-1;
    last_rows_cycle=-1;last_cache_write_cycle=-1;ready_rise_cycle=-1;
    start_evals=0;command_fires=0;negative_inconclusive=0;
    previous_bank_ready=0;cycle=0;
    repeat(12) @(negedge core_clk);
    rst_n=1;
    repeat(3) @(negedge core_clk);
  endtask

  task automatic run_case(input integer which,input integer bank);
    reg [31:0] status,dma;
    reg [1:0] start_response;
    integer started;
    reset_case(which,bank);
    // Metadata bank1 valid at generation1 and owner MLP admitted are fixture
    // inputs; all command control and readiness remain the actual RTL.
    write_ok(12'h118,32'd2+which);
    write_ok(12'h11c,32'd0);
    write_ok(12'h120,32'h48384605);
    write_ok(12'h124,bank ? 32'h7c300000 : 32'h7c000000);
    write_ok(12'h128,bank ? 32'h7c300000 : 32'h7c000000);
    write_ok(12'h12c,32'h01400000);write_ok(12'h130,32'h02000000);
    write_ok(12'h134,32'h03000000);write_ok(12'h138,32'h04000000);
    write_ok(12'h13c,bank);write_ok(12'h140,32'd1);
    write_ok(12'h280,32'd100+which);write_ok(12'h284,bank<<16);
    write_ok(12'h174,32'd1);
    started=cycle;
    do begin
      read_csr(12'h178,dma);
      check(dma[3]===1'b0,"tensor DMA error before store arm");
      check(cycle-started<200000,"tensor DMA load timeout");
    end while (dma[0]!==1'b0);
    read_csr(12'h17c,status);check(status===BEATS,"input beat count");
    read_csr(12'h244,status);check(status===128,"input group count");
    check(read_index==BEATS && last_beat_cycle>=0 && last_input_cycle>=0,
      "missing full real tensor transfer");
    if (which!=0) begin
      started=cycle;
      do begin
        read_csr(12'h178,dma);
        read_csr(12'h114,status);
        check(dma[3]===1'b0 && (status & 32'h1804)===32'd0,
          "health while waiting selected bank");
        check(cycle-started<200000,"selected bank timeout");
      end while (status[6+bank]!==1'b1);
    end
    write_ok(12'h174,32'd2);
    started=cycle;
    do begin
      read_csr(12'h178,dma);
      check(cycle-started<200,"store arm timeout");
    end while (dma[1]!==1'b1);
    write_csr(12'h110,32'd1,start_response);
    repeat(2) @(negedge core_clk);
    check(start_evals==1,"start evaluation count");
    if (which==0) begin
      if (negative_inconclusive) begin
        check(start_response===2'b00,"late old start response");
        $display("LOCAL_INCONCLUSIVE old_start_ready_before_evaluation");
      end else begin
        check(start_response===2'b10 && negative_refusals==1 &&
              command_fires==0 && error_sticky===1'b1 && irq===1'b1,
              "old early start refusal/diagnostic");
        read_csr(12'h2a0,status);
        check(status===32'd1,"old refusal idle diagnostic");
        read_csr(12'h148,status);
        check(status===32'h00000100,"old refusal error code");
        read_csr(12'h114,status);
        $display("LOCAL_NEGATIVE_PROVED gap_cycles=%0d",gap_cycles);
      end
    end else begin
      check(start_response===2'b00 && command_fires==1 &&
            positive_fires==which && bank_ready[bank]===1'b1 &&
            !error_sticky && !tensor_error && !wrapper_error,
            "corrected launch acceptance");
      check(gap_cycles>0 && last_rows_cycle>=0 &&
            last_cache_write_cycle>=0 && ready_rise_cycle>=0,
            "real final-group readiness gap/events missing");
      $display("LOCAL_POSITIVE_PROVED bank=%0d gap_cycles=%0d final_beat=%0d in_fire=%0d rows=%0d cache_write=%0d ready_rise=%0d",
        bank,gap_cycles,last_beat_cycle,last_input_cycle,last_rows_cycle,
        last_cache_write_cycle,ready_rise_cycle);
    end
  endtask

  initial begin
    check($value$plusargs("TENSOR_FILE=%s",tensor_path),"missing TENSOR_FILE");
    tensor_fd=$fopen(tensor_path,"rb");
    check(tensor_fd!=0,"cannot open saved feedback tensor");
    bytes_read=$fread(tensor_bytes,tensor_fd);
    $fclose(tensor_fd);
    check(bytes_read==196608,"saved feedback tensor length");
    $display("LOCAL_FIXTURE tensor_bytes=%0d metadata_bank=1 generation=1 owner=MLP core100 ddr200/200",bytes_read);
    run_case(0,0);
    run_case(1,0);
    run_case(2,1);
    $display("LOCAL_DONE negative_refusals=%0d negative_inconclusive=%0d corrected_bank0_bank1_fires=%0d",negative_refusals,negative_inconclusive,positive_fires);
    $finish;
  end
endmodule
