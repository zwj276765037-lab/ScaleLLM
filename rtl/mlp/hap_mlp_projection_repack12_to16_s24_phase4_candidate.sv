`timescale 1ns / 1ps

// Run 0124 resource-exploration candidate.  This is intentionally separate
// from the signed-off generic repacker and is not a production replacement.
//
// Legal full-pass traffic advances the gearbox through tail counts
// 0 -> 12 -> 8 -> 4 -> 0.  A final partial pass can terminate at the matching
// phase.  Encoding only those four reachable pre-input states turns the
// generic 13-way row permutation into a four-way LUT mux while preserving the
// external protocol and fail-closed handling.
module hap_mlp_projection_repack12_to16_s24_phase4_candidate #(
    parameter integer ROWS = 16,
    parameter integer MATRICES = 2,
    parameter integer TAG_W = 9,
    parameter integer MATRIX_W = (MATRICES <= 1) ? 1 : $clog2(MATRICES)
) (
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              clear,

    input  wire                              in_valid,
    output wire                              in_ready,
    input  wire signed [ROWS*12*24-1:0]      in_projection_s24xrowsx12,
    input  wire [TAG_W-1:0]                  in_block_tag,
    input  wire [1:0]                        in_pass_index,
    input  wire [MATRIX_W-1:0]               in_matrix,
    input  wire [11:0]                       in_col_valid_u12,
    input  wire                              in_last_pass,

    output wire                              out_valid,
    input  wire                              out_ready,
    output wire signed [ROWS*16*24-1:0]      out_projection_s24xrowsx16,
    output wire [TAG_W-1:0]                  out_block_tag,
    output wire [1:0]                        out_record_index,
    output wire [MATRIX_W-1:0]               out_matrix,
    output wire [15:0]                       out_col_valid_u16,
    output wire                              out_last_record,

    output reg  [31:0]                       input_pass_count,
    output reg  [31:0]                       output_record_count,
    output wire                              error
);

    localparam integer IN_PAYLOAD_W = ROWS * 12 * 24;
    localparam integer OUT_PAYLOAD_W = ROWS * 16 * 24;
    localparam integer ROW_IN_W = 12 * 24;
    localparam integer ROW_OUT_W = 16 * 24;
    localparam integer ROW_COMBINED_W = 24 * 24;

    reg signed [IN_PAYLOAD_W-1:0] tail_payload_r [0:MATRICES-1];
    reg [3:0] tail_count_r [0:MATRICES-1];
    reg [1:0] record_count_r [0:MATRICES-1];

    reg sequence_active_r;
    reg [TAG_W-1:0] expected_block_r;
    reg [1:0] expected_pass_r;
    reg [MATRIX_W-1:0] expected_matrix_r;
    reg [11:0] pass_mask_r;
    reg pass_last_r;
    reg error_r;

    reg out_valid_r;
    reg signed [OUT_PAYLOAD_W-1:0] out_payload_r;
    reg [TAG_W-1:0] out_block_r;
    reg [1:0] out_record_r;
    reg [MATRIX_W-1:0] out_matrix_r;
    reg out_last_r;

    reg matrix_legal_c;
    reg mask_legal_c;
    reg order_legal_c;
    reg [3:0] input_columns_c;
    reg [3:0] selected_tail_count_c;
    reg signed [IN_PAYLOAD_W-1:0] selected_tail_payload_c;
    reg [4:0] total_columns_c;
    reg produces_output_c;
    reg [3:0] next_tail_count_c;

    integer m;
    wire signed [IN_PAYLOAD_W-1:0] next_tail_payload_w;
    wire signed [OUT_PAYLOAD_W-1:0] assembled_output_w;
    wire [ROW_COMBINED_W-1:0] combined_row_w [0:ROWS-1];

    function automatic [ROW_COMBINED_W-1:0] concatenate_row_phase4;
        input [ROW_IN_W-1:0] tail_row;
        input [ROW_IN_W-1:0] input_row;
        input [3:0] tail_columns;
        begin
            case (tail_columns)
                4'd0:  concatenate_row_phase4 = {288'b0, input_row};
                4'd4:  concatenate_row_phase4 = {192'b0, input_row,
                                                  tail_row[95:0]};
                4'd8:  concatenate_row_phase4 = {96'b0, input_row,
                                                  tail_row[191:0]};
                4'd12: concatenate_row_phase4 = {input_row, tail_row};
                default: concatenate_row_phase4 = '0;
            endcase
        end
    endfunction

    always @* begin
        mask_legal_c = 1'b1;
        input_columns_c = 4'd0;
        case (in_col_valid_u12)
            12'h001: input_columns_c = 4'd1;
            12'h003: input_columns_c = 4'd2;
            12'h007: input_columns_c = 4'd3;
            12'h00f: input_columns_c = 4'd4;
            12'h01f: input_columns_c = 4'd5;
            12'h03f: input_columns_c = 4'd6;
            12'h07f: input_columns_c = 4'd7;
            12'h0ff: input_columns_c = 4'd8;
            12'h1ff: input_columns_c = 4'd9;
            12'h3ff: input_columns_c = 4'd10;
            12'h7ff: input_columns_c = 4'd11;
            12'hfff: input_columns_c = 4'd12;
            default: begin
                input_columns_c = 4'd0;
                mask_legal_c = 1'b0;
            end
        endcase
        if ((!in_last_pass && in_col_valid_u12 != 12'hfff) ||
            (in_pass_index == 2'd3 && !in_last_pass))
            mask_legal_c = 1'b0;
    end

    always @* begin
        matrix_legal_c = (in_matrix < MATRICES);
        order_legal_c = matrix_legal_c && mask_legal_c;
        if (!sequence_active_r) begin
            if (in_pass_index != 2'd0 || in_matrix != {MATRIX_W{1'b0}})
                order_legal_c = 1'b0;
        end else begin
            if (in_block_tag != expected_block_r ||
                in_pass_index != expected_pass_r ||
                in_matrix != expected_matrix_r)
                order_legal_c = 1'b0;
        end
        if (sequence_active_r && expected_matrix_r != {MATRIX_W{1'b0}} &&
            (in_col_valid_u12 != pass_mask_r ||
             in_last_pass != pass_last_r))
            order_legal_c = 1'b0;
    end

    always @* begin
        selected_tail_count_c = 4'd0;
        selected_tail_payload_c = '0;
        for (m = 0; m < MATRICES; m = m + 1) begin
            if (in_matrix == m[MATRIX_W-1:0]) begin
                selected_tail_count_c = tail_count_r[m];
                selected_tail_payload_c = tail_payload_r[m];
            end
        end
    end

    always @* begin
        total_columns_c = selected_tail_count_c + input_columns_c;
        produces_output_c = (total_columns_c >= 5'd16);
        next_tail_count_c = produces_output_c ?
            total_columns_c - 5'd16 : total_columns_c[3:0];
    end

    genvar row_index;
    generate
        for (row_index = 0; row_index < ROWS;
             row_index = row_index + 1) begin : g_row_pack
            assign combined_row_w[row_index] = concatenate_row_phase4(
                selected_tail_payload_c[row_index*ROW_IN_W +: ROW_IN_W],
                in_projection_s24xrowsx12[
                    row_index*ROW_IN_W +: ROW_IN_W],
                selected_tail_count_c);
            assign assembled_output_w[
                row_index*ROW_OUT_W +: ROW_OUT_W] =
                combined_row_w[row_index][0 +: ROW_OUT_W];
            assign next_tail_payload_w[
                row_index*ROW_IN_W +: ROW_IN_W] = produces_output_c ?
                {96'b0,
                 combined_row_w[row_index][ROW_OUT_W +: 8*24]} :
                combined_row_w[row_index][0 +: ROW_IN_W];
        end
    endgenerate

    wire output_capacity = !out_valid_r || out_ready;
    wire input_fire = in_valid && in_ready;
    assign in_ready = output_capacity && order_legal_c && !error_r;
    assign out_valid = out_valid_r;
    assign out_projection_s24xrowsx16 = out_payload_r;
    assign out_block_tag = out_block_r;
    assign out_record_index = out_record_r;
    assign out_matrix = out_matrix_r;
    assign out_col_valid_u16 = 16'hffff;
    assign out_last_record = out_last_r;
    assign error = error_r;

    integer state_index;
    reg residual_error_v;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            sequence_active_r <= 1'b0;
            expected_block_r <= '0;
            expected_pass_r <= '0;
            expected_matrix_r <= '0;
            pass_mask_r <= '0;
            pass_last_r <= 1'b0;
            error_r <= 1'b0;
            out_valid_r <= 1'b0;
            input_pass_count <= 32'd0;
            output_record_count <= 32'd0;
            for (state_index = 0; state_index < MATRICES;
                 state_index = state_index + 1) begin
                tail_count_r[state_index] <= 4'd0;
                record_count_r[state_index] <= 2'd0;
            end
        end else begin
            if (out_valid_r && out_ready)
                out_valid_r <= 1'b0;
            if (in_valid && output_capacity && !order_legal_c)
                error_r <= 1'b1;

            if (input_fire) begin
                input_pass_count <= input_pass_count + 1'b1;
                if (!sequence_active_r) begin
                    expected_block_r <= in_block_tag;
                    expected_pass_r <= 2'd0;
                    expected_matrix_r <= '0;
                    for (state_index = 0; state_index < MATRICES;
                         state_index = state_index + 1)
                        record_count_r[state_index] <= 2'd0;
                end

                for (state_index = 0; state_index < MATRICES;
                     state_index = state_index + 1) begin
                    if (in_matrix == state_index[MATRIX_W-1:0]) begin
                        tail_payload_r[state_index] <= next_tail_payload_w;
                        tail_count_r[state_index] <= next_tail_count_c;
                        if (produces_output_c)
                            record_count_r[state_index] <=
                                record_count_r[state_index] + 1'b1;
                    end
                end

                if (produces_output_c) begin
                    out_valid_r <= 1'b1;
                    out_payload_r <= assembled_output_w;
                    out_block_r <= in_block_tag;
                    out_record_r <= record_count_r[in_matrix];
                    out_matrix_r <= in_matrix;
                    out_last_r <= in_last_pass;
                    output_record_count <= output_record_count + 1'b1;
                end

                if (in_matrix == {MATRIX_W{1'b0}}) begin
                    pass_mask_r <= in_col_valid_u12;
                    pass_last_r <= in_last_pass;
                end

                if (in_matrix == MATRICES-1) begin
                    expected_matrix_r <= '0;
                    if (in_last_pass) begin
                        sequence_active_r <= 1'b0;
                        expected_pass_r <= '0;
                        residual_error_v = (next_tail_count_c != 0);
                        for (state_index = 0; state_index < MATRICES;
                             state_index = state_index + 1)
                            if (state_index != in_matrix &&
                                tail_count_r[state_index] != 0)
                                residual_error_v = 1'b1;
                        if (residual_error_v)
                            error_r <= 1'b1;
                    end else begin
                        sequence_active_r <= 1'b1;
                        expected_pass_r <= in_pass_index + 1'b1;
                    end
                end else begin
                    sequence_active_r <= 1'b1;
                    expected_matrix_r <= in_matrix + 1'b1;
                    expected_pass_r <= in_pass_index;
                end
            end
        end
    end

    initial begin
        if (ROWS <= 0 || MATRICES <= 0 || TAG_W <= 0)
            $error("projection repacker parameters must be positive");
        if (MATRICES > (1 << MATRIX_W))
            $error("MATRIX_W cannot represent all contexts");
    end

endmodule
