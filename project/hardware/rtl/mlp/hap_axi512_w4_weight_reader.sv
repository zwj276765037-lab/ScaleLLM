`timescale 1ns / 1ps

// One DDR-channel A8W4 weight reader.
//
// A physical channel carries eight output columns x group32 x W4 = 1024
// bits, exactly two 512-bit beats per group.  A 16-beat AXI burst therefore
// contains eight complete groups.  The received beat counter increments only
// at the final MIG-facing RVALID/RREADY handshake and is the raw DDR-byte
// measurement point (64 bytes/beat).
module hap_axi512_w4_weight_reader #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer OUTSTANDING_DEPTH = 8,
    parameter integer BURST_BEATS = 16
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     cmd_valid,
    output wire                     cmd_ready,
    input  wire [AXI_ADDR_W-1:0]    cmd_base_addr,
    input  wire [19:0]              cmd_group_count,
    output wire                     beat_valid,
    input  wire                     beat_ready,
    output wire [511:0]             beat_data,
    output wire                     beat_group_last,
    output wire                     m_axi_arvalid,
    input  wire                     m_axi_arready,
    output wire [AXI_ADDR_W-1:0]    m_axi_araddr,
    output wire [7:0]               m_axi_arlen,
    output wire [2:0]               m_axi_arsize,
    output wire [1:0]               m_axi_arburst,
    input  wire                     m_axi_rvalid,
    output wire                     m_axi_rready,
    input  wire [511:0]             m_axi_rdata,
    input  wire [1:0]               m_axi_rresp,
    input  wire                     m_axi_rlast,
    output wire                     busy,
    output reg                      done,
    output reg                      error,
    output reg [31:0]               command_count,
    output reg [31:0]               issued_burst_count,
    output reg [31:0]               received_burst_count,
    output reg [31:0]               received_beat_count,
    output reg [31:0]               emitted_group_count,
    output reg [31:0]               protocol_error_count,
    output reg [31:0]               max_outstanding_count,
    output reg [31:0]               reader_elapsed_cycle_count,
    output reg [31:0]               ar_stall_cycle_count,
    output reg [31:0]               r_backpressure_cycle_count,
    output reg [31:0]               response_idle_cycle_count
);

    localparam integer OUTSTANDING_W = $clog2(OUTSTANDING_DEPTH + 1);
    localparam integer BURST_BYTE_SHIFT = 10;
    localparam [1:0] AXI_BURST_INCR = 2'b01;

    reg active_r;
    reg [AXI_ADDR_W-1:0] next_araddr_r;
    reg [31:0] target_burst_count_r;
    reg [OUTSTANDING_W-1:0] outstanding_r;
    reg [3:0] response_burst_beat_r;
    reg response_group_beat_r;
    reg elapsed_active_r;

    wire command_shape_valid = cmd_group_count != 0 &&
        cmd_group_count[2:0] == 3'b000 &&
        cmd_base_addr[BURST_BYTE_SHIFT-1:0] == 0;
    wire [31:0] command_burst_count = {12'd0, cmd_group_count} >> 3;
    wire can_issue = active_r &&
        issued_burst_count < target_burst_count_r &&
        outstanding_r < OUTSTANDING_DEPTH;
    wire ar_fire = m_axi_arvalid && m_axi_arready;
    wire r_fire = m_axi_rvalid && m_axi_rready;
    wire response_expected_last = response_burst_beat_r == BURST_BEATS-1;
    wire response_burst_end = r_fire && response_expected_last;
    wire response_final = r_fire &&
        received_beat_count + 32'd1 == target_burst_count_r*BURST_BEATS;
    wire response_protocol_error = r_fire &&
        (m_axi_rresp != 2'b00 || m_axi_rlast != response_expected_last);

    assign cmd_ready = rst_n && !clear && !active_r;
    assign busy = active_r;
    assign m_axi_arvalid = can_issue;
    assign m_axi_araddr = next_araddr_r;
    assign m_axi_arlen = BURST_BEATS-1;
    assign m_axi_arsize = 3'd6;
    assign m_axi_arburst = AXI_BURST_INCR;
    assign beat_valid = active_r && outstanding_r != 0 && m_axi_rvalid;
    assign beat_data = m_axi_rdata;
    assign beat_group_last = response_group_beat_r;
    assign m_axi_rready = active_r && outstanding_r != 0 && beat_ready;

    initial begin
        if (BURST_BEATS != 16)
            $error("W4 reader requires 16-beat bursts");
        if (OUTSTANDING_DEPTH < 2 ||
            (OUTSTANDING_DEPTH & (OUTSTANDING_DEPTH-1)) != 0)
            $error("OUTSTANDING_DEPTH must be power-of-two >=2");
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            next_araddr_r <= '0;
            target_burst_count_r <= 32'd0;
            outstanding_r <= '0;
            response_burst_beat_r <= '0;
            response_group_beat_r <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            command_count <= 32'd0;
            issued_burst_count <= 32'd0;
            received_burst_count <= 32'd0;
            received_beat_count <= 32'd0;
            emitted_group_count <= 32'd0;
            protocol_error_count <= 32'd0;
            max_outstanding_count <= 32'd0;
            reader_elapsed_cycle_count <= 32'd0;
            ar_stall_cycle_count <= 32'd0;
            r_backpressure_cycle_count <= 32'd0;
            response_idle_cycle_count <= 32'd0;
            elapsed_active_r <= 1'b0;
        end else if (clear) begin
            active_r <= 1'b0;
            next_araddr_r <= '0;
            target_burst_count_r <= 32'd0;
            outstanding_r <= '0;
            response_burst_beat_r <= '0;
            response_group_beat_r <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            command_count <= 32'd0;
            issued_burst_count <= 32'd0;
            received_burst_count <= 32'd0;
            received_beat_count <= 32'd0;
            emitted_group_count <= 32'd0;
            protocol_error_count <= 32'd0;
            max_outstanding_count <= 32'd0;
            reader_elapsed_cycle_count <= 32'd0;
            ar_stall_cycle_count <= 32'd0;
            r_backpressure_cycle_count <= 32'd0;
            response_idle_cycle_count <= 32'd0;
            elapsed_active_r <= 1'b0;
        end else begin
            done <= 1'b0;
            if (cmd_valid && cmd_ready) begin
                command_count <= command_count + 32'd1;
                next_araddr_r <= cmd_base_addr;
                target_burst_count_r <= command_burst_count;
                outstanding_r <= '0;
                response_burst_beat_r <= '0;
                response_group_beat_r <= 1'b0;
                issued_burst_count <= 32'd0;
                received_burst_count <= 32'd0;
                received_beat_count <= 32'd0;
                emitted_group_count <= 32'd0;
                max_outstanding_count <= 32'd0;
                reader_elapsed_cycle_count <= 32'd0;
                ar_stall_cycle_count <= 32'd0;
                r_backpressure_cycle_count <= 32'd0;
                response_idle_cycle_count <= 32'd0;
                elapsed_active_r <= 1'b0;
                if (command_shape_valid)
                    active_r <= 1'b1;
                else begin
                    error <= 1'b1;
                    protocol_error_count <= protocol_error_count + 32'd1;
                    done <= 1'b1;
                end
            end
            if (ar_fire) begin
                issued_burst_count <= issued_burst_count + 32'd1;
                next_araddr_r <= next_araddr_r + BURST_BEATS*64;
            end
            // The signed bandwidth interval is inclusive from the first
            // accepted AR through the final accepted R beat.  It therefore
            // includes initial response latency, AXI bubbles and downstream
            // backpressure instead of counting only productive R cycles.
            if (ar_fire && issued_burst_count == 0) begin
                elapsed_active_r <= 1'b1;
                reader_elapsed_cycle_count <= 32'd1;
            end else if (elapsed_active_r) begin
                reader_elapsed_cycle_count <=
                    reader_elapsed_cycle_count + 32'd1;
            end
            if (m_axi_arvalid && !m_axi_arready)
                ar_stall_cycle_count <= ar_stall_cycle_count + 32'd1;
            if (m_axi_rvalid && !m_axi_rready)
                r_backpressure_cycle_count <=
                    r_backpressure_cycle_count + 32'd1;
            if (elapsed_active_r && outstanding_r != 0 && !m_axi_rvalid)
                response_idle_cycle_count <=
                    response_idle_cycle_count + 32'd1;
            if (r_fire) begin
                received_beat_count <= received_beat_count + 32'd1;
                if (response_group_beat_r) begin
                    response_group_beat_r <= 1'b0;
                    emitted_group_count <= emitted_group_count + 32'd1;
                end else begin
                    response_group_beat_r <= 1'b1;
                end
                if (response_expected_last) begin
                    response_burst_beat_r <= '0;
                    received_burst_count <= received_burst_count + 32'd1;
                end else begin
                    response_burst_beat_r <= response_burst_beat_r + 1'b1;
                end
                if (response_protocol_error) begin
                    error <= 1'b1;
                    protocol_error_count <= protocol_error_count + 32'd1;
                end
                if (response_final) begin
                    active_r <= 1'b0;
                    elapsed_active_r <= 1'b0;
                    done <= 1'b1;
                    if (issued_burst_count != target_burst_count_r ||
                        !response_expected_last ||
                        !response_group_beat_r) begin
                        error <= 1'b1;
                        protocol_error_count <=
                            protocol_error_count + 32'd1;
                    end
                end
            end
            case ({ar_fire, response_burst_end})
                2'b10: outstanding_r <= outstanding_r + 1'b1;
                2'b01: outstanding_r <= outstanding_r - 1'b1;
                default: outstanding_r <= outstanding_r;
            endcase
            if (ar_fire && !response_burst_end &&
                outstanding_r + 1'b1 > max_outstanding_count)
                max_outstanding_count <= outstanding_r + 1'b1;
        end
    end

endmodule
