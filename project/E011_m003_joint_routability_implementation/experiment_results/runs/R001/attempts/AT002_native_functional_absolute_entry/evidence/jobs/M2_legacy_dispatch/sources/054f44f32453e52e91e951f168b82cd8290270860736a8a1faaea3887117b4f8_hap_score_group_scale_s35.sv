`timescale 1ns / 1ps

module hap_score_group_scale_s35 #(
    parameter integer FIFO_DEPTH = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire signed [39:0]    in_dot_s40,
    input  wire [7:0]            in_key_code,
    input  wire [5:0]            in_key_shift,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [34:0]    out_group_q14_s35,
    output reg  [31:0]           input_group_count,
    output reg  [31:0]           output_group_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);

    reg code_valid_r;
    (* use_dsp = "yes" *) reg signed [47:0] coded_s48_r;
    reg [5:0] coded_shift_r;

    // 5793 = 4096 + 1024 + 512 + 128 + 32 + 1.  A three-stage
    // shift-add pipeline avoids replicating a 48x13 multiplier while retaining
    // the exact S61 mathematical result.
    reg scale1_valid_r;
    (* use_dsp = "no" *) reg signed [60:0] scale1_a_s61_r;
    (* use_dsp = "no" *) reg signed [60:0] scale1_b_s61_r;
    (* use_dsp = "no" *) reg signed [60:0] scale1_c_s61_r;
    reg [5:0] scale1_shift_r;
    reg scale2_valid_r;
    (* use_dsp = "no" *) reg signed [60:0] scale2_a_s61_r;
    (* use_dsp = "no" *) reg signed [60:0] scale2_b_s61_r;
    reg [5:0] scale2_shift_r;
    reg scale3_valid_r;
    (* use_dsp = "no" *) reg signed [60:0] scaled_s61_r;
    reg [5:0] scaled_shift_r;
    reg align_valid_r;
    reg signed [34:0] aligned_s35_r;

    (* ram_style = "distributed" *) reg signed [34:0]
        fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr_r;
    reg [PTR_W-1:0] fifo_rd_ptr_r;
    reg [COUNT_W-1:0] fifo_count_r;
    reg [COUNT_W-1:0] used_count_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire fifo_commit = align_valid_r &&
        ((fifo_count_r != FIFO_DEPTH) || out_fire);
    wire signed [60:0] coded_ext_s61 =
        {{13{coded_s48_r[47]}}, coded_s48_r};

    assign in_ready = rst_n && !clear && (used_count_r < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_group_q14_s35 = fifo_mem[fifo_rd_ptr_r];

    always @(posedge clk) begin
        if (in_fire) begin
            coded_s48_r <= in_dot_s40 * $signed({1'b0, in_key_code});
            coded_shift_r <= in_key_shift;
        end
        if (code_valid_r) begin
            scale1_a_s61_r <= (coded_ext_s61 <<< 12) +
                (coded_ext_s61 <<< 10);
            scale1_b_s61_r <= (coded_ext_s61 <<< 9) +
                (coded_ext_s61 <<< 7);
            scale1_c_s61_r <= (coded_ext_s61 <<< 5) + coded_ext_s61;
            scale1_shift_r <= coded_shift_r;
        end
        if (scale1_valid_r) begin
            scale2_a_s61_r <= scale1_a_s61_r + scale1_b_s61_r;
            scale2_b_s61_r <= scale1_c_s61_r;
            scale2_shift_r <= scale1_shift_r;
        end
        if (scale2_valid_r) begin
            scaled_s61_r <= scale2_a_s61_r + scale2_b_s61_r;
            scaled_shift_r <= scale2_shift_r;
        end
        if (scale3_valid_r)
            aligned_s35_r <= $signed(scaled_s61_r) >>>
                (scaled_shift_r + 6'd18);
        if (fifo_commit)
            fifo_mem[fifo_wr_ptr_r] <= aligned_s35_r;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            code_valid_r <= 1'b0;
            scale1_valid_r <= 1'b0;
            scale2_valid_r <= 1'b0;
            scale3_valid_r <= 1'b0;
            align_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            code_valid_r <= 1'b0;
            scale1_valid_r <= 1'b0;
            scale2_valid_r <= 1'b0;
            scale3_valid_r <= 1'b0;
            align_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            code_valid_r <= in_fire;
            scale1_valid_r <= code_valid_r;
            scale2_valid_r <= scale1_valid_r;
            scale3_valid_r <= scale2_valid_r;
            align_valid_r <= scale3_valid_r;

            if (in_fire) begin
                input_group_count <= input_group_count + 32'd1;
                if (((in_key_code == 0) && (in_key_shift != 0)) ||
                    ((in_key_code != 0) &&
                        ((in_key_shift < 8) || (in_key_shift > 32))))
                    error <= 1'b1;
            end
            if (align_valid_r) begin
                if ((fifo_count_r == FIFO_DEPTH) && !out_fire)
                    error <= 1'b1;
                else
                    fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                output_group_count <= output_group_count + 32'd1;
            end
            case ({fifo_commit, out_fire})
                2'b10: fifo_count_r <= fifo_count_r + 1'b1;
                2'b01: fifo_count_r <= fifo_count_r - 1'b1;
                default: fifo_count_r <= fifo_count_r;
            endcase
            case ({in_fire, out_fire})
                2'b10: used_count_r <= used_count_r + 1'b1;
                2'b01: used_count_r <= used_count_r - 1'b1;
                default: used_count_r <= used_count_r;
            endcase
            if ((used_count_r > FIFO_DEPTH) ||
                (fifo_count_r > FIFO_DEPTH) ||
                (fifo_count_r > used_count_r))
                error <= 1'b1;
        end
    end

    initial begin
        if (FIFO_DEPTH != 16)
            $error("hap_score_group_scale_s35 FIFO_DEPTH must be 16");
    end

endmodule
