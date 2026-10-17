`timescale 1ns / 1ps

// Board-level HAP Attention FixBit v2 core.  MIG/XDMA/SmartConnect remain in
// the Vivado Block Design; every port below is a real active datapath.
module hap_attention_board_core (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 core_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 150000000, ASSOCIATED_BUSIF S_AXIL:M_AXI_DATA, ASSOCIATED_RESET core_rst_n" *)
    input  wire          core_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 core_rst_n RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire          core_rst_n,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL AWADDR" *) input wire [11:0] s_axil_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL AWVALID" *) input wire s_axil_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL AWREADY" *) output wire s_axil_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WDATA" *) input wire [31:0] s_axil_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WSTRB" *) input wire [3:0] s_axil_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WVALID" *) input wire s_axil_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WREADY" *) output wire s_axil_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL BRESP" *) output wire [1:0] s_axil_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL BVALID" *) output wire s_axil_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL BREADY" *) input wire s_axil_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL ARADDR" *) input wire [11:0] s_axil_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL ARVALID" *) input wire s_axil_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL ARREADY" *) output wire s_axil_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RDATA" *) output wire [31:0] s_axil_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RRESP" *) output wire [1:0] s_axil_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RVALID" *) output wire s_axil_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RREADY" *) input wire s_axil_rready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARVALID" *) output wire m_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARREADY" *) input wire m_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARADDR" *) output wire [31:0] m_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARLEN" *) output wire [7:0] m_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARSIZE" *) output wire [2:0] m_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARBURST" *) output wire [1:0] m_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RVALID" *) input wire m_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RREADY" *) output wire m_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RDATA" *) input wire [255:0] m_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RRESP" *) input wire [1:0] m_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RLAST" *) input wire m_axi_rlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWVALID" *) output wire m_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWREADY" *) input wire m_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWADDR" *) output wire [31:0] m_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWLEN" *) output wire [7:0] m_axi_awlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWSIZE" *) output wire [2:0] m_axi_awsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWBURST" *) output wire [1:0] m_axi_awburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WVALID" *) output wire m_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WREADY" *) input wire m_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WDATA" *) output wire [255:0] m_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WSTRB" *) output wire [31:0] m_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WLAST" *) output wire m_axi_wlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA BVALID" *) input wire m_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA BREADY" *) output wire m_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA BRESP" *) input wire [1:0] m_axi_bresp,

    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ddr0_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 300000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C0, ASSOCIATED_RESET ddr0_rst_n" *) input wire ddr0_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ddr0_rst_n RST" *) input wire ddr0_rst_n,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARVALID" *) output wire ddr0_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARREADY" *) input wire ddr0_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4, DATA_WIDTH 512, ADDR_WIDTH 32, READ_WRITE_MODE READ_ONLY, MAX_BURST_LENGTH 16, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] ddr0_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARLEN" *) output wire [7:0] ddr0_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARSIZE" *) output wire [2:0] ddr0_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARBURST" *) output wire [1:0] ddr0_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RVALID" *) input wire ddr0_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RREADY" *) output wire ddr0_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RDATA" *) input wire [511:0] ddr0_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RRESP" *) input wire [1:0] ddr0_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RLAST" *) input wire ddr0_axi_rlast,
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ddr1_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 300000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1, ASSOCIATED_RESET ddr1_rst_n" *) input wire ddr1_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ddr1_rst_n RST" *) input wire ddr1_rst_n,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARVALID" *) output wire ddr1_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARREADY" *) input wire ddr1_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4, DATA_WIDTH 512, ADDR_WIDTH 32, READ_WRITE_MODE READ_ONLY, MAX_BURST_LENGTH 16, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] ddr1_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARLEN" *) output wire [7:0] ddr1_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARSIZE" *) output wire [2:0] ddr1_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARBURST" *) output wire [1:0] ddr1_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RVALID" *) input wire ddr1_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RREADY" *) output wire ddr1_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RDATA" *) input wire [511:0] ddr1_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RRESP" *) input wire [1:0] ddr1_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RLAST" *) input wire ddr1_axi_rlast,
    input  wire attention_launch_enable,
    input  wire engine_soft_clear,
    input  wire command_pause,
    output wire weight_source_quiescent,
    output wire ddr_quiescent,
    output wire data_axi_busy,
    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq INTERRUPT" *)
    (* X_INTERFACE_PARAMETER = "SENSITIVITY LEVEL_HIGH" *)
    output wire irq
);
    localparam [3:0] ST_IDLE=0, ST_META_CMD=1, ST_META_DATA=2,
        ST_ROPE_CMD=3, ST_ROPE_DATA=4, ST_INPUT_CMD=5,
        ST_INPUT_DATA=6, ST_LAUNCH=7, ST_RUN=8,
        ST_OUTPUT_CMD=9, ST_OUTPUT_DATA=10, ST_ERROR=15;
    reg [3:0] state_r;
    reg board_done_r, board_error_r;
    reg [31:0] board_error_code_r;
    reg metadata_loaded_r, rope_loaded_r;
    reg compute_complete_r;
    reg rope_dma_complete_r;
    wire control_start, control_clear, reload_metadata, reload_rope;
    wire preserve_historical_kv;
    wire [31:0] command_id, layer_id, run_format_id;
    wire [6:0] query_start;
    wire [7:0] valid_key_count, query_count;
    wire [31:0] input_base, output_base, weight_c0_base, weight_c1_base;
    wire [31:0] weight_meta_base, rope_base;
    wire dma_done;
    wire engine_busy = state_r != ST_IDLE;
    // V4 preserves the old Attention control clear as a sticky-status
    // acknowledgement. Fabric maintenance is a separate global transaction.
    wire system_clear = engine_soft_clear;
    wire launch_compute_clear = (state_r==ST_INPUT_DATA) && dma_done &&
        !preserve_historical_kv;
    wire compute_clear = system_clear || launch_compute_clear;

    wire compute_busy, compute_done, compute_error;
    wire weight_command_ready;
    wire [31:0] compute_cycles, compute_weight_groups;
    wire [31:0] compute_projection_tiles, compute_attention_rows;
    wire [31:0] compute_wo_tiles;
    wire [31:0] compute_input_cycles, compute_qkv_cycles;
    wire [31:0] compute_rope_cycles, compute_kv12_cycles;
    wire [31:0] compute_attention_cycles, compute_context_cycles;
    wire [31:0] compute_wo_cycles, compute_control_cycles;

    hap_attention_axil_control u_control (
        .clk(core_clk), .rst_n(core_rst_n),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awvalid(s_axil_awvalid),
        .s_axil_awready(s_axil_awready), .s_axil_wdata(s_axil_wdata),
        .s_axil_wstrb(s_axil_wstrb), .s_axil_wvalid(s_axil_wvalid),
        .s_axil_wready(s_axil_wready), .s_axil_bresp(s_axil_bresp),
        .s_axil_bvalid(s_axil_bvalid), .s_axil_bready(s_axil_bready),
        .s_axil_araddr(s_axil_araddr), .s_axil_arvalid(s_axil_arvalid),
        .s_axil_arready(s_axil_arready), .s_axil_rdata(s_axil_rdata),
        .s_axil_rresp(s_axil_rresp), .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(s_axil_rready), .engine_busy(engine_busy),
        .launch_enable(attention_launch_enable && !command_pause),
        .maintenance_busy(command_pause),
        .engine_done(board_done_r), .engine_error(board_error_r),
        .engine_error_code(board_error_code_r),
        .metadata_loaded(metadata_loaded_r), .rope_loaded(rope_loaded_r),
        .cycle_count(compute_cycles),
        .weight_group_count(compute_weight_groups),
        .projection_tile_count(compute_projection_tiles),
        .attention_row_count(compute_attention_rows),
        .wo_tile_count(compute_wo_tiles),
        .input_frontend_cycle_count(compute_input_cycles),
        .qkv_projection_cycle_count(compute_qkv_cycles),
        .rope_cycle_count(compute_rope_cycles),
        .kv12_cycle_count(compute_kv12_cycles),
        .attention_cycle_count(compute_attention_cycles),
        .context_frontend_cycle_count(compute_context_cycles),
        .wo_projection_cycle_count(compute_wo_cycles),
        .control_overhead_cycle_count(compute_control_cycles),
        .start_pulse(control_start),
        .clear_pulse(control_clear), .reload_metadata(reload_metadata),
        .reload_rope(reload_rope),
        .preserve_historical_kv(preserve_historical_kv),
        .command_id(command_id), .layer_id(layer_id),
        .query_start(query_start), .valid_key_count(valid_key_count),
        .query_count(query_count), .run_format_id(run_format_id),
        .input_base(input_base), .output_base(output_base),
        .weight_c0_base(weight_c0_base), .weight_c1_base(weight_c1_base),
        .weight_meta_base(weight_meta_base), .rope_base(rope_base),
        .irq(irq), .done_sticky(), .error_sticky()
    );

    wire dma_cmd_valid = (state_r==ST_META_CMD)||(state_r==ST_ROPE_CMD)||
        (state_r==ST_INPUT_CMD)||(state_r==ST_OUTPUT_CMD);
    wire dma_cmd_ready, dma_busy, dma_error;
    assign data_axi_busy = dma_busy;
    wire dma_cmd_write = state_r==ST_OUTPUT_CMD;
    wire [31:0] dma_cmd_base = state_r==ST_META_CMD ? weight_meta_base :
        state_r==ST_ROPE_CMD ? rope_base :
        state_r==ST_INPUT_CMD ? input_base : output_base;
    wire [31:0] dma_cmd_beats = state_r==ST_META_CMD ? 32'd81920 :
        state_r==ST_ROPE_CMD ? 32'd128 : 32'd3072;
    wire dma_rd_valid, dma_rd_ready, dma_rd_last;
    wire [255:0] dma_rd_data;
    wire dma_wr_valid, dma_wr_ready;
    wire [255:0] dma_wr_data;

    hap_axi256_dma u_dma (
        .clk(core_clk), .rst_n(core_rst_n), .clear(system_clear),
        .cmd_valid(dma_cmd_valid), .cmd_ready(dma_cmd_ready),
        .cmd_write(dma_cmd_write), .cmd_base_addr(dma_cmd_base),
        .cmd_beat_count(dma_cmd_beats), .busy(dma_busy), .done(dma_done),
        .error(dma_error), .rd_valid(dma_rd_valid),
        .rd_ready(dma_rd_ready), .rd_data(dma_rd_data),
        .rd_last(dma_rd_last), .wr_valid(dma_wr_valid),
        .wr_ready(dma_wr_ready), .wr_data(dma_wr_data),
        .m_axi_arvalid(m_axi_arvalid), .m_axi_arready(m_axi_arready),
        .m_axi_araddr(m_axi_araddr), .m_axi_arlen(m_axi_arlen),
        .m_axi_arsize(m_axi_arsize), .m_axi_arburst(m_axi_arburst),
        .m_axi_rvalid(m_axi_rvalid), .m_axi_rready(m_axi_rready),
        .m_axi_rdata(m_axi_rdata), .m_axi_rresp(m_axi_rresp),
        .m_axi_rlast(m_axi_rlast), .m_axi_awvalid(m_axi_awvalid),
        .m_axi_awready(m_axi_awready), .m_axi_awaddr(m_axi_awaddr),
        .m_axi_awlen(m_axi_awlen), .m_axi_awsize(m_axi_awsize),
        .m_axi_awburst(m_axi_awburst), .m_axi_wvalid(m_axi_wvalid),
        .m_axi_wready(m_axi_wready), .m_axi_wdata(m_axi_wdata),
        .m_axi_wstrb(m_axi_wstrb), .m_axi_wlast(m_axi_wlast),
        .m_axi_bvalid(m_axi_bvalid), .m_axi_bready(m_axi_bready),
        .m_axi_bresp(m_axi_bresp), .command_count(), .read_beat_count(),
        .write_beat_count(), .burst_count(), .protocol_error_count()
    );

    reg [16:0] artifact_index_r;
    wire meta_wr_valid = state_r==ST_META_DATA && dma_rd_valid;
    wire meta_wr_ready;
    wire meta_rd_ready, meta_rsp_valid, meta_rsp_ready;
    wire [255:0] meta_rsp_data;
    wire meta_store_error;
    reg [16:0] meta_read_addr_r;
    reg meta_read_pending_r;
    wire meta_rd_valid = state_r==ST_RUN &&
        (meta_read_addr_r < 17'd81920) && !meta_read_pending_r;
    wire meta_rd_fire = meta_rd_valid && meta_rd_ready;
    wire meta_rsp_fire = meta_rsp_valid && meta_rsp_ready;

    hap_weight_meta_resident u_meta (
        .clk(core_clk), .rst_n(core_rst_n), .clear(system_clear),
        .wr_valid(meta_wr_valid), .wr_ready(meta_wr_ready),
        .wr_addr(artifact_index_r), .wr_meta16(dma_rd_data),
        .rd_valid(meta_rd_valid), .rd_ready(meta_rd_ready),
        .rd_addr(meta_read_addr_r), .rsp_valid(meta_rsp_valid),
        .rsp_ready(meta_rsp_ready), .rsp_meta16(meta_rsp_data),
        .write_count(), .read_count(), .format_error_count(),
        .error(meta_store_error)
    );

    reg rope_buffer_valid_r;
    reg [255:0] rope_buffer_r;
    reg [1:0] rope_subindex_r;
    reg [8:0] rope_record_addr_r;
    wire rope_wr_valid = state_r==ST_ROPE_DATA && rope_buffer_valid_r;
    wire rope_wr_ready;
    wire [63:0] rope_record =
        rope_buffer_r[rope_subindex_r*64 +: 64];

    wire input_wr_valid = state_r==ST_INPUT_DATA && dma_rd_valid;
    wire input_wr_ready;
    wire activation_valid, activation_ready;
    wire [6:0] activation_group;
    wire [6143:0] activation_s24;
    wire input_buffer_busy, input_buffer_error;
    wire input_load_start = state_r==ST_LAUNCH && weight_command_ready;
    hap_tensor24_input_buffer u_input_buffer (
        .clk(core_clk), .rst_n(core_rst_n), .clear(system_clear),
        .wr_valid(input_wr_valid), .wr_ready(input_wr_ready),
        .wr_addr(artifact_index_r[11:0]), .wr_data(dma_rd_data),
        .load_start(input_load_start),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_group(activation_group),
        .activation_s24(activation_s24), .busy(input_buffer_busy),
        .error(input_buffer_error)
    );

    // command_pause closes admission at the AXI-Lite launch boundary.  Once
    // a board command has reached ST_LAUNCH, its fixed-size weight command
    // must still start and finish; pausing here would strand ST_LAUNCH.
    wire weight_command_valid = state_r==ST_LAUNCH;
    wire weight_frontend_busy, weight_frontend_error;
    assign ddr_quiescent = !engine_busy && !weight_frontend_busy;
    wire weight_valid, weight_ready;
    wire [9:0] weight_tile;
    wire [6:0] weight_group;
    wire [4095:0] weight_s8;
    wire [255:0] weight_meta16;
    hap_dual_ddr_weight_frontend u_weight_frontend (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(system_clear), .command_valid(weight_command_valid),
        .command_ready(weight_command_ready),
        .ddr0_base_addr(weight_c0_base), .ddr1_base_addr(weight_c1_base),
        .group_count(17'd81920), .ddr0_clk(ddr0_clk),
        .ddr0_rst_n(ddr0_rst_n), .ddr0_axi_arvalid(ddr0_axi_arvalid),
        .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize),
        .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid),
        .ddr0_axi_rready(ddr0_axi_rready), .ddr0_axi_rdata(ddr0_axi_rdata),
        .ddr0_axi_rresp(ddr0_axi_rresp), .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(ddr1_axi_arvalid),
        .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize),
        .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid),
        .ddr1_axi_rready(ddr1_axi_rready), .ddr1_axi_rdata(ddr1_axi_rdata),
        .ddr1_axi_rresp(ddr1_axi_rresp), .ddr1_axi_rlast(ddr1_axi_rlast),
        .meta_valid(meta_rsp_valid), .meta_ready(meta_rsp_ready),
        .meta_tile(meta_read_addr_r[16:7]),
        .meta_group(meta_read_addr_r[6:0]), .meta16(meta_rsp_data),
        .out_valid(weight_valid), .out_ready(weight_ready),
        .out_tile(weight_tile), .out_group(weight_group),
        .out_weight_s8(weight_s8), .out_meta16(weight_meta16),
        .busy(weight_frontend_busy), .error(weight_frontend_error)
    );
    // A started command is allowed to complete naturally.  This avoids the
    // deadlock caused by pausing AR issue in the middle of a fixed-size reader
    // command while still preventing a new command from entering ST_LAUNCH.
    assign weight_source_quiescent = command_pause &&
        !weight_command_valid && !weight_frontend_busy;

    wire compute_out_valid, compute_out_ready;
    wire [7:0] compute_out_tile;
    wire [3071:0] compute_out_s24;
    wire output_image_ready, output_buffer_error;
    wire output_rd_valid, output_rd_ready, output_rsp_valid;
    wire [255:0] output_rsp_data;
    reg [11:0] output_read_addr_r;
    wire output_rsp_fire = output_rsp_valid && dma_wr_ready;
    assign dma_wr_valid = state_r==ST_OUTPUT_DATA && output_rsp_valid;
    assign dma_wr_data = output_rsp_data;
    assign output_rd_valid = state_r==ST_OUTPUT_DATA &&
        (output_read_addr_r < 3072);
    hap_tensor24_output_buffer u_output_buffer (
        .clk(core_clk), .rst_n(core_rst_n), .clear(system_clear),
        .in_valid(compute_out_valid), .in_ready(compute_out_ready),
        .in_tile(compute_out_tile), .in_s24(compute_out_s24),
        .image_ready(output_image_ready), .image_release(dma_done &&
            state_r==ST_OUTPUT_DATA), .rd_valid(output_rd_valid),
        .rd_ready(output_rd_ready), .rd_addr(output_read_addr_r),
        .rsp_valid(output_rsp_valid), .rsp_ready(dma_wr_ready),
        .rsp_data(output_rsp_data), .error(output_buffer_error)
    );

    wire compute_start = state_r==ST_LAUNCH && weight_command_ready;
    hap_attention_compute_top u_compute (
        .clk(core_clk), .rst_n(core_rst_n), .clear(compute_clear),
        .start(compute_start), .format_id(run_format_id),
        .query_start(query_start), .valid_key_count(valid_key_count),
        .busy(compute_busy), .done(compute_done), .error(compute_error),
        .rope_wr_valid(rope_wr_valid), .rope_wr_ready(rope_wr_ready),
        .rope_wr_addr(rope_record_addr_r),
        .rope_wr_cos_s18(rope_record[17:0]),
        .rope_wr_sin_s18(rope_record[35:18]),
        .kv_preload_valid(1'b0), .kv_preload_ready(),
        .kv_preload_is_v(1'b0), .kv_preload_addr(12'd0),
        .kv_preload_s12(384'd0), .kv_preload_meta16(16'd0),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_group(activation_group),
        .activation_s24(activation_s24), .weight_valid(weight_valid),
        .weight_ready(weight_ready), .weight_tile(weight_tile),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16), .out_valid(compute_out_valid),
        .out_ready(compute_out_ready), .out_tile(compute_out_tile),
        .out_s24(compute_out_s24), .cycle_count(compute_cycles),
        .accepted_weight_group_count(compute_weight_groups),
        .completed_projection_tile_count(compute_projection_tiles),
        .completed_attention_row_count(compute_attention_rows),
        .completed_wo_tile_count(compute_wo_tiles),
        .input_frontend_cycle_count(compute_input_cycles),
        .qkv_projection_cycle_count(compute_qkv_cycles),
        .rope_cycle_count(compute_rope_cycles),
        .kv12_cycle_count(compute_kv12_cycles),
        .attention_cycle_count(compute_attention_cycles),
        .context_frontend_cycle_count(compute_context_cycles),
        .wo_projection_cycle_count(compute_wo_cycles),
        .control_overhead_cycle_count(compute_control_cycles)
    );

    assign dma_rd_ready = state_r==ST_META_DATA ? meta_wr_ready :
        state_r==ST_ROPE_DATA ? !rope_buffer_valid_r :
        state_r==ST_INPUT_DATA ? input_wr_ready : 1'b0;

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            state_r <= ST_IDLE;
            board_done_r <= 1'b0;
            board_error_r <= 1'b0;
            board_error_code_r <= 32'd0;
            metadata_loaded_r <= 1'b0;
            rope_loaded_r <= 1'b0;
            compute_complete_r <= 1'b0;
            rope_dma_complete_r <= 1'b0;
            artifact_index_r <= 17'd0;
            rope_buffer_valid_r <= 1'b0;
            rope_buffer_r <= 256'd0;
            rope_subindex_r <= 2'd0;
            rope_record_addr_r <= 9'd0;
            meta_read_addr_r <= 17'd0;
            meta_read_pending_r <= 1'b0;
            output_read_addr_r <= 12'd0;
        end else begin
            board_done_r <= 1'b0;
            board_error_r <= 1'b0;
            if (system_clear) begin
                state_r <= ST_IDLE;
                artifact_index_r <= 17'd0;
                rope_buffer_valid_r <= 1'b0;
                compute_complete_r <= 1'b0;
                rope_dma_complete_r <= 1'b0;
                meta_read_addr_r <= 17'd0;
                meta_read_pending_r <= 1'b0;
                output_read_addr_r <= 12'd0;
                board_error_code_r <= 32'd0;
            end else begin
                case (state_r)
                    ST_IDLE: if (control_start) begin
                        artifact_index_r <= 17'd0;
                        rope_record_addr_r <= 9'd0;
                        rope_subindex_r <= 2'd0;
                        rope_buffer_valid_r <= 1'b0;
                        compute_complete_r <= 1'b0;
                        rope_dma_complete_r <= 1'b0;
                        if (reload_metadata) begin
                            metadata_loaded_r <= 1'b0;
                            state_r <= ST_META_CMD;
                        end else if (reload_rope) begin
                            rope_loaded_r <= 1'b0;
                            state_r <= ST_ROPE_CMD;
                        end else state_r <= ST_INPUT_CMD;
                    end
                    ST_META_CMD: if (dma_cmd_valid && dma_cmd_ready) begin
                        artifact_index_r <= 17'd0;
                        state_r <= ST_META_DATA;
                    end
                    ST_META_DATA: begin
                        if (dma_rd_valid && dma_rd_ready)
                            artifact_index_r <= artifact_index_r + 1'b1;
                        if (dma_done) begin
                            if (artifact_index_r +
                                (dma_rd_valid && dma_rd_ready) !=
                                17'd81920) begin
                                board_error_code_r <= 32'h0000_0002;
                                state_r <= ST_ERROR;
                            end else begin
                                metadata_loaded_r <= 1'b1;
                                if (reload_rope) begin
                                    rope_loaded_r <= 1'b0;
                                    state_r <= ST_ROPE_CMD;
                                end else state_r <= ST_INPUT_CMD;
                            end
                        end
                    end
                    ST_ROPE_CMD: if (dma_cmd_valid && dma_cmd_ready) begin
                        artifact_index_r <= 17'd0;
                        rope_record_addr_r <= 9'd0;
                        rope_dma_complete_r <= 1'b0;
                        state_r <= ST_ROPE_DATA;
                    end
                    ST_ROPE_DATA: begin
                        if (dma_rd_valid && dma_rd_ready) begin
                            rope_buffer_r <= dma_rd_data;
                            rope_buffer_valid_r <= 1'b1;
                            rope_subindex_r <= 2'd0;
                            artifact_index_r <= artifact_index_r + 1'b1;
                        end
                        if (rope_wr_valid && rope_wr_ready) begin
                            rope_record_addr_r <= rope_record_addr_r + 1'b1;
                            if (rope_subindex_r == 3) begin
                                rope_subindex_r <= 0;
                                rope_buffer_valid_r <= 0;
                            end else rope_subindex_r <= rope_subindex_r + 1'b1;
                        end
                        if (dma_done)
                            rope_dma_complete_r <= 1'b1;
                        if ((rope_dma_complete_r || dma_done) &&
                            !(rope_buffer_valid_r ||
                              (dma_rd_valid && dma_rd_ready))) begin
                            if (artifact_index_r != 128 ||
                                rope_record_addr_r != 0) begin
                                board_error_code_r <= 32'h0000_0004;
                                state_r <= ST_ERROR;
                            end else begin
                                rope_loaded_r <= 1'b1;
                                rope_dma_complete_r <= 1'b0;
                                state_r <= ST_INPUT_CMD;
                            end
                        end
                    end
                    ST_INPUT_CMD: if (dma_cmd_valid && dma_cmd_ready) begin
                        artifact_index_r <= 0;
                        state_r <= ST_INPUT_DATA;
                    end
                    ST_INPUT_DATA: begin
                        if (dma_rd_valid && dma_rd_ready)
                            artifact_index_r <= artifact_index_r + 1'b1;
                        if (dma_done) begin
                            if (artifact_index_r +
                                (dma_rd_valid && dma_rd_ready) != 3072) begin
                                board_error_code_r <= 32'h0000_0008;
                                state_r <= ST_ERROR;
                            end else state_r <= ST_LAUNCH;
                        end
                    end
                    ST_LAUNCH: if (weight_command_ready) begin
                        meta_read_addr_r <= 0;
                        meta_read_pending_r <= 0;
                        compute_complete_r <= 1'b0;
                        state_r <= ST_RUN;
                    end
                    ST_RUN: begin
                        if (compute_done)
                            compute_complete_r <= 1'b1;
                        if ((compute_complete_r || compute_done) &&
                            output_image_ready) begin
                            compute_complete_r <= 1'b0;
                            output_read_addr_r <= 0;
                            state_r <= ST_OUTPUT_CMD;
                        end
                    end
                    ST_OUTPUT_CMD: if (dma_cmd_valid && dma_cmd_ready)
                        state_r <= ST_OUTPUT_DATA;
                    ST_OUTPUT_DATA: begin
                        if (output_rsp_fire)
                            output_read_addr_r <= output_read_addr_r + 1'b1;
                        if (dma_done) begin
                            if (output_read_addr_r != 3072) begin
                                board_error_code_r <= 32'h0000_0010;
                                state_r <= ST_ERROR;
                            end else begin
                                board_done_r <= 1'b1;
                                state_r <= ST_IDLE;
                            end
                        end
                    end
                    ST_ERROR: begin
                        board_error_r <= 1'b1;
                        state_r <= ST_IDLE;
                    end
                    default: begin
                        board_error_code_r <= 32'h8000_0000;
                        state_r <= ST_ERROR;
                    end
                endcase
                if (meta_rd_fire)
                    meta_read_pending_r <= 1'b1;
                if (meta_rsp_fire) begin
                    meta_read_pending_r <= 1'b0;
                    meta_read_addr_r <= meta_read_addr_r + 1'b1;
                end
                if ((dma_error || meta_store_error || input_buffer_error ||
                    output_buffer_error || weight_frontend_error ||
                    compute_error) && state_r != ST_IDLE) begin
                    board_error_code_r <= 32'h4000_0000;
                    state_r <= ST_ERROR;
                end
            end
        end
    end
endmodule
