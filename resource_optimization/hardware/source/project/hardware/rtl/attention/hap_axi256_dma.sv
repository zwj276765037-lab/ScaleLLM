`timescale 1ns / 1ps

// Sequential command AXI4 DMA.  Commands are either read-to-stream or
// stream-to-write.  Bursts are capped at 16 beats and split at every 4-KiB
// boundary, so board ABI bases only require native 32-byte alignment.
module hap_axi256_dma #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer MAX_BURST_BEATS = 16
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     cmd_valid,
    output wire                     cmd_ready,
    input  wire                     cmd_write,
    input  wire [AXI_ADDR_W-1:0]    cmd_base_addr,
    input  wire [31:0]              cmd_beat_count,
    output wire                     busy,
    output reg                      done,
    output reg                      error,

    output wire                     rd_valid,
    input  wire                     rd_ready,
    output wire [255:0]             rd_data,
    output wire                     rd_last,
    input  wire                     wr_valid,
    output wire                     wr_ready,
    input  wire [255:0]             wr_data,

    output wire                     m_axi_arvalid,
    input  wire                     m_axi_arready,
    output wire [AXI_ADDR_W-1:0]    m_axi_araddr,
    output wire [7:0]               m_axi_arlen,
    output wire [2:0]               m_axi_arsize,
    output wire [1:0]               m_axi_arburst,
    input  wire                     m_axi_rvalid,
    output wire                     m_axi_rready,
    input  wire [255:0]             m_axi_rdata,
    input  wire [1:0]               m_axi_rresp,
    input  wire                     m_axi_rlast,
    output wire                     m_axi_awvalid,
    input  wire                     m_axi_awready,
    output wire [AXI_ADDR_W-1:0]    m_axi_awaddr,
    output wire [7:0]               m_axi_awlen,
    output wire [2:0]               m_axi_awsize,
    output wire [1:0]               m_axi_awburst,
    output wire                     m_axi_wvalid,
    input  wire                     m_axi_wready,
    output wire [255:0]             m_axi_wdata,
    output wire [31:0]              m_axi_wstrb,
    output wire                     m_axi_wlast,
    input  wire                     m_axi_bvalid,
    output wire                     m_axi_bready,
    input  wire [1:0]               m_axi_bresp,

    output reg [31:0]               command_count,
    output reg [31:0]               read_beat_count,
    output reg [31:0]               write_beat_count,
    output reg [31:0]               burst_count,
    output reg [31:0]               protocol_error_count
);
    localparam [2:0] ST_IDLE=0, ST_READ_AR=1, ST_READ_R=2,
        ST_WRITE_AW=3, ST_WRITE_W=4, ST_WRITE_B=5;
    reg [2:0] state_r;
    reg [AXI_ADDR_W-1:0] address_r;
    reg [31:0] remaining_r;
    reg [7:0] active_burst_beats_r;
    reg [7:0] burst_beat_r;
    wire [7:0] beats_to_4k = (13'd4096 - {1'b0,address_r[11:0]}) >> 5;
    wire [31:0] burst_limit = (beats_to_4k < MAX_BURST_BEATS) ?
        beats_to_4k : MAX_BURST_BEATS;
    wire [7:0] next_burst_beats = (remaining_r < burst_limit) ?
        remaining_r[7:0] : burst_limit[7:0];
    wire r_fire = m_axi_rvalid && m_axi_rready;
    wire w_fire = m_axi_wvalid && m_axi_wready;
    wire expected_r_last = burst_beat_r + 1'b1 == active_burst_beats_r;

    assign cmd_ready = rst_n && !clear && (state_r == ST_IDLE);
    assign busy = state_r != ST_IDLE;
    assign rd_valid = (state_r == ST_READ_R) && m_axi_rvalid;
    assign rd_data = m_axi_rdata;
    assign rd_last = remaining_r == 1;
    assign wr_ready = (state_r == ST_WRITE_W) && m_axi_wready;
    assign m_axi_arvalid = state_r == ST_READ_AR;
    assign m_axi_araddr = address_r;
    assign m_axi_arlen = next_burst_beats - 1'b1;
    assign m_axi_arsize = 3'd5;
    assign m_axi_arburst = 2'b01;
    assign m_axi_rready = (state_r == ST_READ_R) && rd_ready;
    assign m_axi_awvalid = state_r == ST_WRITE_AW;
    assign m_axi_awaddr = address_r;
    assign m_axi_awlen = next_burst_beats - 1'b1;
    assign m_axi_awsize = 3'd5;
    assign m_axi_awburst = 2'b01;
    assign m_axi_wvalid = (state_r == ST_WRITE_W) && wr_valid;
    assign m_axi_wdata = wr_data;
    assign m_axi_wstrb = 32'hffff_ffff;
    assign m_axi_wlast = burst_beat_r + 1'b1 == active_burst_beats_r;
    assign m_axi_bready = state_r == ST_WRITE_B;

    initial begin
        if (MAX_BURST_BEATS != 16)
            $error("hap_axi256_dma production burst shape is 16 beats");
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_IDLE;
            address_r <= '0;
            remaining_r <= 0;
            active_burst_beats_r <= 0;
            burst_beat_r <= 0;
            done <= 0;
            error <= 0;
            command_count <= 0;
            read_beat_count <= 0;
            write_beat_count <= 0;
            burst_count <= 0;
            protocol_error_count <= 0;
        end else if (clear) begin
            state_r <= ST_IDLE;
            done <= 0;
            error <= 0;
            command_count <= 0;
            read_beat_count <= 0;
            write_beat_count <= 0;
            burst_count <= 0;
            protocol_error_count <= 0;
        end else begin
            done <= 0;
            if (cmd_valid && cmd_ready) begin
                command_count <= command_count + 1;
                address_r <= cmd_base_addr;
                remaining_r <= cmd_beat_count;
                burst_beat_r <= 0;
                if ((cmd_base_addr[4:0] != 0) || (cmd_beat_count == 0)) begin
                    error <= 1;
                    protocol_error_count <= protocol_error_count + 1;
                    done <= 1;
                end else begin
                    state_r <= cmd_write ? ST_WRITE_AW : ST_READ_AR;
                end
            end
            if (m_axi_arvalid && m_axi_arready) begin
                active_burst_beats_r <= next_burst_beats;
                burst_beat_r <= 0;
                burst_count <= burst_count + 1;
                state_r <= ST_READ_R;
            end
            if (r_fire) begin
                read_beat_count <= read_beat_count + 1;
                remaining_r <= remaining_r - 1;
                if ((m_axi_rresp != 0) || (m_axi_rlast != expected_r_last)) begin
                    error <= 1;
                    protocol_error_count <= protocol_error_count + 1;
                end
                if (expected_r_last) begin
                    address_r <= address_r + active_burst_beats_r*32;
                    if (remaining_r == 1) begin
                        state_r <= ST_IDLE;
                        done <= 1;
                    end else begin
                        state_r <= ST_READ_AR;
                    end
                    burst_beat_r <= 0;
                end else begin
                    burst_beat_r <= burst_beat_r + 1;
                end
            end
            if (m_axi_awvalid && m_axi_awready) begin
                active_burst_beats_r <= next_burst_beats;
                burst_beat_r <= 0;
                burst_count <= burst_count + 1;
                state_r <= ST_WRITE_W;
            end
            if (w_fire) begin
                write_beat_count <= write_beat_count + 1;
                remaining_r <= remaining_r - 1;
                if (m_axi_wlast) begin
                    state_r <= ST_WRITE_B;
                    burst_beat_r <= 0;
                end else begin
                    burst_beat_r <= burst_beat_r + 1;
                end
            end
            if (m_axi_bvalid && m_axi_bready) begin
                address_r <= address_r + active_burst_beats_r*32;
                if (m_axi_bresp != 0) begin
                    error <= 1;
                    protocol_error_count <= protocol_error_count + 1;
                end
                if (remaining_r == 0) begin
                    state_r <= ST_IDLE;
                    done <= 1;
                end else begin
                    state_r <= ST_WRITE_AW;
                end
            end
        end
    end
endmodule
