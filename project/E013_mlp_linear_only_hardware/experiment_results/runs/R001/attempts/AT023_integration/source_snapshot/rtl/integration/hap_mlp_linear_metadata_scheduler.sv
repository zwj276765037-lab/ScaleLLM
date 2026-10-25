`timescale 1ns / 1ps

// Sequential address generator between the MLP consumer and the resident
// gate/up + down URAM ports.  There is at most one buffered response on each
// path (enforced by the resident memory interface), and addresses advance on
// URAM request acceptance rather than consumer ready.
module hap_mlp_linear_metadata_scheduler #(
    parameter integer GATE_RECORDS = 229376,
    parameter integer DOWN_RECORDS = 114688,
    parameter integer GATE_ADDR_W = 18,
    parameter integer DOWN_ADDR_W = 17,
    parameter integer RESPONSE_FIFO_DEPTH = 2,
    parameter integer PRODUCTION_SHAPE = 1
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       clear,
    input  wire                       command_start,
    input  wire                       command_done,
    input wire [1:0]                  command_opcode,
    output wire                       drained,
    input  wire                       gate_enable,
    input  wire                       down_enable,

    output wire                       gate_rd_valid,
    input  wire                       gate_rd_ready,
    output wire [GATE_ADDR_W-1:0]     gate_rd_addr,
    input  wire                       gate_rsp_valid,
    output wire                       gate_rsp_ready,
    input  wire [223:0]               gate_rsp_meta,
    output wire                       gate_meta_valid,
    input  wire                       gate_meta_ready,
    output wire [223:0]               gate_meta,

    output wire                       down_rd_valid,
    input  wire                       down_rd_ready,
    output wire [DOWN_ADDR_W-1:0]     down_rd_addr,
    input  wire                       down_rsp_valid,
    output wire                       down_rsp_ready,
    input  wire [223:0]               down_rsp_meta,
    output wire                       down_meta_valid,
    input  wire                       down_meta_ready,
    output wire [223:0]               down_meta,

    output wire                       active,
    output reg  [31:0]                gate_issue_count,
    output reg  [31:0]                gate_delivery_count,
    output reg  [31:0]                down_issue_count,
    output reg  [31:0]                down_delivery_count,
    output reg                        done,
    output reg                        error
);
    reg active_r;
    reg [1:0] opcode_r;
    wire [31:0] expected_gate=opcode_r==1?GATE_RECORDS:0;
    wire [31:0] expected_down=opcode_r==2?DOWN_RECORDS:0;

    // RESPONSE_FIFO_DEPTH is contractually fixed at two below.  Spell the
    // payload slots out as independent, resetless registers instead of using
    // a variable-indexed unpacked array: the latter is inferred as RAMD/RAMG
    // and creates a dedicated URAM-to-distributed-RAM write path across the
    // metadata pblock.  These attributes are an additional synthesis guard;
    // the explicit slot decode is what removes the RAM inference template.
    (* ram_style = "registers", shreg_extract = "no" *)
    reg [223:0] gate_fifo_slot0_r,gate_fifo_slot1_r;
    (* ram_style = "registers", shreg_extract = "no" *)
    reg [223:0] down_fifo_slot0_r,down_fifo_slot1_r;
    reg gate_fifo_wr_ptr_r,gate_fifo_rd_ptr_r;
    reg down_fifo_wr_ptr_r,down_fifo_rd_ptr_r;
    reg [1:0] gate_fifo_count_r,down_fifo_count_r;
    wire gate_rd_fire = gate_rd_valid && gate_rd_ready;
    wire gate_rsp_fire = gate_rsp_valid && gate_rsp_ready;
    wire gate_meta_fire = gate_meta_valid && gate_meta_ready;
    wire down_rd_fire = down_rd_valid && down_rd_ready;
    wire down_rsp_fire = down_rsp_valid && down_rsp_ready;
    wire down_meta_fire = down_meta_valid && down_meta_ready;

    assign drained=gate_issue_count==expected_gate&&gate_delivery_count==expected_gate&&
        down_issue_count==expected_down&&down_delivery_count==expected_down&&
        gate_fifo_count_r==0&&down_fifo_count_r==0&&!gate_rsp_valid&&!down_rsp_valid;
    assign active = active_r;
    assign gate_rd_valid = active_r && gate_enable &&
        gate_issue_count < expected_gate;
    assign gate_rd_addr = gate_issue_count[GATE_ADDR_W-1:0];
    // The response FIFOs are a physical timing boundary.  In particular,
    // rsp_ready depends only on registered occupancy, never combinationally
    // on the MLP consumer ready chain.  This prevents kernel backpressure
    // from propagating across SLRs into a cascaded URAM enable input.
    assign gate_rsp_ready = active_r && gate_enable &&
        gate_fifo_count_r < RESPONSE_FIFO_DEPTH;
    assign gate_meta_valid = active_r && gate_enable &&
        gate_fifo_count_r != 0;
    assign gate_meta = gate_fifo_rd_ptr_r ?
        gate_fifo_slot1_r : gate_fifo_slot0_r;
    assign down_rd_valid = active_r && down_enable &&
        down_issue_count < expected_down;
    assign down_rd_addr = down_issue_count[DOWN_ADDR_W-1:0];
    assign down_rsp_ready = active_r && down_enable &&
        down_fifo_count_r < RESPONSE_FIFO_DEPTH;
    assign down_meta_valid = active_r && down_enable &&
        down_fifo_count_r != 0;
    assign down_meta = down_fifo_rd_ptr_r ?
        down_fifo_slot1_r : down_fifo_slot0_r;

    // FIFO payload contents are observable only when the registered count is
    // non-zero.  Keep all four slots out of the asynchronous reset process;
    // reset/clear invalidate them by clearing occupancy and both pointers, and
    // every exposed slot is written before its count increments.  This retains
    // the reset-fanout reduction while deliberately spending 896 resetless FFs
    // to avoid distributed-RAM write timing arcs.
    always @(posedge clk) begin
        if (gate_rsp_fire) begin
            if (gate_fifo_wr_ptr_r)
                gate_fifo_slot1_r <= gate_rsp_meta;
            else
                gate_fifo_slot0_r <= gate_rsp_meta;
        end
        if (down_rsp_fire) begin
            if (down_fifo_wr_ptr_r)
                down_fifo_slot1_r <= down_rsp_meta;
            else
                down_fifo_slot0_r <= down_rsp_meta;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_r <= 1'b0;
            opcode_r <= 0;
            gate_issue_count <= 32'd0;
            gate_delivery_count <= 32'd0;
            down_issue_count <= 32'd0;
            down_delivery_count <= 32'd0;
            gate_fifo_wr_ptr_r <= 1'b0;
            gate_fifo_rd_ptr_r <= 1'b0;
            down_fifo_wr_ptr_r <= 1'b0;
            down_fifo_rd_ptr_r <= 1'b0;
            gate_fifo_count_r <= 2'd0;
            down_fifo_count_r <= 2'd0;
            done <= 1'b0;
            error <= 1'b0;
        end else if (clear) begin
            active_r <= 1'b0;
            opcode_r <= 0;
            gate_issue_count <= 32'd0;
            gate_delivery_count <= 32'd0;
            down_issue_count <= 32'd0;
            down_delivery_count <= 32'd0;
            gate_fifo_wr_ptr_r <= 1'b0;
            gate_fifo_rd_ptr_r <= 1'b0;
            down_fifo_wr_ptr_r <= 1'b0;
            down_fifo_rd_ptr_r <= 1'b0;
            gate_fifo_count_r <= 2'd0;
            down_fifo_count_r <= 2'd0;
            done <= 1'b0;
            error <= 1'b0;
        end else begin
            done <= 1'b0;
            if (command_start) begin
                if (active_r)
                    error <= 1'b1;
                else begin
                    active_r <= 1'b1;
                    opcode_r <= command_opcode;
                    gate_issue_count <= 32'd0;
                    gate_delivery_count <= 32'd0;
                    down_issue_count <= 32'd0;
                    down_delivery_count <= 32'd0;
                    gate_fifo_wr_ptr_r <= 1'b0;
                    gate_fifo_rd_ptr_r <= 1'b0;
                    down_fifo_wr_ptr_r <= 1'b0;
                    down_fifo_rd_ptr_r <= 1'b0;
                    gate_fifo_count_r <= 2'd0;
                    down_fifo_count_r <= 2'd0;
                    error <= 1'b0;
                end
            end
            if (gate_rd_fire)
                gate_issue_count <= gate_issue_count + 1'b1;
            if (gate_meta_fire)
                gate_delivery_count <= gate_delivery_count + 1'b1;
            if (down_rd_fire)
                down_issue_count <= down_issue_count + 1'b1;
            if (down_meta_fire)
                down_delivery_count <= down_delivery_count + 1'b1;

            if (gate_rsp_fire) begin
                gate_fifo_wr_ptr_r <= gate_fifo_wr_ptr_r + 1'b1;
            end
            if (gate_meta_fire)
                gate_fifo_rd_ptr_r <= gate_fifo_rd_ptr_r + 1'b1;
            case ({gate_rsp_fire,gate_meta_fire})
                2'b10: gate_fifo_count_r <= gate_fifo_count_r + 1'b1;
                2'b01: gate_fifo_count_r <= gate_fifo_count_r - 1'b1;
                default: gate_fifo_count_r <= gate_fifo_count_r;
            endcase

            if (down_rsp_fire) begin
                down_fifo_wr_ptr_r <= down_fifo_wr_ptr_r + 1'b1;
            end
            if (down_meta_fire)
                down_fifo_rd_ptr_r <= down_fifo_rd_ptr_r + 1'b1;
            case ({down_rsp_fire,down_meta_fire})
                2'b10: down_fifo_count_r <= down_fifo_count_r + 1'b1;
                2'b01: down_fifo_count_r <= down_fifo_count_r - 1'b1;
                default: down_fifo_count_r <= down_fifo_count_r;
            endcase

            if (command_done) begin
                active_r <= 1'b0;
                done <= 1'b1;
                if (gate_issue_count + gate_rd_fire != expected_gate ||
                    gate_delivery_count + gate_meta_fire != expected_gate ||
                    down_issue_count + down_rd_fire != expected_down ||
                    down_delivery_count + down_meta_fire != expected_down ||
                    (gate_rsp_valid && !gate_rsp_fire) ||
                    (down_rsp_valid && !down_rsp_fire) ||
                    ({1'b0,gate_fifo_count_r} + gate_rsp_fire -
                        gate_meta_fire) != 0 ||
                    ({1'b0,down_fifo_count_r} + down_rsp_fire -
                        down_meta_fire) != 0)
                    error <= 1'b1;
            end
            if ((gate_meta_fire && gate_delivery_count >= expected_gate) ||
                (down_meta_fire && down_delivery_count >= expected_down) ||
                gate_fifo_count_r > RESPONSE_FIFO_DEPTH ||
                down_fifo_count_r > RESPONSE_FIFO_DEPTH ||
                (gate_enable && down_enable))
                error <= 1'b1;
        end
    end

    initial begin
        if (PRODUCTION_SHAPE &&
            (GATE_RECORDS != 229376 || DOWN_RECORDS != 114688 ||
             GATE_ADDR_W != 18 || DOWN_ADDR_W != 17))
            $error("production MLP metadata shape required");
        if (RESPONSE_FIFO_DEPTH != 2)
            $error("metadata scheduler timing boundary requires depth-2 FIFOs");
    end
endmodule
