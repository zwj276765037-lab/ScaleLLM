`timescale 1ns / 1ps

// Board-level cohort16 Attention core. MIG/XDMA/SmartConnect remain in the
// Vivado Block Design; every port below is a real active datapath.
module hap_attention_board_cohort16_core #(
    parameter integer COMMAND_TIMEOUT_CYCLES = 10000000
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 core_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 100000000, ASSOCIATED_BUSIF S_AXIL:M_AXI_DATA, ASSOCIATED_RESET core_rst_n" *)
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
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C0, ASSOCIATED_RESET ddr0_rst_n" *) input wire ddr0_clk,
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
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1, ASSOCIATED_RESET ddr1_rst_n" *) input wire ddr1_clk,
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
    localparam [7:0] COMPLETION_SUCCESS=8'h00,
        COMPLETION_PROTOCOL_ERROR=8'h01,
        COMPLETION_DDR_ERROR=8'h02,
        COMPLETION_FORMAT_ERROR=8'h03,
        COMPLETION_TIMEOUT=8'h04,
        COMPLETION_MAINTENANCE_ABORT=8'h05,
        COMPLETION_INTERNAL_ERROR=8'hff;
    reg [3:0] state_r;
    reg board_done_r, board_error_r;
    reg [31:0] board_error_code_r;
    reg [7:0] board_completion_status_r;
    reg [31:0] command_cycle_count_r;
    reg command_abort_clear_r;
    reg metadata_loaded_r, rope_loaded_r;
    reg compute_complete_r;
    reg rope_dma_complete_r;
    wire control_start, control_clear;
    wire control_reload_metadata, control_reload_rope;
    wire control_preserve_historical_kv;
    wire [31:0] control_request_id, control_command_id;
    wire [15:0] control_cohort_id, control_buffer_id;
    wire [31:0] control_layer_id, control_run_format_id;
    wire [6:0] control_query_start;
    wire [7:0] control_valid_key_count, control_query_count;
    wire [31:0] control_input_base, control_output_base;
    wire [31:0] control_weight_c0_base, control_weight_c1_base;
    wire [31:0] control_weight_meta_base, control_rope_base;

    reg [31:0] active_request_id_r, active_command_id_r;
    reg [15:0] active_cohort_id_r, active_buffer_id_r;
    reg [5:0] active_layer_id_r;
    reg [31:0] active_run_format_id_r;
    reg [6:0] active_query_start_r;
    reg [7:0] active_valid_key_count_r, active_query_count_r;
    reg [31:0] active_input_base_r, active_output_base_r;
    reg [31:0] active_weight_c0_base_r, active_weight_c1_base_r;
    reg [31:0] active_weight_meta_base_r, active_rope_base_r;
    reg active_reload_metadata_r, active_reload_rope_r;
    reg active_preserve_historical_kv_r;
    wire dma_done;
    wire engine_busy = state_r != ST_IDLE;
    // V4 preserves the old Attention control clear as a sticky-status
    // acknowledgement. Fabric maintenance is a separate global transaction.
    wire system_clear = engine_soft_clear;
    wire datapath_clear = system_clear || command_abort_clear_r;
    wire launch_compute_clear = (state_r==ST_INPUT_DATA) && dma_done &&
        !active_preserve_historical_kv_r;
    wire compute_clear = datapath_clear || launch_compute_clear;

    wire compute_busy, compute_done, compute_error;
    wire weight_command_ready;
    wire [31:0] compute_cycles, compute_weight_groups;
    wire [31:0] compute_consumed_wave_groups;
    wire [31:0] compute_released_weight_groups;
    wire [31:0] compute_projection_wave_tiles;
    wire [31:0] compute_projection_tiles, compute_attention_rows;
    wire [31:0] compute_wo_tiles;
    wire [31:0] compute_input_cycles, compute_qkv_cycles;
    wire [31:0] compute_rope_cycles, compute_kv12_cycles;
    wire [31:0] compute_attention_cycles, compute_context_cycles;
    wire [31:0] compute_wo_cycles, compute_control_cycles;

    wire completion_valid = board_done_r || board_error_r;
    hap_attention_cohort16_axil_control u_control (
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
        .completion_valid(completion_valid),
        .completion_request_id(active_request_id_r),
        .completion_command_id(active_command_id_r),
        .completion_cohort_id(active_cohort_id_r),
        .completion_buffer_id(active_buffer_id_r),
        .completion_layer_id(active_layer_id_r),
        .completion_op_id(3'd0),
        .completion_status(board_error_r ? board_completion_status_r :
            COMPLETION_SUCCESS),
        .start_pulse(control_start),
        .clear_pulse(control_clear),
        .reload_metadata(control_reload_metadata),
        .reload_rope(control_reload_rope),
        .preserve_historical_kv(control_preserve_historical_kv),
        .request_id(control_request_id), .command_id(control_command_id),
        .cohort_id(control_cohort_id), .buffer_id(control_buffer_id),
        .layer_id(control_layer_id), .query_start(control_query_start),
        .valid_key_count(control_valid_key_count),
        .query_count(control_query_count),
        .run_format_id(control_run_format_id),
        .input_base(control_input_base), .output_base(control_output_base),
        .weight_c0_base(control_weight_c0_base),
        .weight_c1_base(control_weight_c1_base),
        .weight_meta_base(control_weight_meta_base),
        .rope_base(control_rope_base),
        .irq(irq), .done_sticky(), .error_sticky()
    );

    wire dma_cmd_valid = (state_r==ST_META_CMD)||(state_r==ST_ROPE_CMD)||
        (state_r==ST_INPUT_CMD)||(state_r==ST_OUTPUT_CMD);
    wire dma_cmd_ready, dma_busy, dma_error;
    assign data_axi_busy = dma_busy;
    wire dma_cmd_write = state_r==ST_OUTPUT_CMD;
    wire [31:0] dma_cmd_base = state_r==ST_META_CMD ?
        active_weight_meta_base_r : state_r==ST_ROPE_CMD ?
        active_rope_base_r : state_r==ST_INPUT_CMD ?
        active_input_base_r : active_output_base_r;
    wire [31:0] dma_cmd_beats = state_r==ST_META_CMD ? 32'd81920 :
        state_r==ST_ROPE_CMD ? 32'd256 : 32'd6144;
    wire dma_rd_valid, dma_rd_ready, dma_rd_last;
    wire [255:0] dma_rd_data;
    wire dma_wr_valid, dma_wr_ready;
    wire [255:0] dma_wr_data;

    hap_axi256_dma u_dma (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
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
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
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
    reg [9:0] rope_record_addr_r;
    wire rope_wr_valid = state_r==ST_ROPE_DATA && rope_buffer_valid_r;
    wire rope_wr_ready;
    wire [63:0] rope_record =
        rope_buffer_r[rope_subindex_r*64 +: 64];

    wire input_wr_valid = state_r==ST_INPUT_DATA && dma_rd_valid;
    wire input_wr_ready;
    wire activation_valid, activation_ready;
    wire activation_wave;
    wire [6:0] activation_group;
    wire [6143:0] activation_s24;
    wire input_buffer_busy, input_buffer_error;
    wire input_load_start = state_r==ST_LAUNCH && weight_command_ready;
    hap_tensor24_input_buffer16 u_input_buffer (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
        .wr_valid(input_wr_valid), .wr_ready(input_wr_ready),
        .wr_addr(artifact_index_r[12:0]), .wr_data(dma_rd_data),
        .load_start(input_load_start),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_wave(activation_wave),
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
        .core_clear(datapath_clear), .command_valid(weight_command_valid),
        .command_ready(weight_command_ready),
        .ddr0_base_addr(active_weight_c0_base_r),
        .ddr1_base_addr(active_weight_c1_base_r),
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
    wire compute_out_wave;
    wire [7:0] compute_out_tile;
    wire [3071:0] compute_out_s24;
    wire output_image_ready, output_buffer_error;
    wire output_rd_valid, output_rd_ready, output_rsp_valid;
    wire [255:0] output_rsp_data;
    reg [12:0] output_read_addr_r;
    wire output_rsp_fire = output_rsp_valid && dma_wr_ready;
    assign dma_wr_valid = state_r==ST_OUTPUT_DATA && output_rsp_valid;
    assign dma_wr_data = output_rsp_data;
    assign output_rd_valid = state_r==ST_OUTPUT_DATA &&
        (output_read_addr_r < 13'd6144);
    hap_tensor24_output_buffer16 u_output_buffer (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
        .in_valid(compute_out_valid), .in_ready(compute_out_ready),
        .in_wave(compute_out_wave), .in_tile(compute_out_tile),
        .in_s24(compute_out_s24),
        .image_ready(output_image_ready), .image_release(dma_done &&
            state_r==ST_OUTPUT_DATA), .rd_valid(output_rd_valid),
        .rd_ready(output_rd_ready), .rd_addr(output_read_addr_r),
        .rsp_valid(output_rsp_valid), .rsp_ready(dma_wr_ready),
        .rsp_data(output_rsp_data), .error(output_buffer_error)
    );

    wire compute_start = state_r==ST_LAUNCH && weight_command_ready;
    hap_attention_compute_cohort16_top u_compute (
        .clk(core_clk), .rst_n(core_rst_n), .clear(compute_clear),
        .start(compute_start), .format_id(active_run_format_id_r),
        .request_id(active_request_id_r),
        .cohort_id(active_cohort_id_r), .layer_id(active_layer_id_r),
        .query_start(active_query_start_r),
        .query_count(active_query_count_r),
        .valid_key_count(active_valid_key_count_r),
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
        .activation_wave(activation_wave),
        .activation_group(activation_group),
        .activation_s24(activation_s24), .weight_valid(weight_valid),
        .weight_ready(weight_ready), .weight_tile(weight_tile),
        .weight_group(weight_group), .weight_s8(weight_s8),
        .weight_meta16(weight_meta16), .out_valid(compute_out_valid),
        .out_ready(compute_out_ready), .out_wave(compute_out_wave),
        .out_tile(compute_out_tile),
        .out_s24(compute_out_s24), .cycle_count(compute_cycles),
        .accepted_weight_group_count(compute_weight_groups),
        .consumed_wave_group_count(compute_consumed_wave_groups),
        .released_weight_group_count(compute_released_weight_groups),
        .completed_projection_wave_tile_count(compute_projection_wave_tiles),
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
            board_completion_status_r <= COMPLETION_SUCCESS;
            command_cycle_count_r <= 32'd0;
            command_abort_clear_r <= 1'b0;
            metadata_loaded_r <= 1'b0;
            rope_loaded_r <= 1'b0;
            compute_complete_r <= 1'b0;
            rope_dma_complete_r <= 1'b0;
            artifact_index_r <= 17'd0;
            rope_buffer_valid_r <= 1'b0;
            rope_buffer_r <= 256'd0;
            rope_subindex_r <= 2'd0;
            rope_record_addr_r <= 10'd0;
            meta_read_addr_r <= 17'd0;
            meta_read_pending_r <= 1'b0;
            output_read_addr_r <= 13'd0;
            active_request_id_r <= 32'd0;
            active_command_id_r <= 32'd0;
            active_cohort_id_r <= 16'd0;
            active_buffer_id_r <= 16'd0;
            active_layer_id_r <= 6'd0;
            active_run_format_id_r <= 32'd0;
            active_query_start_r <= 7'd0;
            active_valid_key_count_r <= 8'd0;
            active_query_count_r <= 8'd0;
            active_input_base_r <= 32'd0;
            active_output_base_r <= 32'd0;
            active_weight_c0_base_r <= 32'd0;
            active_weight_c1_base_r <= 32'd0;
            active_weight_meta_base_r <= 32'd0;
            active_rope_base_r <= 32'd0;
            active_reload_metadata_r <= 1'b0;
            active_reload_rope_r <= 1'b0;
            active_preserve_historical_kv_r <= 1'b0;
        end else begin
            board_done_r <= 1'b0;
            board_error_r <= 1'b0;
            command_abort_clear_r <= 1'b0;
            if (system_clear) begin
                if (state_r != ST_IDLE) begin
                    board_error_r <= 1'b1;
                    board_error_code_r <= 32'h0001_0000;
                    board_completion_status_r <=
                        COMPLETION_MAINTENANCE_ABORT;
                end else begin
                    board_error_code_r <= 32'd0;
                    board_completion_status_r <= COMPLETION_SUCCESS;
                end
                state_r <= ST_IDLE;
                metadata_loaded_r <= 1'b0;
                rope_loaded_r <= 1'b0;
                artifact_index_r <= 17'd0;
                rope_buffer_valid_r <= 1'b0;
                compute_complete_r <= 1'b0;
                rope_dma_complete_r <= 1'b0;
                meta_read_addr_r <= 17'd0;
                meta_read_pending_r <= 1'b0;
                output_read_addr_r <= 13'd0;
                command_cycle_count_r <= 32'd0;
            end else begin
                if (state_r == ST_IDLE)
                    command_cycle_count_r <= 32'd0;
                else
                    command_cycle_count_r <= command_cycle_count_r + 32'd1;
                case (state_r)
                    ST_IDLE: if (control_start) begin
                        artifact_index_r <= 17'd0;
                        rope_record_addr_r <= 10'd0;
                        rope_subindex_r <= 2'd0;
                        rope_buffer_valid_r <= 1'b0;
                        compute_complete_r <= 1'b0;
                        rope_dma_complete_r <= 1'b0;
                        board_error_code_r <= 32'd0;
                        board_completion_status_r <= COMPLETION_SUCCESS;
                        command_cycle_count_r <= 32'd0;
                        active_request_id_r <= control_request_id;
                        active_command_id_r <= control_command_id;
                        active_cohort_id_r <= control_cohort_id;
                        active_buffer_id_r <= control_buffer_id;
                        active_layer_id_r <= control_layer_id[5:0];
                        active_run_format_id_r <= control_run_format_id;
                        active_query_start_r <= control_query_start;
                        active_valid_key_count_r <= control_valid_key_count;
                        active_query_count_r <= control_query_count;
                        active_input_base_r <= control_input_base;
                        active_output_base_r <= control_output_base;
                        active_weight_c0_base_r <= control_weight_c0_base;
                        active_weight_c1_base_r <= control_weight_c1_base;
                        active_weight_meta_base_r <= control_weight_meta_base;
                        active_rope_base_r <= control_rope_base;
                        active_reload_metadata_r <= control_reload_metadata;
                        active_reload_rope_r <= control_reload_rope;
                        active_preserve_historical_kv_r <=
                            control_preserve_historical_kv;
                        if (control_reload_metadata) begin
                            metadata_loaded_r <= 1'b0;
                            state_r <= ST_META_CMD;
                        end else if (control_reload_rope) begin
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
                                board_completion_status_r <=
                                    COMPLETION_PROTOCOL_ERROR;
                                command_abort_clear_r <= 1'b1;
                                state_r <= ST_ERROR;
                            end else begin
                                metadata_loaded_r <= 1'b1;
                                if (active_reload_rope_r) begin
                                    rope_loaded_r <= 1'b0;
                                    state_r <= ST_ROPE_CMD;
                                end else state_r <= ST_INPUT_CMD;
                            end
                        end
                    end
                    ST_ROPE_CMD: if (dma_cmd_valid && dma_cmd_ready) begin
                        artifact_index_r <= 17'd0;
                        rope_record_addr_r <= 10'd0;
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
                            if (artifact_index_r != 17'd256 ||
                                rope_record_addr_r != 10'd0) begin
                                board_error_code_r <= 32'h0000_0004;
                                board_completion_status_r <=
                                    COMPLETION_PROTOCOL_ERROR;
                                command_abort_clear_r <= 1'b1;
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
                                (dma_rd_valid && dma_rd_ready) != 17'd6144) begin
                                board_error_code_r <= 32'h0000_0008;
                                board_completion_status_r <=
                                    COMPLETION_PROTOCOL_ERROR;
                                command_abort_clear_r <= 1'b1;
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
                            if (output_read_addr_r != 13'd6144) begin
                                board_error_code_r <= 32'h0000_0010;
                                board_completion_status_r <=
                                    COMPLETION_PROTOCOL_ERROR;
                                command_abort_clear_r <= 1'b1;
                                state_r <= ST_ERROR;
                            end else begin
                                board_done_r <= 1'b1;
                                state_r <= ST_IDLE;
                            end
                        end
                    end
                    ST_ERROR: begin
                        board_error_r <= 1'b1;
                        metadata_loaded_r <= 1'b0;
                        rope_loaded_r <= 1'b0;
                        command_cycle_count_r <= 32'd0;
                        state_r <= ST_IDLE;
                    end
                    default: begin
                        board_error_code_r <= 32'h8000_0000;
                        board_completion_status_r <=
                            COMPLETION_INTERNAL_ERROR;
                        command_abort_clear_r <= 1'b1;
                        state_r <= ST_ERROR;
                    end
                endcase
                if (meta_rd_fire)
                    meta_read_pending_r <= 1'b1;
                if (meta_rsp_fire) begin
                    meta_read_pending_r <= 1'b0;
                    meta_read_addr_r <= meta_read_addr_r + 1'b1;
                end
                if ((state_r != ST_IDLE) && (state_r != ST_ERROR) &&
                    (command_cycle_count_r >= COMMAND_TIMEOUT_CYCLES-1)) begin
                    board_error_code_r <= 32'h0002_0000;
                    board_completion_status_r <= COMPLETION_TIMEOUT;
                    command_abort_clear_r <= 1'b1;
                    state_r <= ST_ERROR;
                end
                if ((state_r != ST_IDLE) && (state_r != ST_ERROR) &&
                    (dma_error || meta_store_error || input_buffer_error ||
                     output_buffer_error || weight_frontend_error ||
                     compute_error)) begin
                    command_abort_clear_r <= 1'b1;
                    if (dma_error) begin
                        board_error_code_r <= 32'h0000_0100;
                        board_completion_status_r <= COMPLETION_DDR_ERROR;
                    end else if (meta_store_error) begin
                        board_error_code_r <= 32'h0000_0200;
                        board_completion_status_r <= COMPLETION_FORMAT_ERROR;
                    end else if (input_buffer_error) begin
                        board_error_code_r <= 32'h0000_0400;
                        board_completion_status_r <=
                            COMPLETION_PROTOCOL_ERROR;
                    end else if (output_buffer_error) begin
                        board_error_code_r <= 32'h0000_0800;
                        board_completion_status_r <=
                            COMPLETION_PROTOCOL_ERROR;
                    end else if (weight_frontend_error) begin
                        board_error_code_r <= 32'h0000_1000;
                        board_completion_status_r <= COMPLETION_DDR_ERROR;
                    end else begin
                        board_error_code_r <= 32'h0000_2000;
                        board_completion_status_r <= COMPLETION_FORMAT_ERROR;
                    end
                    state_r <= ST_ERROR;
                end
            end
        end
    end
endmodule
