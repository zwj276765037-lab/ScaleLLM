`timescale 1ns / 1ps

// Single simple-dual-port URAM inference leaf plus its bank-local response
// boundary.  Keeping each large memory in its own module and using
// unconditional address ports is required for Vivado to recognize the
// UltraRAM template at this depth/width.
//
// The two resetless payload slots and the URAM output register form a
// three-credit response pipe.  That extra credit is intentional: rd_ready is
// derived only from registered outstanding occupancy and never from
// rsp_ready, yet an unstalled stream can still accept one read every cycle.
// When the consumer stalls, a pending URAM result remains in rd_data_uram_r
// until a local slot is available, so it cannot be overwritten.  Since this
// logic is below each physical bank root, the production hard pblock places
// the first 224-bit fabric capture beside that bank's URAM cascade.
module hap_mlp_weight_meta_uram_leaf #(
    parameter integer DEPTH = 229376,
    parameter integer ADDR_W = 18,
    parameter integer BANK_ID = 0
) (
    input  wire                   clk,
    input  wire                   wr_valid,
    input  wire                   wr_bank,
    input  wire [ADDR_W-1:0]      wr_addr,
    input  wire [223:0]           wr_data,
    input  wire                   rst_n,
    input  wire                   clear,
    input  wire                   rd_valid,
    output wire                   rd_ready,
    input  wire [ADDR_W-1:0]      rd_addr,
    output wire                   rsp_valid,
    input  wire                   rsp_ready,
    output wire [223:0]           rsp_data,
    output wire                   response_idle
);
    (* ram_style = "ultra" *) reg [223:0] mem [0:DEPTH-1];
    reg [223:0] rd_data_uram_r;
    (* ram_style = "registers", shreg_extract = "no" *)
    reg [223:0] rsp_fifo_slot0_r,rsp_fifo_slot1_r;
    reg rsp_fifo_wr_ptr_r,rsp_fifo_rd_ptr_r;
    reg [1:0] rsp_fifo_count_r;
    reg rd_pending_r;
    reg [1:0] outstanding_count_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg wr_en_local_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [ADDR_W-1:0] wr_addr_local_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [223:0] wr_data_local_r;

    wire rd_fire = rd_valid && rd_ready;
    wire rsp_fire = rsp_valid && rsp_ready;
    wire capture_ready = rsp_fifo_count_r < 2 || rsp_fire;
    wire capture_fire = rd_pending_r && capture_ready;

    // A same-cycle credit return is deliberately not bypassed into rd_ready.
    // This is the timing isolation that prevents scheduler/consumer ready
    // from reaching a cascaded URAM enable.  Three physical credits hide that
    // registered return during a normal one-response-per-cycle stream.
    assign rd_ready = rst_n && !clear && outstanding_count_r < 3;
    assign rsp_valid = rst_n && !clear && rsp_fifo_count_r != 0;
    assign rsp_data = rsp_fifo_rd_ptr_r ?
        rsp_fifo_slot1_r : rsp_fifo_slot0_r;
    assign response_idle = outstanding_count_r == 0 &&
        rsp_fifo_count_r == 0 && !rd_pending_r;

    // Decode and capture at each physical bank root. The one-bit bank selector
    // now terminates at four local FFs instead of driving the distributed URAM
    // write enables, while accepted writes remain capable of II=1 operation.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            wr_en_local_r <= 1'b0;
        else if (clear)
            wr_en_local_r <= 1'b0;
        else
            wr_en_local_r <= wr_valid && (wr_bank == BANK_ID[0]);
    end

    always @(posedge clk) begin
        if (wr_valid && (wr_bank == BANK_ID[0])) begin
            wr_addr_local_r <= wr_addr;
            wr_data_local_r <= wr_data;
        end
        if (wr_en_local_r)
            mem[wr_addr_local_r] <= wr_data_local_r;
        if (rd_fire)
            rd_data_uram_r <= mem[rd_addr];
    end

    // Payload slots intentionally have no reset.  Reset/clear invalidate the
    // registered occupancy before any slot can be observed, and every visible
    // slot is written before its count increments.
    always @(posedge clk) begin
        if (capture_fire) begin
            if (rsp_fifo_wr_ptr_r)
                rsp_fifo_slot1_r <= rd_data_uram_r;
            else
                rsp_fifo_slot0_r <= rd_data_uram_r;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rsp_fifo_wr_ptr_r <= 1'b0;
            rsp_fifo_rd_ptr_r <= 1'b0;
            rsp_fifo_count_r <= 2'd0;
            rd_pending_r <= 1'b0;
            outstanding_count_r <= 2'd0;
        end else if (clear) begin
            rsp_fifo_wr_ptr_r <= 1'b0;
            rsp_fifo_rd_ptr_r <= 1'b0;
            rsp_fifo_count_r <= 2'd0;
            rd_pending_r <= 1'b0;
            outstanding_count_r <= 2'd0;
        end else begin
            if (capture_fire)
                rsp_fifo_wr_ptr_r <= rsp_fifo_wr_ptr_r + 1'b1;
            if (rsp_fire)
                rsp_fifo_rd_ptr_r <= rsp_fifo_rd_ptr_r + 1'b1;
            case ({capture_fire,rsp_fire})
                2'b10: rsp_fifo_count_r <= rsp_fifo_count_r + 1'b1;
                2'b01: rsp_fifo_count_r <= rsp_fifo_count_r - 1'b1;
                default: rsp_fifo_count_r <= rsp_fifo_count_r;
            endcase

            // If capture is blocked, retain both rd_pending_r and the stable
            // URAM output.  With all three credits occupied rd_ready is low,
            // so no later read can overwrite that pending response.
            if (capture_fire)
                rd_pending_r <= 1'b0;
            if (rd_fire)
                rd_pending_r <= 1'b1;

            case ({rd_fire,rsp_fire})
                2'b10: outstanding_count_r <= outstanding_count_r + 1'b1;
                2'b01: outstanding_count_r <= outstanding_count_r - 1'b1;
                default: outstanding_count_r <= outstanding_count_r;
            endcase
        end
    end
endmodule

// Two resident MLP metadata images.  Gate/up and down have independent read
// ports because their physical schedules and address widths differ.  The
// inactive bank can be loaded through the two write ports while the active
// bank serves the current layer.  A bank becomes selectable only after both
// exact write counts have been observed and software commits its generation.
module hap_mlp_weight_meta_resident_ab #(
    parameter integer GATE_DEPTH = 229376,
    parameter integer DOWN_DEPTH = 114688,
    parameter integer GATE_ADDR_W = 18,
    parameter integer DOWN_ADDR_W = 17,
    parameter integer PRODUCTION_SHAPE = 1
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       clear,

    input  wire                       load_begin_valid,
    output wire                       load_begin_ready,
    input  wire                       load_begin_bank,

    input  wire                       gate_wr_valid,
    output wire                       gate_wr_ready,
    input  wire                       gate_wr_bank,
    input  wire [GATE_ADDR_W-1:0]     gate_wr_addr,
    input  wire [223:0]               gate_wr_meta_u224,
    input  wire                       down_wr_valid,
    output wire                       down_wr_ready,
    input  wire                       down_wr_bank,
    input  wire [DOWN_ADDR_W-1:0]     down_wr_addr,
    input  wire [223:0]               down_wr_meta_u224,

    input  wire                       commit_valid,
    output wire                       commit_ready,
    input  wire                       commit_bank,
    input  wire [31:0]                commit_generation,
    input  wire                       consumer_quiescent,
    output reg                        active_bank,
    output reg  [31:0]                active_generation,
    output reg  [1:0]                 bank_valid,
    output reg  [1:0]                 bank_loading,

    input  wire                       gate_rd_valid,
    output wire                       gate_rd_ready,
    input  wire [GATE_ADDR_W-1:0]     gate_rd_addr,
    output wire                       gate_rsp_valid,
    input  wire                       gate_rsp_ready,
    output wire [223:0]               gate_rsp_meta_u224,
    input  wire                       down_rd_valid,
    output wire                       down_rd_ready,
    input  wire [DOWN_ADDR_W-1:0]     down_rd_addr,
    output wire                       down_rsp_valid,
    input  wire                       down_rsp_ready,
    output wire [223:0]               down_rsp_meta_u224,

    output reg  [31:0]                gate_write_count_bank0,
    output reg  [31:0]                gate_write_count_bank1,
    output reg  [31:0]                down_write_count_bank0,
    output reg  [31:0]                down_write_count_bank1,
    output reg  [31:0]                gate_read_count,
    output reg  [31:0]                down_read_count,
    output reg                        error
);
    wire [223:0] gate_bank0_rsp_data,gate_bank1_rsp_data;
    wire [223:0] down_bank0_rsp_data,down_bank1_rsp_data;
    wire gate_bank0_rd_ready,gate_bank1_rd_ready;
    wire down_bank0_rd_ready,down_bank1_rd_ready;
    wire gate_bank0_rsp_valid,gate_bank1_rsp_valid;
    wire down_bank0_rsp_valid,down_bank1_rsp_valid;
    wire gate_bank0_idle,gate_bank1_idle,down_bank0_idle,down_bank1_idle;
    wire gate_read_allowed = rst_n && !clear && bank_valid[active_bank] &&
        gate_rd_addr < GATE_DEPTH;
    wire down_read_allowed = rst_n && !clear && bank_valid[active_bank] &&
        down_rd_addr < DOWN_DEPTH;

    wire gate_wr_fire = gate_wr_valid && gate_wr_ready;
    wire down_wr_fire = down_wr_valid && down_wr_ready;
    wire gate_rd_fire = gate_rd_valid && gate_rd_ready;
    wire down_rd_fire = down_rd_valid && down_rd_ready;
    wire gate_rsp_fire = gate_rsp_valid && gate_rsp_ready;
    wire down_rsp_fire = down_rsp_valid && down_rsp_ready;
    wire commit_fire = commit_valid && commit_ready;
    wire load_begin_fire = load_begin_valid && load_begin_ready;

    wire [31:0] selected_gate_write_count = commit_bank ?
        gate_write_count_bank1 : gate_write_count_bank0;
    wire [31:0] selected_down_write_count = commit_bank ?
        down_write_count_bank1 : down_write_count_bank0;
    wire [31:0] gate_target_write_count = gate_wr_bank ?
        gate_write_count_bank1 : gate_write_count_bank0;
    wire [31:0] down_target_write_count = down_wr_bank ?
        down_write_count_bank1 : down_write_count_bank0;

    assign load_begin_ready = rst_n && !clear &&
        load_begin_bank != active_bank && !bank_loading[load_begin_bank];
    assign gate_wr_ready = rst_n && !clear &&
        gate_wr_bank != active_bank && bank_loading[gate_wr_bank] &&
        gate_target_write_count < GATE_DEPTH && gate_wr_addr < GATE_DEPTH &&
        gate_wr_addr == gate_target_write_count[GATE_ADDR_W-1:0];
    assign down_wr_ready = rst_n && !clear &&
        down_wr_bank != active_bank && bank_loading[down_wr_bank] &&
        down_target_write_count < DOWN_DEPTH && down_wr_addr < DOWN_DEPTH &&
        down_wr_addr == down_target_write_count[DOWN_ADDR_W-1:0];
    assign commit_ready = rst_n && !clear &&
        commit_bank != active_bank && bank_loading[commit_bank] &&
        selected_gate_write_count == GATE_DEPTH &&
        selected_down_write_count == DOWN_DEPTH && consumer_quiescent &&
        !gate_rd_valid && !down_rd_valid && gate_bank0_idle &&
        gate_bank1_idle && down_bank0_idle && down_bank1_idle;

    assign gate_rd_ready = gate_read_allowed && (active_bank ?
        gate_bank1_rd_ready : gate_bank0_rd_ready);
    assign down_rd_ready = down_read_allowed && (active_bank ?
        down_bank1_rd_ready : down_bank0_rd_ready);
    // Select only payload that has already crossed the bank-local capture FF.
    assign gate_rsp_valid = rst_n && !clear && (active_bank ?
        gate_bank1_rsp_valid : gate_bank0_rsp_valid);
    assign down_rsp_valid = rst_n && !clear && (active_bank ?
        down_bank1_rsp_valid : down_bank0_rsp_valid);
    assign gate_rsp_meta_u224 = active_bank ? gate_bank1_rsp_data :
        gate_bank0_rsp_data;
    assign down_rsp_meta_u224 = active_bank ? down_bank1_rsp_data :
        down_bank0_rsp_data;

    hap_mlp_weight_meta_uram_leaf #(
        .DEPTH(GATE_DEPTH),.ADDR_W(GATE_ADDR_W),.BANK_ID(0)
    ) u_gate_bank0 (
        .clk(clk),.wr_valid(gate_wr_fire),.wr_bank(gate_wr_bank),
        .wr_addr(gate_wr_addr),.wr_data(gate_wr_meta_u224),
        .rst_n(rst_n),.clear(clear),
        .rd_valid(gate_rd_valid&&gate_read_allowed&&!active_bank),
        .rd_ready(gate_bank0_rd_ready),.rd_addr(gate_rd_addr),
        .rsp_valid(gate_bank0_rsp_valid),
        .rsp_ready(gate_rsp_ready&&!active_bank),
        .rsp_data(gate_bank0_rsp_data),.response_idle(gate_bank0_idle)
    );
    hap_mlp_weight_meta_uram_leaf #(
        .DEPTH(GATE_DEPTH),.ADDR_W(GATE_ADDR_W),.BANK_ID(1)
    ) u_gate_bank1 (
        .clk(clk),.wr_valid(gate_wr_fire),.wr_bank(gate_wr_bank),
        .wr_addr(gate_wr_addr),.wr_data(gate_wr_meta_u224),
        .rst_n(rst_n),.clear(clear),
        .rd_valid(gate_rd_valid&&gate_read_allowed&&active_bank),
        .rd_ready(gate_bank1_rd_ready),.rd_addr(gate_rd_addr),
        .rsp_valid(gate_bank1_rsp_valid),
        .rsp_ready(gate_rsp_ready&&active_bank),
        .rsp_data(gate_bank1_rsp_data),.response_idle(gate_bank1_idle)
    );
    hap_mlp_weight_meta_uram_leaf #(
        .DEPTH(DOWN_DEPTH),.ADDR_W(DOWN_ADDR_W),.BANK_ID(0)
    ) u_down_bank0 (
        .clk(clk),.wr_valid(down_wr_fire),.wr_bank(down_wr_bank),
        .wr_addr(down_wr_addr),.wr_data(down_wr_meta_u224),
        .rst_n(rst_n),.clear(clear),
        .rd_valid(down_rd_valid&&down_read_allowed&&!active_bank),
        .rd_ready(down_bank0_rd_ready),.rd_addr(down_rd_addr),
        .rsp_valid(down_bank0_rsp_valid),
        .rsp_ready(down_rsp_ready&&!active_bank),
        .rsp_data(down_bank0_rsp_data),.response_idle(down_bank0_idle)
    );
    hap_mlp_weight_meta_uram_leaf #(
        .DEPTH(DOWN_DEPTH),.ADDR_W(DOWN_ADDR_W),.BANK_ID(1)
    ) u_down_bank1 (
        .clk(clk),.wr_valid(down_wr_fire),.wr_bank(down_wr_bank),
        .wr_addr(down_wr_addr),.wr_data(down_wr_meta_u224),
        .rst_n(rst_n),.clear(clear),
        .rd_valid(down_rd_valid&&down_read_allowed&&active_bank),
        .rd_ready(down_bank1_rd_ready),.rd_addr(down_rd_addr),
        .rsp_valid(down_bank1_rsp_valid),
        .rsp_ready(down_rsp_ready&&active_bank),
        .rsp_data(down_bank1_rsp_data),.response_idle(down_bank1_idle)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_bank <= 1'b0;
            active_generation <= 32'd0;
            bank_valid <= 2'b00;
            bank_loading <= 2'b00;
            gate_write_count_bank0 <= 32'd0;
            gate_write_count_bank1 <= 32'd0;
            down_write_count_bank0 <= 32'd0;
            down_write_count_bank1 <= 32'd0;
            gate_read_count <= 32'd0;
            down_read_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            // Contents remain resident, but their validity is intentionally
            // revoked so software cannot reuse an image after a hard clear.
            active_bank <= 1'b0;
            active_generation <= 32'd0;
            bank_valid <= 2'b00;
            bank_loading <= 2'b00;
            gate_write_count_bank0 <= 32'd0;
            gate_write_count_bank1 <= 32'd0;
            down_write_count_bank0 <= 32'd0;
            down_write_count_bank1 <= 32'd0;
            gate_read_count <= 32'd0;
            down_read_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (load_begin_fire) begin
                bank_valid[load_begin_bank] <= 1'b0;
                bank_loading[load_begin_bank] <= 1'b1;
                if (load_begin_bank) begin
                    gate_write_count_bank1 <= 32'd0;
                    down_write_count_bank1 <= 32'd0;
                end else begin
                    gate_write_count_bank0 <= 32'd0;
                    down_write_count_bank0 <= 32'd0;
                end
            end

            if (gate_wr_fire) begin
                if (gate_wr_bank) begin
                    gate_write_count_bank1 <= gate_write_count_bank1 + 1'b1;
                    bank_valid[1] <= 1'b0;
                end else begin
                    gate_write_count_bank0 <= gate_write_count_bank0 + 1'b1;
                    bank_valid[0] <= 1'b0;
                end
            end
            if (down_wr_fire) begin
                if (down_wr_bank) begin
                    down_write_count_bank1 <= down_write_count_bank1 + 1'b1;
                    bank_valid[1] <= 1'b0;
                end else begin
                    down_write_count_bank0 <= down_write_count_bank0 + 1'b1;
                    bank_valid[0] <= 1'b0;
                end
            end
            if (gate_rsp_fire)
                gate_read_count <= gate_read_count + 1'b1;
            if (down_rsp_fire)
                down_read_count <= down_read_count + 1'b1;

            if (commit_fire) begin
                active_bank <= commit_bank;
                active_generation <= commit_generation;
                bank_valid[commit_bank] <= 1'b1;
                bank_loading[commit_bank] <= 1'b0;
            end

            if ((gate_wr_valid && gate_wr_bank == active_bank) ||
                (down_wr_valid && down_wr_bank == active_bank) ||
                (gate_wr_valid && gate_wr_addr >= GATE_DEPTH) ||
                (down_wr_valid && down_wr_addr >= DOWN_DEPTH) ||
                (gate_wr_valid && bank_loading[gate_wr_bank] &&
                    gate_wr_addr != gate_target_write_count[GATE_ADDR_W-1:0]) ||
                (down_wr_valid && bank_loading[down_wr_bank] &&
                    down_wr_addr != down_target_write_count[DOWN_ADDR_W-1:0]) ||
                (gate_rd_valid && gate_rd_addr >= GATE_DEPTH) ||
                (down_rd_valid && down_rd_addr >= DOWN_DEPTH) ||
                (load_begin_valid && load_begin_bank == active_bank))
                error <= 1'b1;
        end
    end

    initial begin
        if (PRODUCTION_SHAPE && (GATE_DEPTH != 229376 || DOWN_DEPTH != 114688 ||
            GATE_ADDR_W != 18 || DOWN_ADDR_W != 17))
            $error("hap_mlp_weight_meta_resident_ab production shape required");
    end
endmodule
