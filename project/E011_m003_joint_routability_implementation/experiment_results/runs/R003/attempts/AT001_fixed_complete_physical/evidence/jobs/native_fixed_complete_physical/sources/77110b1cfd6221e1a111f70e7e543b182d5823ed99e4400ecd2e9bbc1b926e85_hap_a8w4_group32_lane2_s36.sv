`timescale 1ns / 1ps

(* KEEP_HIERARCHY = "yes" *)
module hap_a8w4_ingress_capture_leaf (
    input  wire in_event,
    output wire out_event
);
`ifdef SYNTHESIS
    (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
    u_leaf (.I0(in_event), .O(out_event));
`else
    assign out_event = in_event;
`endif
endmodule

// Production two-column A8W4 ScaleCode lane.
//
// One accepted group32 contains centered S9 activations and two signed S4
// weight columns.  The lane produces two S36 Q12.24 group contributions:
//   dot_s17 = sum(centered_activation * weight)
//   raw_s33 = dot_s17 * activation_code * weight_code
//   guard    = raw_s33 * 2**(24 - total_shift)
//
// Metadata FIFOs keep the independently backpressured dot/recovery pipelines
// bit-exactly paired.  Legal nonzero MLP total_shift is 21..44.
module hap_a8w4_group32_lane2_s36 #(
    parameter integer META_DEPTH = 32,
    parameter integer SHIFT_DEPTH = 16,
    parameter integer GUARD_DEPTH = 2,
    parameter integer LOCKSTEP_EVENT_INPUT = 0
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       clear,
    input  wire                       in_valid,
    output wire                       in_ready,
    input  wire signed [32*9-1:0]     activation_s9x32,
    input  wire signed [32*4-1:0]     weight0_s4x32,
    input  wire signed [32*4-1:0]     weight1_s4x32,
    input  wire [7:0]                 activation_code_u8,
    input  wire [5:0]                 activation_shift_u6,
    input  wire [7:0]                 weight0_code_u8,
    input  wire [5:0]                 weight0_shift_u6,
    input  wire [7:0]                 weight1_code_u8,
    input  wire [5:0]                 weight1_shift_u6,
    output wire                       out_valid,
    input  wire                       out_ready,
    output wire signed [35:0]         guard0_s36,
    output wire signed [35:0]         guard1_s36,
    output reg  [31:0]                input_group_count,
    output reg  [31:0]                output_group_count,
    output reg                        error
);

    localparam integer META_PTR_W = $clog2(META_DEPTH);
    localparam integer META_COUNT_W = $clog2(META_DEPTH + 1);
    localparam integer SHIFT_PTR_W = $clog2(SHIFT_DEPTH);
    localparam integer SHIFT_COUNT_W = $clog2(SHIFT_DEPTH + 1);
    localparam integer GUARD_PTR_W = $clog2(GUARD_DEPTH);
    localparam integer GUARD_COUNT_W = $clog2(GUARD_DEPTH + 1);

    wire dot_in_ready;
    wire dot_out_valid;
    wire dot_out_ready;
    wire signed [16:0] dot0_s17;
    wire signed [16:0] dot1_s17;

    wire recover_in_valid;
    wire recover_in_ready;
    wire recover_out_valid;
    wire recover_out_ready;
    wire signed [32:0] raw0_s33;
    wire signed [32:0] raw1_s33;

    // One-entry elastic ingress.  At slice scale this turns the global valid
    // fanout into 64 local register enables; each registered valid then only
    // drives the 32 packed leaves inside its own lane.
    reg ingress_valid_r;
    reg signed [32*9-1:0] ingress_activation_s9x32_r;
    reg signed [32*4-1:0] ingress_weight0_s4x32_r;
    reg signed [32*4-1:0] ingress_weight1_s4x32_r;
    reg [7:0] ingress_activation_code_u8_r;
    reg [5:0] ingress_activation_shift_u6_r;
    reg [7:0] ingress_weight0_code_u8_r;
    reg [5:0] ingress_weight0_shift_u6_r;
    reg [7:0] ingress_weight1_code_u8_r;
    reg [5:0] ingress_weight1_shift_u6_r;

    localparam integer ACT_CAPTURE_DOMAINS = 8;
    localparam integer WGT_CAPTURE_DOMAINS = 4;
    localparam integer ACT_CAPTURE_W = (32*9) / ACT_CAPTURE_DOMAINS;
    localparam integer WGT_CAPTURE_W = (32*4) / WGT_CAPTURE_DOMAINS;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [ACT_CAPTURE_DOMAINS-1:0] ingress_activation_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [WGT_CAPTURE_DOMAINS-1:0] ingress_weight0_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [WGT_CAPTURE_DOMAINS-1:0] ingress_weight1_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire ingress_metadata_capture_enable;

    reg [7:0] meta_act_code_mem [0:META_DEPTH-1];
    reg [7:0] meta_w0_code_mem [0:META_DEPTH-1];
    reg [7:0] meta_w1_code_mem [0:META_DEPTH-1];
    reg [6:0] meta_total0_mem [0:META_DEPTH-1];
    reg [6:0] meta_total1_mem [0:META_DEPTH-1];
    reg [META_PTR_W-1:0] meta_wr_ptr_r;
    reg [META_PTR_W-1:0] meta_rd_ptr_r;
    reg [META_COUNT_W-1:0] meta_count_r;

    reg [6:0] shift0_mem [0:SHIFT_DEPTH-1];
    reg [6:0] shift1_mem [0:SHIFT_DEPTH-1];
    reg [SHIFT_PTR_W-1:0] shift_wr_ptr_r;
    reg [SHIFT_PTR_W-1:0] shift_rd_ptr_r;
    reg [SHIFT_COUNT_W-1:0] shift_count_r;

    // A real output FIFO terminates the combinational ready path at the lane
    // boundary.  This is essential when 64 lanes are replicated in a slice:
    // top-level out_ready must not propagate backwards through every recover,
    // dot reduction and packed DSP leaf in one cycle.
    // Keep the two-entry guard FIFO in flip-flops.  Two entries are enough
    // for unstalled II=1 while retaining a registered ready boundary.  When
    // the former 16-entry FIFO was inferred as
    // distributed RAM, all 4,608 slice output bits became RAMG dedicated
    // clock-to-output paths with only 0.113 ns min delay; neither the router
    // nor phys_opt -hold_fix could add delay.  Register storage preserves the
    // same elastic/II=1 contract and leaves routable Q-to-D data paths for
    // hold closure at the slice boundary.
    (* ram_style = "registers", shreg_extract = "no" *)
    reg signed [35:0] guard0_mem [0:GUARD_DEPTH-1];
    (* ram_style = "registers", shreg_extract = "no" *)
    reg signed [35:0] guard1_mem [0:GUARD_DEPTH-1];
    reg [GUARD_PTR_W-1:0] guard_wr_ptr_r;
    reg [GUARD_PTR_W-1:0] guard_rd_ptr_r;
    reg [GUARD_COUNT_W-1:0] guard_count_r;

    wire [6:0] ingress_total0 =
        {1'b0, ingress_activation_shift_u6_r} +
        {1'b0, ingress_weight0_shift_u6_r};
    wire [6:0] ingress_total1 =
        {1'b0, ingress_activation_shift_u6_r} +
        {1'b0, ingress_weight1_shift_u6_r};
    wire meta_full = (meta_count_r == META_DEPTH);
    wire meta_empty = (meta_count_r == 0);
    wire shift_full = (shift_count_r == SHIFT_DEPTH);
    wire shift_empty = (shift_count_r == 0);
    wire guard_full = (guard_count_r == GUARD_DEPTH);
    wire guard_empty = (guard_count_r == 0);

    wire dot_fire = dot_out_valid && dot_out_ready;
    wire core_meta_ready = !meta_full || dot_fire;
    wire core_in_ready = dot_in_ready && core_meta_ready;
    wire ingress_to_core_fire = ingress_valid_r && core_in_ready;
    wire ingress_ready = !ingress_valid_r || core_in_ready;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire guard_commit = recover_out_valid && !shift_empty && !guard_full;

    assign in_ready = rst_n && !clear && ingress_ready;
    assign recover_in_valid = dot_out_valid && !meta_empty && !shift_full;
    assign dot_out_ready = recover_in_ready && !meta_empty &&
        !shift_full;
    assign out_valid = rst_n && !clear && !guard_empty;
    assign recover_out_ready = !shift_empty && !guard_full;

    genvar capture_domain;
    generate
        for (capture_domain = 0; capture_domain < ACT_CAPTURE_DOMAINS;
             capture_domain = capture_domain + 1) begin : g_act_capture_control
            (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
            hap_a8w4_ingress_capture_leaf
            u_capture_enable (
                .in_event(in_fire),
                .out_event(ingress_activation_capture_enable[capture_domain])
            );
        end
        for (capture_domain = 0; capture_domain < WGT_CAPTURE_DOMAINS;
             capture_domain = capture_domain + 1) begin : g_wgt_capture_control
            (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
            hap_a8w4_ingress_capture_leaf
            u_weight0_capture_enable (
                .in_event(in_fire),
                .out_event(ingress_weight0_capture_enable[capture_domain])
            );
            (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
            hap_a8w4_ingress_capture_leaf
            u_weight1_capture_enable (
                .in_event(in_fire),
                .out_event(ingress_weight1_capture_enable[capture_domain])
            );
        end
    endgenerate

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_a8w4_ingress_capture_leaf
    u_metadata_capture_enable (
        .in_event(in_fire),
        .out_event(ingress_metadata_capture_enable)
    );

    hap_a8w4_group32_pack2_s17 u_dot (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(ingress_valid_r && core_meta_ready),
        .in_ready(dot_in_ready),
        .activation_s9x32(ingress_activation_s9x32_r),
        .weight0_s4x32(ingress_weight0_s4x32_r),
        .weight1_s4x32(ingress_weight1_s4x32_r),
        .out_valid(dot_out_valid), .out_ready(dot_out_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17)
    );

    hap_a8w4_scalecode_recover2_lut u_recover (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(recover_in_valid), .in_ready(recover_in_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(meta_act_code_mem[meta_rd_ptr_r]),
        .weight0_code_u8(meta_w0_code_mem[meta_rd_ptr_r]),
        .weight1_code_u8(meta_w1_code_mem[meta_rd_ptr_r]),
        .out_valid(recover_out_valid), .out_ready(recover_out_ready),
        .raw0_s33(raw0_s33), .raw1_s33(raw1_s33)
    );

    function automatic signed [35:0] align_raw_s36;
        input signed [32:0] raw_s33;
        input [6:0] total_shift_u7;
        reg signed [35:0] extended_s36;
        begin
            extended_s36 = {{3{raw_s33[32]}}, raw_s33};
            if (raw_s33 == 0)
                align_raw_s36 = 36'sd0;
            else if (total_shift_u7 < 7'd21 ||
                     total_shift_u7 > 7'd44)
                align_raw_s36 = 36'sd0;
            else if (total_shift_u7 < 7'd24)
                align_raw_s36 = extended_s36 <<<
                    (7'd24 - total_shift_u7);
            else
                align_raw_s36 = extended_s36 >>>
                    (total_shift_u7 - 7'd24);
        end
    endfunction

    assign guard0_s36 = guard0_mem[guard_rd_ptr_r];
    assign guard1_s36 = guard1_mem[guard_rd_ptr_r];

    integer ingress_capture_index;
    always @(posedge clk) begin
        if (!rst_n) begin
            ingress_valid_r <= 1'b0;
            meta_wr_ptr_r <= '0;
            meta_rd_ptr_r <= '0;
            meta_count_r <= '0;
            shift_wr_ptr_r <= '0;
            shift_rd_ptr_r <= '0;
            shift_count_r <= '0;
            guard_wr_ptr_r <= '0;
            guard_rd_ptr_r <= '0;
            guard_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            ingress_valid_r <= 1'b0;
            meta_wr_ptr_r <= '0;
            meta_rd_ptr_r <= '0;
            meta_count_r <= '0;
            shift_wr_ptr_r <= '0;
            shift_rd_ptr_r <= '0;
            shift_count_r <= '0;
            guard_wr_ptr_r <= '0;
            guard_rd_ptr_r <= '0;
            guard_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (ingress_ready) begin
                ingress_valid_r <= in_fire;
                if (ingress_metadata_capture_enable) begin
                    ingress_activation_code_u8_r <= activation_code_u8;
                    ingress_activation_shift_u6_r <= activation_shift_u6;
                    ingress_weight0_code_u8_r <= weight0_code_u8;
                    ingress_weight0_shift_u6_r <= weight0_shift_u6;
                    ingress_weight1_code_u8_r <= weight1_code_u8;
                    ingress_weight1_shift_u6_r <= weight1_shift_u6;
                end
            end
            for (ingress_capture_index = 0;
                 ingress_capture_index < ACT_CAPTURE_DOMAINS;
                 ingress_capture_index = ingress_capture_index + 1)
                if (ingress_activation_capture_enable[ingress_capture_index])
                    ingress_activation_s9x32_r[
                        ingress_capture_index*ACT_CAPTURE_W +:
                        ACT_CAPTURE_W] <= activation_s9x32[
                        ingress_capture_index*ACT_CAPTURE_W +:
                        ACT_CAPTURE_W];
            for (ingress_capture_index = 0;
                 ingress_capture_index < WGT_CAPTURE_DOMAINS;
                 ingress_capture_index = ingress_capture_index + 1) begin
                if (ingress_weight0_capture_enable[ingress_capture_index])
                    ingress_weight0_s4x32_r[
                        ingress_capture_index*WGT_CAPTURE_W +:
                        WGT_CAPTURE_W] <= weight0_s4x32[
                        ingress_capture_index*WGT_CAPTURE_W +:
                        WGT_CAPTURE_W];
                if (ingress_weight1_capture_enable[ingress_capture_index])
                    ingress_weight1_s4x32_r[
                        ingress_capture_index*WGT_CAPTURE_W +:
                        WGT_CAPTURE_W] <= weight1_s4x32[
                        ingress_capture_index*WGT_CAPTURE_W +:
                        WGT_CAPTURE_W];
            end

            if (ingress_to_core_fire) begin
                meta_act_code_mem[meta_wr_ptr_r] <=
                    ingress_activation_code_u8_r;
                meta_w0_code_mem[meta_wr_ptr_r] <=
                    ingress_weight0_code_u8_r;
                meta_w1_code_mem[meta_wr_ptr_r] <=
                    ingress_weight1_code_u8_r;
                meta_total0_mem[meta_wr_ptr_r] <= ingress_total0;
                meta_total1_mem[meta_wr_ptr_r] <= ingress_total1;
                meta_wr_ptr_r <= meta_wr_ptr_r + 1'b1;
                input_group_count <= input_group_count + 32'd1;

                if (((ingress_activation_code_u8_r == 0) &&
                     (ingress_activation_shift_u6_r != 0)) ||
                    ((ingress_weight0_code_u8_r == 0) &&
                     (ingress_weight0_shift_u6_r != 0)) ||
                    ((ingress_weight1_code_u8_r == 0) &&
                     (ingress_weight1_shift_u6_r != 0)) ||
                    ((ingress_activation_code_u8_r != 0) &&
                     (ingress_weight0_code_u8_r != 0) &&
                     (ingress_total0 < 21 || ingress_total0 > 44)) ||
                    ((ingress_activation_code_u8_r != 0) &&
                     (ingress_weight1_code_u8_r != 0) &&
                     (ingress_total1 < 21 || ingress_total1 > 44)))
                    error <= 1'b1;
            end
            if (dot_fire) begin
                meta_rd_ptr_r <= meta_rd_ptr_r + 1'b1;
                shift0_mem[shift_wr_ptr_r] <=
                    meta_total0_mem[meta_rd_ptr_r];
                shift1_mem[shift_wr_ptr_r] <=
                    meta_total1_mem[meta_rd_ptr_r];
                shift_wr_ptr_r <= shift_wr_ptr_r + 1'b1;
            end
            case ({ingress_to_core_fire, dot_fire})
                2'b10: meta_count_r <= meta_count_r + 1'b1;
                2'b01: meta_count_r <= meta_count_r - 1'b1;
                default: meta_count_r <= meta_count_r;
            endcase

            if (guard_commit) begin
                guard0_mem[guard_wr_ptr_r] <= align_raw_s36(
                    raw0_s33, shift0_mem[shift_rd_ptr_r]);
                guard1_mem[guard_wr_ptr_r] <= align_raw_s36(
                    raw1_s33, shift1_mem[shift_rd_ptr_r]);
                guard_wr_ptr_r <= guard_wr_ptr_r + 1'b1;
                shift_rd_ptr_r <= shift_rd_ptr_r + 1'b1;
            end
            case ({dot_fire, guard_commit})
                2'b10: shift_count_r <= shift_count_r + 1'b1;
                2'b01: shift_count_r <= shift_count_r - 1'b1;
                default: shift_count_r <= shift_count_r;
            endcase

            if (out_fire) begin
                guard_rd_ptr_r <= guard_rd_ptr_r + 1'b1;
                output_group_count <= output_group_count + 32'd1;
            end
            case ({guard_commit, out_fire})
                2'b10: guard_count_r <= guard_count_r + 1'b1;
                2'b01: guard_count_r <= guard_count_r - 1'b1;
                default: guard_count_r <= guard_count_r;
            endcase

            if ((meta_count_r > META_DEPTH) ||
                (shift_count_r > SHIFT_DEPTH) ||
                (guard_count_r > GUARD_DEPTH) ||
                ((LOCKSTEP_EVENT_INPUT != 0) && in_valid && !in_ready))
                error <= 1'b1;
        end
    end

    initial begin
        if (META_DEPTH < 16 || (META_DEPTH & (META_DEPTH-1)) != 0)
            $error("META_DEPTH must be a power of two >=16");
        if (SHIFT_DEPTH < 8 || (SHIFT_DEPTH & (SHIFT_DEPTH-1)) != 0)
            $error("SHIFT_DEPTH must be a power of two >=8");
        if (GUARD_DEPTH < 2 || (GUARD_DEPTH & (GUARD_DEPTH-1)) != 0)
            $error("GUARD_DEPTH must be a power of two >=2");
        if (LOCKSTEP_EVENT_INPUT != 0 && LOCKSTEP_EVENT_INPUT != 1)
            $error("LOCKSTEP_EVENT_INPUT must be 0 or 1");
    end

endmodule
