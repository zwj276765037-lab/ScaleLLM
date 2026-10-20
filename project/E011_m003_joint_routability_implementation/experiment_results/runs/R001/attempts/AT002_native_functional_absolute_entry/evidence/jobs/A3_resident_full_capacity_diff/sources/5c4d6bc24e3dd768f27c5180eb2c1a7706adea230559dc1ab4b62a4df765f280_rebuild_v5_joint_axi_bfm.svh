// Include once inside a 1ns/1ps testbench module. Instantiate the production
// core with `REBUILD_V5_JOINT_PORTS; this file contains no DUT or numeric oracle.
parameter realtime BFM_CORE_PHASE_NS = 1.125;
parameter realtime BFM_DDR0_PHASE_NS = 0.625;
parameter realtime BFM_DDR1_PHASE_NS = 2.375;
parameter integer BFM_AXIL_LIMIT = 256;
localparam integer BFM_QUEUE_DEPTH = 64;
localparam integer BFM_MAX_PLANS = 64;
localparam integer BFM_ATTN_INPUT = 1, BFM_ATTN_OUTPUT = 2;
localparam integer BFM_MLP_INPUT = 3, BFM_MLP_OUTPUT = 4;
localparam integer BFM_ATTN_META = 5, BFM_ROPE = 6;
localparam integer BFM_GATE_META = 7, BFM_DOWN_META = 8;
localparam integer BFM_ATTN_WEIGHT = 9, BFM_GATE_WEIGHT = 10;
localparam integer BFM_DOWN_WEIGHT = 11;

reg core_clk = 0, ddr0_clk = 0, ddr1_clk = 0;
reg core_rst_n = 0, ddr0_rst_n = 0, ddr1_rst_n = 0, core_clear = 0;
initial begin #(BFM_CORE_PHASE_NS); forever #5.0 core_clk = ~core_clk; end
initial begin #(BFM_DDR0_PHASE_NS); forever #2.5 ddr0_clk = ~ddr0_clk; end
initial begin #(BFM_DDR1_PHASE_NS); forever #2.5 ddr1_clk = ~ddr1_clk; end

reg [11:0] ctrl_awaddr = 0, ctrl_araddr = 0;
reg ctrl_awvalid = 0, ctrl_wvalid = 0, ctrl_bready = 0;
reg ctrl_arvalid = 0, ctrl_rready = 0;
reg [31:0] ctrl_wdata = 0;
reg [3:0] ctrl_wstrb = 0;
wire ctrl_awready, ctrl_wready, ctrl_bvalid, ctrl_arready, ctrl_rvalid;
wire [1:0] ctrl_bresp, ctrl_rresp;
wire [31:0] ctrl_rdata;
wire data_axi_arvalid, data_axi_arready, data_axi_rvalid, data_axi_rready;
wire [31:0] data_axi_araddr, data_axi_awaddr;
wire [7:0] data_axi_arlen, data_axi_awlen;
wire [2:0] data_axi_arsize, data_axi_awsize;
wire [1:0] data_axi_arburst, data_axi_awburst, data_axi_rresp;
wire [255:0] data_axi_rdata, data_axi_wdata;
wire data_axi_rlast, data_axi_awvalid, data_axi_wvalid;
wire data_axi_awready, data_axi_wready, data_axi_wlast, data_axi_bready;
wire [31:0] data_axi_wstrb;
reg data_axi_bvalid = 0;
wire [1:0] data_axi_bresp = 2'b00;
wire ddr0_axi_arvalid, ddr0_axi_arready, ddr0_axi_rvalid, ddr0_axi_rready;
wire ddr1_axi_arvalid, ddr1_axi_arready, ddr1_axi_rvalid, ddr1_axi_rready;
wire [31:0] ddr0_axi_araddr, ddr1_axi_araddr;
wire [7:0] ddr0_axi_arlen, ddr1_axi_arlen;
wire [2:0] ddr0_axi_arsize, ddr1_axi_arsize;
wire [1:0] ddr0_axi_arburst, ddr1_axi_arburst;
wire [511:0] ddr0_axi_rdata, ddr1_axi_rdata;
wire [1:0] ddr0_axi_rresp, ddr1_axi_rresp;
wire ddr0_axi_rlast, ddr1_axi_rlast;
wire attention_irq, mlp_irq, integration_error;

`define REBUILD_V5_JOINT_PORTS \
 .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(core_clear), \
 .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n), \
 .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n), \
 .ctrl_awaddr(ctrl_awaddr), .ctrl_awvalid(ctrl_awvalid), .ctrl_awready(ctrl_awready), \
 .ctrl_wdata(ctrl_wdata), .ctrl_wstrb(ctrl_wstrb), .ctrl_wvalid(ctrl_wvalid), \
 .ctrl_wready(ctrl_wready), .ctrl_bresp(ctrl_bresp), .ctrl_bvalid(ctrl_bvalid), \
 .ctrl_bready(ctrl_bready), .ctrl_araddr(ctrl_araddr), .ctrl_arvalid(ctrl_arvalid), \
 .ctrl_arready(ctrl_arready), .ctrl_rdata(ctrl_rdata), .ctrl_rresp(ctrl_rresp), \
 .ctrl_rvalid(ctrl_rvalid), .ctrl_rready(ctrl_rready), \
 .data_axi_arvalid(data_axi_arvalid), .data_axi_arready(data_axi_arready), \
 .data_axi_araddr(data_axi_araddr), .data_axi_arlen(data_axi_arlen), \
 .data_axi_arsize(data_axi_arsize), .data_axi_arburst(data_axi_arburst), \
 .data_axi_rvalid(data_axi_rvalid), .data_axi_rready(data_axi_rready), \
 .data_axi_rdata(data_axi_rdata), .data_axi_rresp(data_axi_rresp), .data_axi_rlast(data_axi_rlast), \
 .data_axi_awvalid(data_axi_awvalid), .data_axi_awready(data_axi_awready), \
 .data_axi_awaddr(data_axi_awaddr), .data_axi_awlen(data_axi_awlen), \
 .data_axi_awsize(data_axi_awsize), .data_axi_awburst(data_axi_awburst), \
 .data_axi_wvalid(data_axi_wvalid), .data_axi_wready(data_axi_wready), \
 .data_axi_wdata(data_axi_wdata), .data_axi_wstrb(data_axi_wstrb), .data_axi_wlast(data_axi_wlast), \
 .data_axi_bvalid(data_axi_bvalid), .data_axi_bready(data_axi_bready), .data_axi_bresp(data_axi_bresp), \
 .ddr0_axi_arvalid(ddr0_axi_arvalid), .ddr0_axi_arready(ddr0_axi_arready), \
 .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen), \
 .ddr0_axi_arsize(ddr0_axi_arsize), .ddr0_axi_arburst(ddr0_axi_arburst), \
 .ddr0_axi_rvalid(ddr0_axi_rvalid), .ddr0_axi_rready(ddr0_axi_rready), \
 .ddr0_axi_rdata(ddr0_axi_rdata), .ddr0_axi_rresp(ddr0_axi_rresp), .ddr0_axi_rlast(ddr0_axi_rlast), \
 .ddr1_axi_arvalid(ddr1_axi_arvalid), .ddr1_axi_arready(ddr1_axi_arready), \
 .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen), \
 .ddr1_axi_arsize(ddr1_axi_arsize), .ddr1_axi_arburst(ddr1_axi_arburst), \
 .ddr1_axi_rvalid(ddr1_axi_rvalid), .ddr1_axi_rready(ddr1_axi_rready), \
 .ddr1_axi_rdata(ddr1_axi_rdata), .ddr1_axi_rresp(ddr1_axi_rresp), .ddr1_axi_rlast(ddr1_axi_rlast), \
 .attention_irq(attention_irq), .mlp_irq(mlp_irq), .integration_error(integration_error)

typedef struct packed {
  bit [31:0] request_id, command_id, cohort_id, layer_id, buffer_id, bank, generation;
} bfm_identity_t;
typedef struct {
  integer bus, kind;
  bit write_transfer;
  bit [31:0] base;
  bfm_identity_t identity;
  integer beats, issued, delivered, bursts, retired;
} bfm_plan_t;
typedef struct packed {
  bit [31:0] address;
  integer beats, plan;
} bfm_descriptor_t;
typedef bfm_descriptor_t bfm_descriptor_queue_t[$];
bfm_plan_t bfm_plans [0:BFM_MAX_PLANS-1];
integer bfm_plan_count = 0, bfm_trace_fd = 0;
longint signed bfm_checks = 0;
integer bfm_core_cycles = 0, bfm_axil_sequence = 0, bfm_pair_checked = 0;
integer bfm_ddr_overlap_edges [0:2];
integer bfm_read_head [0:2], bfm_read_tail [0:2];
bfm_identity_t bfm_ddr_overlap_attn [0:2], bfm_ddr_overlap_mlp [0:2];
bit bfm_reset_released = 0;
bit bfm_first_ar_seen = 0, bfm_first_ar_active = 0;
semaphore bfm_axil_lock = new(1);
reg [255:0] bfm_data_image [bit [31:0]];
reg [511:0] bfm_ddr0_image [bit [31:0]];
reg [511:0] bfm_ddr1_image [bit [31:0]];
bfm_descriptor_queue_t bfm_ddr_history [0:1];

task automatic bfm_check(input logic condition, input string message);
  bfm_checks = bfm_checks + 1;
  if (condition !== 1'b1) $fatal(1, "FAIL joint_bfm: %s", message);
endtask

function automatic integer bfm_kind_bytes(input integer kind);
  case (kind)
    BFM_ATTN_INPUT, BFM_ATTN_OUTPUT, BFM_MLP_INPUT: return 196608;
    BFM_MLP_OUTPUT: return 262144;
    BFM_ATTN_META: return 2621440;
    BFM_ROPE: return 8192;
    BFM_GATE_META: return 7340032;
    BFM_DOWN_META: return 3670016;
    BFM_ATTN_WEIGHT: return 20971520;
    BFM_GATE_WEIGHT: return 29360128;
    BFM_DOWN_WEIGHT: return 14680064;
    default: $fatal(1, "FAIL unknown transfer kind %0d", kind);
  endcase
endfunction

function automatic bit [31:0] bfm_kind_base(input integer kind, input bfm_identity_t id);
  case (kind)
    BFM_ATTN_INPUT, BFM_ATTN_OUTPUT, BFM_MLP_INPUT, BFM_MLP_OUTPUT:
      return 32'h7c000000 + id.buffer_id * 1048576;
    BFM_ATTN_META: return 32'h7c800000 + (id.layer_id & 1) * 4194304;
    BFM_ROPE: return 32'h7e800000;
    BFM_GATE_META: return 32'h7d000000 + id.bank * 12582912;
    BFM_DOWN_META: return 32'h7d700000 + id.bank * 12582912;
    BFM_ATTN_WEIGHT: return id.layer_id * 65011712;
    BFM_GATE_WEIGHT: return id.layer_id * 65011712 + 20971520;
    BFM_DOWN_WEIGHT: return id.layer_id * 65011712 + 50331648;
    default: $fatal(1, "FAIL unknown transfer base kind %0d", kind);
  endcase
endfunction

task automatic bfm_open_trace(input string path);
  bfm_check(bfm_trace_fd == 0, "trace already open");
  bfm_trace_fd = $fopen(path, "w");
  bfm_check(bfm_trace_fd != 0, $sformatf("cannot open trace %s", path));
  $fdisplay(bfm_trace_fd,
    "bus,event,sequence,address,beats,beat,payload,strobe,last,kind,request,command,cohort,layer,buffer,bank,generation");
endtask

task automatic bfm_trace(input string bus, input string event_name,
    input integer sequence_index, input bit [31:0] address,
    input integer beats, input integer beat, input logic [511:0] payload,
    input bit [31:0] strobe, input bit last, input integer kind,
    input bfm_identity_t id);
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=task_body sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=trace_fd_check sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  bfm_check(bfm_trace_fd != 0, "open a report trace before bus activity");
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=trace_fd_check sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=trace_payload_check sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  bfm_check(!$isunknown(payload), "unknown trace payload");
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=trace_payload_check sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=row_write sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  $fdisplay(bfm_trace_fd, "%s,%s,%0d,%08h,%0d,%0d,%0h,%08h,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
    bus, event_name, sequence_index, address, beats, beat, payload, strobe, last,
    kind, id.request_id, id.command_id, id.cohort_id, id.layer_id,
    id.buffer_id, id.bank, id.generation);
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=row_write sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
  if (bfm_first_ar_active)
    $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=task_body sequence=%0d address=%08h time=%0t",
      sequence_index, address, $realtime);
endtask

task automatic bfm_add_plan(input integer bus, input integer kind,
    input bfm_identity_t id, output integer plan);
  bfm_check(bfm_plan_count < BFM_MAX_PLANS, "transfer plan capacity exceeded");
  bfm_check(bus >= 0 && bus <= 2 && id.layer_id < 32 && id.buffer_id < 6 &&
    id.cohort_id < 65536 && id.bank < 2, "invalid public transfer identity");
  bfm_check((bus == 0 && kind >= BFM_ATTN_INPUT && kind <= BFM_DOWN_META) ||
    (bus != 0 && kind >= BFM_ATTN_WEIGHT && kind <= BFM_DOWN_WEIGHT),
    "transfer kind does not belong to this public bus");
  if (kind == BFM_MLP_INPUT || kind == BFM_MLP_OUTPUT || kind == BFM_GATE_META ||
      kind == BFM_DOWN_META || kind == BFM_GATE_WEIGHT || kind == BFM_DOWN_WEIGHT)
    bfm_check(id.generation == id.layer_id+1, "MLP generation does not match layer");
  plan = bfm_plan_count;
  bfm_plan_count = bfm_plan_count + 1;
  bfm_plans[plan].bus = bus;
  bfm_plans[plan].kind = kind;
  bfm_plans[plan].write_transfer = kind == BFM_ATTN_OUTPUT || kind == BFM_MLP_OUTPUT;
  bfm_plans[plan].base = bfm_kind_base(kind, id);
  bfm_plans[plan].identity = id;
  bfm_plans[plan].beats = bfm_kind_bytes(kind) / (bus == 0 ? 32 : 64);
  bfm_plans[plan].issued = 0;
  bfm_plans[plan].delivered = 0;
  bfm_plans[plan].bursts = 0;
  bfm_plans[plan].retired = 0;
endtask

// File images are immutable inputs. Reload only the environment memory at a
// reviewed, drained Host rendezvous; never clear an accepted AXI transaction.
task automatic bfm_load_image(input integer bus, input integer kind,
    input bfm_identity_t id, input string path);
  integer fd, offset, lane, value, width_bytes;
  bit [31:0] base;
  reg [511:0] word_value;
  bfm_check(bus >= 0 && bus <= 2, "invalid image bus");
  bfm_check((bus == 0 && kind >= BFM_ATTN_INPUT && kind <= BFM_DOWN_META) ||
    (bus != 0 && kind >= BFM_ATTN_WEIGHT && kind <= BFM_DOWN_WEIGHT), "image kind/bus mismatch");
  base = bfm_kind_base(kind, id);
  if (bfm_reset_released) begin
    for (integer plan = 0; plan < bfm_plan_count; plan = plan + 1)
      if (bfm_plans[plan].bus == bus &&
          (bfm_plans[plan].issued != bfm_plans[plan].delivered ||
           bfm_plans[plan].retired != bfm_plans[plan].bursts) &&
          {1'b0,base} < {1'b0,bfm_plans[plan].base}+bfm_kind_bytes(bfm_plans[plan].kind) &&
          {1'b0,bfm_plans[plan].base} < {1'b0,base}+bfm_kind_bytes(kind))
        $fatal(1, "FAIL environment image reload overlaps accepted plan %0d", plan);
  end
  width_bytes = bus == 0 ? 32 : 64;
  fd = $fopen(path, "rb");
  bfm_check(fd != 0, $sformatf("cannot load image %s", path));
  for (offset = 0; offset < bfm_kind_bytes(kind); offset = offset + width_bytes) begin
    word_value = '0;
    for (lane = 0; lane < width_bytes; lane = lane + 1) begin
      value = $fgetc(fd);
      bfm_check(value >= 0 && value <= 255, $sformatf("short image %s byte=%0d", path, offset+lane));
      word_value[lane*8 +: 8] = value[7:0];
    end
    if (kind == BFM_GATE_META || kind == BFM_DOWN_META)
      bfm_check(word_value[255:224] === 32'd0, "MLP metadata reserved bytes are nonzero");
    case (bus)
      0: bfm_data_image[base+offset] = word_value[255:0];
      1: bfm_ddr0_image[base+offset] = word_value;
      2: bfm_ddr1_image[base+offset] = word_value;
    endcase
  end
  bfm_check($fgetc(fd) == -1, $sformatf("oversize image %s", path));
  $fclose(fd);
endtask

function automatic logic [511:0] bfm_memory_beat(input integer bus, input bit [31:0] address);
  case (bus)
    0: begin
      if (!bfm_data_image.exists(address)) $fatal(1, "FAIL unmapped AXI256 address %08h", address);
      return {256'd0, bfm_data_image[address]};
    end
    1: begin
      if (!bfm_ddr0_image.exists(address)) $fatal(1, "FAIL unmapped DDR0 address %08h", address);
      return bfm_ddr0_image[address];
    end
    2: begin
      if (!bfm_ddr1_image.exists(address)) $fatal(1, "FAIL unmapped DDR1 address %08h", address);
      return bfm_ddr1_image[address];
    end
    default: $fatal(1, "FAIL invalid memory bus");
  endcase
endfunction

function automatic integer bfm_find_plan(input integer bus, input bit write_transfer,
    input bit [31:0] address);
  integer i;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=find_plan bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, -1, bfm_read_head[0], bfm_read_tail[0], $realtime);
  for (i = 0; i < bfm_plan_count; i = i + 1) begin
    if (bfm_first_ar_active && bus == 0 && !write_transfer)
      $display("JOINT_FIRST_AR_DIAG ENTER stage=find_plan_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
        bus, address, i, bfm_read_head[0], bfm_read_tail[0], $realtime);
    if (bfm_plans[i].bus == bus && bfm_plans[i].write_transfer == write_transfer &&
        bfm_plans[i].issued < bfm_plans[i].beats && address >= bfm_plans[i].base &&
        {1'b0,address} < {1'b0,bfm_plans[i].base} + bfm_kind_bytes(bfm_plans[i].kind)) begin
      if (bfm_first_ar_active && bus == 0 && !write_transfer)
        $display("JOINT_FIRST_AR_DIAG EXIT stage=find_plan_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
          bus, address, i, bfm_read_head[0], bfm_read_tail[0], $realtime);
      if (bfm_first_ar_active && bus == 0 && !write_transfer)
        $display("JOINT_FIRST_AR_DIAG EXIT stage=find_plan bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
          bus, address, i, bfm_read_head[0], bfm_read_tail[0], $realtime);
      return i;
    end
    if (bfm_first_ar_active && bus == 0 && !write_transfer)
      $display("JOINT_FIRST_AR_DIAG EXIT stage=find_plan_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
        bus, address, i, bfm_read_head[0], bfm_read_tail[0], $realtime);
  end
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=find_plan bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, i, bfm_read_head[0], bfm_read_tail[0], $realtime);
  $fatal(1, "FAIL unplanned bus=%0d write=%0d address=%08h", bus, write_transfer, address);
endfunction

task automatic bfm_accept_address(input integer bus, input bit write_transfer,
    input logic [31:0] address, input logic [7:0] len,
    input logic [2:0] size, input logic [1:0] burst, output bfm_descriptor_t descriptor);
  integer plan, beat_bytes, expected_beats, remaining, boundary;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=accept_address bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, -1, bfm_read_head[0], bfm_read_tail[0], $realtime);
  bfm_check(!$isunknown({address,len,size,burst}), "X/Z AXI address descriptor");
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=plan_lookup bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, -1, bfm_read_head[0], bfm_read_tail[0], $realtime);
  plan = bfm_find_plan(bus, write_transfer, address);
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=plan_lookup bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  beat_bytes = bus == 0 ? 32 : 64;
  bfm_check(size === (bus == 0 ? 3'd5 : 3'd6) && burst === 2'b01,
    "AXI size/burst attributes mismatch");
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=address_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  bfm_check(address === bfm_plans[plan].base + bfm_plans[plan].issued * beat_bytes,
    "AXI address skipped, repeated, or crossed a command identity");
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=address_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=remaining_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  remaining = bfm_plans[plan].beats - bfm_plans[plan].issued;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=remaining_fields bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  boundary = (4096 - (address & 4095)) / beat_bytes;
  expected_beats = remaining < 16 ? remaining : 16;
  if (boundary < expected_beats) expected_beats = boundary;
  bfm_check(address % beat_bytes == 0 && int'(len)+1 == expected_beats,
    "AXI full-shape burst/4KiB boundary mismatch");
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=descriptor_address bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  descriptor.address = address;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=descriptor_address bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=descriptor_beats bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  descriptor.beats = expected_beats;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=descriptor_beats bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=descriptor_plan bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  descriptor.plan = plan;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=descriptor_plan bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG ENTER stage=plan_update bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  bfm_plans[plan].issued = bfm_plans[plan].issued + expected_beats;
  bfm_plans[plan].bursts = bfm_plans[plan].bursts + 1;
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=plan_update bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
  if (bfm_first_ar_active && bus == 0 && !write_transfer)
    $display("JOINT_FIRST_AR_DIAG EXIT stage=accept_address bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
      bus, address, plan, bfm_read_head[0], bfm_read_tail[0], $realtime);
endtask

wire bfm_read_clk [0:2], bfm_read_rst_n [0:2];
assign bfm_read_clk[0] = core_clk;
assign bfm_read_clk[1] = ddr0_clk;
assign bfm_read_clk[2] = ddr1_clk;
assign bfm_read_rst_n[0] = core_rst_n;
assign bfm_read_rst_n[1] = ddr0_rst_n;
assign bfm_read_rst_n[2] = ddr1_rst_n;
wire [2:0] bfm_arvalid = {ddr1_axi_arvalid,ddr0_axi_arvalid,data_axi_arvalid};
wire [2:0] bfm_rready = {ddr1_axi_rready,ddr0_axi_rready,data_axi_rready};
wire [31:0] bfm_araddr [0:2];
wire [7:0] bfm_arlen [0:2];
wire [2:0] bfm_arsize [0:2];
wire [1:0] bfm_arburst [0:2];
assign bfm_araddr[0] = data_axi_araddr;
assign bfm_araddr[1] = ddr0_axi_araddr;
assign bfm_araddr[2] = ddr1_axi_araddr;
assign bfm_arlen[0] = data_axi_arlen;
assign bfm_arlen[1] = ddr0_axi_arlen;
assign bfm_arlen[2] = ddr1_axi_arlen;
assign bfm_arsize[0] = data_axi_arsize;
assign bfm_arsize[1] = ddr0_axi_arsize;
assign bfm_arsize[2] = ddr1_axi_arsize;
assign bfm_arburst[0] = data_axi_arburst;
assign bfm_arburst[1] = ddr0_axi_arburst;
assign bfm_arburst[2] = ddr1_axi_arburst;
wire [2:0] bfm_arready;
reg [2:0] bfm_rvalid = 0, bfm_rlast = 0;
reg [511:0] bfm_rdata [0:2];
assign {ddr1_axi_arready,ddr0_axi_arready,data_axi_arready} = bfm_arready;
assign {ddr1_axi_rvalid,ddr0_axi_rvalid,data_axi_rvalid} = bfm_rvalid;
assign {ddr1_axi_rlast,ddr0_axi_rlast,data_axi_rlast} = bfm_rlast;
assign data_axi_rdata = bfm_rdata[0][255:0];
assign ddr0_axi_rdata = bfm_rdata[1];
assign ddr1_axi_rdata = bfm_rdata[2];
assign data_axi_rresp = 0;
assign ddr0_axi_rresp = 0;
assign ddr1_axi_rresp = 0;

generate for (genvar bus = 0; bus < 3; bus = bus + 1) begin : bfm_reads
  localparam integer BEAT_BYTES = bus == 0 ? 32 : 64;
  bfm_descriptor_t queue [0:BFM_QUEUE_DEPTH-1];
  bfm_descriptor_t accepted, current;
  integer trace_plan, trace_sequence, trace_beats, trace_beat, trace_kind;
  bit [31:0] trace_address, trace_strobe;
  logic [511:0] trace_payload;
  bit trace_last;
  bfm_identity_t trace_identity;
  string trace_bus, trace_event;
  integer r_trace_plan, r_trace_sequence, r_trace_beats, r_trace_beat, r_trace_kind;
  bit [31:0] r_trace_address, r_trace_strobe;
  logic [511:0] r_trace_payload;
  bit r_trace_last;
  bfm_identity_t r_trace_identity;
  string r_trace_bus, r_trace_event;
  integer cycles = 0, beat_index = 0;
  integer survivor_head, survivor_tail, active_index, attn_plan, mlp_plan;
  reg ar_hold = 0, r_hold = 0;
  reg [44:0] held_ar;
  reg [514:0] held_r;
  wire [44:0] ar_payload = {bfm_araddr[bus],bfm_arlen[bus],bfm_arsize[bus],bfm_arburst[bus]};
  assign bfm_arready[bus] = bfm_read_rst_n[bus] &&
    bfm_read_tail[bus]-bfm_read_head[bus] < BFM_QUEUE_DEPTH &&
    ((cycles + bus*3) % (bus == 2 ? 11 : 7) >= 2);
  always @(posedge bfm_read_clk[bus] or negedge bfm_read_rst_n[bus]) begin
    if (!bfm_read_rst_n[bus]) begin
      if (bfm_reset_released && bfm_read_head[bus] != bfm_read_tail[bus])
        $fatal(1, "FAIL public reset discarded pending bus %0d", bus);
      cycles <= 0; beat_index = 0;
      bfm_read_head[bus] <= 0; bfm_read_tail[bus] <= 0;
      bfm_rvalid[bus] <= 0; bfm_rlast[bus] <= 0; bfm_rdata[bus] <= 0;
      ar_hold = 0; r_hold = 0;
      if (bus != 0) begin
        bfm_ddr_overlap_edges[bus] <= 0;
        bfm_ddr_overlap_attn[bus] <= '0; bfm_ddr_overlap_mlp[bus] <= '0;
      end
    end else begin
      cycles <= cycles + 1;
      bfm_check(!$isunknown({bfm_arvalid[bus],bfm_arready[bus],bfm_rvalid[bus],bfm_rready[bus]}),
        "X/Z read-channel handshake");
      if (ar_hold) bfm_check(bfm_arvalid[bus] === 1'b1 && ar_payload === held_ar,
        "AR payload changed while stalled");
      if (bfm_arvalid[bus] === 1'b1) bfm_check(!$isunknown(ar_payload), "X/Z held AR payload");
      ar_hold = bfm_arvalid[bus] === 1'b1 && bfm_arready[bus] === 1'b0;
      held_ar = ar_payload;
      if (r_hold) bfm_check(bfm_rvalid[bus] === 1'b1 &&
        {bfm_rdata[bus],2'b00,bfm_rlast[bus]} === held_r, "R payload changed while stalled");
      if (bfm_rvalid[bus] === 1'b1) bfm_check(!$isunknown({bfm_rdata[bus],bfm_rlast[bus]}),
        "X/Z held R payload");
      r_hold = bfm_rvalid[bus] === 1'b1 && bfm_rready[bus] === 1'b0;
      held_r = {bfm_rdata[bus],2'b00,bfm_rlast[bus]};
      if (bfm_arvalid[bus] === 1'b1 && bfm_arready[bus] === 1'b1) begin
        if (bus == 0 && !bfm_first_ar_seen) begin
          bfm_first_ar_seen = 1;
          bfm_first_ar_active = 1;
          $display("JOINT_FIRST_AR_DIAG ENTER stage=first_accepted_ar bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        end
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_FIRST_AR_DIAG ENTER stage=accept_call bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        bfm_accept_address(bus, 0, bfm_araddr[bus], bfm_arlen[bus],
          bfm_arsize[bus], bfm_arburst[bus], accepted);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_FIRST_AR_DIAG EXIT stage=accept_call bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_FIRST_AR_DIAG ENTER stage=queue_insert bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        queue[bfm_read_tail[bus] % BFM_QUEUE_DEPTH] = accepted;
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_FIRST_AR_DIAG EXIT stage=queue_insert bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        if (bus != 0) bfm_ddr_history[bus-1].push_back(accepted);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_FIRST_AR_DIAG ENTER stage=trace_publish bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=arg_plan bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        trace_plan = accepted.plan;
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=arg_plan bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=arg_scalars bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        trace_sequence = bfm_read_tail[bus];
        trace_address = accepted.address;
        trace_beats = accepted.beats;
        trace_beat = 0;
        trace_payload = '0;
        trace_strobe = 0;
        trace_last = 0;
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=arg_scalars bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=arg_kind bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        trace_kind = bfm_plans[trace_plan].kind;
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=arg_kind bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=arg_identity bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        trace_identity = bfm_plans[trace_plan].identity;
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=arg_identity bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=arg_bus_string bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        trace_bus = bus == 0 ? "DATA" : (bus == 1 ? "DDR0" : "DDR1");
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=arg_bus_string bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=arg_event_string bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        trace_event = "AR";
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=arg_event_string bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG ENTER stage=trace_call bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        bfm_trace(trace_bus, trace_event, trace_sequence, trace_address,
          trace_beats, trace_beat, trace_payload, trace_strobe, trace_last,
          trace_kind, trace_identity);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_TRACE_PUBLISH_DIAG EXIT stage=trace_call bus=%0d address=%08h tail=%0d time=%0t",
            bus, accepted.address, bfm_read_tail[bus], $realtime);
        if (bus == 0 && bfm_first_ar_active)
          $display("JOINT_FIRST_AR_DIAG EXIT stage=trace_publish bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
        bfm_read_tail[bus] <= bfm_read_tail[bus] + 1;
        if (bus == 0 && bfm_first_ar_active) begin
          $display("JOINT_FIRST_AR_DIAG EXIT stage=first_accepted_ar bus=%0d address=%08h index=%0d head=%0d tail=%0d time=%0t",
            bus, bfm_araddr[bus], bfm_read_tail[bus] % BFM_QUEUE_DEPTH,
            bfm_read_head[bus], bfm_read_tail[bus], $realtime);
          bfm_first_ar_active = 0;
        end
      end
      if (bfm_rvalid[bus] === 1'b1 && bfm_rready[bus] === 1'b1) begin
        current = queue[bfm_read_head[bus] % BFM_QUEUE_DEPTH];
        bfm_check(bfm_rlast[bus] === (beat_index == current.beats-1), "R framing mismatch");
        r_trace_plan = current.plan;
        r_trace_bus = bus == 0 ? "DATA" : (bus == 1 ? "DDR0" : "DDR1");
        r_trace_event = "R";
        r_trace_sequence = bfm_read_head[bus];
        r_trace_address = current.address+beat_index*BEAT_BYTES;
        r_trace_beats = current.beats;
        r_trace_beat = beat_index;
        r_trace_payload = bfm_rdata[bus];
        r_trace_strobe = 0;
        r_trace_last = bfm_rlast[bus];
        r_trace_kind = bfm_plans[r_trace_plan].kind;
        r_trace_identity = bfm_plans[r_trace_plan].identity;
        bfm_trace(r_trace_bus, r_trace_event, r_trace_sequence, r_trace_address,
          r_trace_beats, r_trace_beat, r_trace_payload, r_trace_strobe, r_trace_last,
          r_trace_kind, r_trace_identity);
        bfm_plans[current.plan].delivered = bfm_plans[current.plan].delivered + 1;
        bfm_rvalid[bus] <= 0;
        if (beat_index == current.beats-1) begin
          bfm_plans[current.plan].retired = bfm_plans[current.plan].retired + 1;
          bfm_read_head[bus] <= bfm_read_head[bus] + 1; beat_index = 0;
        end else beat_index = beat_index + 1;
      end
      if (bus != 0) begin
        // Only accepted descriptors surviving this edge establish an interval.
        // A last-R retirement plus an opposite AR handoff alone is not overlap.
        survivor_head = bfm_read_head[bus];
        survivor_tail = bfm_read_tail[bus];
        if (bfm_rvalid[bus] === 1'b1 && bfm_rready[bus] === 1'b1 &&
            bfm_rlast[bus] === 1'b1) survivor_head = survivor_head + 1;
        if (bfm_arvalid[bus] === 1'b1 && bfm_arready[bus] === 1'b1)
          survivor_tail = survivor_tail + 1;
        attn_plan = -1; mlp_plan = -1;
        for (active_index = survivor_head; active_index < survivor_tail;
             active_index = active_index + 1) begin
          case (bfm_plans[queue[active_index % BFM_QUEUE_DEPTH].plan].kind)
            BFM_ATTN_WEIGHT: attn_plan = queue[active_index % BFM_QUEUE_DEPTH].plan;
            BFM_GATE_WEIGHT, BFM_DOWN_WEIGHT:
              mlp_plan = queue[active_index % BFM_QUEUE_DEPTH].plan;
            default: $fatal(1, "FAIL non-weight descriptor on physical DDR%0d", bus-1);
          endcase
        end
        if (attn_plan >= 0 && mlp_plan >= 0) begin
          if (bfm_ddr_overlap_edges[bus] == 0) begin
            bfm_ddr_overlap_attn[bus] <= bfm_plans[attn_plan].identity;
            bfm_ddr_overlap_mlp[bus] <= bfm_plans[mlp_plan].identity;
          end
          bfm_ddr_overlap_edges[bus] <= bfm_ddr_overlap_edges[bus] + 1;
        end
      end
      if (bfm_read_head[bus] < bfm_read_tail[bus] && bfm_rvalid[bus] === 1'b0 &&
          (cycles+bus*5) % (bus == 2 ? 13 : 5) != 0) begin
        current = queue[bfm_read_head[bus] % BFM_QUEUE_DEPTH];
        bfm_rdata[bus] <= bfm_memory_beat(bus, current.address+beat_index*BEAT_BYTES);
        bfm_rlast[bus] <= beat_index == current.beats-1;
        bfm_rvalid[bus] <= 1;
      end
    end
  end
end endgenerate

bfm_descriptor_t bfm_write_queue [0:BFM_QUEUE_DEPTH-1];
bfm_descriptor_t bfm_write_accepted, bfm_write_current;
integer bfm_aw_count = 0, bfm_wburst_count = 0, bfm_b_count = 0, bfm_write_beat = 0;
integer bfm_write_trace_plan, bfm_write_trace_sequence, bfm_write_trace_beats;
integer bfm_write_trace_beat, bfm_write_trace_kind;
bit [31:0] bfm_write_trace_address, bfm_write_trace_strobe;
logic [511:0] bfm_write_trace_payload;
bit bfm_write_trace_last;
bfm_identity_t bfm_write_trace_identity;
string bfm_write_trace_bus, bfm_write_trace_event;
reg bfm_aw_hold = 0, bfm_w_hold = 0, bfm_b_hold = 0;
reg [44:0] bfm_held_aw;
reg [288:0] bfm_held_w;
assign data_axi_awready = core_rst_n && bfm_aw_count-bfm_b_count < BFM_QUEUE_DEPTH &&
  bfm_core_cycles % 7 >= 2;
assign data_axi_wready = core_rst_n && bfm_wburst_count < bfm_aw_count &&
  bfm_core_cycles % 9 >= 3;
always @(posedge core_clk or negedge core_rst_n) begin
  if (!core_rst_n) begin
    if (bfm_reset_released && bfm_aw_count != bfm_b_count)
      $fatal(1, "FAIL public reset discarded an accepted write");
    bfm_core_cycles <= 0; bfm_aw_count <= 0; bfm_wburst_count <= 0;
    bfm_b_count <= 0; bfm_write_beat = 0; data_axi_bvalid <= 0;
    bfm_aw_hold = 0; bfm_w_hold = 0; bfm_b_hold = 0;
  end else begin
    bfm_core_cycles <= bfm_core_cycles + 1;
    bfm_check(!$isunknown({data_axi_awvalid,data_axi_awready,data_axi_wvalid,
      data_axi_wready,data_axi_bvalid,data_axi_bready}), "X/Z write-channel handshake");
    if (bfm_aw_hold) bfm_check(data_axi_awvalid === 1'b1 &&
      {data_axi_awaddr,data_axi_awlen,data_axi_awsize,data_axi_awburst} === bfm_held_aw,
      "AW payload changed while stalled");
    if (data_axi_awvalid === 1'b1) bfm_check(!$isunknown(
      {data_axi_awaddr,data_axi_awlen,data_axi_awsize,data_axi_awburst}), "X/Z held AW payload");
    bfm_aw_hold = data_axi_awvalid === 1'b1 && data_axi_awready === 1'b0;
    bfm_held_aw = {data_axi_awaddr,data_axi_awlen,data_axi_awsize,data_axi_awburst};
    if (bfm_w_hold) bfm_check(data_axi_wvalid === 1'b1 &&
      {data_axi_wdata,data_axi_wstrb,data_axi_wlast} === bfm_held_w, "W payload changed while stalled");
    if (data_axi_wvalid === 1'b1) bfm_check(!$isunknown(
      {data_axi_wdata,data_axi_wstrb,data_axi_wlast}), "X/Z held W payload");
    bfm_w_hold = data_axi_wvalid === 1'b1 && data_axi_wready === 1'b0;
    bfm_held_w = {data_axi_wdata,data_axi_wstrb,data_axi_wlast};
    if (bfm_b_hold) bfm_check(data_axi_bvalid === 1'b1 && data_axi_bresp === 2'b00,
      "B response changed while stalled");
    bfm_b_hold = data_axi_bvalid === 1'b1 && data_axi_bready === 1'b0;
    if (data_axi_awvalid === 1'b1 && data_axi_awready === 1'b1) begin
      bfm_accept_address(0, 1, data_axi_awaddr, data_axi_awlen, data_axi_awsize,
        data_axi_awburst, bfm_write_accepted);
      bfm_write_queue[bfm_aw_count % BFM_QUEUE_DEPTH] = bfm_write_accepted;
      bfm_write_trace_plan = bfm_write_accepted.plan;
      bfm_write_trace_bus = "DATA";
      bfm_write_trace_event = "AW";
      bfm_write_trace_sequence = bfm_aw_count;
      bfm_write_trace_address = bfm_write_accepted.address;
      bfm_write_trace_beats = bfm_write_accepted.beats;
      bfm_write_trace_beat = 0;
      bfm_write_trace_payload = '0;
      bfm_write_trace_strobe = 0;
      bfm_write_trace_last = 0;
      bfm_write_trace_kind = bfm_plans[bfm_write_trace_plan].kind;
      bfm_write_trace_identity = bfm_plans[bfm_write_trace_plan].identity;
      bfm_trace(bfm_write_trace_bus, bfm_write_trace_event, bfm_write_trace_sequence,
        bfm_write_trace_address, bfm_write_trace_beats, bfm_write_trace_beat,
        bfm_write_trace_payload, bfm_write_trace_strobe, bfm_write_trace_last,
        bfm_write_trace_kind, bfm_write_trace_identity);
      bfm_aw_count <= bfm_aw_count + 1;
    end
    if (data_axi_wvalid === 1'b1 && data_axi_wready === 1'b1) begin
      bfm_write_current = bfm_write_queue[bfm_wburst_count % BFM_QUEUE_DEPTH];
      bfm_check(data_axi_wstrb === 32'hffffffff, "tensor write does not have all byte strobes");
      bfm_check(data_axi_wlast === (bfm_write_beat == bfm_write_current.beats-1), "W framing mismatch");
      bfm_data_image[bfm_write_current.address+bfm_write_beat*32] = data_axi_wdata;
      bfm_write_trace_plan = bfm_write_current.plan;
      bfm_write_trace_bus = "DATA";
      bfm_write_trace_event = "W";
      bfm_write_trace_sequence = bfm_wburst_count;
      bfm_write_trace_address = bfm_write_current.address+bfm_write_beat*32;
      bfm_write_trace_beats = bfm_write_current.beats;
      bfm_write_trace_beat = bfm_write_beat;
      bfm_write_trace_payload = {256'd0,data_axi_wdata};
      bfm_write_trace_strobe = data_axi_wstrb;
      bfm_write_trace_last = data_axi_wlast;
      bfm_write_trace_kind = bfm_plans[bfm_write_trace_plan].kind;
      bfm_write_trace_identity = bfm_plans[bfm_write_trace_plan].identity;
      bfm_trace(bfm_write_trace_bus, bfm_write_trace_event, bfm_write_trace_sequence,
        bfm_write_trace_address, bfm_write_trace_beats, bfm_write_trace_beat,
        bfm_write_trace_payload, bfm_write_trace_strobe, bfm_write_trace_last,
        bfm_write_trace_kind, bfm_write_trace_identity);
      bfm_plans[bfm_write_current.plan].delivered = bfm_plans[bfm_write_current.plan].delivered + 1;
      if (bfm_write_beat == bfm_write_current.beats-1) begin
        bfm_wburst_count <= bfm_wburst_count + 1; bfm_write_beat = 0;
      end else bfm_write_beat = bfm_write_beat + 1;
    end
    if (data_axi_bvalid === 1'b1 && data_axi_bready === 1'b1) begin
      bfm_write_current = bfm_write_queue[bfm_b_count % BFM_QUEUE_DEPTH];
      bfm_write_trace_plan = bfm_write_current.plan;
      bfm_write_trace_bus = "DATA";
      bfm_write_trace_event = "B";
      bfm_write_trace_sequence = bfm_b_count;
      bfm_write_trace_address = bfm_write_current.address;
      bfm_write_trace_beats = bfm_write_current.beats;
      bfm_write_trace_beat = 0;
      bfm_write_trace_payload = '0;
      bfm_write_trace_strobe = 0;
      bfm_write_trace_last = 0;
      bfm_write_trace_kind = bfm_plans[bfm_write_trace_plan].kind;
      bfm_write_trace_identity = bfm_plans[bfm_write_trace_plan].identity;
      bfm_trace(bfm_write_trace_bus, bfm_write_trace_event, bfm_write_trace_sequence,
        bfm_write_trace_address, bfm_write_trace_beats, bfm_write_trace_beat,
        bfm_write_trace_payload, bfm_write_trace_strobe, bfm_write_trace_last,
        bfm_write_trace_kind, bfm_write_trace_identity);
      bfm_plans[bfm_write_current.plan].retired = bfm_plans[bfm_write_current.plan].retired + 1;
      bfm_b_count <= bfm_b_count + 1; data_axi_bvalid <= 0;
    end
    if (bfm_b_count < bfm_wburst_count && data_axi_bvalid === 1'b0 && bfm_core_cycles % 5 != 0)
      data_axi_bvalid <= 1;
  end
end

// This is an observation scoreboard across clocks, not a replacement CDC path.
always @(negedge core_clk) if (core_rst_n === 1'b1) begin : bfm_pair_scoreboard
  bfm_descriptor_t d0, d1;
  if (bfm_pair_checked < bfm_ddr_history[0].size() &&
      bfm_pair_checked < bfm_ddr_history[1].size()) begin
    d0 = bfm_ddr_history[0][bfm_pair_checked];
    d1 = bfm_ddr_history[1][bfm_pair_checked];
    bfm_check(d0.beats == d1.beats && bfm_plans[d0.plan].kind == bfm_plans[d1.plan].kind &&
      bfm_plans[d0.plan].identity === bfm_plans[d1.plan].identity &&
      d0.address-bfm_plans[d0.plan].base == d1.address-bfm_plans[d1.plan].base,
      $sformatf("paired DDR descriptor/identity mismatch sequence=%0d", bfm_pair_checked));
    bfm_pair_checked = bfm_pair_checked + 1;
  end
end

task automatic bfm_check_plan(input integer plan);
  bfm_check(plan >= 0 && plan < bfm_plan_count, "invalid plan index");
  bfm_check(bfm_plans[plan].issued == bfm_plans[plan].beats &&
    bfm_plans[plan].delivered == bfm_plans[plan].beats &&
    bfm_plans[plan].retired == bfm_plans[plan].bursts,
    $sformatf("incomplete full-shape plan=%0d kind=%0d issued=%0d delivered=%0d expected=%0d retired=%0d/%0d",
      plan,bfm_plans[plan].kind,bfm_plans[plan].issued,bfm_plans[plan].delivered,
      bfm_plans[plan].beats,bfm_plans[plan].retired,bfm_plans[plan].bursts));
endtask

task automatic bfm_check_drained;
  for (integer bus = 0; bus < 3; bus = bus + 1)
    bfm_check(bfm_read_head[bus] == bfm_read_tail[bus] && bfm_rvalid[bus] === 1'b0,
      "accepted read has not drained");
  bfm_check(bfm_aw_count == bfm_wburst_count && bfm_aw_count == bfm_b_count &&
    data_axi_bvalid === 1'b0, "accepted write has not drained through B");
  bfm_check(bfm_pair_checked == bfm_ddr_history[0].size() &&
    bfm_pair_checked == bfm_ddr_history[1].size(), "unmatched/unobserved paired DDR descriptor");
endtask

task automatic bfm_release_reset;
  bfm_check(!bfm_reset_released && core_rst_n === 1'b0 &&
    ddr0_rst_n === 1'b0 && ddr1_rst_n === 1'b0, "initial reset already released");
  fork
    begin repeat (8) @(negedge core_clk); core_rst_n = 1; end
    begin repeat (17) @(negedge ddr0_clk); ddr0_rst_n = 1; end
    begin repeat (19) @(negedge ddr1_clk); ddr1_rst_n = 1; end
  join
  bfm_reset_released = 1;
endtask

task automatic bfm_dump_output(input integer plan, input string path);
  integer fd, beat, lane;
  reg [255:0] word_value;
  bfm_check_plan(plan);
  bfm_check(bfm_plans[plan].write_transfer, "cannot capture a read plan as DUT output");
  fd = $fopen(path, "wb");
  bfm_check(fd != 0, $sformatf("cannot capture %s", path));
  for (beat = 0; beat < bfm_plans[plan].beats; beat = beat + 1) begin
    word_value = bfm_memory_beat(0, bfm_plans[plan].base+beat*32);
    bfm_check(!$isunknown(word_value), "X/Z captured output");
    for (lane = 0; lane < 32; lane = lane + 1) $fwrite(fd, "%c", word_value[lane*8 +: 8]);
  end
  $fclose(fd);
  $fflush(bfm_trace_fd);
endtask

task automatic bfm_axil_write(input logic [11:0] address, input logic [31:0] value,
    input logic [3:0] strobes, input logic [1:0] expected_response);
  integer guard;
  bit aw_done, w_done, b_done;
  bfm_axil_lock.get(1);
  bfm_check(!$isunknown({address,value,strobes,expected_response}) && address[1:0] == 0,
    "invalid AXI-Lite write request");
  aw_done = 0; w_done = 0; b_done = 0;
  for (guard = 0; guard < BFM_AXIL_LIMIT && (!aw_done || !w_done); guard = guard + 1) begin
    @(negedge core_clk);
    ctrl_awaddr = address; ctrl_wdata = value; ctrl_wstrb = strobes;
    ctrl_awvalid = !aw_done && guard >= bfm_axil_sequence % 3;
    ctrl_wvalid = !w_done && guard >= (bfm_axil_sequence+1) % 3;
    @(posedge core_clk);
    bfm_check(!$isunknown({ctrl_awready,ctrl_wready}), "X/Z AXI-Lite write readiness");
    if (ctrl_awvalid === 1'b1 && ctrl_awready === 1'b1) aw_done = 1;
    if (ctrl_wvalid === 1'b1 && ctrl_wready === 1'b1) w_done = 1;
  end
  bfm_check(aw_done && w_done, "AXI-Lite AW/W timeout");
  @(negedge core_clk); ctrl_awvalid = 0; ctrl_wvalid = 0;
  repeat (2) @(negedge core_clk);
  ctrl_bready = 1;
  for (guard = 0; guard < BFM_AXIL_LIMIT && !b_done; guard = guard + 1) begin
    @(posedge core_clk);
    bfm_check(!$isunknown(ctrl_bvalid), "X/Z AXI-Lite BVALID");
    if (ctrl_bvalid === 1'b1) begin
      bfm_check(ctrl_bresp === expected_response, $sformatf("AXI-Lite BRESP address=%03h", address));
      b_done = 1;
    end
  end
  bfm_check(b_done, "AXI-Lite B timeout");
  @(negedge core_clk); ctrl_bready = 0;
  bfm_trace("AXIL", "WRITE", bfm_axil_sequence, {20'd0,address}, 1, 0,
    {480'd0,value}, {28'd0,strobes}, 1, 0, '0);
  bfm_axil_sequence = bfm_axil_sequence + 1;
  bfm_axil_lock.put(1);
endtask

task automatic bfm_axil_read(input logic [11:0] address, output logic [31:0] value,
    input logic [1:0] expected_response);
  integer guard;
  bit ar_done, r_done;
  bfm_axil_lock.get(1);
  bfm_check(!$isunknown({address,expected_response}) && address[1:0] == 0,
    "invalid AXI-Lite read request");
  ar_done = 0; r_done = 0;
  @(negedge core_clk); ctrl_araddr = address; ctrl_arvalid = 1;
  for (guard = 0; guard < BFM_AXIL_LIMIT && !ar_done; guard = guard + 1) begin
    @(posedge core_clk);
    bfm_check(!$isunknown(ctrl_arready), "X/Z AXI-Lite ARREADY");
    if (ctrl_arready === 1'b1) ar_done = 1;
  end
  bfm_check(ar_done, "AXI-Lite AR timeout");
  @(negedge core_clk); ctrl_arvalid = 0;
  repeat (2) @(negedge core_clk);
  ctrl_rready = 1;
  for (guard = 0; guard < BFM_AXIL_LIMIT && !r_done; guard = guard + 1) begin
    @(posedge core_clk);
    bfm_check(!$isunknown(ctrl_rvalid), "X/Z AXI-Lite RVALID");
    if (ctrl_rvalid === 1'b1) begin
      bfm_check(ctrl_rresp === expected_response && !$isunknown(ctrl_rdata),
        $sformatf("AXI-Lite R response address=%03h", address));
      value = ctrl_rdata; r_done = 1;
    end
  end
  bfm_check(r_done, "AXI-Lite R timeout");
  @(negedge core_clk); ctrl_rready = 0;
  bfm_trace("AXIL", "READ", bfm_axil_sequence, {20'd0,address}, 1, 0,
    {480'd0,value}, 0, 1, 0, '0);
  bfm_axil_sequence = bfm_axil_sequence + 1;
  bfm_axil_lock.put(1);
endtask

reg bfm_ctrl_b_hold = 0, bfm_ctrl_r_hold = 0;
reg [1:0] bfm_ctrl_held_b;
reg [33:0] bfm_ctrl_held_r;
always @(posedge core_clk or negedge core_rst_n) begin
  if (!core_rst_n) begin bfm_ctrl_b_hold = 0; bfm_ctrl_r_hold = 0; end
  else begin
    bfm_check(!$isunknown({ctrl_bvalid,ctrl_rvalid}), "X/Z AXI-Lite response valid");
    if (ctrl_bvalid === 1'b1) bfm_check(!$isunknown(ctrl_bresp), "X/Z AXI-Lite BRESP");
    if (ctrl_rvalid === 1'b1) bfm_check(!$isunknown({ctrl_rdata,ctrl_rresp}), "X/Z AXI-Lite read payload");
    if (bfm_ctrl_b_hold) bfm_check(ctrl_bvalid === 1'b1 && ctrl_bresp === bfm_ctrl_held_b,
      "AXI-Lite B changed while stalled");
    if (bfm_ctrl_r_hold) bfm_check(ctrl_rvalid === 1'b1 &&
      {ctrl_rdata,ctrl_rresp} === bfm_ctrl_held_r, "AXI-Lite R changed while stalled");
    bfm_ctrl_b_hold = ctrl_bvalid === 1'b1 && ctrl_bready === 1'b0;
    bfm_ctrl_r_hold = ctrl_rvalid === 1'b1 && ctrl_rready === 1'b0;
    bfm_ctrl_held_b = ctrl_bresp; bfm_ctrl_held_r = {ctrl_rdata,ctrl_rresp};
  end
end

task automatic bfm_expect_register(input logic [11:0] address, input logic [31:0] expected_value);
  logic [31:0] actual;
  bfm_axil_read(address, actual, 2'b00);
  bfm_check(actual === expected_value,
    $sformatf("CSR %03h actual=%08h expected=%08h", address, actual, expected_value));
endtask

task automatic bfm_check_completion(input bit mlp, input bfm_identity_t id,
    input bit [7:0] expected_status);
  bit [11:0] base;
  base = mlp ? 12'h288 : 12'h078;
  bfm_expect_register(base, id.request_id);
  bfm_expect_register(base+4, id.command_id);
  bfm_expect_register(base+8, (id.buffer_id << 16) | id.cohort_id);
  bfm_expect_register(base+12, id.layer_id);
  bfm_expect_register(base+16, (int'(expected_status) << 19) | (int'(mlp) << 16) | id.buffer_id);
  if (mlp) begin
    bfm_expect_register(12'h13c, id.bank);
    bfm_expect_register(12'h144, id.generation);
  end
endtask

task automatic bfm_check_healthy_mlp;
  bfm_check(integration_error === 1'b0, "integration error is not known zero");
  bfm_expect_register(12'h148, 0);
  bfm_expect_register(12'h17c, 6144);
  bfm_expect_register(12'h244, 128);
  bfm_expect_register(12'h248, 8192);
  bfm_expect_register(12'h24c, 256);
  bfm_expect_register(12'h2b0, 0);
  bfm_expect_register(12'h2b4, 0);
  // 0x2AC is legitimate terminal saturation, not a blanket zero requirement.
endtask

task automatic bfm_finish_transport;
  bfm_check_drained();
  for (integer plan = 0; plan < bfm_plan_count; plan = plan + 1) bfm_check_plan(plan);
  bfm_check(bfm_trace_fd != 0, "missing transport trace");
  $fclose(bfm_trace_fd); bfm_trace_fd = 0;
endtask
