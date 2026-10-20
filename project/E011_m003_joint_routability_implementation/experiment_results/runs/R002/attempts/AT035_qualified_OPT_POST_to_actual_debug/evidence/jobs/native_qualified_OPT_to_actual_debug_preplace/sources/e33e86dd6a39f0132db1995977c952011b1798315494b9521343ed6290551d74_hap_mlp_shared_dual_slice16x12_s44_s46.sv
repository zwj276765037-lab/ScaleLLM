`timescale 1ns / 1ps

// V5 production candidate: exactly two physical 8x12 A8W4 kernels are shared
// between the gate/up and down command phases.  Every physical branch owns
// its kernel, gate S44 accumulator and down group-major S46 accumulator.  The
// wide S37 guard therefore never leaves the branch hierarchy; only completed
// S24 projections are joined at this parent boundary.
module hap_mlp_shared_dual_slice16x12_s44_s46 #(
    parameter integer DOWN_TILES = 342,
    parameter integer DOWN_GROUPS = 448,
    parameter integer TILE_W =
        (DOWN_TILES <= 2) ? 1 : $clog2(DOWN_TILES)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_down,
    input  wire                          in_first,
    input  wire                          in_last,
    input  wire [TILE_W-1:0]             in_tile,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [12*32*4-1:0]     weights_s4x12x32,
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [12*8-1:0]               weight_code_u8x12,
    input  wire [12*6-1:0]               weight_shift_u6x12,
    input  wire [11:0]                    column_valid_u12,

    output wire                          gate_valid,
    input  wire                          gate_ready,
    output wire signed [16*12*24-1:0]    gate_s24x16x12,
    output wire                          down_valid,
    input  wire                          down_ready,
    output wire [TILE_W-1:0]             down_tile,
    output wire signed [16*12*24-1:0]    down_s24x16x12,
    output wire [31:0]                   gate_saturation,
    output wire [31:0]                   down_saturation,
    output wire                          guard_overflow,
    output wire                          accumulator_overflow,
    output reg  [31:0]                   input_transaction_count,
    output reg  [31:0]                   gate_output_pass_count,
    output reg  [31:0]                   down_output_pass_count,
    output reg                           error
);

    wire ready0;
    wire ready1;
    wire gate_valid0;
    wire gate_valid1;
    wire down_valid0;
    wire down_valid1;
    wire gate_ready0 = gate_ready && gate_valid1;
    wire gate_ready1 = gate_ready && gate_valid0;
    wire down_ready0;
    wire down_ready1;
    wire [TILE_W-1:0] down_tile0;
    wire [TILE_W-1:0] down_tile1;
    wire signed [8*12*24-1:0] gate_s24_0;
    wire signed [8*12*24-1:0] gate_s24_1;
    wire signed [8*12*24-1:0] down_s24_0;
    wire signed [8*12*24-1:0] down_s24_1;
    wire [31:0] gate_saturation0;
    wire [31:0] gate_saturation1;
    wire [31:0] down_saturation0;
    wire [31:0] down_saturation1;
    wire error0;
    wire error1;
    wire guard_overflow0;
    wire guard_overflow1;
    wire accumulator_overflow0;
    wire accumulator_overflow1;
    wire in_fire = in_valid && in_ready;

    // The branch-local ingress queues live in the two outer SLR partitions.
    // Their credit must not feed the central gather scheduler combinationally:
    // that path was the P7 core setup limiter.  This non-bypass two-entry FIFO
    // makes the parent boundary elastic while keeping its upstream credit a
    // function of central registered occupancy only.  A full FIFO deliberately
    // waits one cycle after a branch dequeue before reasserting in_ready.
    localparam integer PARENT_DOWN_LO = 0;
    localparam integer PARENT_FIRST_LO = PARENT_DOWN_LO + 1;
    localparam integer PARENT_LAST_LO = PARENT_FIRST_LO + 1;
    localparam integer PARENT_TILE_LO = PARENT_LAST_LO + 1;
    localparam integer PARENT_ACTIVATION_LO = PARENT_TILE_LO + TILE_W;
    localparam integer PARENT_WEIGHT_LO = PARENT_ACTIVATION_LO + 16*32*9;
    localparam integer PARENT_ACODE_LO = PARENT_WEIGHT_LO + 12*32*4;
    localparam integer PARENT_ASHIFT_LO = PARENT_ACODE_LO + 16*8;
    localparam integer PARENT_WCODE_LO = PARENT_ASHIFT_LO + 16*6;
    localparam integer PARENT_WSHIFT_LO = PARENT_WCODE_LO + 12*8;
    localparam integer PARENT_MASK_LO = PARENT_WSHIFT_LO + 12*6;
    localparam integer PARENT_PAYLOAD_W = PARENT_MASK_LO + 12;

    wire [PARENT_PAYLOAD_W-1:0] parent_input_payload = {
        column_valid_u12, weight_shift_u6x12, weight_code_u8x12,
        activation_shift_u6x16, activation_code_u8x16,
        weights_s4x12x32, activation_s9x16x32, in_tile,
        in_last, in_first, in_down
    };
    // A fixed head removes a payload-wide read-pointer mux from both SLR
    // crossings.  Tail moves into head only when a full FIFO drains.
    (* ram_style = "registers", SHREG_EXTRACT = "NO" *)
    reg [PARENT_PAYLOAD_W-1:0] parent_head_r;
    (* ram_style = "registers", SHREG_EXTRACT = "NO" *)
    reg [PARENT_PAYLOAD_W-1:0] parent_tail_r;
    reg [1:0] parent_count_r;

    wire parent_full = parent_count_r == 2;
    wire parent_empty = parent_count_r == 0;
    wire parent_valid = rst_n && !clear && !parent_empty;
    wire parent_pop = parent_valid && ready0 && ready1;

    // A transaction is presented to either local ingress only when the other
    // branch also has credit.  Both local copies are consequently accepted on
    // the same edge without a central S37 or kernel-result fork.  Branch credit
    // controls only this FIFO's dequeue and cannot affect upstream in_ready.
    assign in_ready = rst_n && !clear && !parent_full;
    assign gate_valid = rst_n && !clear && gate_valid0 && gate_valid1;
    // Each branch owns a two-entry down elastic queue below.  The central
    // consumer therefore sees only queue heads; its ready no longer reaches
    // either S46 accumulator through this atomic 16-row join.
    assign down_valid = rst_n && !clear && down_valid0 && down_valid1;
    assign down_ready0 = down_ready && down_valid1;
    assign down_ready1 = down_ready && down_valid0;
    assign gate_s24x16x12 = {gate_s24_1, gate_s24_0};
    assign down_s24x16x12 = {down_s24_1, down_s24_0};
    assign down_tile = down_tile0;
    assign gate_saturation = gate_saturation0 + gate_saturation1;
    assign down_saturation = down_saturation0 + down_saturation1;
    assign guard_overflow = guard_overflow0 || guard_overflow1;
    assign accumulator_overflow =
        accumulator_overflow0 || accumulator_overflow1;

    (* keep_hierarchy = "yes" *)
    hap_mlp_shared_local_slice8x12_s44_s46 #(
        .DOWN_TILES(DOWN_TILES), .DOWN_GROUPS(DOWN_GROUPS),
        .TILE_W(TILE_W)
    ) u_branch0 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(parent_valid && ready1), .in_ready(ready0),
        .in_down(parent_head_r[PARENT_DOWN_LO]),
        .in_first(parent_head_r[PARENT_FIRST_LO]),
        .in_last(parent_head_r[PARENT_LAST_LO]),
        .in_tile(parent_head_r[PARENT_TILE_LO +: TILE_W]),
        .activation_s9x8x32(parent_head_r[
            PARENT_ACTIVATION_LO +: 8*32*9]),
        .weights_s4x12x32(parent_head_r[
            PARENT_WEIGHT_LO +: 12*32*4]),
        .activation_code_u8x8(parent_head_r[
            PARENT_ACODE_LO +: 8*8]),
        .activation_shift_u6x8(parent_head_r[
            PARENT_ASHIFT_LO +: 8*6]),
        .weight_code_u8x12(parent_head_r[
            PARENT_WCODE_LO +: 12*8]),
        .weight_shift_u6x12(parent_head_r[
            PARENT_WSHIFT_LO +: 12*6]),
        .column_valid_u12(parent_head_r[PARENT_MASK_LO +: 12]),
        .gate_valid(gate_valid0), .gate_ready(gate_ready0),
        .gate_s24x8x12(gate_s24_0),
        .down_valid(down_valid0), .down_ready(down_ready0),
        .down_tile(down_tile0), .down_s24x8x12(down_s24_0),
        .gate_saturation(gate_saturation0),
        .down_saturation(down_saturation0),
        .guard_overflow(guard_overflow0),
        .accumulator_overflow(accumulator_overflow0), .error(error0)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_shared_local_slice8x12_s44_s46 #(
        .DOWN_TILES(DOWN_TILES), .DOWN_GROUPS(DOWN_GROUPS),
        .TILE_W(TILE_W)
    ) u_branch1 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(parent_valid && ready0), .in_ready(ready1),
        .in_down(parent_head_r[PARENT_DOWN_LO]),
        .in_first(parent_head_r[PARENT_FIRST_LO]),
        .in_last(parent_head_r[PARENT_LAST_LO]),
        .in_tile(parent_head_r[PARENT_TILE_LO +: TILE_W]),
        .activation_s9x8x32(parent_head_r[
            PARENT_ACTIVATION_LO + 8*32*9 +: 8*32*9]),
        .weights_s4x12x32(parent_head_r[
            PARENT_WEIGHT_LO +: 12*32*4]),
        .activation_code_u8x8(parent_head_r[
            PARENT_ACODE_LO + 8*8 +: 8*8]),
        .activation_shift_u6x8(parent_head_r[
            PARENT_ASHIFT_LO + 8*6 +: 8*6]),
        .weight_code_u8x12(parent_head_r[
            PARENT_WCODE_LO +: 12*8]),
        .weight_shift_u6x12(parent_head_r[
            PARENT_WSHIFT_LO +: 12*6]),
        .column_valid_u12(parent_head_r[PARENT_MASK_LO +: 12]),
        .gate_valid(gate_valid1), .gate_ready(gate_ready1),
        .gate_s24x8x12(gate_s24_1),
        .down_valid(down_valid1), .down_ready(down_ready1),
        .down_tile(down_tile1), .down_s24x8x12(down_s24_1),
        .gate_saturation(gate_saturation1),
        .down_saturation(down_saturation1),
        .guard_overflow(guard_overflow1),
        .accumulator_overflow(accumulator_overflow1), .error(error1)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            parent_count_r <= 2'd0;
        end else begin
            case ({in_fire, parent_pop})
                2'b10: begin
                    if (parent_empty)
                        parent_head_r <= parent_input_payload;
                    else
                        parent_tail_r <= parent_input_payload;
                    parent_count_r <= parent_count_r + 1'b1;
                end
                2'b01: begin
                    if (parent_full)
                        parent_head_r <= parent_tail_r;
                    parent_count_r <= parent_count_r - 1'b1;
                end
                // A simultaneous push/pop can occur only at occupancy one:
                // replace the consumed head directly and remain nonempty.
                2'b11: begin
                    parent_head_r <= parent_input_payload;
                    parent_count_r <= parent_count_r;
                end
                default: parent_count_r <= parent_count_r;
            endcase
        end
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            input_transaction_count <= 32'd0;
            gate_output_pass_count <= 32'd0;
            down_output_pass_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire)
                input_transaction_count <= input_transaction_count + 1'b1;
            if (gate_valid && gate_ready)
                gate_output_pass_count <= gate_output_pass_count + 1'b1;
            if (down_valid && down_ready)
                down_output_pass_count <= down_output_pass_count + 1'b1;
            if (error0 || error1 || (down_valid0 != down_valid1) ||
                (down_valid0 && down_valid1 && down_tile0 != down_tile1))
                error <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear && parent_count_r > 2)
            $error("V5 shared parent ingress overflow");
        if (rst_n && !clear && parent_pop && (!ready0 || !ready1))
            $error("V5 shared parent ingress lost atomic branch delivery");
    end
`endif

endmodule


// One physical branch.  The two-entry ingress is the registered SLR boundary;
// the 3552-bit S37 guard connects only the local kernel to the two local
// accumulators.  A tag FIFO follows the elastic kernel pipeline exactly.
module hap_mlp_shared_local_slice8x12_s44_s46 #(
    parameter integer DOWN_TILES = 342,
    parameter integer DOWN_GROUPS = 448,
    parameter integer TILE_W =
        (DOWN_TILES <= 2) ? 1 : $clog2(DOWN_TILES),
    parameter integer INGRESS_DEPTH = 2
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_down,
    input  wire                         in_first,
    input  wire                         in_last,
    input  wire [TILE_W-1:0]            in_tile,
    input  wire signed [8*32*9-1:0]     activation_s9x8x32,
    input  wire signed [12*32*4-1:0]    weights_s4x12x32,
    input  wire [8*8-1:0]               activation_code_u8x8,
    input  wire [8*6-1:0]               activation_shift_u6x8,
    input  wire [12*8-1:0]              weight_code_u8x12,
    input  wire [12*6-1:0]              weight_shift_u6x12,
    input  wire [11:0]                   column_valid_u12,
    output wire                         gate_valid,
    input  wire                         gate_ready,
    output wire signed [8*12*24-1:0]    gate_s24x8x12,
    output wire                         down_valid,
    input  wire                         down_ready,
    output wire [TILE_W-1:0]            down_tile,
    output wire signed [8*12*24-1:0]    down_s24x8x12,
    output wire [31:0]                  gate_saturation,
    output wire [31:0]                  down_saturation,
    output wire                         guard_overflow,
    output wire                         accumulator_overflow,
    output wire                         error
);

    localparam integer LANES = 8*12;

    // This register is the physical SLR-local maintenance-clear boundary.
    // Preserve it so synthesis cannot merge the two branch copies back into
    // the central maintenance pulse and recreate a cross-SLR control net.
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg clear_local_r;
    reg ingress_down [0:INGRESS_DEPTH-1];
    reg ingress_first [0:INGRESS_DEPTH-1];
    reg ingress_last [0:INGRESS_DEPTH-1];
    reg [TILE_W-1:0] ingress_tile [0:INGRESS_DEPTH-1];
    reg signed [8*32*9-1:0] ingress_activation [0:INGRESS_DEPTH-1];
    reg signed [12*32*4-1:0] ingress_weights [0:INGRESS_DEPTH-1];
    // Preserve the existing two-entry elastic metadata boundary.  Without
    // this constraint synthesis propagated the down scheduler's activation
    // code through both local branches into 4,832 loads and inserted a data
    // BUFG.  These are functional FIFO registers, not added data replicas.
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [8*8-1:0] ingress_activation_code [0:INGRESS_DEPTH-1];
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [8*6-1:0] ingress_activation_shift [0:INGRESS_DEPTH-1];
    reg [12*8-1:0] ingress_weight_code [0:INGRESS_DEPTH-1];
    reg [12*6-1:0] ingress_weight_shift [0:INGRESS_DEPTH-1];
    reg [11:0] ingress_mask [0:INGRESS_DEPTH-1];
    reg ingress_wr_ptr_r;
    reg ingress_rd_ptr_r;
    reg [1:0] ingress_count_r;

    reg tag_mode [0:31];
    reg tag_first [0:31];
    reg tag_last [0:31];
    reg [TILE_W-1:0] tag_tile [0:31];
    reg [4:0] tag_wr_ptr_r;
    reg [4:0] tag_rd_ptr_r;
    reg [5:0] tag_count_r;

    wire ingress_full = ingress_count_r == INGRESS_DEPTH;
    wire ingress_empty = ingress_count_r == 0;
    wire tag_full = tag_count_r == 32;
    wire tag_empty = tag_count_r == 0;
    wire kernel_ready;
    wire kernel_valid;
    wire signed [LANES*37-1:0] guard_s37;
    wire gate_accum_ready;
    wire down_accum_ready;
    wire selected_accum_ready = tag_mode[tag_rd_ptr_r] ?
        down_accum_ready : gate_accum_ready;
    wire dispatch_valid = !ingress_empty && !tag_full;
    wire input_fire = in_valid && in_ready;
    wire dispatch_fire = dispatch_valid && kernel_ready;
    wire kernel_fire = kernel_valid && !tag_empty && selected_accum_ready;
    wire kernel_error;
    wire gate_error;
    wire down_error;
    wire kernel_guard_overflow;
    wire gate_accumulator_overflow;
    wire down_accumulator_overflow;

    // Completed gate projections cross the branch boundary through a real
    // row-banked elastic slot.  The accumulator's ready depends only on local
    // credit, so central projection/SwiGLU backpressure no longer propagates
    // combinationally into the kernel ready tree.
    wire gate_accum_valid;
    wire gate_accum_output_ready;
    wire signed [8*12*24-1:0] gate_accum_s24;
    wire gate_accum_fire;
    reg gate_slot_valid_r;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [7:0] gate_slot_capture_pending_bank_r;
    reg signed [12*24-1:0] gate_slot_row_r [0:7];
    wire gate_slot_pop = gate_slot_valid_r && gate_ready;

    // The S46 accumulator already owns one output holding register, but a
    // single additional slot would either bubble every other cycle or feed
    // the central down_ready combinationally back into process_ready.  A real
    // two-entry branch-local queue below absorbs consecutive final-group
    // tiles at II=1.  Its input credit is registered occupancy only: neither
    // the sibling branch nor the central inverse-repacker ready reaches the
    // accumulator or kernel ready tree in the same cycle.
    wire down_accum_valid;
    wire down_accum_output_ready;
    wire [TILE_W-1:0] down_accum_tile;
    wire signed [8*12*24-1:0] down_accum_s24;

    assign gate_accum_output_ready = !gate_slot_valid_r &&
        !(|gate_slot_capture_pending_bank_r);
    assign gate_accum_fire = gate_accum_valid && gate_accum_output_ready;
    assign gate_valid = rst_n && !clear_local_r && gate_slot_valid_r;

    genvar gate_slot_row;
    generate
        for (gate_slot_row = 0; gate_slot_row < 8;
             gate_slot_row = gate_slot_row + 1) begin : gen_gate_slot_row
            assign gate_s24x8x12[
                gate_slot_row*12*24 +: 12*24] =
                gate_slot_row_r[gate_slot_row];
        end
    endgenerate

    assign in_ready = rst_n && !clear_local_r && !ingress_full;

    (* keep_hierarchy = "yes" *)
    hap_a8w4_slice8x12_group_s37 u_kernel (
        .clk(clk), .rst_n(rst_n), .clear_by_row({8{clear_local_r}}),
        .in_valid(dispatch_valid), .in_ready(kernel_ready),
        .activation_s9x8x32(ingress_activation[ingress_rd_ptr_r]),
        .weights_s4x12x32(ingress_weights[ingress_rd_ptr_r]),
        .activation_code_u8x8(
            ingress_activation_code[ingress_rd_ptr_r]),
        .activation_shift_u6x8(
            ingress_activation_shift[ingress_rd_ptr_r]),
        .weight_code_u8x12(ingress_weight_code[ingress_rd_ptr_r]),
        .weight_shift_u6x12(ingress_weight_shift[ingress_rd_ptr_r]),
        .column_valid_u12(ingress_mask[ingress_rd_ptr_r]),
        .out_valid(kernel_valid),
        .out_ready(!tag_empty && selected_accum_ready),
        .guard_s37x8x12(guard_s37),
        .guard_overflow(kernel_guard_overflow), .input_group_count(),
        .output_group_count(), .error(kernel_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_tile_accum_s37 #(
        .LANES(LANES), .ACC_W(44), .GROUPS(128),
        .ALLOW_V5_96_LANES(1)
    ) u_gate_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear_local_r),
        .in_valid(kernel_valid && !tag_empty &&
            !tag_mode[tag_rd_ptr_r]),
        .in_ready(gate_accum_ready),
        .in_first_group(tag_first[tag_rd_ptr_r]),
        .in_last_group(tag_last[tag_rd_ptr_r]),
        .in_guard_s37(guard_s37),
        .out_valid(gate_accum_valid), .out_ready(gate_accum_output_ready),
        .out_projection_s24(gate_accum_s24), .input_group_count(),
        .output_tile_count(), .saturation_count(gate_saturation),
        .accumulator_overflow(gate_accumulator_overflow),
        .error(gate_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_down_group_major_accum_s46 #(
        .LANES(LANES), .TILES(DOWN_TILES), .GROUPS(DOWN_GROUPS),
        .TILE_W(TILE_W)
    ) u_down_accum (
        .clk(clk), .rst_n(rst_n), .clear(clear_local_r),
        .in_valid(kernel_valid && !tag_empty && tag_mode[tag_rd_ptr_r]),
        .in_ready(down_accum_ready),
        .in_first_group(tag_first[tag_rd_ptr_r]),
        .in_last_group(tag_last[tag_rd_ptr_r]),
        .in_tile_index(tag_tile[tag_rd_ptr_r]),
        .in_guard_s37(guard_s37),
        .out_valid(down_accum_valid),
        .out_ready(down_accum_output_ready),
        .out_tile_index(down_accum_tile),
        .out_projection_s24(down_accum_s24), .input_tile_count(),
        .input_group_count(), .output_tile_count(),
        .saturation_count(down_saturation),
        .accumulator_overflow(down_accumulator_overflow),
        .error(down_error)
    );

    (* keep_hierarchy = "yes" *)
    hap_mlp_down_branch_elastic2_s24_v6 #(
        .ROWS(8), .COLS(12), .TILE_W(TILE_W)
    ) u_down_output_queue (
        .clk(clk), .rst_n(rst_n), .clear(clear_local_r),
        .in_valid(down_accum_valid),
        .in_ready(down_accum_output_ready),
        .in_tile(down_accum_tile), .in_projection_s24(down_accum_s24),
        .out_valid(down_valid), .out_ready(down_ready),
        .out_tile(down_tile), .out_projection_s24(down_s24x8x12)
    );

    assign guard_overflow = kernel_guard_overflow;
    assign accumulator_overflow =
        gate_accumulator_overflow || down_accumulator_overflow;
    assign error = kernel_error || gate_error || down_error ||
        guard_overflow || accumulator_overflow;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            clear_local_r <= 1'b1;
        else
            clear_local_r <= clear;
    end

    integer gate_row;
    always @(posedge clk) begin
        if (!rst_n || clear_local_r) begin
            gate_slot_valid_r <= 1'b0;
            gate_slot_capture_pending_bank_r <= 8'd0;
        end else begin
            gate_slot_capture_pending_bank_r <= {8{gate_accum_fire}};
            if (gate_slot_pop)
                gate_slot_valid_r <= 1'b0;
            if (gate_slot_capture_pending_bank_r[0])
                gate_slot_valid_r <= 1'b1;
            for (gate_row = 0; gate_row < 8; gate_row = gate_row + 1)
                if (gate_slot_capture_pending_bank_r[gate_row])
                    gate_slot_row_r[gate_row] <= gate_accum_s24[
                        gate_row*12*24 +: 12*24];
        end
    end

    always @(posedge clk) begin
        if (!rst_n || clear_local_r) begin
            ingress_wr_ptr_r <= 1'b0;
            ingress_rd_ptr_r <= 1'b0;
            ingress_count_r <= 2'd0;
            tag_wr_ptr_r <= 5'd0;
            tag_rd_ptr_r <= 5'd0;
            tag_count_r <= 6'd0;
        end else begin
            if (input_fire) begin
                ingress_down[ingress_wr_ptr_r] <= in_down;
                ingress_first[ingress_wr_ptr_r] <= in_first;
                ingress_last[ingress_wr_ptr_r] <= in_last;
                ingress_tile[ingress_wr_ptr_r] <= in_tile;
                ingress_activation[ingress_wr_ptr_r] <=
                    activation_s9x8x32;
                ingress_weights[ingress_wr_ptr_r] <= weights_s4x12x32;
                ingress_activation_code[ingress_wr_ptr_r] <=
                    activation_code_u8x8;
                ingress_activation_shift[ingress_wr_ptr_r] <=
                    activation_shift_u6x8;
                ingress_weight_code[ingress_wr_ptr_r] <=
                    weight_code_u8x12;
                ingress_weight_shift[ingress_wr_ptr_r] <=
                    weight_shift_u6x12;
                ingress_mask[ingress_wr_ptr_r] <= column_valid_u12;
                ingress_wr_ptr_r <= ingress_wr_ptr_r + 1'b1;
            end

            if (dispatch_fire) begin
                tag_mode[tag_wr_ptr_r] <= ingress_down[ingress_rd_ptr_r];
                tag_first[tag_wr_ptr_r] <= ingress_first[ingress_rd_ptr_r];
                tag_last[tag_wr_ptr_r] <= ingress_last[ingress_rd_ptr_r];
                tag_tile[tag_wr_ptr_r] <= ingress_tile[ingress_rd_ptr_r];
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
                ingress_rd_ptr_r <= ingress_rd_ptr_r + 1'b1;
            end

            if (kernel_fire)
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;

            case ({input_fire, dispatch_fire})
                2'b10: ingress_count_r <= ingress_count_r + 1'b1;
                2'b01: ingress_count_r <= ingress_count_r - 1'b1;
                default: ingress_count_r <= ingress_count_r;
            endcase
            case ({dispatch_fire, kernel_fire})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
        end
    end

`ifndef SYNTHESIS
    always @(posedge clk) begin
        if (rst_n && !clear_local_r && kernel_valid && tag_empty)
            $error("V5 shared 8x12 kernel produced guard without tag");
        if (rst_n && !clear_local_r && ingress_count_r > INGRESS_DEPTH)
            $error("V5 shared 8x12 ingress overflow");
        if (rst_n && !clear_local_r &&
            gate_slot_capture_pending_bank_r !=
            {8{gate_slot_capture_pending_bank_r[0]}})
            $error("V5 shared gate slot capture banks diverged");
    end
`endif

    initial begin
        if (INGRESS_DEPTH != 2)
            $error("V5 shared 8x12 local ingress depth must be two");
        if (DOWN_TILES <= 0 || DOWN_GROUPS <= 0)
            $error("V5 shared 8x12 down shape must be positive");
    end

endmodule


// Two-entry completed-projection queue for one physical 8-row branch.
//
// The payload is split into one 2x(COLS*24) register bank per row.  Every row
// owns its write/read pointer and occupancy controls, so no single capture CE
// drives the full projection.  All control banks start together and execute
// the same push/pop sequence; simulation assertions make that invariant
// explicit.  Importantly, in_ready is a function of registered local
// occupancy only.  A full queue intentionally releases credit one cycle after
// a downstream pop instead of creating a down_ready -> accumulator path.
module hap_mlp_down_branch_elastic2_s24_v6 #(
    parameter integer ROWS = 8,
    parameter integer COLS = 12,
    parameter integer TILE_W = 9,
    parameter integer ROW_W = COLS*24
) (
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              clear,
    input  wire                              in_valid,
    output wire                              in_ready,
    input  wire [TILE_W-1:0]                 in_tile,
    input  wire signed [ROWS*COLS*24-1:0]    in_projection_s24,
    output wire                              out_valid,
    input  wire                              out_ready,
    output wire [TILE_W-1:0]                 out_tile,
    output wire signed [ROWS*COLS*24-1:0]    out_projection_s24
);

    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [1:0] occupancy_bank_r [0:ROWS-1];
    (* ram_style = "registers", SHREG_EXTRACT = "NO" *)
    reg signed [ROW_W-1:0] head_row_r [0:ROWS-1];
    (* ram_style = "registers", SHREG_EXTRACT = "NO" *)
    reg signed [ROW_W-1:0] tail_row_r [0:ROWS-1];
    reg [TILE_W-1:0] head_tile_r;
    reg [TILE_W-1:0] tail_tile_r;

    wire [ROWS-1:0] credit_bank;
    wire [ROWS-1:0] valid_bank;
    wire [ROWS-1:0] push_bank;
    // Keep one sink-ready predicate per row.  A central output_fire select
    // across every head payload bit recreated a 2304-bit CE/mux fanout even
    // though the queue had already isolated the accumulator.  These eight
    // equivalent-in-lockstep predicates limit each payload select to ROW_W
    // bits; the assertion below proves their atomic equivalence in simulation.
    (* KEEP = "yes" *) wire [ROWS-1:0] pop_bank;
    wire output_fire = out_valid && out_ready;
    wire input_fire = in_valid && in_ready;

    assign in_ready = rst_n && !clear && (&credit_bank);
    assign out_valid = rst_n && !clear && (&valid_bank);
    assign out_tile = head_tile_r;

    genvar row;
    generate
        for (row = 0; row < ROWS; row = row + 1) begin : gen_row_queue
            // This local predicate is intentionally not the shared input_fire
            // net.  With lockstep occupancy it is cycle-equivalent, while its
            // fanout is confined to one ROW_W payload bank.
            assign credit_bank[row] = occupancy_bank_r[row] != 2;
            assign valid_bank[row] = occupancy_bank_r[row] != 0;
            assign push_bank[row] = rst_n && !clear && in_valid &&
                credit_bank[row];
            assign pop_bank[row] = out_ready && valid_bank[row];
            assign out_projection_s24[row*ROW_W +: ROW_W] =
                head_row_r[row];

            always @(posedge clk) begin
                if (!rst_n || clear) begin
                    occupancy_bank_r[row] <= 2'd0;
                end else begin
                    case ({push_bank[row], pop_bank[row]})
                        2'b10: begin
                            if (occupancy_bank_r[row] == 0)
                                head_row_r[row] <= in_projection_s24[
                                    row*ROW_W +: ROW_W];
                            else
                                tail_row_r[row] <= in_projection_s24[
                                    row*ROW_W +: ROW_W];
                            occupancy_bank_r[row] <=
                                occupancy_bank_r[row] + 1'b1;
                        end
                        2'b01: begin
                            if (occupancy_bank_r[row] == 2)
                                head_row_r[row] <= tail_row_r[row];
                            occupancy_bank_r[row] <=
                                occupancy_bank_r[row] - 1'b1;
                        end
                        // With registered-credit isolation push+pop can only
                        // occur at occupancy one.  Replace the consumed head
                        // directly and remain nonempty for the next cycle.
                        2'b11: begin
                            head_row_r[row] <= in_projection_s24[
                                row*ROW_W +: ROW_W];
                            occupancy_bank_r[row] <=
                                occupancy_bank_r[row];
                        end
                        default: begin
                            occupancy_bank_r[row] <=
                                occupancy_bank_r[row];
                        end
                    endcase
                end
            end
        end
    endgenerate

    always @(posedge clk) begin
        if (rst_n && !clear) begin
            case ({input_fire, output_fire})
                2'b10: begin
                    if (occupancy_bank_r[0] == 0)
                        head_tile_r <= in_tile;
                    else
                        tail_tile_r <= in_tile;
                end
                2'b01: begin
                    if (occupancy_bank_r[0] == 2)
                        head_tile_r <= tail_tile_r;
                end
                2'b11: head_tile_r <= in_tile;
                default: begin
                    head_tile_r <= head_tile_r;
                    tail_tile_r <= tail_tile_r;
                end
            endcase
        end
    end

`ifndef SYNTHESIS
    integer check_row;
    always @(posedge clk) begin
        if (rst_n && !clear) begin
            if (push_bank != {ROWS{input_fire}})
                $error("V5 down queue row push banks diverged");
            if (pop_bank != {ROWS{output_fire}})
                $error("V5 down queue row pop banks diverged");
            for (check_row = 1; check_row < ROWS;
                 check_row = check_row + 1) begin
                if (occupancy_bank_r[check_row] != occupancy_bank_r[0])
                    $error("V5 down queue row controls diverged");
            end
            if (occupancy_bank_r[0] > 2)
                $error("V5 down queue occupancy overflow");
            if (output_fire && !(&valid_bank))
                $error("V5 down queue atomic pop without all rows valid");
        end
    end
`endif

    initial begin
        if (ROWS <= 0 || COLS <= 0 || TILE_W <= 0 || ROW_W != COLS*24)
            $error("V5 down queue shape must be positive row-major S24");
    end

endmodule
