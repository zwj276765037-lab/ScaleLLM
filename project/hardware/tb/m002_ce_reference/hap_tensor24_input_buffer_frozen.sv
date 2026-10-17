`timescale 1ns / 1ps

// 8x4096 S24 input buffer.  DMA writes row-major 256-bit beats; the loader
// transposes 24 beats/group into the compute top's 8-row x group32 record.
module hap_tensor24_input_buffer_frozen (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 wr_valid,
    output wire                 wr_ready,
    input  wire [11:0]          wr_addr,
    input  wire [255:0]         wr_data,
    input  wire                 load_start,
    output wire                 activation_valid,
    input  wire                 activation_ready,
    output wire [6:0]           activation_group,
    output wire [6143:0]        activation_s24,
    output wire                 busy,
    output reg                  error
);
    (* ram_style = "block" *) reg [255:0] input_mem [0:3071];
    reg active_r;
    reg output_valid_r;
    reg [6:0] group_r;
    reg [4:0] issue_index_r;
    reg [4:0] capture_index_r;
    reg read_pending_r;
    reg [255:0] read_data_r;
    // Keep a second explicit register after the inferred BRAM output.  The
    // full VCU118 design places the input BRAM bank in SLR1 and the 6144-bit
    // activation record in SLR2; without this stage Vivado routed a cascaded
    // BRAM output directly across the SLR boundary.  The loader is not the
    // II=2 projection datapath, so the one-cycle group-fill latency does not
    // reduce the array throughput.
    reg read_stage_valid_r;
    reg [255:0] read_stage_data_r;
    reg [6143:0] activation_r;
    wire output_fire = output_valid_r && activation_ready;
    wire [2:0] issue_row = issue_index_r / 3;
    wire [1:0] issue_beat = issue_index_r % 3;
    wire [11:0] issue_addr = issue_row*12'd384 +
        group_r*12'd3 + issue_beat;

    assign wr_ready = rst_n && !clear && !active_r && (wr_addr < 3072);
    assign activation_valid = output_valid_r;
    assign activation_group = group_r;
    assign activation_s24 = activation_r;
    assign busy = active_r || output_valid_r;

    always @(posedge clk) begin
        if (wr_valid && wr_ready)
            input_mem[wr_addr] <= wr_data;
        if (active_r && !output_valid_r && (issue_index_r < 24))
            read_data_r <= input_mem[issue_addr];
        if (read_pending_r)
            read_stage_data_r <= read_data_r;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            output_valid_r <= 1'b0;
            group_r <= 7'd0;
            issue_index_r <= 5'd0;
            capture_index_r <= 5'd0;
            read_pending_r <= 1'b0;
            read_stage_valid_r <= 1'b0;
            activation_r <= '0;
            error <= 1'b0;
        end else if (clear) begin
            active_r <= 1'b0;
            output_valid_r <= 1'b0;
            group_r <= 7'd0;
            issue_index_r <= 5'd0;
            capture_index_r <= 5'd0;
            read_pending_r <= 1'b0;
            read_stage_valid_r <= 1'b0;
            error <= 1'b0;
        end else begin
            if (load_start) begin
                if (busy) begin
                    error <= 1'b1;
                end else begin
                    active_r <= 1'b1;
                    group_r <= 7'd0;
                    issue_index_r <= 5'd0;
                    capture_index_r <= 5'd0;
                    read_pending_r <= 1'b0;
                    read_stage_valid_r <= 1'b0;
                end
            end
            if (active_r && !output_valid_r) begin
                read_stage_valid_r <= read_pending_r;
                if (read_stage_valid_r) begin
                    activation_r[capture_index_r*256 +: 256] <=
                        read_stage_data_r;
                    capture_index_r <= capture_index_r + 1'b1;
                    if (capture_index_r == 23) begin
                        // Drain the final BRAM response explicitly.  Leaving
                        // this set is harmless while output_valid_r stalls the
                        // loader, but it leaves a stale pending token across
                        // the group boundary and obscures the intended
                        // two-stage read-pipeline state.
                        read_pending_r <= 1'b0;
                        read_stage_valid_r <= 1'b0;
                        output_valid_r <= 1'b1;
                    end
                end
                if (issue_index_r < 24) begin
                    issue_index_r <= issue_index_r + 1'b1;
                    read_pending_r <= 1'b1;
                end
            end
            if (output_fire) begin
                output_valid_r <= 1'b0;
                if (group_r == 127) begin
                    active_r <= 1'b0;
                end else begin
                    group_r <= group_r + 1'b1;
                    issue_index_r <= 5'd0;
                    capture_index_r <= 5'd0;
                    read_pending_r <= 1'b0;
                    read_stage_valid_r <= 1'b0;
                end
            end
            if (wr_valid && (wr_addr >= 3072))
                error <= 1'b1;
        end
    end
endmodule
