`timescale 1ns / 1ps

// Production dual-MIG weight ingress.  A core-domain command is delivered to
// both independent MIG UI domains.  Each AXI reader emits four 512-bit beats
// per half-group; the existing CDC bridge joins both halves with resident
// meta16 and presents the native 4096+256-bit projection operand.
module hap_dual_ddr_weight_frontend #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer OUTSTANDING_DEPTH = 8
) (
    input  wire                     core_clk,
    input  wire                     core_rst_n,
    input  wire                     core_clear,
    input  wire                     command_valid,
    output wire                     command_ready,
    input  wire [AXI_ADDR_W-1:0]    ddr0_base_addr,
    input  wire [AXI_ADDR_W-1:0]    ddr1_base_addr,
    input  wire [16:0]              group_count,

    input  wire                     ddr0_clk,
    input  wire                     ddr0_rst_n,
    output wire                     ddr0_axi_arvalid,
    input  wire                     ddr0_axi_arready,
    output wire [AXI_ADDR_W-1:0]    ddr0_axi_araddr,
    output wire [7:0]               ddr0_axi_arlen,
    output wire [2:0]               ddr0_axi_arsize,
    output wire [1:0]               ddr0_axi_arburst,
    input  wire                     ddr0_axi_rvalid,
    output wire                     ddr0_axi_rready,
    input  wire [511:0]             ddr0_axi_rdata,
    input  wire [1:0]               ddr0_axi_rresp,
    input  wire                     ddr0_axi_rlast,

    input  wire                     ddr1_clk,
    input  wire                     ddr1_rst_n,
    output wire                     ddr1_axi_arvalid,
    input  wire                     ddr1_axi_arready,
    output wire [AXI_ADDR_W-1:0]    ddr1_axi_araddr,
    output wire [7:0]               ddr1_axi_arlen,
    output wire [2:0]               ddr1_axi_arsize,
    output wire [1:0]               ddr1_axi_arburst,
    input  wire                     ddr1_axi_rvalid,
    output wire                     ddr1_axi_rready,
    input  wire [511:0]             ddr1_axi_rdata,
    input  wire [1:0]               ddr1_axi_rresp,
    input  wire                     ddr1_axi_rlast,

    input  wire                     meta_valid,
    output wire                     meta_ready,
    input  wire [9:0]               meta_tile,
    input  wire [6:0]               meta_group,
    input  wire [255:0]             meta16,
    output wire                     out_valid,
    input  wire                     out_ready,
    output wire [9:0]               out_tile,
    output wire [6:0]               out_group,
    output wire [4095:0]            out_weight_s8,
    output wire [255:0]             out_meta16,
    output wire                     busy,
    output wire                     error
);

    localparam integer CMD_W = AXI_ADDR_W + 17;
    reg command0_send_r;
    reg command1_send_r;
    reg core_active_r;
    reg [16:0] active_group_count_r;
    reg [16:0] delivered_group_count_r;
    reg [CMD_W-1:0] command0_payload_r;
    reg [CMD_W-1:0] command1_payload_r;
    wire command0_received;
    wire command1_received;
    wire [CMD_W-1:0] command0_dest_payload;
    wire [CMD_W-1:0] command1_dest_payload;
    wire command0_dest_req;
    wire command1_dest_req;
    reg command0_dest_ack_r;
    reg command1_dest_ack_r;

    wire reader0_cmd_ready;
    wire reader1_cmd_ready;
    wire reader0_cmd_valid = command0_dest_req && !command0_dest_ack_r;
    wire reader1_cmd_valid = command1_dest_req && !command1_dest_ack_r;
    wire reader0_beat_valid;
    wire reader0_beat_ready;
    wire [511:0] reader0_beat_data;
    wire reader0_group_last;
    wire reader1_beat_valid;
    wire reader1_beat_ready;
    wire [511:0] reader1_beat_data;
    wire reader1_group_last;
    wire reader0_busy;
    wire reader1_busy;
    wire reader0_error;
    wire reader1_error;
    wire bridge_error;
    wire ddr0_clear_sync;
    wire ddr1_clear_sync;
    wire ddr0_half_valid;
    wire ddr0_half_ready;
    wire [2047:0] ddr0_half_data;
    wire ddr1_half_valid;
    wire ddr1_half_ready;
    wire [2047:0] ddr1_half_data;
    wire ddr0_fifo_error;
    wire ddr1_fifo_error;
    wire assembler_error;
    (* ASYNC_REG = "TRUE" *) reg reader0_busy_sync1_r;
    (* ASYNC_REG = "TRUE" *) reg reader0_busy_sync2_r;
    (* ASYNC_REG = "TRUE" *) reg reader1_busy_sync1_r;
    (* ASYNC_REG = "TRUE" *) reg reader1_busy_sync2_r;
    (* ASYNC_REG = "TRUE" *) reg reader0_error_sync1_r;
    (* ASYNC_REG = "TRUE" *) reg reader0_error_sync2_r;
    (* ASYNC_REG = "TRUE" *) reg reader1_error_sync1_r;
    (* ASYNC_REG = "TRUE" *) reg reader1_error_sync2_r;

    wire out_fire = out_valid && out_ready;
    assign command_ready = core_rst_n && !core_clear && !core_active_r &&
        !command0_send_r && !command1_send_r &&
        !command0_received && !command1_received &&
        !reader0_busy_sync2_r && !reader1_busy_sync2_r;
    // Reader busy can fall before the last async-FIFO entries are consumed.
    // Keep the transaction active until the core actually accepts every
    // assembled group, otherwise metadata can be withdrawn one group early.
    assign busy = core_active_r || command0_send_r || command1_send_r;
    assign bridge_error = ddr0_fifo_error || ddr1_fifo_error ||
        assembler_error;
    assign error = reader0_error_sync2_r || reader1_error_sync2_r ||
        bridge_error;

    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(1)
    ) u_clear0_cdc (
        .src_clk(core_clk), .src_in(core_clear),
        .dest_clk(ddr0_clk), .dest_out(ddr0_clear_sync)
    );

    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(1)
    ) u_clear1_cdc (
        .src_clk(core_clk), .src_in(core_clear),
        .dest_clk(ddr1_clk), .dest_out(ddr1_clear_sync)
    );


    xpm_cdc_handshake #(
        .DEST_EXT_HSK(1), .DEST_SYNC_FF(2), .INIT_SYNC_FF(1),
        .SIM_ASSERT_CHK(0), .SRC_SYNC_FF(2), .WIDTH(CMD_W)
    ) u_command0_cdc (
        .src_clk(core_clk), .src_in(command0_payload_r),
        .src_send(command0_send_r), .src_rcv(command0_received),
        .dest_clk(ddr0_clk), .dest_out(command0_dest_payload),
        .dest_req(command0_dest_req), .dest_ack(command0_dest_ack_r)
    );

    xpm_cdc_handshake #(
        .DEST_EXT_HSK(1), .DEST_SYNC_FF(2), .INIT_SYNC_FF(1),
        .SIM_ASSERT_CHK(0), .SRC_SYNC_FF(2), .WIDTH(CMD_W)
    ) u_command1_cdc (
        .src_clk(core_clk), .src_in(command1_payload_r),
        .src_send(command1_send_r), .src_rcv(command1_received),
        .dest_clk(ddr1_clk), .dest_out(command1_dest_payload),
        .dest_req(command1_dest_req), .dest_ack(command1_dest_ack_r)
    );

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            command0_send_r <= 1'b0;
            command1_send_r <= 1'b0;
            core_active_r <= 1'b0;
            active_group_count_r <= 17'd0;
            delivered_group_count_r <= 17'd0;
            command0_payload_r <= '0;
            command1_payload_r <= '0;
            reader0_busy_sync1_r <= 1'b0;
            reader0_busy_sync2_r <= 1'b0;
            reader1_busy_sync1_r <= 1'b0;
            reader1_busy_sync2_r <= 1'b0;
            reader0_error_sync1_r <= 1'b0;
            reader0_error_sync2_r <= 1'b0;
            reader1_error_sync1_r <= 1'b0;
            reader1_error_sync2_r <= 1'b0;
        end else begin
            reader0_busy_sync1_r <= reader0_busy;
            reader0_busy_sync2_r <= reader0_busy_sync1_r;
            reader1_busy_sync1_r <= reader1_busy;
            reader1_busy_sync2_r <= reader1_busy_sync1_r;
            reader0_error_sync1_r <= reader0_error;
            reader0_error_sync2_r <= reader0_error_sync1_r;
            reader1_error_sync1_r <= reader1_error;
            reader1_error_sync2_r <= reader1_error_sync1_r;
            if (core_clear) begin
                command0_send_r <= 1'b0;
                command1_send_r <= 1'b0;
                core_active_r <= 1'b0;
                active_group_count_r <= 17'd0;
                delivered_group_count_r <= 17'd0;
            end else begin
                if (command_valid && command_ready) begin
                    command0_payload_r <= {ddr0_base_addr, group_count};
                    command1_payload_r <= {ddr1_base_addr, group_count};
                    command0_send_r <= 1'b1;
                    command1_send_r <= 1'b1;
                    core_active_r <= 1'b1;
                    active_group_count_r <= group_count;
                    delivered_group_count_r <= 17'd0;
                end
                if (command0_send_r && command0_received)
                    command0_send_r <= 1'b0;
                if (command1_send_r && command1_received)
                    command1_send_r <= 1'b0;
                if (out_fire) begin
                    delivered_group_count_r <= delivered_group_count_r + 1'b1;
                    if (delivered_group_count_r + 1'b1 ==
                        active_group_count_r)
                        core_active_r <= 1'b0;
                end
            end
        end
    end

    always @(posedge ddr0_clk or negedge ddr0_rst_n) begin
        if (!ddr0_rst_n)
            command0_dest_ack_r <= 1'b0;
        else if (!command0_dest_req)
            command0_dest_ack_r <= 1'b0;
        else if (reader0_cmd_valid && reader0_cmd_ready)
            command0_dest_ack_r <= 1'b1;
    end

    always @(posedge ddr1_clk or negedge ddr1_rst_n) begin
        if (!ddr1_rst_n)
            command1_dest_ack_r <= 1'b0;
        else if (!command1_dest_req)
            command1_dest_ack_r <= 1'b0;
        else if (reader1_cmd_valid && reader1_cmd_ready)
            command1_dest_ack_r <= 1'b1;
    end

    hap_axi512_weight_reader #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_reader0 (
        .clk(ddr0_clk), .rst_n(ddr0_rst_n), .clear(ddr0_clear_sync),
        .cmd_valid(reader0_cmd_valid), .cmd_ready(reader0_cmd_ready),
        .cmd_base_addr(command0_dest_payload[CMD_W-1:17]),
        .cmd_group_count(command0_dest_payload[16:0]),
        .beat_valid(reader0_beat_valid), .beat_ready(reader0_beat_ready),
        .beat_data(reader0_beat_data),
        .beat_group_last(reader0_group_last),
        .m_axi_arvalid(ddr0_axi_arvalid),
        .m_axi_arready(ddr0_axi_arready), .m_axi_araddr(ddr0_axi_araddr),
        .m_axi_arlen(ddr0_axi_arlen), .m_axi_arsize(ddr0_axi_arsize),
        .m_axi_arburst(ddr0_axi_arburst), .m_axi_rvalid(ddr0_axi_rvalid),
        .m_axi_rready(ddr0_axi_rready), .m_axi_rdata(ddr0_axi_rdata),
        .m_axi_rresp(ddr0_axi_rresp), .m_axi_rlast(ddr0_axi_rlast),
        .busy(reader0_busy), .done(), .error(reader0_error),
        .command_count(), .issued_burst_count(),
        .received_burst_count(), .received_beat_count(),
        .emitted_group_count(), .protocol_error_count(),
        .max_outstanding_count()
    );

    hap_axi512_weight_reader #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_reader1 (
        .clk(ddr1_clk), .rst_n(ddr1_rst_n), .clear(ddr1_clear_sync),
        .cmd_valid(reader1_cmd_valid), .cmd_ready(reader1_cmd_ready),
        .cmd_base_addr(command1_dest_payload[CMD_W-1:17]),
        .cmd_group_count(command1_dest_payload[16:0]),
        .beat_valid(reader1_beat_valid), .beat_ready(reader1_beat_ready),
        .beat_data(reader1_beat_data),
        .beat_group_last(reader1_group_last),
        .m_axi_arvalid(ddr1_axi_arvalid),
        .m_axi_arready(ddr1_axi_arready), .m_axi_araddr(ddr1_axi_araddr),
        .m_axi_arlen(ddr1_axi_arlen), .m_axi_arsize(ddr1_axi_arsize),
        .m_axi_arburst(ddr1_axi_arburst), .m_axi_rvalid(ddr1_axi_rvalid),
        .m_axi_rready(ddr1_axi_rready), .m_axi_rdata(ddr1_axi_rdata),
        .m_axi_rresp(ddr1_axi_rresp), .m_axi_rlast(ddr1_axi_rlast),
        .busy(reader1_busy), .done(), .error(reader1_error),
        .command_count(), .issued_burst_count(),
        .received_burst_count(), .received_beat_count(),
        .emitted_group_count(), .protocol_error_count(),
        .max_outstanding_count()
    );

    hap_ddr512_halfgroup_async u_half0 (
        .ddr_clk(ddr0_clk), .ddr_rst_n(ddr0_rst_n),
        .ddr_clear(ddr0_clear_sync),
        .beat_valid(reader0_beat_valid), .beat_ready(reader0_beat_ready),
        .beat_data(reader0_beat_data), .beat_last(reader0_group_last),
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .half_valid(ddr0_half_valid),
        .half_ready(ddr0_half_ready), .half_data(ddr0_half_data),
        .ddr_beat_count(), .ddr_half_count(), .core_half_count(),
        .error(ddr0_fifo_error)
    );

    hap_ddr512_halfgroup_async u_half1 (
        .ddr_clk(ddr1_clk), .ddr_rst_n(ddr1_rst_n),
        .ddr_clear(ddr1_clear_sync),
        .beat_valid(reader1_beat_valid), .beat_ready(reader1_beat_ready),
        .beat_data(reader1_beat_data), .beat_last(reader1_group_last),
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .half_valid(ddr1_half_valid),
        .half_ready(ddr1_half_ready), .half_data(ddr1_half_data),
        .ddr_beat_count(), .ddr_half_count(), .core_half_count(),
        .error(ddr1_fifo_error)
    );

    hap_dual_ddr_weight_group_assembler u_assembler (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .ddr0_valid(ddr0_half_valid), .ddr0_ready(ddr0_half_ready),
        .ddr0_half(ddr0_half_data), .ddr1_valid(ddr1_half_valid),
        .ddr1_ready(ddr1_half_ready), .ddr1_half(ddr1_half_data),
        .meta_valid(meta_valid), .meta_ready(meta_ready),
        .meta_tile(meta_tile), .meta_group(meta_group), .meta16(meta16),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile(out_tile), .out_group(out_group),
        .out_weight_s8(out_weight_s8), .out_meta16(out_meta16),
        .assembled_group_count(), .error(assembler_error)
    );

endmodule
