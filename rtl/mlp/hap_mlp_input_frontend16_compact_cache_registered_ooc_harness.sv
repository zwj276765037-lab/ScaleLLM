`timescale 1ns / 1ps

// Registered-boundary physical harness for the production compact MLP input
// frontend.  This module is diagnostic-only and is not instantiated by the
// production design.  Resetless source/sink FFs replace raw OOC partition pins
// with ordinary same-clock paths while leaving the DUT RTL unchanged.
module hap_mlp_input_frontend16_compact_cache_registered_ooc_harness (
    input wire clk
);
    localparam integer SRC_W = 12311;
    localparam integer SINK_W = 4623;

    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_IN_BANK = 3;
    localparam integer S_IN_GROUP = 4;
    localparam integer S_IN_S24 = 11;
    localparam integer S_RD_REQ_VALID = 12299;
    localparam integer S_RD_REQ_BANK = 12300;
    localparam integer S_RD_REQ_GROUP = 12301;
    localparam integer S_RD_RSP_READY = 12308;
    localparam integer S_RELEASE_VALID = 12309;
    localparam integer S_RELEASE_BANK = 12310;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire rd_req_ready;
    wire rd_rsp_valid;
    wire rd_rsp_bank;
    wire [6:0] rd_rsp_group;
    wire [16*32*8-1:0] rd_rsp_u8x16x32;
    wire [16*24-1:0] rd_rsp_meta_u24x16;
    wire release_ready;
    wire [1:0] bank_ready;
    wire [31:0] input_group_count;
    wire [31:0] read_group_count;
    wire [31:0] release_count;
    wire [31:0] hadamard_saturation_count;
    wire error;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error,
        hadamard_saturation_count,
        release_count,
        read_group_count,
        input_group_count,
        bank_ready,
        release_ready,
        rd_rsp_meta_u24x16,
        rd_rsp_u8x16x32,
        rd_rsp_group,
        rd_rsp_bank,
        rd_rsp_valid,
        rd_req_ready,
        in_ready
    };

    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_input_frontend16_compact_cache u_dut (
        .clk(clk),
        .rst_n(src_r[S_RST_N]),
        .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]),
        .in_ready(in_ready),
        .in_bank(src_r[S_IN_BANK]),
        .in_group(src_r[S_IN_GROUP +: 7]),
        .in_s24x16x32(src_r[S_IN_S24 +: 16*32*24]),
        .rd_req_valid(src_r[S_RD_REQ_VALID]),
        .rd_req_ready(rd_req_ready),
        .rd_req_bank(src_r[S_RD_REQ_BANK]),
        .rd_req_group(src_r[S_RD_REQ_GROUP +: 7]),
        .rd_rsp_valid(rd_rsp_valid),
        .rd_rsp_ready(src_r[S_RD_RSP_READY]),
        .rd_rsp_bank(rd_rsp_bank),
        .rd_rsp_group(rd_rsp_group),
        .rd_rsp_u8x16x32(rd_rsp_u8x16x32),
        .rd_rsp_meta_u24x16(rd_rsp_meta_u24x16),
        .release_valid(src_r[S_RELEASE_VALID]),
        .release_ready(release_ready),
        .release_bank(src_r[S_RELEASE_BANK]),
        .bank_ready(bank_ready),
        .input_group_count(input_group_count),
        .read_group_count(read_group_count),
        .release_count(release_count),
        .hadamard_saturation_count(hadamard_saturation_count),
        .error(error)
    );

    initial begin
        if (S_RELEASE_BANK != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("compact-input registered OOC vector layout mismatch");
    end
endmodule
