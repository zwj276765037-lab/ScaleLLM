`timescale 1ns / 1ps

// Handshake-safe ScaleCode pair lane used after the production wrapper's
// distinct-tile drain bug was exposed.  Numerical leaves remain production:
// packed A8W4 dot and LUT ScaleCode recovery.  Tags are delayed beside the
// explicit recovery pipeline and the final contribution is accumulated and
// retired without requiring a following transaction as a flush token.
module m09_sc_a8w4_lane2_accum #(
    parameter integer GROUPS = 128,
    parameter integer META_DEPTH = 32,
    parameter integer RESULT_DEPTH = 2
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     in_valid,
    output wire                     in_ready,
    input  wire                     in_first_group,
    input  wire                     in_last_group,
    input  wire signed [32*9-1:0]  activation_s9x32,
    input  wire signed [32*4-1:0]  weight0_s4x32,
    input  wire signed [32*4-1:0]  weight1_s4x32,
    input  wire [7:0]               activation_code_u8,
    input  wire [5:0]               activation_shift_u6,
    input  wire [7:0]               weight0_code_u8,
    input  wire [5:0]               weight0_shift_u6,
    input  wire [7:0]               weight1_code_u8,
    input  wire [5:0]               weight1_shift_u6,
    output wire                     out_valid,
    input  wire                     out_ready,
    output wire signed [23:0]       out0_s24,
    output wire signed [23:0]       out1_s24,
    output reg [31:0]               input_group_count,
    output reg [31:0]               output_tile_count,
    output reg                      error
);
    localparam integer META_W = 44;
    localparam integer META_PTR_W = $clog2(META_DEPTH);
    localparam integer META_COUNT_W = $clog2(META_DEPTH+1);
    localparam integer GROUP_W = $clog2(GROUPS);

    wire dot_in_ready;
    wire dot_out_valid;
    wire dot_out_ready;
    wire signed [16:0] dot0_s17;
    wire signed [16:0] dot1_s17;
    wire recover_in_ready;
    wire recover_out_valid;
    wire signed [32:0] raw0_s33;
    wire signed [32:0] raw1_s33;

    reg [META_W-1:0] meta_mem [0:META_DEPTH-1];
    reg [META_PTR_W-1:0] meta_wr_ptr_r;
    reg [META_PTR_W-1:0] meta_rd_ptr_r;
    reg [META_COUNT_W-1:0] meta_count_r;
    wire meta_full = meta_count_r == META_DEPTH;
    wire meta_empty = meta_count_r == 0;

    reg signed [42:0] accum0_s43_r;
    reg signed [42:0] accum1_s43_r;
    reg signed [23:0] result0_mem [0:RESULT_DEPTH-1];
    reg signed [23:0] result1_mem [0:RESULT_DEPTH-1];
    reg result_wr_ptr_r;
    reg result_rd_ptr_r;
    reg [1:0] result_count_r;
    reg [1:0] outstanding_tiles_r;
    reg [GROUP_W-1:0] input_group_index_r;
    reg [GROUP_W-1:0] dot_group_index_r;

    wire result_empty = result_count_r == 0;
    wire result_full = result_count_r == RESULT_DEPTH;
    wire out_fire = out_valid && out_ready;
    wire tile_credit = outstanding_tiles_r < RESULT_DEPTH || out_fire;
    wire in_fire = in_valid && in_ready;
    wire dot_fire = dot_out_valid && dot_out_ready;

    assign in_ready = rst_n && !clear && dot_in_ready && !meta_full &&
        (!in_first_group || tile_credit);
    assign dot_out_ready = recover_in_ready && !meta_empty;
    assign out_valid = rst_n && !clear && !result_empty;
    assign out0_s24 = result0_mem[result_rd_ptr_r];
    assign out1_s24 = result1_mem[result_rd_ptr_r];

    hap_a8w4_group32_pack2_s17 u_dot (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && in_ready), .in_ready(dot_in_ready),
        .activation_s9x32(activation_s9x32),
        .weight0_s4x32(weight0_s4x32),
        .weight1_s4x32(weight1_s4x32),
        .out_valid(dot_out_valid), .out_ready(dot_out_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17)
    );

    wire [META_W-1:0] dot_meta = meta_mem[meta_rd_ptr_r];
    wire [7:0] dot_act_code = dot_meta[0 +: 8];
    wire [7:0] dot_weight0_code = dot_meta[8 +: 8];
    wire [7:0] dot_weight1_code = dot_meta[16 +: 8];
    wire [5:0] dot_act_shift = dot_meta[24 +: 6];
    wire [5:0] dot_weight0_shift = dot_meta[30 +: 6];
    wire [5:0] dot_weight1_shift = dot_meta[36 +: 6];
    wire dot_first = dot_meta[42];
    wire dot_last = dot_meta[43];
    wire [6:0] dot_total0 = {1'b0,dot_act_shift} +
        {1'b0,dot_weight0_shift};
    wire [6:0] dot_total1 = {1'b0,dot_act_shift} +
        {1'b0,dot_weight1_shift};

    hap_a8w4_scalecode_recover2_lut u_recover (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(dot_fire), .in_ready(recover_in_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(dot_act_code),
        .weight0_code_u8(dot_weight0_code),
        .weight1_code_u8(dot_weight1_code),
        .out_valid(recover_out_valid), .out_ready(1'b1),
        .raw0_s33(raw0_s33), .raw1_s33(raw1_s33)
    );

    wire recover_tag_valid;
    wire [15:0] recover_tag;
    m09_delay_bus #(.WIDTH(16), .DEPTH(3)) u_recover_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(dot_fire),
        .in_data({dot_last,dot_first,dot_total1,dot_total0}),
        .out_valid(recover_tag_valid), .out_data(recover_tag));
    wire [6:0] recover_total0 = recover_tag[0 +: 7];
    wire [6:0] recover_total1 = recover_tag[7 +: 7];
    wire recover_first = recover_tag[14];
    wire recover_last = recover_tag[15];

    function automatic signed [35:0] align_raw_s36;
        input signed [32:0] raw_s33;
        input [6:0] total_shift;
        reg signed [35:0] extended;
        begin
            extended = {{3{raw_s33[32]}},raw_s33};
            if (raw_s33 == 0 || total_shift < 21 || total_shift > 44)
                align_raw_s36 = 36'sd0;
            else if (total_shift < 24)
                align_raw_s36 = extended <<< (24-total_shift);
            else
                align_raw_s36 = extended >>> (total_shift-24);
        end
    endfunction

    function automatic signed [23:0] round_sat_s43_to_s24;
        input signed [43:0] value;
        reg signed [44:0] extended;
        reg [44:0] magnitude;
        reg signed [44:0] rounded;
        begin
            extended = {value[43],value};
            if (value < 0) begin
                magnitude = -extended;
                rounded = -$signed((magnitude+128) >> 8);
            end else begin
                rounded = (extended+128) >>> 8;
            end
            if (rounded > 8388607)
                round_sat_s43_to_s24 = 24'sh7f_ffff;
            else if (rounded < -8388608)
                round_sat_s43_to_s24 = -24'sd8388608;
            else
                round_sat_s43_to_s24 = rounded[23:0];
        end
    endfunction

    wire signed [35:0] guard0_s36 = align_raw_s36(
        raw0_s33,recover_total0);
    wire signed [35:0] guard1_s36 = align_raw_s36(
        raw1_s33,recover_total1);
    wire signed [43:0] sum0_s44 = recover_first ?
        $signed({{8{guard0_s36[35]}},guard0_s36}) :
        $signed({accum0_s43_r[42],accum0_s43_r}) +
        $signed({{8{guard0_s36[35]}},guard0_s36});
    wire signed [43:0] sum1_s44 = recover_first ?
        $signed({{8{guard1_s36[35]}},guard1_s36}) :
        $signed({accum1_s43_r[42],accum1_s43_r}) +
        $signed({{8{guard1_s36[35]}},guard1_s36});
    wire result_push = recover_out_valid && recover_tag_valid && recover_last;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            meta_wr_ptr_r <= '0;
            meta_rd_ptr_r <= '0;
            meta_count_r <= '0;
            accum0_s43_r <= '0;
            accum1_s43_r <= '0;
            result_wr_ptr_r <= 1'b0;
            result_rd_ptr_r <= 1'b0;
            result_count_r <= '0;
            outstanding_tiles_r <= '0;
            input_group_index_r <= '0;
            dot_group_index_r <= '0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire) begin
                meta_mem[meta_wr_ptr_r] <= {in_last_group,in_first_group,
                    weight1_shift_u6,weight0_shift_u6,
                    activation_shift_u6,weight1_code_u8,
                    weight0_code_u8,activation_code_u8};
                meta_wr_ptr_r <= meta_wr_ptr_r + 1'b1;
                input_group_count <= input_group_count + 1'b1;
                if (in_first_group != (input_group_index_r == 0) ||
                    in_last_group != (input_group_index_r == GROUPS-1))
                    error <= 1'b1;
                if (in_last_group)
                    input_group_index_r <= '0;
                else
                    input_group_index_r <= input_group_index_r + 1'b1;
            end
            if (dot_fire) begin
                meta_rd_ptr_r <= meta_rd_ptr_r + 1'b1;
                if (dot_first != (dot_group_index_r == 0) ||
                    dot_last != (dot_group_index_r == GROUPS-1))
                    error <= 1'b1;
                if (dot_last)
                    dot_group_index_r <= '0;
                else
                    dot_group_index_r <= dot_group_index_r + 1'b1;
            end
            case ({in_fire,dot_fire})
                2'b10: meta_count_r <= meta_count_r + 1'b1;
                2'b01: meta_count_r <= meta_count_r - 1'b1;
                default: meta_count_r <= meta_count_r;
            endcase

            if (recover_out_valid && recover_tag_valid) begin
                accum0_s43_r <= sum0_s44[42:0];
                accum1_s43_r <= sum1_s44[42:0];
                if (sum0_s44[43] != sum0_s44[42] ||
                    sum1_s44[43] != sum1_s44[42])
                    error <= 1'b1;
            end
            if (recover_out_valid != recover_tag_valid)
                error <= 1'b1;

            if (result_push) begin
                result0_mem[result_wr_ptr_r] <=
                    round_sat_s43_to_s24(sum0_s44);
                result1_mem[result_wr_ptr_r] <=
                    round_sat_s43_to_s24(sum1_s44);
                result_wr_ptr_r <= result_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                result_rd_ptr_r <= result_rd_ptr_r + 1'b1;
                output_tile_count <= output_tile_count + 1'b1;
            end
            case ({result_push,out_fire})
                2'b10: result_count_r <= result_count_r + 1'b1;
                2'b01: result_count_r <= result_count_r - 1'b1;
                default: result_count_r <= result_count_r;
            endcase
            case ({in_fire && in_first_group,out_fire})
                2'b10: outstanding_tiles_r <= outstanding_tiles_r + 1'b1;
                2'b01: outstanding_tiles_r <= outstanding_tiles_r - 1'b1;
                default: outstanding_tiles_r <= outstanding_tiles_r;
            endcase
            if ((result_push && result_full && !out_fire) ||
                meta_count_r > META_DEPTH ||
                result_count_r > RESULT_DEPTH ||
                outstanding_tiles_r > RESULT_DEPTH)
                error <= 1'b1;
        end
    end
endmodule
