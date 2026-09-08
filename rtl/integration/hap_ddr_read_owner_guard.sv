`timescale 1ns / 1ps

// One physical AXI read-channel owner register.  Every signal in this module
// is in the corresponding MIG UI clock domain.  The request payload is held by
// an enclosing xpm_cdc_handshake until request_ack is asserted.
module hap_ddr_read_owner_channel_guard #(
    parameter integer OUTSTANDING_W = 8
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         request_req,
    output reg                          request_ack,
    input  wire [1:0]                   request_owner,
    input  wire                         ar_fire,
    input  wire                         rlast_fire,
    output reg  [1:0]                   active_owner,
    output reg  [OUTSTANDING_W-1:0]     outstanding,
    output reg                          protocol_error
);
    localparam [1:0] OWNER_IDLE = 2'd0;
    localparam [1:0] OWNER_ATTN = 2'd1;
    localparam [1:0] OWNER_MLP  = 2'd2;
    localparam [OUTSTANDING_W-1:0] OUTSTANDING_MAX =
        {OUTSTANDING_W{1'b1}};

    wire owner_legal = request_owner == OWNER_IDLE ||
        request_owner == OWNER_ATTN || request_owner == OWNER_MLP;
    // Do not switch on a cycle carrying any AXI completion/issue event.  This
    // also catches an unexpected late AR after core-domain quiescence.
    wire channel_idle = outstanding == {OUTSTANDING_W{1'b0}} &&
        !ar_fire && !rlast_fire;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            request_ack <= 1'b0;
            active_owner <= OWNER_IDLE;
            outstanding <= {OUTSTANDING_W{1'b0}};
            protocol_error <= 1'b0;
        end else begin
            if (!request_req)
                request_ack <= 1'b0;

            case ({ar_fire,rlast_fire})
                2'b10: begin
                    if (outstanding == OUTSTANDING_MAX)
                        protocol_error <= 1'b1;
                    else
                        outstanding <= outstanding + 1'b1;
                end
                2'b01: begin
                    if (outstanding == {OUTSTANDING_W{1'b0}})
                        protocol_error <= 1'b1;
                    else
                        outstanding <= outstanding - 1'b1;
                end
                default: outstanding <= outstanding;
            endcase

            if (clear) begin
                // A reset while responses remain in flight would allow them to
                // be delivered to a later owner.  Retain the owner and flag it.
                if (channel_idle && !request_req) begin
                    request_ack <= 1'b0;
                    active_owner <= OWNER_IDLE;
                    outstanding <= {OUTSTANDING_W{1'b0}};
                    protocol_error <= 1'b0;
                end else begin
                    protocol_error <= 1'b1;
                end
            end else if (request_req && !request_ack) begin
                if (!owner_legal) begin
                    protocol_error <= 1'b1;
                    request_ack <= 1'b1;
                end else if (channel_idle) begin
                    active_owner <= request_owner;
                    request_ack <= 1'b1;
                end
            end
        end
    end
endmodule

// CDC-safe command-level owner for two independent MIG UI domains.
//
// The core accepts a target owner, blocks new engine launches, waits for the
// current engine to become quiescent, and then holds one handshake request to
// each DDR domain.  Each channel changes its local mux select only after its
// own AXI outstanding counter reaches zero.  The target engine is enabled only
// after both channel acknowledgements return to the core domain.
module hap_ddr_read_owner_guard #(
    parameter integer OUTSTANDING_W = 8
) (
    input  wire                         core_clk,
    input  wire                         core_rst_n,
    input  wire                         core_clear,
    input  wire                         request_valid,
    output wire                         request_ready,
    input  wire [1:0]                   request_owner,
    output reg                          request_done,
    input  wire                         attention_quiescent,
    input  wire                         mlp_quiescent,

    input  wire                         ddr0_clk,
    input  wire                         ddr0_rst_n,
    input  wire                         ddr0_clear,
    input  wire                         ddr0_ar_fire,
    input  wire                         ddr0_rlast_fire,
    output wire [1:0]                   ddr0_active_owner,
    output wire [OUTSTANDING_W-1:0]     ddr0_outstanding,

    input  wire                         ddr1_clk,
    input  wire                         ddr1_rst_n,
    input  wire                         ddr1_clear,
    input  wire                         ddr1_ar_fire,
    input  wire                         ddr1_rlast_fire,
    output wire [1:0]                   ddr1_active_owner,
    output wire [OUTSTANDING_W-1:0]     ddr1_outstanding,

    output reg  [1:0]                   active_owner,
    output wire                         attention_launch_enable,
    output wire                         mlp_launch_enable,
    output wire                         switch_pending,
    output wire                         protocol_error
);
    localparam [1:0] OWNER_IDLE = 2'd0;
    localparam [1:0] OWNER_ATTN = 2'd1;
    localparam [1:0] OWNER_MLP  = 2'd2;

    reg       pending_r;
    reg       switch_started_r;
    reg [1:0] pending_owner_r;
    reg       ddr0_send_r;
    reg       ddr1_send_r;
    reg       core_protocol_error_r;

    wire [1:0] ddr0_request_owner;
    wire [1:0] ddr1_request_owner;
    wire ddr0_request_req;
    wire ddr1_request_req;
    wire ddr0_request_ack;
    wire ddr1_request_ack;
    wire ddr0_received;
    wire ddr1_received;
    wire ddr0_protocol_error;
    wire ddr1_protocol_error;
    wire ddr0_protocol_error_core;
    wire ddr1_protocol_error_core;

    wire request_fire = request_valid && request_ready;
    wire request_owner_legal = request_owner == OWNER_IDLE ||
        request_owner == OWNER_ATTN || request_owner == OWNER_MLP;
    wire active_quiescent = active_owner == OWNER_IDLE ? 1'b1 :
        active_owner == OWNER_ATTN ? attention_quiescent :
        active_owner == OWNER_MLP ? mlp_quiescent : 1'b0;

    assign request_ready = core_rst_n && !core_clear && !pending_r;
    assign switch_pending = pending_r;
    assign attention_launch_enable = active_owner == OWNER_ATTN && !pending_r;
    assign mlp_launch_enable = active_owner == OWNER_MLP && !pending_r;
    assign protocol_error = core_protocol_error_r ||
        ddr0_protocol_error_core || ddr1_protocol_error_core;

    xpm_cdc_handshake #(
        .DEST_EXT_HSK(1), .DEST_SYNC_FF(2), .INIT_SYNC_FF(1),
        .SIM_ASSERT_CHK(0), .SRC_SYNC_FF(2), .WIDTH(2)
    ) u_owner0_cdc (
        .src_clk(core_clk), .src_in(pending_owner_r),
        .src_send(ddr0_send_r), .src_rcv(ddr0_received),
        .dest_clk(ddr0_clk), .dest_out(ddr0_request_owner),
        .dest_req(ddr0_request_req), .dest_ack(ddr0_request_ack)
    );

    xpm_cdc_handshake #(
        .DEST_EXT_HSK(1), .DEST_SYNC_FF(2), .INIT_SYNC_FF(1),
        .SIM_ASSERT_CHK(0), .SRC_SYNC_FF(2), .WIDTH(2)
    ) u_owner1_cdc (
        .src_clk(core_clk), .src_in(pending_owner_r),
        .src_send(ddr1_send_r), .src_rcv(ddr1_received),
        .dest_clk(ddr1_clk), .dest_out(ddr1_request_owner),
        .dest_req(ddr1_request_req), .dest_ack(ddr1_request_ack)
    );

    hap_ddr_read_owner_channel_guard #(
        .OUTSTANDING_W(OUTSTANDING_W)
    ) u_channel0 (
        .clk(ddr0_clk),.rst_n(ddr0_rst_n),.clear(ddr0_clear),
        .request_req(ddr0_request_req),.request_ack(ddr0_request_ack),
        .request_owner(ddr0_request_owner),.ar_fire(ddr0_ar_fire),
        .rlast_fire(ddr0_rlast_fire),.active_owner(ddr0_active_owner),
        .outstanding(ddr0_outstanding),
        .protocol_error(ddr0_protocol_error)
    );

    hap_ddr_read_owner_channel_guard #(
        .OUTSTANDING_W(OUTSTANDING_W)
    ) u_channel1 (
        .clk(ddr1_clk),.rst_n(ddr1_rst_n),.clear(ddr1_clear),
        .request_req(ddr1_request_req),.request_ack(ddr1_request_ack),
        .request_owner(ddr1_request_owner),.ar_fire(ddr1_ar_fire),
        .rlast_fire(ddr1_rlast_fire),.active_owner(ddr1_active_owner),
        .outstanding(ddr1_outstanding),
        .protocol_error(ddr1_protocol_error)
    );

    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(1)
    ) u_error0_cdc (
        .src_clk(ddr0_clk),.src_in(ddr0_protocol_error),
        .dest_clk(core_clk),.dest_out(ddr0_protocol_error_core)
    );

    xpm_cdc_single #(
        .DEST_SYNC_FF(2), .INIT_SYNC_FF(1), .SIM_ASSERT_CHK(0),
        .SRC_INPUT_REG(1)
    ) u_error1_cdc (
        .src_clk(ddr1_clk),.src_in(ddr1_protocol_error),
        .dest_clk(core_clk),.dest_out(ddr1_protocol_error_core)
    );

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            active_owner <= OWNER_IDLE;
            pending_r <= 1'b0;
            switch_started_r <= 1'b0;
            pending_owner_r <= OWNER_IDLE;
            ddr0_send_r <= 1'b0;
            ddr1_send_r <= 1'b0;
            request_done <= 1'b0;
            core_protocol_error_r <= 1'b0;
        end else begin
            request_done <= 1'b0;

            if (ddr0_send_r && ddr0_received)
                ddr0_send_r <= 1'b0;
            if (ddr1_send_r && ddr1_received)
                ddr1_send_r <= 1'b0;

            if (core_clear) begin
                // Software may clear only after requesting IDLE and receiving
                // its acknowledgement.  Reject a destructive mid-switch clear.
                if (!pending_r && active_owner == OWNER_IDLE) begin
                    pending_r <= 1'b0;
                    switch_started_r <= 1'b0;
                    pending_owner_r <= OWNER_IDLE;
                    ddr0_send_r <= 1'b0;
                    ddr1_send_r <= 1'b0;
                    core_protocol_error_r <= 1'b0;
                end else begin
                    core_protocol_error_r <= 1'b1;
                end
            end else begin
                if (request_fire) begin
                    if (!request_owner_legal) begin
                        core_protocol_error_r <= 1'b1;
                    end else if (request_owner == active_owner) begin
                        request_done <= 1'b1;
                    end else begin
                        pending_r <= 1'b1;
                        switch_started_r <= 1'b0;
                        pending_owner_r <= request_owner;
                    end
                end

                if (pending_r && !switch_started_r && active_quiescent) begin
                    ddr0_send_r <= 1'b1;
                    ddr1_send_r <= 1'b1;
                    switch_started_r <= 1'b1;
                end

                if (pending_r && switch_started_r &&
                    !ddr0_send_r && !ddr1_send_r) begin
                    active_owner <= pending_owner_r;
                    pending_r <= 1'b0;
                    switch_started_r <= 1'b0;
                    request_done <= 1'b1;
                end
            end
        end
    end
endmodule
