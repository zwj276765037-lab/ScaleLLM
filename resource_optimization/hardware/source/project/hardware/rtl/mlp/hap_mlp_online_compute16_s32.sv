`timescale 1ns / 1ps

// Standalone online-H32/A8 -> unchanged GU/scale restoration -> SiLU*Up.
// This is a streaming arithmetic boundary; the existing board ABI is untouched.
module hap_mlp_online_compute16_s32 #(
    parameter integer INTERMEDIATE_COLUMNS = 14336,
    parameter integer ENFORCE_PRODUCTION_SHAPE = 1,
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input wire core_clk,
    input wire core_rst_n,
    input wire core_clear,
    input wire begin_valid,
    output wire begin_ready,
    input wire [31:0] begin_batch_tag,
    input wire [31:0] gate_ddr0_base_addr,
    input wire [31:0] gate_ddr1_base_addr,
    input wire in_valid,
    output wire in_ready,
    input wire [8:0] in_group,
    input wire [16*32*24-1:0] in_s24x16x32,
    input wire gate_meta_valid,
    output wire gate_meta_ready,
    input wire [223:0] gate_meta_u224,
    input wire ddr0_clk,
    input wire ddr0_rst_n,
    output wire ddr0_axi_arvalid,
    input wire ddr0_axi_arready,
    output wire [31:0] ddr0_axi_araddr,
    output wire [7:0] ddr0_axi_arlen,
    output wire [2:0] ddr0_axi_arsize,
    output wire [1:0] ddr0_axi_arburst,
    input wire ddr0_axi_rvalid,
    output wire ddr0_axi_rready,
    input wire [511:0] ddr0_axi_rdata,
    input wire [1:0] ddr0_axi_rresp,
    input wire ddr0_axi_rlast,
    input wire ddr1_clk,
    input wire ddr1_rst_n,
    output wire ddr1_axi_arvalid,
    input wire ddr1_axi_arready,
    output wire [31:0] ddr1_axi_araddr,
    output wire [7:0] ddr1_axi_arlen,
    output wire [2:0] ddr1_axi_arsize,
    output wire [1:0] ddr1_axi_arburst,
    input wire ddr1_axi_rvalid,
    output wire ddr1_axi_rready,
    input wire [511:0] ddr1_axi_rdata,
    input wire [1:0] ddr1_axi_rresp,
    input wire ddr1_axi_rlast,
    output wire out_valid,
    input wire out_ready,
    output wire [8191:0] out_s32x16x16,
    output wire [9:0] out_tile,
    output wire out_last,
    output wire [31:0] out_batch_tag,
    output wire busy,
    output reg done,
    output wire error,
    output wire weight_source_quiescent,
    output wire [31:0] gu_saturation_count,
    output wire [31:0] gu_total_shift_format_count,
    output wire [31:0] gu_numeric_status
);
    localparam [2:0] S_IDLE=0, S_LOAD=1, S_SEAL=2, S_LAUNCH=3,
        S_RUN=4, S_RELEASE=5;
    reg [2:0] state_r;
    reg [31:0] batch_tag_r, base0_r, base1_r;
    reg [8:0] next_group_r;
    reg sticky_error_r, gu_finished_r, product_finished_r;
    wire frontend_in_ready;
    wire frontend_error, frontend_format_error;
    wire [1:0] bank_ready;
    wire cache_req_valid, cache_req_ready, cache_req_bank;
    wire [8:0] cache_req_group;
    wire cache_rsp_valid, cache_rsp_ready, cache_rsp_bank;
    wire [6:0] cache_rsp_group;
    wire [4095:0] cache_rsp_q;
    wire [383:0] cache_rsp_meta;
    wire release_ready;
    wire gu_command_ready, gu_done, gu_error, gu_quiescent;
    wire gu_valid, gu_ready, gu_matrix, gu_last;
    wire [6143:0] gu_s24;
    wire [9:0] gu_tile;
    wire endpoint_error;
    wire group_legal = in_group == next_group_r && in_group < 128;
    wire input_fire = in_valid && in_ready;

    assign error = sticky_error_r || frontend_error || frontend_format_error ||
        gu_error || endpoint_error;
    assign begin_ready = core_rst_n && !core_clear && !error &&
        state_r == S_IDLE && !bank_ready[0] && weight_source_quiescent;
    assign in_ready = core_rst_n && !core_clear && !error &&
        state_r == S_LOAD && frontend_in_ready;
    assign busy = state_r != S_IDLE;
    assign out_batch_tag = batch_tag_r;

    hap_mlp_input_frontend16_compact_cache u_online_input (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .in_valid(in_valid && state_r == S_LOAD && group_legal && !error),
        .in_ready(frontend_in_ready), .in_bank(1'b0),
        .in_group(in_group[6:0]), .in_s24x16x32(in_s24x16x32),
        .rd_req_valid(cache_req_valid), .rd_req_ready(cache_req_ready),
        .rd_req_bank(cache_req_bank), .rd_req_group(cache_req_group[6:0]),
        .rd_rsp_valid(cache_rsp_valid), .rd_rsp_ready(cache_rsp_ready),
        .rd_rsp_bank(cache_rsp_bank), .rd_rsp_group(cache_rsp_group),
        .rd_rsp_u8x16x32(cache_rsp_q), .rd_rsp_meta_u24x16(cache_rsp_meta),
        .release_valid(state_r == S_RELEASE), .release_ready(release_ready),
        .release_bank(1'b0), .bank_ready(bank_ready),
        .input_group_count(), .read_group_count(), .release_count(),
        .hadamard_saturation_count(), .format_error(frontend_format_error),
        .error(frontend_error)
    );

    hap_mlp_gu_compute16_s44 #(
        .INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS),
        .ENFORCE_PRODUCTION_SHAPE(ENFORCE_PRODUCTION_SHAPE)
    ) u_gu (
        .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(core_clear),
        .command_pause(1'b0), .weight_source_quiescent(weight_source_quiescent),
        .command_valid(state_r == S_LAUNCH && !error),
        .command_ready(gu_command_ready), .command_opcode(2'd1),
        .cache_sealed(bank_ready[0]),
        .gate_ddr0_base_addr(base0_r), .gate_ddr1_base_addr(base1_r),
        .cache_rd_req_valid(cache_req_valid), .cache_rd_req_ready(cache_req_ready),
        .cache_rd_req_bank(cache_req_bank), .cache_rd_req_group(cache_req_group),
        .cache_rd_rsp_valid(cache_rsp_valid), .cache_rd_rsp_ready(cache_rsp_ready),
        .cache_rd_rsp_bank(cache_rsp_bank),
        .cache_rd_rsp_group({2'b0,cache_rsp_group}),
        .cache_rd_rsp_u8x16x32(cache_rsp_q), .cache_rd_rsp_meta_u24x16(cache_rsp_meta),
        .gate_meta_valid(gate_meta_valid), .gate_meta_ready(gate_meta_ready),
        .gate_meta_u224(gate_meta_u224),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_axi_arvalid(ddr0_axi_arvalid), .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize), .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid), .ddr0_axi_rready(ddr0_axi_rready),
        .ddr0_axi_rdata(ddr0_axi_rdata), .ddr0_axi_rresp(ddr0_axi_rresp),
        .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(ddr1_axi_arvalid), .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize), .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid), .ddr1_axi_rready(ddr1_axi_rready),
        .ddr1_axi_rdata(ddr1_axi_rdata), .ddr1_axi_rresp(ddr1_axi_rresp),
        .ddr1_axi_rlast(ddr1_axi_rlast),
        .gu_out_valid(gu_valid), .gu_out_ready(gu_ready),
        .gu_out_s24x16x16(gu_s24), .gu_out_tile(gu_tile),
        .gu_out_matrix(gu_matrix), .gu_out_last(gu_last),
        .compute_quiescent(gu_quiescent), .flow_stall(), .busy(),
        .done(gu_done), .error(gu_error), .phase(),
        .saturation_count(gu_saturation_count),
        .total_shift_format_count(gu_total_shift_format_count),
        .numeric_status(gu_numeric_status)
    );

    hap_mlp_swiglu_s32_endpoint16 #(
        .INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS), .SILU_LUT_FILE(SILU_LUT_FILE)
    ) u_product (
        .clk(core_clk), .rst_n(core_rst_n), .clear(core_clear),
        .in_valid(gu_valid), .in_ready(gu_ready), .in_s24x16x16(gu_s24),
        .in_tile(gu_tile), .in_matrix(gu_matrix), .in_last(gu_last),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_s32x16x16(out_s32x16x16), .out_tile(out_tile), .out_last(out_last),
        .busy(), .error(endpoint_error), .input_tile_count(), .product_tile_count()
    );

    always @(posedge core_clk) begin
        if (!core_rst_n || core_clear) begin
            state_r <= S_IDLE;
            batch_tag_r <= 0;
            base0_r <= 0;
            base1_r <= 0;
            next_group_r <= 0;
            sticky_error_r <= 0;
            gu_finished_r <= 0;
            product_finished_r <= 0;
            done <= 0;
        end else begin
            done <= 0;
            if (begin_valid && begin_ready) begin
                state_r <= S_LOAD;
                batch_tag_r <= begin_batch_tag;
                base0_r <= gate_ddr0_base_addr;
                base1_r <= gate_ddr1_base_addr;
                next_group_r <= 0;
                gu_finished_r <= 0;
                product_finished_r <= 0;
            end
            if (input_fire) begin
                if (!group_legal)
                    sticky_error_r <= 1;
                else begin
                    next_group_r <= next_group_r + 1'b1;
                    if (in_group == 127)
                        state_r <= S_SEAL;
                end
            end
            if (state_r == S_SEAL && bank_ready[0] && !error)
                state_r <= S_LAUNCH;
            if (state_r == S_LAUNCH && gu_command_ready && !error)
                state_r <= S_RUN;
            if (gu_done)
                gu_finished_r <= 1;
            if (out_valid && out_ready && out_last)
                product_finished_r <= 1;
            if (state_r == S_RUN && gu_finished_r && product_finished_r &&
                    gu_quiescent && weight_source_quiescent && !error)
                state_r <= S_RELEASE;
            if (state_r == S_RELEASE && release_ready && !error) begin
                state_r <= S_IDLE;
                done <= 1;
            end
        end
    end
endmodule
