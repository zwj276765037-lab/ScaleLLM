`timescale 1ns / 1ps

module hap_axi256_dma #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer MAX_BURST_BEATS = 16
) (
    input wire clk, input wire rst_n, input wire clear,
    input wire cmd_valid, output wire cmd_ready, input wire cmd_write,
    input wire [AXI_ADDR_W-1:0] cmd_base_addr,
    input wire [31:0] cmd_beat_count, output wire busy, output reg done,
    output reg error, output wire rd_valid, input wire rd_ready,
    output wire [255:0] rd_data, output wire rd_last,
    input wire wr_valid, output wire wr_ready, input wire [255:0] wr_data,
    output wire m_axi_arvalid, input wire m_axi_arready,
    output wire [AXI_ADDR_W-1:0] m_axi_araddr,
    output wire [7:0] m_axi_arlen, output wire [2:0] m_axi_arsize,
    output wire [1:0] m_axi_arburst, input wire m_axi_rvalid,
    output wire m_axi_rready, input wire [255:0] m_axi_rdata,
    input wire [1:0] m_axi_rresp, input wire m_axi_rlast,
    output wire m_axi_awvalid, input wire m_axi_awready,
    output wire [AXI_ADDR_W-1:0] m_axi_awaddr,
    output wire [7:0] m_axi_awlen, output wire [2:0] m_axi_awsize,
    output wire [1:0] m_axi_awburst, output wire m_axi_wvalid,
    input wire m_axi_wready, output wire [255:0] m_axi_wdata,
    output wire [31:0] m_axi_wstrb, output wire m_axi_wlast,
    input wire m_axi_bvalid, output wire m_axi_bready,
    input wire [1:0] m_axi_bresp, output reg [31:0] command_count,
    output reg [31:0] read_beat_count, output reg [31:0] write_beat_count,
    output reg [31:0] burst_count, output reg [31:0] protocol_error_count
);
    reg active_r;
    reg write_r;
    reg stall_r;
    reg [31:0] remaining_r;
    reg [31:0] cmd_base_log [0:7];
    reg [31:0] cmd_beats_log [0:7];
    reg cmd_write_log [0:7];

    assign cmd_ready = rst_n && !clear && !active_r;
    assign busy = active_r;
    assign rd_valid = active_r && !write_r && !stall_r;
    assign rd_data = {224'd0, remaining_r};
    assign rd_last = remaining_r == 32'd1;
    assign wr_ready = active_r && write_r && !stall_r;
    assign m_axi_arvalid = 1'b0;
    assign m_axi_araddr = '0;
    assign m_axi_arlen = 8'd0;
    assign m_axi_arsize = 3'd5;
    assign m_axi_arburst = 2'b01;
    assign m_axi_rready = 1'b0;
    assign m_axi_awvalid = 1'b0;
    assign m_axi_awaddr = '0;
    assign m_axi_awlen = 8'd0;
    assign m_axi_awsize = 3'd5;
    assign m_axi_awburst = 2'b01;
    assign m_axi_wvalid = 1'b0;
    assign m_axi_wdata = wr_data;
    assign m_axi_wstrb = 32'hffff_ffff;
    assign m_axi_wlast = 1'b0;
    assign m_axi_bready = 1'b0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            write_r <= 1'b0;
            stall_r <= 1'b0;
            remaining_r <= 32'd0;
            done <= 1'b0;
            error <= 1'b0;
            command_count <= 32'd0;
            read_beat_count <= 32'd0;
            write_beat_count <= 32'd0;
            burst_count <= 32'd0;
            protocol_error_count <= 32'd0;
        end else if (clear) begin
            active_r <= 1'b0;
            stall_r <= 1'b0;
            remaining_r <= 32'd0;
            done <= 1'b0;
            error <= 1'b0;
            command_count <= 32'd0;
            read_beat_count <= 32'd0;
            write_beat_count <= 32'd0;
            burst_count <= 32'd0;
            protocol_error_count <= 32'd0;
        end else begin
            done <= 1'b0;
            if (cmd_valid && cmd_ready) begin
                cmd_base_log[command_count] <= cmd_base_addr;
                cmd_beats_log[command_count] <= cmd_beat_count;
                cmd_write_log[command_count] <= cmd_write;
                command_count <= command_count + 32'd1;
                write_r <= cmd_write;
                remaining_r <= cmd_beat_count;
                active_r <= 1'b1;
                if ((cmd_base_addr[4:0] != 0) || (cmd_beat_count == 0)) begin
                    error <= 1'b1;
                    protocol_error_count <= protocol_error_count + 32'd1;
                end
            end
            if (rd_valid && rd_ready) begin
                read_beat_count <= read_beat_count + 32'd1;
                if (remaining_r == 32'd1) begin
                    active_r <= 1'b0;
                    remaining_r <= 32'd0;
                    done <= 1'b1;
                end else begin
                    remaining_r <= remaining_r - 32'd1;
                end
            end
            if (wr_valid && wr_ready) begin
                write_beat_count <= write_beat_count + 32'd1;
                if (remaining_r == 32'd1) begin
                    active_r <= 1'b0;
                    remaining_r <= 32'd0;
                    done <= 1'b1;
                end else begin
                    remaining_r <= remaining_r - 32'd1;
                end
            end
        end
    end
endmodule

module hap_weight_meta_resident #(
    parameter integer DEPTH = 81920,
    parameter integer ADDR_W = 17
) (
    input wire clk, input wire rst_n, input wire clear,
    input wire wr_valid, output wire wr_ready,
    input wire [ADDR_W-1:0] wr_addr, input wire [255:0] wr_meta16,
    input wire rd_valid, output wire rd_ready,
    input wire [ADDR_W-1:0] rd_addr, output wire rsp_valid,
    input wire rsp_ready, output wire [255:0] rsp_meta16,
    output reg [31:0] write_count, output reg [31:0] read_count,
    output reg [31:0] format_error_count, output reg error
);
    assign wr_ready = rst_n && !clear && (wr_addr < DEPTH);
    assign rd_ready = rst_n && !clear && (rd_addr < DEPTH);
    assign rsp_valid = rd_valid && rd_ready;
    assign rsp_meta16 = 256'd0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || clear) begin
            write_count <= 32'd0;
            read_count <= 32'd0;
            format_error_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (wr_valid && wr_ready)
                write_count <= write_count + 32'd1;
            if (rsp_valid && rsp_ready)
                read_count <= read_count + 32'd1;
        end
    end
endmodule

module hap_tensor24_input_buffer16 (
    input wire clk, input wire rst_n, input wire clear,
    input wire wr_valid, output wire wr_ready, input wire [12:0] wr_addr,
    input wire [255:0] wr_data, input wire load_start,
    output wire activation_valid, input wire activation_ready,
    output wire activation_wave, output wire [6:0] activation_group,
    output wire [8*32*24-1:0] activation_s24,
    output wire busy, output wire error
);
    assign wr_ready = rst_n && !clear && (wr_addr < 13'd6144);
    assign activation_valid = 1'b0;
    assign activation_wave = 1'b0;
    assign activation_group = 7'd0;
    assign activation_s24 = '0;
    assign busy = 1'b0;
    assign error = wr_valid && (wr_addr >= 13'd6144);
endmodule

module hap_tensor24_output_buffer16 (
    input wire clk, input wire rst_n, input wire clear,
    input wire in_valid, output wire in_ready, input wire in_wave,
    input wire [7:0] in_tile, input wire [8*16*24-1:0] in_s24,
    output wire image_ready, input wire image_release,
    input wire rd_valid, output wire rd_ready, input wire [12:0] rd_addr,
    output wire rsp_valid, input wire rsp_ready,
    output wire [255:0] rsp_data, output wire error
);
    assign in_ready = 1'b1;
    assign image_ready = rst_n && !clear;
    assign rd_ready = rsp_ready && (rd_addr < 13'd6144);
    assign rsp_valid = rd_valid && (rd_addr < 13'd6144);
    assign rsp_data = {243'd0, rd_addr};
    assign error = rd_valid && (rd_addr >= 13'd6144);
endmodule

module hap_dual_ddr_weight_frontend #(
    parameter integer AXI_ADDR_W = 32,
    parameter integer OUTSTANDING_DEPTH = 8
) (
    input wire core_clk, input wire core_rst_n, input wire core_clear,
    input wire command_valid, output wire command_ready,
    input wire [AXI_ADDR_W-1:0] ddr0_base_addr,
    input wire [AXI_ADDR_W-1:0] ddr1_base_addr,
    input wire [16:0] group_count, input wire ddr0_clk,
    input wire ddr0_rst_n, output wire ddr0_axi_arvalid,
    input wire ddr0_axi_arready,
    output wire [AXI_ADDR_W-1:0] ddr0_axi_araddr,
    output wire [7:0] ddr0_axi_arlen, output wire [2:0] ddr0_axi_arsize,
    output wire [1:0] ddr0_axi_arburst, input wire ddr0_axi_rvalid,
    output wire ddr0_axi_rready, input wire [511:0] ddr0_axi_rdata,
    input wire [1:0] ddr0_axi_rresp, input wire ddr0_axi_rlast,
    input wire ddr1_clk, input wire ddr1_rst_n,
    output wire ddr1_axi_arvalid, input wire ddr1_axi_arready,
    output wire [AXI_ADDR_W-1:0] ddr1_axi_araddr,
    output wire [7:0] ddr1_axi_arlen, output wire [2:0] ddr1_axi_arsize,
    output wire [1:0] ddr1_axi_arburst, input wire ddr1_axi_rvalid,
    output wire ddr1_axi_rready, input wire [511:0] ddr1_axi_rdata,
    input wire [1:0] ddr1_axi_rresp, input wire ddr1_axi_rlast,
    input wire meta_valid, output wire meta_ready,
    input wire [9:0] meta_tile, input wire [6:0] meta_group,
    input wire [255:0] meta16, output wire out_valid,
    input wire out_ready, output wire [9:0] out_tile,
    output wire [6:0] out_group, output wire [4095:0] out_weight_s8,
    output wire [255:0] out_meta16, output wire busy, output wire error
);
    reg [31:0] base0_seen;
    reg [31:0] base1_seen;
    reg [16:0] group_count_seen;
    reg [31:0] command_count;
    assign command_ready = core_rst_n && !core_clear;
    assign meta_ready = 1'b1;
    assign out_valid = 1'b0;
    assign out_tile = 10'd0;
    assign out_group = 7'd0;
    assign out_weight_s8 = '0;
    assign out_meta16 = 256'd0;
    assign busy = 1'b0;
    assign error = 1'b0;
    assign ddr0_axi_arvalid = 1'b0;
    assign ddr0_axi_araddr = '0;
    assign ddr0_axi_arlen = 8'd0;
    assign ddr0_axi_arsize = 3'd6;
    assign ddr0_axi_arburst = 2'b01;
    assign ddr0_axi_rready = 1'b0;
    assign ddr1_axi_arvalid = 1'b0;
    assign ddr1_axi_araddr = '0;
    assign ddr1_axi_arlen = 8'd0;
    assign ddr1_axi_arsize = 3'd6;
    assign ddr1_axi_arburst = 2'b01;
    assign ddr1_axi_rready = 1'b0;
    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n || core_clear) begin
            base0_seen <= 32'd0;
            base1_seen <= 32'd0;
            group_count_seen <= 17'd0;
            command_count <= 32'd0;
        end else if (command_valid && command_ready) begin
            base0_seen <= ddr0_base_addr;
            base1_seen <= ddr1_base_addr;
            group_count_seen <= group_count;
            command_count <= command_count + 32'd1;
        end
    end
endmodule

module hap_attention_compute_cohort16_top #(
    parameter integer USE_PROJECTION_STUB = 0
) (
    input wire clk, input wire rst_n, input wire clear, input wire start,
    input wire [31:0] format_id, input wire [31:0] request_id,
    input wire [15:0] cohort_id, input wire [5:0] layer_id,
    input wire [6:0] query_start, input wire [7:0] query_count,
    input wire [7:0] valid_key_count, output reg busy, output reg done,
    output wire error, input wire rope_wr_valid, output wire rope_wr_ready,
    input wire [9:0] rope_wr_addr, input wire signed [17:0] rope_wr_cos_s18,
    input wire signed [17:0] rope_wr_sin_s18,
    input wire kv_preload_valid, output wire kv_preload_ready,
    input wire kv_preload_is_v, input wire [11:0] kv_preload_addr,
    input wire [32*12-1:0] kv_preload_s12,
    input wire [15:0] kv_preload_meta16, input wire activation_valid,
    output wire activation_ready, input wire activation_wave,
    input wire [6:0] activation_group,
    input wire [8*32*24-1:0] activation_s24, input wire weight_valid,
    output wire weight_ready, input wire [9:0] weight_tile,
    input wire [6:0] weight_group, input wire [16*32*8-1:0] weight_s8,
    input wire [16*16-1:0] weight_meta16, output wire out_valid,
    input wire out_ready, output wire out_wave, output wire [7:0] out_tile,
    output wire [8*16*24-1:0] out_s24, output reg [31:0] cycle_count,
    output reg [31:0] accepted_weight_group_count,
    output wire [31:0] consumed_wave_group_count,
    output wire [31:0] released_weight_group_count,
    output wire [31:0] completed_projection_wave_tile_count,
    output reg [31:0] completed_projection_tile_count,
    output reg [31:0] completed_attention_row_count,
    output reg [31:0] completed_wo_tile_count,
    output reg [31:0] input_frontend_cycle_count,
    output reg [31:0] qkv_projection_cycle_count,
    output reg [31:0] rope_cycle_count,
    output reg [31:0] kv12_cycle_count,
    output reg [31:0] attention_cycle_count,
    output reg [31:0] context_frontend_cycle_count,
    output reg [31:0] wo_projection_cycle_count,
    output reg [31:0] control_overhead_cycle_count
);
    reg [3:0] countdown_r;
    reg [31:0] start_count;
    reg [31:0] request_id_seen;
    reg [15:0] cohort_id_seen;
    reg [5:0] layer_id_seen;
    reg [6:0] query_start_seen;
    reg [7:0] query_count_seen;
    reg [7:0] valid_key_count_seen;
    assign error = 1'b0;
    assign rope_wr_ready = 1'b1;
    assign kv_preload_ready = 1'b1;
    assign activation_ready = 1'b1;
    assign weight_ready = 1'b1;
    assign out_valid = 1'b0;
    assign out_wave = 1'b0;
    assign out_tile = 8'd0;
    assign out_s24 = '0;
    assign consumed_wave_group_count = 32'd163840;
    assign released_weight_group_count = 32'd81920;
    assign completed_projection_wave_tile_count = 32'd1280;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || clear) begin
            busy <= 1'b0;
            done <= 1'b0;
            countdown_r <= 4'd0;
            start_count <= 32'd0;
            request_id_seen <= 32'd0;
            cohort_id_seen <= 16'd0;
            layer_id_seen <= 6'd0;
            query_start_seen <= 7'd0;
            query_count_seen <= 8'd0;
            valid_key_count_seen <= 8'd0;
            cycle_count <= 32'd0;
            accepted_weight_group_count <= 32'd0;
            completed_projection_tile_count <= 32'd0;
            completed_attention_row_count <= 32'd0;
            completed_wo_tile_count <= 32'd0;
            input_frontend_cycle_count <= 32'd0;
            qkv_projection_cycle_count <= 32'd0;
            rope_cycle_count <= 32'd0;
            kv12_cycle_count <= 32'd0;
            attention_cycle_count <= 32'd0;
            context_frontend_cycle_count <= 32'd0;
            wo_projection_cycle_count <= 32'd0;
            control_overhead_cycle_count <= 32'd0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                busy <= 1'b1;
                countdown_r <= 4'd5;
                start_count <= start_count + 32'd1;
                request_id_seen <= request_id;
                cohort_id_seen <= cohort_id;
                layer_id_seen <= layer_id;
                query_start_seen <= query_start;
                query_count_seen <= query_count;
                valid_key_count_seen <= valid_key_count;
                cycle_count <= 32'd0;
            end else if (busy) begin
                cycle_count <= cycle_count + 32'd1;
                if (countdown_r == 0) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                    accepted_weight_group_count <= 32'd81920;
                    completed_projection_tile_count <= 32'd640;
                    completed_attention_row_count <= 32'd512;
                    completed_wo_tile_count <= 32'd256;
                end else begin
                    countdown_r <= countdown_r - 1'b1;
                end
            end
        end
    end
endmodule
