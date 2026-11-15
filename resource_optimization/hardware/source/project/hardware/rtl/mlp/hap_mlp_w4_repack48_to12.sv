`timescale 1ns / 1ps

// Local V5 W4 streaming gearbox: three gathered 16-column DDR records become
// four 12-column compute passes without padding or rereading DDR bytes.
//
// The input records must already belong to the same matrix, K-group and
// 48-column supertile.  They arrive as record_index 0/1/2 with one identical
// tag.  This leaf intentionally rejects arbitrary adjacent V4 gate/up records:
// that stream is tile-major and interleaves gate0/up0/gate1/up1, so an upstream
// address/gather scheduler must first create the legal sequence.
//
// Data movement for a full supertile is:
//
//   record0[ 0:11] -> pass0, record0[12:15]                 -> tail4
//   {tail4,record1[0:7]} -> pass1, record1[8:15]            -> tail8
//   {tail8,record2[0:3]} -> pass2, record2[4:15]            -> tail12
//   tail12 -> pass3
//
// Thus only one registered output pass and one at-most-12-column tail are
// stored, rather than two physical 48-column FF banks.  With an unstalled
// sink the input cadence is three record cycles plus one internal-tail cycle,
// while the compute output remains valid for four consecutive cycles (II=1).
// Backpressure is lossless and freezes both payloads.  Payload registers are
// resetless; reset/clear invalidate only control and counters.
module hap_mlp_w4_repack48_to12 #(
    parameter integer TAG_W = 32
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,

    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire signed [16*32*4-1:0]    in_weights_s4x16x32,
    input  wire [223:0]                 in_weight_meta_u224,
    input  wire [TAG_W-1:0]             in_tag,
    input  wire [1:0]                   in_record_index,
    input  wire [15:0]                  in_col_valid_u16,
    // Closes a one- or two-record tail.  Record index 2 always closes.
    input  wire                         in_flush,

    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [12*32*4-1:0]    out_weights_s4x12x32,
    output wire [167:0]                 out_weight_meta_u168,
    output wire [TAG_W-1:0]             out_tag,
    output wire [1:0]                   out_pass_index,
    output wire [11:0]                  out_col_valid_u12,
    output wire                         out_last_pass,

    output reg  [31:0]                  input_record_count,
    output reg  [31:0]                  input_supertile_count,
    output reg  [31:0]                  output_pass_count,
    output reg                          error
);

    function automatic [4:0] popcount16;
        input [15:0] value;
        integer i;
        begin
            popcount16 = 5'd0;
            for (i = 0; i < 16; i = i + 1)
                popcount16 = popcount16 + value[i];
        end
    endfunction

    reg fill_active_r;
    reg [1:0] expected_record_r;
    reg [5:0] fill_valid_cols_r;
    reg [TAG_W-1:0] fill_tag_r;

    // The tail is always low-packed and low-mask-contiguous.  It holds four,
    // eight, or twelve columns depending on the accepted record index.
    reg signed [12*32*4-1:0] tail_weights_r;
    reg [12*8-1:0] tail_code_r;
    reg [12*6-1:0] tail_shift_r;
    reg [11:0] tail_col_valid_r;
    reg tail_pass_pending_r;
    reg [TAG_W-1:0] tail_tag_r;
    reg [1:0] tail_pass_index_r;

    reg out_valid_r;
    reg signed [12*32*4-1:0] out_weights_r;
    reg [12*8-1:0] out_code_r;
    reg [12*6-1:0] out_shift_r;
    reg [TAG_W-1:0] out_tag_r;
    reg [1:0] out_pass_r;
    reg [11:0] out_col_valid_r;
    (* keep = "true" *) reg out_last_r;

    wire mask_nonzero = |in_col_valid_u16;
    wire mask_low_contiguous = mask_nonzero &&
        ((in_col_valid_u16 & (in_col_valid_u16 + 16'd1)) == 16'd0);
    wire record_closes = in_flush || in_record_index == 2'd2;
    // Any record followed by another must contain all 16 columns, otherwise
    // the logical 48-column vector would contain a hole.
    wire record_shape_legal = mask_low_contiguous &&
        (record_closes || in_col_valid_u16 == 16'hffff);
    wire expected_first = !fill_active_r && in_record_index == 2'd0;
    wire expected_follow = fill_active_r &&
        in_record_index == expected_record_r && in_tag == fill_tag_r;
    wire input_contract_legal = in_record_index != 2'd3 &&
        (expected_first || expected_follow) && record_shape_legal;

    wire output_capacity = !out_valid_r || out_ready;
    // A pending tail has ordering priority over the first record of the next
    // supertile.  It occupies exactly the fourth output cycle.
    wire input_capacity = rst_n && !clear && output_capacity &&
        !tail_pass_pending_r;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    // Vivado may otherwise merge every case-arm write into one predicate
    // with roughly 1.5k payload loads.  Keep output and tail writes local to
    // one 12-column bank: each leaf drives only 128 weight, 8 code, 6 shift
    // and one mask bit.  They are combinational copies of the original
    // handshakes, so latency, capacity and stall behavior do not change.
    wire out_payload_write = output_capacity && in_fire;
    wire tail_payload_write = in_fire;
    wire [11:0] out_column_write_enable;
    wire [11:0] tail_column_write_enable;

    genvar write_column;
    generate for(write_column=0;write_column<12;
            write_column=write_column+1)begin:g_column_write_control
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_out_column_write_enable (
            .I0(out_payload_write),
            .O(out_column_write_enable[write_column])
        );
        (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
        u_tail_column_write_enable (
            .I0(tail_payload_write),
            .O(tail_column_write_enable[write_column])
        );
    end endgenerate
    // Protocol errors are observed even while output backpressure temporarily
    // removes capacity.  Otherwise an illegal producer could hide a bad tag
    // or index by presenting it only during a downstream stall.
    wire invalid_input_attempt = in_valid && rst_n && !clear &&
        !input_contract_legal;
    wire [5:0] accepted_valid_cols = fill_valid_cols_r +
        popcount16(in_col_valid_u16);
    // Record index N directly produces pass N.  A closed aggregate needs one
    // additional tail pass exactly when it extends beyond that pass boundary.
    wire needs_tail_pass = accepted_valid_cols >
        ({4'd0, in_record_index} + 6'd1) * 6'd12;

    assign in_ready = input_capacity && input_contract_legal;
    assign out_valid = rst_n && !clear && out_valid_r;
    assign out_weights_s4x12x32 = out_weights_r;
    assign out_weight_meta_u168 = {out_shift_r, out_code_r};
    assign out_tag = out_tag_r;
    assign out_pass_index = out_pass_r;
    assign out_col_valid_u12 = out_col_valid_r;
    assign out_last_pass = out_last_r;

    integer col;
    always @(posedge clk) begin
        if (!rst_n) begin
            fill_active_r <= 1'b0;
            expected_record_r <= 2'd0;
            fill_valid_cols_r <= 6'd0;
            fill_tag_r <= '0;
            tail_col_valid_r <= 12'd0;
            tail_pass_pending_r <= 1'b0;
            tail_tag_r <= '0;
            tail_pass_index_r <= 2'd0;
            out_valid_r <= 1'b0;
            input_record_count <= 32'd0;
            input_supertile_count <= 32'd0;
            output_pass_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            fill_active_r <= 1'b0;
            expected_record_r <= 2'd0;
            fill_valid_cols_r <= 6'd0;
            fill_tag_r <= '0;
            tail_col_valid_r <= 12'd0;
            tail_pass_pending_r <= 1'b0;
            tail_tag_r <= '0;
            tail_pass_index_r <= 2'd0;
            out_valid_r <= 1'b0;
            input_record_count <= 32'd0;
            input_supertile_count <= 32'd0;
            output_pass_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (invalid_input_attempt)
                error <= 1'b1;

            if (output_capacity) begin
                out_valid_r <= tail_pass_pending_r || in_fire;
                if (tail_pass_pending_r) begin
                    out_weights_r <= tail_weights_r;
                    out_code_r <= tail_code_r;
                    out_shift_r <= tail_shift_r;
                    out_tag_r <= tail_tag_r;
                    out_pass_r <= tail_pass_index_r;
                    out_col_valid_r <= tail_col_valid_r;
                    out_last_r <= 1'b1;
                    tail_pass_pending_r <= 1'b0;
                end else if (in_fire) begin
                    out_tag_r <= in_tag;
                    out_pass_r <= in_record_index;
                    out_last_r <= record_closes && !needs_tail_pass;

                    case (in_record_index)
                        2'd0: begin
                            for (col = 0; col < 12; col = col + 1) begin
                                if (out_column_write_enable[col] &&
                                    in_col_valid_u16[col]) begin
                                    out_weights_r[col*32*4 +: 32*4] <=
                                        in_weights_s4x16x32[
                                            col*32*4 +: 32*4];
                                    out_code_r[col*8 +: 8] <=
                                        in_weight_meta_u224[col*8 +: 8];
                                    out_shift_r[col*6 +: 6] <=
                                        in_weight_meta_u224[
                                            128+col*6 +: 6];
                                end else if (out_column_write_enable[col]) begin
                                    out_weights_r[col*32*4 +: 32*4] <= '0;
                                    out_code_r[col*8 +: 8] <= '0;
                                    out_shift_r[col*6 +: 6] <= '0;
                                end
                                if (out_column_write_enable[col])
                                    out_col_valid_r[col] <=
                                        in_col_valid_u16[col];
                            end
                            // Save record0 columns 12..15 as low tail4.
                            for (col = 0; col < 4; col = col + 1) begin
                                if (tail_column_write_enable[col] &&
                                    in_col_valid_u16[col+12]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <=
                                        in_weights_s4x16x32[
                                            (col+12)*32*4 +: 32*4];
                                    tail_code_r[col*8 +: 8] <=
                                        in_weight_meta_u224[
                                            (col+12)*8 +: 8];
                                    tail_shift_r[col*6 +: 6] <=
                                        in_weight_meta_u224[
                                            128+(col+12)*6 +: 6];
                                    tail_col_valid_r[col] <= 1'b1;
                                end else if (tail_column_write_enable[col]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <= '0;
                                    tail_code_r[col*8 +: 8] <= '0;
                                    tail_shift_r[col*6 +: 6] <= '0;
                                    tail_col_valid_r[col] <= 1'b0;
                                end
                            end
                            for (col = 4; col < 12; col = col + 1) begin
                                if (tail_column_write_enable[col]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <= '0;
                                    tail_code_r[col*8 +: 8] <= '0;
                                    tail_shift_r[col*6 +: 6] <= '0;
                                    tail_col_valid_r[col] <= 1'b0;
                                end
                            end
                        end
                        2'd1: begin
                            // Old tail4 plus record1 columns 0..7.
                            for (col = 0; col < 4; col = col + 1) begin
                                if (out_column_write_enable[col]) begin
                                    out_weights_r[col*32*4 +: 32*4] <=
                                        tail_weights_r[
                                            col*32*4 +: 32*4];
                                    out_code_r[col*8 +: 8] <=
                                        tail_code_r[col*8 +: 8];
                                    out_shift_r[col*6 +: 6] <=
                                        tail_shift_r[col*6 +: 6];
                                    out_col_valid_r[col] <=
                                        tail_col_valid_r[col];
                                end
                            end
                            for (col = 4; col < 12; col = col + 1) begin
                                if (out_column_write_enable[col] &&
                                    in_col_valid_u16[col-4]) begin
                                    out_weights_r[col*32*4 +: 32*4] <=
                                        in_weights_s4x16x32[
                                            (col-4)*32*4 +: 32*4];
                                    out_code_r[col*8 +: 8] <=
                                        in_weight_meta_u224[
                                            (col-4)*8 +: 8];
                                    out_shift_r[col*6 +: 6] <=
                                        in_weight_meta_u224[
                                            128+(col-4)*6 +: 6];
                                    out_col_valid_r[col] <= 1'b1;
                                end else if (out_column_write_enable[col]) begin
                                    out_weights_r[col*32*4 +: 32*4] <= '0;
                                    out_code_r[col*8 +: 8] <= '0;
                                    out_shift_r[col*6 +: 6] <= '0;
                                    out_col_valid_r[col] <= 1'b0;
                                end
                            end
                            // Save record1 columns 8..15 as low tail8.
                            for (col = 0; col < 8; col = col + 1) begin
                                if (tail_column_write_enable[col] &&
                                    in_col_valid_u16[col+8]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <=
                                        in_weights_s4x16x32[
                                            (col+8)*32*4 +: 32*4];
                                    tail_code_r[col*8 +: 8] <=
                                        in_weight_meta_u224[
                                            (col+8)*8 +: 8];
                                    tail_shift_r[col*6 +: 6] <=
                                        in_weight_meta_u224[
                                            128+(col+8)*6 +: 6];
                                    tail_col_valid_r[col] <= 1'b1;
                                end else if (tail_column_write_enable[col]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <= '0;
                                    tail_code_r[col*8 +: 8] <= '0;
                                    tail_shift_r[col*6 +: 6] <= '0;
                                    tail_col_valid_r[col] <= 1'b0;
                                end
                            end
                            for (col = 8; col < 12; col = col + 1) begin
                                if (tail_column_write_enable[col]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <= '0;
                                    tail_code_r[col*8 +: 8] <= '0;
                                    tail_shift_r[col*6 +: 6] <= '0;
                                    tail_col_valid_r[col] <= 1'b0;
                                end
                            end
                        end
                        default: begin
                            // Old tail8 plus record2 columns 0..3.
                            for (col = 0; col < 8; col = col + 1) begin
                                if (out_column_write_enable[col]) begin
                                    out_weights_r[col*32*4 +: 32*4] <=
                                        tail_weights_r[
                                            col*32*4 +: 32*4];
                                    out_code_r[col*8 +: 8] <=
                                        tail_code_r[col*8 +: 8];
                                    out_shift_r[col*6 +: 6] <=
                                        tail_shift_r[col*6 +: 6];
                                    out_col_valid_r[col] <=
                                        tail_col_valid_r[col];
                                end
                            end
                            for (col = 8; col < 12; col = col + 1) begin
                                if (out_column_write_enable[col] &&
                                    in_col_valid_u16[col-8]) begin
                                    out_weights_r[col*32*4 +: 32*4] <=
                                        in_weights_s4x16x32[
                                            (col-8)*32*4 +: 32*4];
                                    out_code_r[col*8 +: 8] <=
                                        in_weight_meta_u224[
                                            (col-8)*8 +: 8];
                                    out_shift_r[col*6 +: 6] <=
                                        in_weight_meta_u224[
                                            128+(col-8)*6 +: 6];
                                    out_col_valid_r[col] <= 1'b1;
                                end else if (out_column_write_enable[col]) begin
                                    out_weights_r[col*32*4 +: 32*4] <= '0;
                                    out_code_r[col*8 +: 8] <= '0;
                                    out_shift_r[col*6 +: 6] <= '0;
                                    out_col_valid_r[col] <= 1'b0;
                                end
                            end
                            // Save record2 columns 4..15 as low tail12.
                            for (col = 0; col < 12; col = col + 1) begin
                                if (tail_column_write_enable[col] &&
                                    in_col_valid_u16[col+4]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <=
                                        in_weights_s4x16x32[
                                            (col+4)*32*4 +: 32*4];
                                    tail_code_r[col*8 +: 8] <=
                                        in_weight_meta_u224[
                                            (col+4)*8 +: 8];
                                    tail_shift_r[col*6 +: 6] <=
                                        in_weight_meta_u224[
                                            128+(col+4)*6 +: 6];
                                    tail_col_valid_r[col] <= 1'b1;
                                end else if (tail_column_write_enable[col]) begin
                                    tail_weights_r[col*32*4 +: 32*4] <= '0;
                                    tail_code_r[col*8 +: 8] <= '0;
                                    tail_shift_r[col*6 +: 6] <= '0;
                                    tail_col_valid_r[col] <= 1'b0;
                                end
                            end
                        end
                    endcase
                end
            end

            if (in_fire) begin
                input_record_count <= input_record_count + 32'd1;
                if (record_closes) begin
                    input_supertile_count <=
                        input_supertile_count + 32'd1;
                    fill_active_r <= 1'b0;
                    expected_record_r <= 2'd0;
                    fill_valid_cols_r <= 6'd0;
                    if (needs_tail_pass) begin
                        tail_pass_pending_r <= 1'b1;
                        tail_tag_r <= in_tag;
                        tail_pass_index_r <=
                            in_record_index + 2'd1;
                    end
                end else begin
                    fill_active_r <= 1'b1;
                    expected_record_r <= in_record_index + 2'd1;
                    fill_valid_cols_r <= accepted_valid_cols;
                    if (!fill_active_r)
                        fill_tag_r <= in_tag;
                end
            end

            if (out_fire)
                output_pass_count <= output_pass_count + 32'd1;
        end
    end

`ifndef SYNTHESIS
    reg stalled_r;
    reg signed [12*32*4-1:0] stalled_weights_r;
    reg [167:0] stalled_meta_r;
    reg [TAG_W-1:0] stalled_tag_r;
    reg [1:0] stalled_pass_r;
    reg [11:0] stalled_mask_r;
    reg stalled_last_r;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            stalled_r <= 1'b0;
        end else begin
            if (stalled_r && (!out_valid ||
                out_weights_s4x12x32 !== stalled_weights_r ||
                out_weight_meta_u168 !== stalled_meta_r ||
                out_tag !== stalled_tag_r ||
                out_pass_index !== stalled_pass_r ||
                out_col_valid_u12 !== stalled_mask_r ||
                out_last_pass !== stalled_last_r))
                $error("hap_mlp_w4_repack48_to12 output changed while stalled");
            stalled_r <= out_valid && !out_ready;
            if (out_valid && !out_ready) begin
                stalled_weights_r <= out_weights_s4x12x32;
                stalled_meta_r <= out_weight_meta_u168;
                stalled_tag_r <= out_tag;
                stalled_pass_r <= out_pass_index;
                stalled_mask_r <= out_col_valid_u12;
                stalled_last_r <= out_last_pass;
            end
        end
    end
`endif

    initial begin
        if (TAG_W <= 0)
            $error("hap_mlp_w4_repack48_to12 TAG_W must be positive");
    end
endmodule
