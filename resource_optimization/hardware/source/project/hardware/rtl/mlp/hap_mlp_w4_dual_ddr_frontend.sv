`timescale 1ns / 1ps

// Dual-MIG W4 ingress for the group-major MLP down projection.  Each MIG
// supplies two 512-bit beats for eight output columns.  Complete 1024-bit
// halves cross independently into the core clock and are atomically joined
// with resident 16-column ScaleCode metadata.
//
// Reader statistics return through one atomic CDC handshake per channel.
// `done` is not asserted until all requested groups have reached the core and
// both channel snapshots are available, so software never reads torn/live
// counters for a completed command.
module hap_mlp_w4_dual_ddr_frontend #(
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
    input  wire [19:0]              group_count,

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
    input  wire [223:0]             meta_u224,
    output wire                     out_valid,
    input  wire                     out_ready,
    output wire [2047:0]            weights_s4x16x32,
    output wire [223:0]             weight_meta_u224,
    output wire                     busy,
    output reg                      done,
    output wire                     error,

    output reg  [31:0]              ddr0_raw_beat_snapshot,
    output reg  [31:0]              ddr1_raw_beat_snapshot,
    output reg  [31:0]              ddr0_elapsed_cycle_snapshot,
    output reg  [31:0]              ddr1_elapsed_cycle_snapshot,
    output reg  [31:0]              ddr0_burst_snapshot,
    output reg  [31:0]              ddr1_burst_snapshot,
    output reg  [31:0]              ddr0_ar_stall_snapshot,
    output reg  [31:0]              ddr1_ar_stall_snapshot,
    output reg  [31:0]              ddr0_r_backpressure_snapshot,
    output reg  [31:0]              ddr1_r_backpressure_snapshot,
    output reg  [31:0]              ddr0_response_idle_snapshot,
    output reg  [31:0]              ddr1_response_idle_snapshot,
    output reg  [31:0]              ddr0_max_outstanding_snapshot,
    output reg  [31:0]              ddr1_max_outstanding_snapshot,
    output wire [63:0]              physical_read_byte_count,
    output wire [63:0]              useful_weight_byte_count,
    output wire [31:0]              useful_group_count
);

    localparam integer CMD_W = AXI_ADDR_W + 20;
    localparam integer SNAP_FIELDS = 7;
    localparam integer SNAP_W = SNAP_FIELDS*32;

    reg command0_send_r;
    reg command1_send_r;
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

    reg core_active_r;
    reg output_complete_r;
    reg [19:0] active_group_count_r;
    reg [19:0] delivered_group_count_r;
    reg snapshot0_seen_r;
    reg snapshot1_seen_r;

    wire ddr0_clear_sync;
    wire ddr1_clear_sync;
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
    wire reader0_done;
    wire reader1_done;
    wire reader0_error;
    wire reader1_error;
    wire [31:0] reader0_bursts;
    wire [31:0] reader1_bursts;
    wire [31:0] reader0_beats;
    wire [31:0] reader1_beats;
    wire [31:0] reader0_max_outstanding;
    wire [31:0] reader1_max_outstanding;
    wire [31:0] reader0_elapsed;
    wire [31:0] reader1_elapsed;
    wire [31:0] reader0_ar_stall;
    wire [31:0] reader1_ar_stall;
    wire [31:0] reader0_r_backpressure;
    wire [31:0] reader1_r_backpressure;
    wire [31:0] reader0_response_idle;
    wire [31:0] reader1_response_idle;

    wire half0_valid;
    wire half0_ready;
    wire [1023:0] half0_data;
    wire half1_valid;
    wire half1_ready;
    wire [1023:0] half1_data;
    wire half0_error;
    wire half1_error;
    wire join_error;

    reg [SNAP_W-1:0] snapshot0_src_payload_r;
    reg [SNAP_W-1:0] snapshot1_src_payload_r;
    reg snapshot0_src_send_r;
    reg snapshot1_src_send_r;
    wire snapshot0_src_received;
    wire snapshot1_src_received;
    wire [SNAP_W-1:0] snapshot0_dest_payload;
    wire [SNAP_W-1:0] snapshot1_dest_payload;
    wire snapshot0_dest_req;
    wire snapshot1_dest_req;
    reg snapshot0_dest_ack_r;
    reg snapshot1_dest_ack_r;
    wire reader0_error_core;
    wire reader1_error_core;

    wire out_fire = out_valid && out_ready;
    assign command_ready = core_rst_n && !core_clear && !core_active_r &&
        !command0_send_r && !command1_send_r &&
        !command0_received && !command1_received &&
        !snapshot0_dest_req && !snapshot1_dest_req;
    assign busy = core_active_r || command0_send_r || command1_send_r;
    assign error = reader0_error_core || reader1_error_core ||
        half0_error || half1_error || join_error;
    assign physical_read_byte_count =
        ({32'd0, ddr0_raw_beat_snapshot} +
         {32'd0, ddr1_raw_beat_snapshot}) << 6;
    // These command-visible counters are derived from the core delivery
    // count, which is reset for every command.  The join leaf also owns
    // lifetime debug counters, but exposing those here would make a second
    // serial phase incorrectly include the first phase's useful bytes.
    assign useful_group_count = {12'd0, delivered_group_count_r};
    assign useful_weight_byte_count =
        {44'd0, delivered_group_count_r} << 8;

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
    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(0)
    ) u_reader0_error_cdc (
        .src_clk(ddr0_clk), .src_in(reader0_error),
        .dest_clk(core_clk), .dest_out(reader0_error_core)
    );
    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(0)
    ) u_reader1_error_cdc (
        .src_clk(ddr1_clk), .src_in(reader1_error),
        .dest_clk(core_clk), .dest_out(reader1_error_core)
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

    xpm_cdc_handshake #(
        .DEST_EXT_HSK(1), .DEST_SYNC_FF(2), .INIT_SYNC_FF(1),
        .SIM_ASSERT_CHK(0), .SRC_SYNC_FF(2), .WIDTH(SNAP_W)
    ) u_snapshot0_cdc (
        .src_clk(ddr0_clk), .src_in(snapshot0_src_payload_r),
        .src_send(snapshot0_src_send_r),
        .src_rcv(snapshot0_src_received), .dest_clk(core_clk),
        .dest_out(snapshot0_dest_payload),
        .dest_req(snapshot0_dest_req), .dest_ack(snapshot0_dest_ack_r)
    );
    xpm_cdc_handshake #(
        .DEST_EXT_HSK(1), .DEST_SYNC_FF(2), .INIT_SYNC_FF(1),
        .SIM_ASSERT_CHK(0), .SRC_SYNC_FF(2), .WIDTH(SNAP_W)
    ) u_snapshot1_cdc (
        .src_clk(ddr1_clk), .src_in(snapshot1_src_payload_r),
        .src_send(snapshot1_src_send_r),
        .src_rcv(snapshot1_src_received), .dest_clk(core_clk),
        .dest_out(snapshot1_dest_payload),
        .dest_req(snapshot1_dest_req), .dest_ack(snapshot1_dest_ack_r)
    );

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            command0_send_r <= 1'b0;
            command1_send_r <= 1'b0;
            command0_payload_r <= '0;
            command1_payload_r <= '0;
            core_active_r <= 1'b0;
            output_complete_r <= 1'b0;
            active_group_count_r <= 20'd0;
            delivered_group_count_r <= 20'd0;
            snapshot0_seen_r <= 1'b0;
            snapshot1_seen_r <= 1'b0;
            snapshot0_dest_ack_r <= 1'b0;
            snapshot1_dest_ack_r <= 1'b0;
            done <= 1'b0;
            ddr0_raw_beat_snapshot <= 32'd0;
            ddr1_raw_beat_snapshot <= 32'd0;
            ddr0_elapsed_cycle_snapshot <= 32'd0;
            ddr1_elapsed_cycle_snapshot <= 32'd0;
            ddr0_burst_snapshot <= 32'd0;
            ddr1_burst_snapshot <= 32'd0;
            ddr0_ar_stall_snapshot <= 32'd0;
            ddr1_ar_stall_snapshot <= 32'd0;
            ddr0_r_backpressure_snapshot <= 32'd0;
            ddr1_r_backpressure_snapshot <= 32'd0;
            ddr0_response_idle_snapshot <= 32'd0;
            ddr1_response_idle_snapshot <= 32'd0;
            ddr0_max_outstanding_snapshot <= 32'd0;
            ddr1_max_outstanding_snapshot <= 32'd0;
        end else begin
            done <= 1'b0;
            snapshot0_dest_ack_r <= 1'b0;
            snapshot1_dest_ack_r <= 1'b0;
            if (core_clear) begin
                command0_send_r <= 1'b0;
                command1_send_r <= 1'b0;
                core_active_r <= 1'b0;
                output_complete_r <= 1'b0;
                active_group_count_r <= 20'd0;
                delivered_group_count_r <= 20'd0;
                snapshot0_seen_r <= 1'b0;
                snapshot1_seen_r <= 1'b0;
            end else begin
                if (command_valid && command_ready) begin
                    command0_payload_r <= {ddr0_base_addr, group_count};
                    command1_payload_r <= {ddr1_base_addr, group_count};
                    command0_send_r <= 1'b1;
                    command1_send_r <= 1'b1;
                    core_active_r <= 1'b1;
                    output_complete_r <= 1'b0;
                    active_group_count_r <= group_count;
                    delivered_group_count_r <= 20'd0;
                    snapshot0_seen_r <= 1'b0;
                    snapshot1_seen_r <= 1'b0;
                end
                if (command0_send_r && command0_received)
                    command0_send_r <= 1'b0;
                if (command1_send_r && command1_received)
                    command1_send_r <= 1'b0;
                if (out_fire) begin
                    delivered_group_count_r <= delivered_group_count_r + 1'b1;
                    if (delivered_group_count_r + 1'b1 ==
                        active_group_count_r)
                        output_complete_r <= 1'b1;
                end
                if (snapshot0_dest_req && !snapshot0_seen_r) begin
                    snapshot0_dest_ack_r <= 1'b1;
                    snapshot0_seen_r <= 1'b1;
                    ddr0_raw_beat_snapshot <= snapshot0_dest_payload[31:0];
                    ddr0_elapsed_cycle_snapshot <= snapshot0_dest_payload[63:32];
                    ddr0_burst_snapshot <= snapshot0_dest_payload[95:64];
                    ddr0_ar_stall_snapshot <= snapshot0_dest_payload[127:96];
                    ddr0_r_backpressure_snapshot <=
                        snapshot0_dest_payload[159:128];
                    ddr0_response_idle_snapshot <=
                        snapshot0_dest_payload[191:160];
                    ddr0_max_outstanding_snapshot <=
                        snapshot0_dest_payload[223:192];
                end
                if (snapshot1_dest_req && !snapshot1_seen_r) begin
                    snapshot1_dest_ack_r <= 1'b1;
                    snapshot1_seen_r <= 1'b1;
                    ddr1_raw_beat_snapshot <= snapshot1_dest_payload[31:0];
                    ddr1_elapsed_cycle_snapshot <= snapshot1_dest_payload[63:32];
                    ddr1_burst_snapshot <= snapshot1_dest_payload[95:64];
                    ddr1_ar_stall_snapshot <= snapshot1_dest_payload[127:96];
                    ddr1_r_backpressure_snapshot <=
                        snapshot1_dest_payload[159:128];
                    ddr1_response_idle_snapshot <=
                        snapshot1_dest_payload[191:160];
                    ddr1_max_outstanding_snapshot <=
                        snapshot1_dest_payload[223:192];
                end
                if (core_active_r && output_complete_r &&
                    snapshot0_seen_r && snapshot1_seen_r) begin
                    core_active_r <= 1'b0;
                    done <= 1'b1;
                end
            end
        end
    end

    always @(posedge ddr0_clk or negedge ddr0_rst_n) begin
        if (!ddr0_rst_n) begin
            command0_dest_ack_r <= 1'b0;
            snapshot0_src_payload_r <= '0;
            snapshot0_src_send_r <= 1'b0;
        end else if (ddr0_clear_sync) begin
            command0_dest_ack_r <= 1'b0;
            snapshot0_src_payload_r <= '0;
            snapshot0_src_send_r <= 1'b0;
        end else begin
            if (!command0_dest_req)
                command0_dest_ack_r <= 1'b0;
            else if (reader0_cmd_valid && reader0_cmd_ready)
                command0_dest_ack_r <= 1'b1;
            if (reader0_done) begin
                snapshot0_src_payload_r <= {
                    reader0_max_outstanding, reader0_response_idle,
                    reader0_r_backpressure, reader0_ar_stall,
                    reader0_bursts, reader0_elapsed, reader0_beats};
                snapshot0_src_send_r <= 1'b1;
            end else if (snapshot0_src_send_r && snapshot0_src_received) begin
                snapshot0_src_send_r <= 1'b0;
            end
        end
    end

    always @(posedge ddr1_clk or negedge ddr1_rst_n) begin
        if (!ddr1_rst_n) begin
            command1_dest_ack_r <= 1'b0;
            snapshot1_src_payload_r <= '0;
            snapshot1_src_send_r <= 1'b0;
        end else if (ddr1_clear_sync) begin
            command1_dest_ack_r <= 1'b0;
            snapshot1_src_payload_r <= '0;
            snapshot1_src_send_r <= 1'b0;
        end else begin
            if (!command1_dest_req)
                command1_dest_ack_r <= 1'b0;
            else if (reader1_cmd_valid && reader1_cmd_ready)
                command1_dest_ack_r <= 1'b1;
            if (reader1_done) begin
                snapshot1_src_payload_r <= {
                    reader1_max_outstanding, reader1_response_idle,
                    reader1_r_backpressure, reader1_ar_stall,
                    reader1_bursts, reader1_elapsed, reader1_beats};
                snapshot1_src_send_r <= 1'b1;
            end else if (snapshot1_src_send_r && snapshot1_src_received) begin
                snapshot1_src_send_r <= 1'b0;
            end
        end
    end

    hap_axi512_w4_weight_reader #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_reader0 (
        .clk(ddr0_clk), .rst_n(ddr0_rst_n), .clear(ddr0_clear_sync),
        .cmd_valid(reader0_cmd_valid), .cmd_ready(reader0_cmd_ready),
        .cmd_base_addr(command0_dest_payload[CMD_W-1:20]),
        .cmd_group_count(command0_dest_payload[19:0]),
        .beat_valid(reader0_beat_valid), .beat_ready(reader0_beat_ready),
        .beat_data(reader0_beat_data),
        .beat_group_last(reader0_group_last),
        .m_axi_arvalid(ddr0_axi_arvalid),
        .m_axi_arready(ddr0_axi_arready), .m_axi_araddr(ddr0_axi_araddr),
        .m_axi_arlen(ddr0_axi_arlen), .m_axi_arsize(ddr0_axi_arsize),
        .m_axi_arburst(ddr0_axi_arburst), .m_axi_rvalid(ddr0_axi_rvalid),
        .m_axi_rready(ddr0_axi_rready), .m_axi_rdata(ddr0_axi_rdata),
        .m_axi_rresp(ddr0_axi_rresp), .m_axi_rlast(ddr0_axi_rlast),
        .busy(reader0_busy), .done(reader0_done), .error(reader0_error),
        .command_count(), .issued_burst_count(),
        .received_burst_count(reader0_bursts),
        .received_beat_count(reader0_beats),
        .emitted_group_count(), .protocol_error_count(),
        .max_outstanding_count(reader0_max_outstanding),
        .reader_elapsed_cycle_count(reader0_elapsed),
        .ar_stall_cycle_count(reader0_ar_stall),
        .r_backpressure_cycle_count(reader0_r_backpressure),
        .response_idle_cycle_count(reader0_response_idle)
    );

    hap_axi512_w4_weight_reader #(
        .AXI_ADDR_W(AXI_ADDR_W),
        .OUTSTANDING_DEPTH(OUTSTANDING_DEPTH)
    ) u_reader1 (
        .clk(ddr1_clk), .rst_n(ddr1_rst_n), .clear(ddr1_clear_sync),
        .cmd_valid(reader1_cmd_valid), .cmd_ready(reader1_cmd_ready),
        .cmd_base_addr(command1_dest_payload[CMD_W-1:20]),
        .cmd_group_count(command1_dest_payload[19:0]),
        .beat_valid(reader1_beat_valid), .beat_ready(reader1_beat_ready),
        .beat_data(reader1_beat_data),
        .beat_group_last(reader1_group_last),
        .m_axi_arvalid(ddr1_axi_arvalid),
        .m_axi_arready(ddr1_axi_arready), .m_axi_araddr(ddr1_axi_araddr),
        .m_axi_arlen(ddr1_axi_arlen), .m_axi_arsize(ddr1_axi_arsize),
        .m_axi_arburst(ddr1_axi_arburst), .m_axi_rvalid(ddr1_axi_rvalid),
        .m_axi_rready(ddr1_axi_rready), .m_axi_rdata(ddr1_axi_rdata),
        .m_axi_rresp(ddr1_axi_rresp), .m_axi_rlast(ddr1_axi_rlast),
        .busy(reader1_busy), .done(reader1_done), .error(reader1_error),
        .command_count(), .issued_burst_count(),
        .received_burst_count(reader1_bursts),
        .received_beat_count(reader1_beats),
        .emitted_group_count(), .protocol_error_count(),
        .max_outstanding_count(reader1_max_outstanding),
        .reader_elapsed_cycle_count(reader1_elapsed),
        .ar_stall_cycle_count(reader1_ar_stall),
        .r_backpressure_cycle_count(reader1_r_backpressure),
        .response_idle_cycle_count(reader1_response_idle)
    );

    hap_ddr512_w4_halfgroup_async u_half0 (
        .ddr_clk(ddr0_clk), .ddr_rst_n(ddr0_rst_n),
        .ddr_clear(ddr0_clear_sync),
        .beat_valid(reader0_beat_valid), .beat_ready(reader0_beat_ready),
        .beat_data(reader0_beat_data),
        .beat_group_last(reader0_group_last),
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .half_valid(half0_valid),
        .half_ready(half0_ready), .half_data(half0_data),
        .ddr_beat_count(), .ddr_half_count(), .core_half_count(),
        .error(half0_error)
    );

    hap_ddr512_w4_halfgroup_async u_half1 (
        .ddr_clk(ddr1_clk), .ddr_rst_n(ddr1_rst_n),
        .ddr_clear(ddr1_clear_sync),
        .beat_valid(reader1_beat_valid), .beat_ready(reader1_beat_ready),
        .beat_data(reader1_beat_data),
        .beat_group_last(reader1_group_last),
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_clear), .half_valid(half1_valid),
        .half_ready(half1_ready), .half_data(half1_data),
        .ddr_beat_count(), .ddr_half_count(), .core_half_count(),
        .error(half1_error)
    );

    hap_mlp_w4_dual_channel_join u_join (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .half0_valid(half0_valid), .half0_ready(half0_ready),
        .half0_data(half0_data), .half1_valid(half1_valid),
        .half1_ready(half1_ready), .half1_data(half1_data),
        .meta_valid(meta_valid), .meta_ready(meta_ready),
        .meta_u224(meta_u224), .out_valid(out_valid),
        .out_ready(out_ready), .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224),
        .useful_group_count(), .useful_weight_byte_count(),
        .error(join_error)
    );

endmodule
