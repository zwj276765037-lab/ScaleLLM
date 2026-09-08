`timescale 1ns / 1ps

// Timing-only registered boundary for the production MLP control plane.
// Every functional DUT input and output crosses a real proxy FF; clk is the
// only top-level port, so OOC timing does not depend on abstract partition
// pin delays or timing exceptions.
module hap_mlp_axil_control_registered_ooc_harness (
    input wire clk
);
    localparam integer S_RST_N = 0;
    localparam integer S_AXIL_AWADDR = S_RST_N + 1;
    localparam integer S_AXIL_AWVALID = S_AXIL_AWADDR + 12;
    localparam integer S_AXIL_WDATA = S_AXIL_AWVALID + 1;
    localparam integer S_AXIL_WSTRB = S_AXIL_WDATA + 32;
    localparam integer S_AXIL_WVALID = S_AXIL_WSTRB + 4;
    localparam integer S_AXIL_BREADY = S_AXIL_WVALID + 1;
    localparam integer S_AXIL_ARADDR = S_AXIL_BREADY + 1;
    localparam integer S_AXIL_ARVALID = S_AXIL_ARADDR + 12;
    localparam integer S_AXIL_RREADY = S_AXIL_ARVALID + 1;
    localparam integer S_OWNER_REQUEST_READY = S_AXIL_RREADY + 1;
    localparam integer S_ADMISSION_PAUSE = S_OWNER_REQUEST_READY + 1;
    localparam integer S_OWNER_REQUEST_DONE = S_ADMISSION_PAUSE + 1;
    localparam integer S_ACTIVE_OWNER = S_OWNER_REQUEST_DONE + 1;
    localparam integer S_OWNER_SWITCH_PENDING = S_ACTIVE_OWNER + 2;
    localparam integer S_ATTENTION_LAUNCH_ENABLE =
        S_OWNER_SWITCH_PENDING + 1;
    localparam integer S_MLP_LAUNCH_ENABLE = S_ATTENTION_LAUNCH_ENABLE + 1;
    localparam integer S_OWNER_PROTOCOL_ERROR = S_MLP_LAUNCH_ENABLE + 1;
    localparam integer S_DDR0_OUTSTANDING = S_OWNER_PROTOCOL_ERROR + 1;
    localparam integer S_DDR1_OUTSTANDING = S_DDR0_OUTSTANDING + 8;
    localparam integer S_MAINTENANCE_BUSY = S_DDR1_OUTSTANDING + 8;
    localparam integer S_MAINTENANCE_REQUEST_PENDING =
        S_MAINTENANCE_BUSY + 1;
    localparam integer S_MLP_ABORT_COMPLETE =
        S_MAINTENANCE_REQUEST_PENDING + 1;
    localparam integer S_PAIRED_QUIESCENT = S_MLP_ABORT_COMPLETE + 1;
    localparam integer S_PAIRED_ATTN_BURSTS = S_PAIRED_QUIESCENT + 1;
    localparam integer S_PAIRED_MLP_BURSTS = S_PAIRED_ATTN_BURSTS + 32;
    localparam integer S_PAIRED_BOTH_CYCLES = S_PAIRED_MLP_BURSTS + 32;
    localparam integer S_PAIRED_HOL0 = S_PAIRED_BOTH_CYCLES + 32;
    localparam integer S_PAIRED_HOL1 = S_PAIRED_HOL0 + 32;
    localparam integer S_PAIRED_HWM0 = S_PAIRED_HOL1 + 32;
    localparam integer S_PAIRED_HWM1 = S_PAIRED_HWM0 + 32;
    localparam integer S_MLP_COMMAND_READY = S_PAIRED_HWM1 + 32;
    localparam integer S_MLP_INPUT_BANK_READY = S_MLP_COMMAND_READY + 1;
    localparam integer S_MLP_BUSY = S_MLP_INPUT_BANK_READY + 2;
    localparam integer S_MLP_DONE = S_MLP_BUSY + 1;
    localparam integer S_MLP_ERROR = S_MLP_DONE + 1;
    localparam integer S_MLP_PHASE = S_MLP_ERROR + 1;
    localparam integer S_MLP_TELEMETRY = S_MLP_PHASE + 3;
    localparam integer S_TENSOR_LOAD_READY = S_MLP_TELEMETRY + 1568;
    localparam integer S_TENSOR_STORE_READY = S_TENSOR_LOAD_READY + 1;
    localparam integer S_TENSOR_STORE_ARMED = S_TENSOR_STORE_READY + 1;
    localparam integer S_TENSOR_DMA_BUSY = S_TENSOR_STORE_ARMED + 1;
    localparam integer S_TENSOR_DMA_DONE = S_TENSOR_DMA_BUSY + 1;
    localparam integer S_TENSOR_DMA_ERROR = S_TENSOR_DMA_DONE + 1;
    localparam integer S_TENSOR_DMA_PHASE = S_TENSOR_DMA_ERROR + 1;
    localparam integer S_TENSOR_INPUT_BEAT_COUNT = S_TENSOR_DMA_PHASE + 3;
    localparam integer S_TENSOR_INPUT_GROUP_COUNT =
        S_TENSOR_INPUT_BEAT_COUNT + 32;
    localparam integer S_TENSOR_OUTPUT_BEAT_COUNT =
        S_TENSOR_INPUT_GROUP_COUNT + 32;
    localparam integer S_TENSOR_OUTPUT_TILE_COUNT =
        S_TENSOR_OUTPUT_BEAT_COUNT + 32;
    localparam integer S_META_DMA_BUSY = S_TENSOR_OUTPUT_TILE_COUNT + 32;
    localparam integer S_META_DMA_DONE = S_META_DMA_BUSY + 1;
    localparam integer S_META_DMA_ERROR = S_META_DMA_DONE + 1;
    localparam integer S_META_DMA_PHASE = S_META_DMA_ERROR + 1;
    localparam integer S_META_DMA_GATE_RECORD_COUNT = S_META_DMA_PHASE + 3;
    localparam integer S_META_DMA_DOWN_RECORD_COUNT =
        S_META_DMA_GATE_RECORD_COUNT + 32;
    localparam integer S_META_DMA_PHYSICAL_BYTES =
        S_META_DMA_DOWN_RECORD_COUNT + 32;
    localparam integer S_META_LOAD_BEGIN_READY =
        S_META_DMA_PHYSICAL_BYTES + 64;
    localparam integer S_META_COMMIT_READY = S_META_LOAD_BEGIN_READY + 1;
    localparam integer S_META_ACTIVE_BANK = S_META_COMMIT_READY + 1;
    localparam integer S_META_ACTIVE_GENERATION = S_META_ACTIVE_BANK + 1;
    localparam integer S_META_BANK_VALID = S_META_ACTIVE_GENERATION + 32;
    localparam integer S_META_BANK_LOADING = S_META_BANK_VALID + 2;
    localparam integer S_META_GATE_WRITE_COUNT_BANK0 =
        S_META_BANK_LOADING + 2;
    localparam integer S_META_GATE_WRITE_COUNT_BANK1 =
        S_META_GATE_WRITE_COUNT_BANK0 + 32;
    localparam integer S_META_DOWN_WRITE_COUNT_BANK0 =
        S_META_GATE_WRITE_COUNT_BANK1 + 32;
    localparam integer S_META_DOWN_WRITE_COUNT_BANK1 =
        S_META_DOWN_WRITE_COUNT_BANK0 + 32;
    localparam integer S_META_ERROR = S_META_DOWN_WRITE_COUNT_BANK1 + 32;
    localparam integer SRC_W = S_META_ERROR + 1;
    localparam integer SINK_W = 409;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire s_axil_awready;
    wire s_axil_wready;
    wire [1:0] s_axil_bresp;
    wire s_axil_bvalid;
    wire s_axil_arready;
    wire [31:0] s_axil_rdata;
    wire [1:0] s_axil_rresp;
    wire s_axil_rvalid;
    wire owner_request_valid;
    wire [1:0] owner_request;
    wire mlp_command_valid;
    wire mlp_clear_pulse;
    wire mlp_abort_pending;
    wire mlp_command_bank;
    wire [31:0] mlp_gate_ddr0_base_addr;
    wire [31:0] mlp_gate_ddr1_base_addr;
    wire [31:0] mlp_down_ddr0_base_addr;
    wire [31:0] mlp_down_ddr1_base_addr;
    wire [31:0] mlp_input_base_addr;
    wire [31:0] mlp_output_base_addr;
    wire [31:0] mlp_command_id;
    wire [31:0] mlp_layer_id;
    wire tensor_load_valid;
    wire tensor_store_valid;
    wire [31:0] meta_gate_base_addr;
    wire [31:0] meta_down_base_addr;
    wire meta_load_begin_valid;
    wire meta_load_bank;
    wire meta_commit_valid;
    wire meta_commit_bank;
    wire [31:0] meta_commit_generation;
    wire irq;
    wire done_sticky;
    wire error_sticky;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error_sticky, done_sticky, irq,
        meta_commit_generation, meta_commit_bank, meta_commit_valid,
        meta_load_bank, meta_load_begin_valid,
        meta_down_base_addr, meta_gate_base_addr,
        tensor_store_valid, tensor_load_valid,
        mlp_layer_id, mlp_command_id, mlp_output_base_addr,
        mlp_input_base_addr, mlp_down_ddr1_base_addr,
        mlp_down_ddr0_base_addr, mlp_gate_ddr1_base_addr,
        mlp_gate_ddr0_base_addr, mlp_command_bank, mlp_abort_pending,
        mlp_clear_pulse, mlp_command_valid,
        owner_request, owner_request_valid,
        s_axil_rvalid, s_axil_rresp, s_axil_rdata, s_axil_arready,
        s_axil_bvalid, s_axil_bresp, s_axil_wready, s_axil_awready
    };

    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_axil_control #(.PRODUCTION_INTEGRATION(1)) u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]),
        .s_axil_awaddr(src_r[S_AXIL_AWADDR +: 12]),
        .s_axil_awvalid(src_r[S_AXIL_AWVALID]),
        .s_axil_awready(s_axil_awready),
        .s_axil_wdata(src_r[S_AXIL_WDATA +: 32]),
        .s_axil_wstrb(src_r[S_AXIL_WSTRB +: 4]),
        .s_axil_wvalid(src_r[S_AXIL_WVALID]),
        .s_axil_wready(s_axil_wready), .s_axil_bresp(s_axil_bresp),
        .s_axil_bvalid(s_axil_bvalid),
        .s_axil_bready(src_r[S_AXIL_BREADY]),
        .s_axil_araddr(src_r[S_AXIL_ARADDR +: 12]),
        .s_axil_arvalid(src_r[S_AXIL_ARVALID]),
        .s_axil_arready(s_axil_arready), .s_axil_rdata(s_axil_rdata),
        .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(src_r[S_AXIL_RREADY]),
        .owner_request_valid(owner_request_valid),
        .owner_request_ready(src_r[S_OWNER_REQUEST_READY]),
        .admission_pause(src_r[S_ADMISSION_PAUSE]),
        .owner_request(owner_request),
        .owner_request_done(src_r[S_OWNER_REQUEST_DONE]),
        .active_owner(src_r[S_ACTIVE_OWNER +: 2]),
        .owner_switch_pending(src_r[S_OWNER_SWITCH_PENDING]),
        .attention_launch_enable(src_r[S_ATTENTION_LAUNCH_ENABLE]),
        .mlp_launch_enable(src_r[S_MLP_LAUNCH_ENABLE]),
        .owner_protocol_error(src_r[S_OWNER_PROTOCOL_ERROR]),
        .ddr0_outstanding(src_r[S_DDR0_OUTSTANDING +: 8]),
        .ddr1_outstanding(src_r[S_DDR1_OUTSTANDING +: 8]),
        .maintenance_busy(src_r[S_MAINTENANCE_BUSY]),
        .maintenance_request_pending(
            src_r[S_MAINTENANCE_REQUEST_PENDING]),
        .mlp_abort_complete(src_r[S_MLP_ABORT_COMPLETE]),
        .paired_quiescent(src_r[S_PAIRED_QUIESCENT]),
        .paired_attn_bursts(src_r[S_PAIRED_ATTN_BURSTS +: 32]),
        .paired_mlp_bursts(src_r[S_PAIRED_MLP_BURSTS +: 32]),
        .paired_both_cycles(src_r[S_PAIRED_BOTH_CYCLES +: 32]),
        .paired_hol0(src_r[S_PAIRED_HOL0 +: 32]),
        .paired_hol1(src_r[S_PAIRED_HOL1 +: 32]),
        .paired_hwm0(src_r[S_PAIRED_HWM0 +: 32]),
        .paired_hwm1(src_r[S_PAIRED_HWM1 +: 32]),
        .mlp_command_valid(mlp_command_valid),
        .mlp_command_ready(src_r[S_MLP_COMMAND_READY]),
        .mlp_clear_pulse(mlp_clear_pulse),
        .mlp_abort_pending(mlp_abort_pending),
        .mlp_command_bank(mlp_command_bank),
        .mlp_gate_ddr0_base_addr(mlp_gate_ddr0_base_addr),
        .mlp_gate_ddr1_base_addr(mlp_gate_ddr1_base_addr),
        .mlp_down_ddr0_base_addr(mlp_down_ddr0_base_addr),
        .mlp_down_ddr1_base_addr(mlp_down_ddr1_base_addr),
        .mlp_input_base_addr(mlp_input_base_addr),
        .mlp_output_base_addr(mlp_output_base_addr),
        .mlp_command_id(mlp_command_id), .mlp_layer_id(mlp_layer_id),
        .mlp_input_bank_ready(src_r[S_MLP_INPUT_BANK_READY +: 2]),
        .mlp_busy(src_r[S_MLP_BUSY]), .mlp_done(src_r[S_MLP_DONE]),
        .mlp_error(src_r[S_MLP_ERROR]),
        .mlp_phase(src_r[S_MLP_PHASE +: 3]),
        .mlp_telemetry(src_r[S_MLP_TELEMETRY +: 1568]),
        .tensor_load_valid(tensor_load_valid),
        .tensor_load_ready(src_r[S_TENSOR_LOAD_READY]),
        .tensor_store_valid(tensor_store_valid),
        .tensor_store_ready(src_r[S_TENSOR_STORE_READY]),
        .tensor_store_armed(src_r[S_TENSOR_STORE_ARMED]),
        .tensor_dma_busy(src_r[S_TENSOR_DMA_BUSY]),
        .tensor_dma_done(src_r[S_TENSOR_DMA_DONE]),
        .tensor_dma_error(src_r[S_TENSOR_DMA_ERROR]),
        .tensor_dma_phase(src_r[S_TENSOR_DMA_PHASE +: 3]),
        .tensor_input_beat_count(
            src_r[S_TENSOR_INPUT_BEAT_COUNT +: 32]),
        .tensor_input_group_count(
            src_r[S_TENSOR_INPUT_GROUP_COUNT +: 32]),
        .tensor_output_beat_count(
            src_r[S_TENSOR_OUTPUT_BEAT_COUNT +: 32]),
        .tensor_output_tile_count(
            src_r[S_TENSOR_OUTPUT_TILE_COUNT +: 32]),
        .meta_gate_base_addr(meta_gate_base_addr),
        .meta_down_base_addr(meta_down_base_addr),
        .meta_dma_busy(src_r[S_META_DMA_BUSY]),
        .meta_dma_done(src_r[S_META_DMA_DONE]),
        .meta_dma_error(src_r[S_META_DMA_ERROR]),
        .meta_dma_phase(src_r[S_META_DMA_PHASE +: 3]),
        .meta_dma_gate_record_count(
            src_r[S_META_DMA_GATE_RECORD_COUNT +: 32]),
        .meta_dma_down_record_count(
            src_r[S_META_DMA_DOWN_RECORD_COUNT +: 32]),
        .meta_dma_physical_bytes(
            src_r[S_META_DMA_PHYSICAL_BYTES +: 64]),
        .meta_load_begin_valid(meta_load_begin_valid),
        .meta_load_begin_ready(src_r[S_META_LOAD_BEGIN_READY]),
        .meta_load_bank(meta_load_bank),
        .meta_commit_valid(meta_commit_valid),
        .meta_commit_ready(src_r[S_META_COMMIT_READY]),
        .meta_commit_bank(meta_commit_bank),
        .meta_commit_generation(meta_commit_generation),
        .meta_active_bank(src_r[S_META_ACTIVE_BANK]),
        .meta_active_generation(src_r[S_META_ACTIVE_GENERATION +: 32]),
        .meta_bank_valid(src_r[S_META_BANK_VALID +: 2]),
        .meta_bank_loading(src_r[S_META_BANK_LOADING +: 2]),
        .meta_gate_write_count_bank0(
            src_r[S_META_GATE_WRITE_COUNT_BANK0 +: 32]),
        .meta_gate_write_count_bank1(
            src_r[S_META_GATE_WRITE_COUNT_BANK1 +: 32]),
        .meta_down_write_count_bank0(
            src_r[S_META_DOWN_WRITE_COUNT_BANK0 +: 32]),
        .meta_down_write_count_bank1(
            src_r[S_META_DOWN_WRITE_COUNT_BANK1 +: 32]),
        .meta_error(src_r[S_META_ERROR]), .irq(irq),
        .done_sticky(done_sticky), .error_sticky(error_sticky)
    );

    initial begin
        if (SRC_W != 2335 || $bits(dut_outputs) != SINK_W)
            $error("MLP AXI-Lite registered OOC vector layout mismatch");
    end
endmodule
