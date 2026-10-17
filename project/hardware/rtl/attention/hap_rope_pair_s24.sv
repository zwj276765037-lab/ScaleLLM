`timescale 1ns / 1ps

module hap_rope_pair_s24 #(
    parameter integer FIFO_DEPTH = 8
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire signed [23:0]    in_x0_s24,
    input  wire signed [23:0]    in_x1_s24,
    input  wire signed [17:0]    in_cos_s18,
    input  wire signed [17:0]    in_sin_s18,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [23:0]    out_y0_s24,
    output wire signed [23:0]    out_y1_s24,
    output reg  [31:0]           input_pair_count,
    output reg  [31:0]           output_pair_count,
    output reg  [31:0]           saturation_count,
    output reg                   error
);

    localparam integer PTR_W = $clog2(FIFO_DEPTH);
    localparam integer COUNT_W = $clog2(FIFO_DEPTH + 1);

    reg product_valid_r;
    // Valid coefficients are constrained to [-1.0, +1.0], so the native
    // S42 multiplier result's top bit is sign extension.  Store the proven
    // mathematical S41 result instead of carrying an unused bit downstream.
    (* use_dsp = "yes" *) reg signed [40:0] x0_cos_s41_r;
    (* use_dsp = "yes" *) reg signed [40:0] x1_sin_s41_r;
    (* use_dsp = "yes" *) reg signed [40:0] x0_sin_s41_r;
    (* use_dsp = "yes" *) reg signed [40:0] x1_cos_s41_r;
    reg rounded_valid_r;
    // Keep the rounding bias adders in fabric.  Without this explicit
    // constraint Vivado maps each bias-only add into a second DSP48E2.
    (* use_dsp = "no" *) reg signed [24:0] x0_cos_s25_r;
    (* use_dsp = "no" *) reg signed [24:0] x1_sin_s25_r;
    (* use_dsp = "no" *) reg signed [24:0] x0_sin_s25_r;
    (* use_dsp = "no" *) reg signed [24:0] x1_cos_s25_r;
    reg sum_valid_r;
    reg signed [25:0] y0_s26_r;
    reg signed [25:0] y1_s26_r;

    (* ram_style = "distributed" *) reg [47:0]
        fifo_mem [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] fifo_wr_ptr_r;
    reg [PTR_W-1:0] fifo_rd_ptr_r;
    reg [COUNT_W-1:0] fifo_count_r;
    reg [COUNT_W-1:0] used_count_r;

    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire fifo_commit = sum_valid_r &&
        ((fifo_count_r != FIFO_DEPTH) || out_fire);

    assign in_ready = rst_n && !clear && (used_count_r < FIFO_DEPTH);
    assign out_valid = rst_n && !clear && (fifo_count_r != 0);
    assign out_y0_s24 = fifo_mem[fifo_rd_ptr_r][23:0];
    assign out_y1_s24 = fifo_mem[fifo_rd_ptr_r][47:24];

    function automatic signed [24:0] round_s41_q32_to_s25_q16;
        input signed [40:0] value;
        reg signed [41:0] biased_value;
        begin
            // For arithmetic floor shift, +32768 on nonnegative values and
            // +32767 on negative values is exactly round-half-away-from-zero.
            // This branch selects only the bias and does not duplicate the
            // multiplier into positive/negative magnitude datapaths.
            biased_value = $signed({value[40], value}) +
                (value[40] ? 42'sd32767 : 42'sd32768);
            round_s41_q32_to_s25_q16 = biased_value >>> 16;
        end
    endfunction

    function automatic signed [23:0] sat_s26_to_s24;
        input signed [25:0] value;
        begin
            if (value > 26'sd8388607)
                sat_s26_to_s24 = 24'sh7f_ffff;
            else if (value < -26'sd8388608)
                sat_s26_to_s24 = -24'sd8388608;
            else
                sat_s26_to_s24 = value[23:0];
        end
    endfunction

    function automatic s26_to_s24_saturates;
        input signed [25:0] value;
        begin
            s26_to_s24_saturates = (value > 26'sd8388607) ||
                (value < -26'sd8388608);
        end
    endfunction

    always @(posedge clk) begin
        if (in_fire) begin
            x0_cos_s41_r <= in_x0_s24 * in_cos_s18;
            x1_sin_s41_r <= in_x1_s24 * in_sin_s18;
            x0_sin_s41_r <= in_x0_s24 * in_sin_s18;
            x1_cos_s41_r <= in_x1_s24 * in_cos_s18;
        end
        if (product_valid_r) begin
            x0_cos_s25_r <= round_s41_q32_to_s25_q16(x0_cos_s41_r);
            x1_sin_s25_r <= round_s41_q32_to_s25_q16(x1_sin_s41_r);
            x0_sin_s25_r <= round_s41_q32_to_s25_q16(x0_sin_s41_r);
            x1_cos_s25_r <= round_s41_q32_to_s25_q16(x1_cos_s41_r);
        end
        if (rounded_valid_r) begin
            y0_s26_r <= $signed({x0_cos_s25_r[24], x0_cos_s25_r}) -
                $signed({x1_sin_s25_r[24], x1_sin_s25_r});
            y1_s26_r <= $signed({x0_sin_s25_r[24], x0_sin_s25_r}) +
                $signed({x1_cos_s25_r[24], x1_cos_s25_r});
        end
        if (fifo_commit) begin
            fifo_mem[fifo_wr_ptr_r][23:0] <= sat_s26_to_s24(y0_s26_r);
            fifo_mem[fifo_wr_ptr_r][47:24] <= sat_s26_to_s24(y1_s26_r);
        end
    end

    wire [1:0] saturation_increment =
        s26_to_s24_saturates(y0_s26_r) +
        s26_to_s24_saturates(y1_s26_r);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            product_valid_r <= 1'b0;
            rounded_valid_r <= 1'b0;
            sum_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_pair_count <= 32'd0;
            output_pair_count <= 32'd0;
            saturation_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            product_valid_r <= 1'b0;
            rounded_valid_r <= 1'b0;
            sum_valid_r <= 1'b0;
            fifo_wr_ptr_r <= '0;
            fifo_rd_ptr_r <= '0;
            fifo_count_r <= '0;
            used_count_r <= '0;
            input_pair_count <= 32'd0;
            output_pair_count <= 32'd0;
            saturation_count <= 32'd0;
            error <= 1'b0;
        end else begin
            product_valid_r <= in_fire;
            rounded_valid_r <= product_valid_r;
            sum_valid_r <= rounded_valid_r;

            if (in_fire) begin
                input_pair_count <= input_pair_count + 32'd1;
                if ((in_cos_s18 > 18'sd65536) ||
                    (in_cos_s18 < -18'sd65536) ||
                    (in_sin_s18 > 18'sd65536) ||
                    (in_sin_s18 < -18'sd65536))
                    error <= 1'b1;
            end

            if (sum_valid_r) begin
                if ((fifo_count_r == FIFO_DEPTH) && !out_fire) begin
                    error <= 1'b1;
                end else begin
                    saturation_count <= saturation_count +
                        saturation_increment;
                    fifo_wr_ptr_r <= fifo_wr_ptr_r + 1'b1;
                end
            end
            if (out_fire) begin
                fifo_rd_ptr_r <= fifo_rd_ptr_r + 1'b1;
                output_pair_count <= output_pair_count + 32'd1;
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
        if (FIFO_DEPTH != 8)
            $error("hap_rope_pair_s24 production FIFO_DEPTH must be 8");
    end

endmodule
